#!/usr/bin/env python3
"""pdf-to-md: thin wrapper around MinerU with session-lifecycle server.

Server lifecycle:
  start-server  → launch mineru-api in background, preload VLM (~3 min cold)
  convert <pdf> → use server if running (warm), else fall back to ad-hoc CLI
  stop-server   → kill the server process

State at /tmp/pdf-to-md-server.json. Server logs at /tmp/pdf-to-md-server.log.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
from glob import glob
from pathlib import Path

IS_WIN = os.name == "nt"

IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp", ".heic"}
_NAT = re.compile(r"(\d+)")

if IS_WIN:
    VENV_BIN = Path.home() / "mineru-test" / ".venv" / "Scripts"
    MINERU_API = VENV_BIN / "mineru-api.exe"
    MINERU_CLI = VENV_BIN / "mineru.exe"
else:
    VENV_BIN = Path.home() / "mineru-test" / ".venv" / "bin"
    MINERU_API = VENV_BIN / "mineru-api"
    MINERU_CLI = VENV_BIN / "mineru"
_TMP = Path(tempfile.gettempdir())
STATE_FILE = _TMP / "pdf-to-md-server.json"
LOG_FILE = _TMP / "pdf-to-md-server.log"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 18000
DEFAULT_OUT = Path.home() / "preprocessed"


def _read_state() -> dict | None:
    if not STATE_FILE.exists():
        return None
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return None


def _http_ok(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 500
    except Exception:
        return False


def _server_alive(state: dict | None) -> bool:
    if not state:
        return False
    pid = state.get("pid")
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return _http_ok(f"http://{state['host']}:{state['port']}/docs")


def cmd_start_server(args) -> dict:
    state = _read_state()
    if state is not None and _server_alive(state):
        return {"already_running": True, **state}

    if not _cuda_available():
        return {
            "error": "CUDA not available — the VLM server requires a CUDA GPU.",
            "hint": "Skip start-server and run: dispatcher.py convert <pdf> --backend pipeline",
        }

    log_f = open(LOG_FILE, "ab")
    proc = subprocess.Popen(
        [
            str(MINERU_API),
            "--host", args.host,
            "--port", str(args.port),
            "--enable-vlm-preload", "true",
        ],
        stdout=log_f,
        stderr=log_f,
        start_new_session=(os.name != "nt"),
        creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0),
    )
    state = {
        "pid": proc.pid,
        "host": args.host,
        "port": args.port,
        "log": str(LOG_FILE),
        "started_at": int(time.time()),
    }
    STATE_FILE.write_text(json.dumps(state))

    deadline = time.time() + args.wait
    while time.time() < deadline:
        if _server_alive(state):
            state["ready_seconds"] = int(time.time() - state["started_at"])
            return state
        if proc.poll() is not None:
            STATE_FILE.unlink(missing_ok=True)
            return {"error": "server process exited", "returncode": proc.returncode, "log": str(LOG_FILE)}
        time.sleep(3)
    return {"error": "timeout waiting for server ready", **state, "log_hint": f"tail -50 {LOG_FILE}"}


def _kill_pid(pid: int) -> None:
    if IS_WIN:
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                           capture_output=True, check=False)
        except FileNotFoundError:
            pass
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def cmd_stop_server(args) -> dict:
    state = _read_state()
    if not state:
        return {"stopped": False, "reason": "no state file"}
    pid = state.get("pid")
    if isinstance(pid, int):
        _kill_pid(pid)
    STATE_FILE.unlink(missing_ok=True)
    return {"stopped": True, "pid": pid}


def _cuda_available() -> bool:
    """Probe the venv's torch for CUDA. ~0.5s; result is not cached."""
    if not MINERU_CLI.exists():
        return False
    py = VENV_BIN / ("python.exe" if IS_WIN else "python")
    if not py.exists():
        return False
    try:
        out = subprocess.run(
            [str(py), "-c", "import torch,sys;sys.stdout.write('1' if torch.cuda.is_available() else '0')"],
            capture_output=True, text=True, timeout=15,
        )
        return out.stdout.strip() == "1"
    except Exception:
        return False


def cmd_status(args) -> dict:
    state = _read_state()
    return {"alive": _server_alive(state), "state": state}


def _natkey(p: Path):
    return [int(s) if s.isdigit() else s.lower() for s in _NAT.split(p.name)]


