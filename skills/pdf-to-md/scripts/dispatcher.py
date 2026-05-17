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
import signal
import subprocess
import time
import urllib.request
from pathlib import Path

VENV_BIN = Path.home() / "mineru-test" / ".venv" / "bin"
MINERU_API = VENV_BIN / "mineru-api"
MINERU_CLI = VENV_BIN / "mineru"
STATE_FILE = Path("/tmp/pdf-to-md-server.json")
LOG_FILE = Path("/tmp/pdf-to-md-server.log")
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
        start_new_session=True,
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


def cmd_stop_server(args) -> dict:
    state = _read_state()
    if not state:
        return {"stopped": False, "reason": "no state file"}
    pid = state.get("pid")
    if isinstance(pid, int):
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    STATE_FILE.unlink(missing_ok=True)
    return {"stopped": True, "pid": pid}


def cmd_status(args) -> dict:
    state = _read_state()
    return {"alive": _server_alive(state), "state": state}


def cmd_convert(args) -> dict:
    pdf = Path(args.pdf).expanduser().resolve()
    if not pdf.exists():
        return {"error": f"not found: {pdf}"}
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    state = _read_state()
    server_url = None
    if state is not None and _server_alive(state):
        server_url = f"http://{state['host']}:{state['port']}"

    cmd = [
        str(MINERU_CLI),
        "-p", str(pdf),
        "-o", str(out_dir),
        "-l", args.lang,
        "-b", args.backend,
    ]
    if server_url:
        cmd += ["--api-url", server_url]

    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = int(time.time() - t0)

    md_candidates = sorted(out_dir.glob(f"{pdf.stem}/**/*.md"))
    md_path = str(md_candidates[0]) if md_candidates else None

    return {
        "pdf": str(pdf),
        "out_md": md_path,
        "mode": "warm" if server_url else "cold",
        "elapsed_seconds": elapsed,
        "backend": args.backend,
        "returncode": proc.returncode,
        "stderr_tail": (proc.stderr or "")[-500:],
    }


def main() -> None:
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

    sp = sub.add_parser("convert", help="PDF → md")
    sp.add_argument("pdf")
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