def _collect_images(inputs: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in inputs:
        p = Path(os.path.expanduser(raw))
        if p.is_dir():
            files += [c for c in p.iterdir() if c.suffix.lower() in IMG_EXTS]
        elif any(ch in raw for ch in "*?["):
            files += [Path(m) for m in glob(os.path.expanduser(raw))
                      if Path(m).suffix.lower() in IMG_EXTS]
        elif p.suffix.lower() in IMG_EXTS:
            files.append(p)
    return sorted({f.resolve() for f in files}, key=_natkey)


def _images_to_pdf(images: list[Path], out_pdf: Path) -> None:
    from PIL import Image  # lazy

    def to_rgb(img: "Image.Image") -> "Image.Image":
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
            return bg
        return img.convert("RGB") if img.mode != "RGB" else img

    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    first, *rest = [to_rgb(Image.open(p)) for p in images]
    first.save(out_pdf, "PDF", save_all=True, append_images=rest, resolution=150.0)


def _resolve_input(inputs: list[str], name: str | None) -> tuple[Path, list[Path] | None]:
    """Return (pdf_path, bundled_images_or_None).

    - One existing .pdf → use as-is.
    - Anything else (directory / glob / image paths) → bundle into a PDF first.
    """
    if len(inputs) == 1:
        only = Path(os.path.expanduser(inputs[0]))
        if only.suffix.lower() == ".pdf":
            if not only.exists():
                raise FileNotFoundError(only)
            return only.resolve(), None

    images = _collect_images(inputs)
    if not images:
        raise FileNotFoundError(f"no PDF or images in: {inputs}")

    stem = name or (
        Path(os.path.expanduser(inputs[0])).resolve().name
        if len(inputs) == 1 and Path(os.path.expanduser(inputs[0])).is_dir()
        else images[0].parent.name
    )
    out_pdf = Path.home() / "preprocessed" / "_pic_bundles" / f"{stem}.pdf"
    _images_to_pdf(images, out_pdf)
    return out_pdf, images


def cmd_convert(args) -> dict:
    try:
        pdf, bundled = _resolve_input(args.input, args.name)
    except FileNotFoundError as e:
        return {"error": str(e)}
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    state = _read_state()
    server_url = None
    if state is not None and _server_alive(state):
        server_url = f"http://{state['host']}:{state['port']}"

    backend = args.backend
    fallback_note = None
    if not server_url and backend != "pipeline" and not _cuda_available():
        fallback_note = f"CUDA not available — falling back from {backend} to pipeline"
        backend = "pipeline"

    cmd = [
        str(MINERU_CLI),
        "-p", str(pdf),
        "-o", str(out_dir),
        "-l", args.lang,
        "-b", backend,
    ]
    if server_url:
        cmd += ["--api-url", server_url]

    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = int(time.time() - t0)

    md_candidates = sorted(out_dir.glob(f"{pdf.stem}/**/*.md"))
    md_path = str(md_candidates[0]) if md_candidates else None

    result = {
        "pdf": str(pdf),
        "out_md": md_path,
        "mode": "warm" if server_url else "cold",
        "elapsed_seconds": elapsed,
        "backend": backend,
        "returncode": proc.returncode,
        "stderr_tail": (proc.stderr or "")[-500:],
    }
    if fallback_note:
        result["fallback"] = fallback_note
    if bundled is not None:
        result["bundled_from_images"] = len(bundled)
    return result


def _force_utf8_stdout() -> None:
    """Windows consoles default to cp932/cp1252; force UTF-8 so JSON with non-ASCII never blows up."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except Exception:
                pass


def main() -> None:
    _force_utf8_stdout()
    p = argparse.ArgumentParser(prog="dispatcher.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("start-server", help="launch mineru-api with VLM preload")
    sp.add_argument("--host", default=DEFAULT_HOST)
    sp.add_argument("--port", type=int, default=DEFAULT_PORT)
    sp.add_argument("--wait", type=int, default=420, help="seconds to wait for ready")
    sp.set_defaults(func=cmd_start_server)

    sp = sub.add_parser("stop-server", help="kill the running mineru-api")
    sp.set_defaults(func=cmd_stop_server)

    sp = sub.add_parser("status", help="report server liveness")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("convert", help="PDF or image sequence → md")
    sp.add_argument("input", nargs="+",
                    help="a .pdf, or a directory/glob/list of images (png/jpg/webp/heic/tif/bmp)")
    sp.add_argument("--name", help="stem for bundled-image PDF (default: source dir name)")
    sp.add_argument("--out", default=str(DEFAULT_OUT))
    sp.add_argument("--lang", default="japan", help="OCR language hint")
    sp.add_argument("--backend", default="hybrid-auto-engine",
                    help="pipeline (fast, ~85%%) / hybrid-auto-engine (default, ~95%%) / vlm-auto-engine")
    sp.set_defaults(func=cmd_convert)

    args = p.parse_args()
    result = args.func(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
