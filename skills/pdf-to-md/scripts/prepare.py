#!/usr/bin/env python3
"""pdf-to-md prepare (Claude-native pipeline — no MinerU).

Normalize input → per-page PNG (pdftoppm) + per-page text layer (pdftotext) →
born-digital detection → heading-outline HINT → batch manifest that SKILL.md
drives transcription subagents from.

Design: _dev/REDESIGN_2026-06.md. The engine is Claude (Read vision); this script
only does the mechanical front matter. Encrypted PDFs with copy/print permission
are handled directly by poppler — no qpdf/decryption step needed.

Usage:
  python3 prepare.py <input...> [--out-dir DIR] [--name STEM] [--batch-size N] [--dpi N]
  <input> = a .pdf, a directory of images, a glob, or a list of image paths.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from glob import glob
from pathlib import Path

IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp", ".heic"}
_NAT = re.compile(r"(\d+)")
BORN_DIGITAL_MIN_CHARS = 50  # per-page text-layer chars to count as born-digital
DEFAULT_OUT = Path.home() / "preprocessed"

# Heading-outline HINT patterns (text-layer line → candidate heading). A hint only;
# the transcribing subagent makes the real structural call from the page image.
_HEADING_HINT = re.compile(r"^\s*(第?\s*[0-9０-９]+\s*[章節条]|[0-9０-９]+\s*[\.．、]|[０-９0-9]+\s)")


def _natkey(p: Path):
    return [int(s) if s.isdigit() else s.lower() for s in _NAT.split(p.name)]


def _which(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        sys.exit(f"[error] required tool not found on PATH: {tool} (install poppler)")
    return path


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


def _pdf_page_count(pdf: Path) -> int:
    out = subprocess.run([_which("pdfinfo"), str(pdf)], capture_output=True, text=True)
    for line in out.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    raise RuntimeError(f"could not read page count from {pdf}")


def _render_pdf(pdf: Path, img_dir: Path, dpi: int) -> list[Path]:
    img_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run([_which("pdftoppm"), "-png", "-r", str(dpi), str(pdf), str(img_dir / "page")],
                   check=True, capture_output=True)
    produced = sorted(img_dir.glob("page-*.png"), key=_natkey)
    out = []
    for i, p in enumerate(produced, start=1):
        tgt = img_dir / f"page-{i:03d}.png"
        if p != tgt:
            p.rename(tgt)
        out.append(tgt)
    return out


def _extract_text(pdf: Path, page: int, text_dir: Path) -> Path:
    text_dir.mkdir(parents=True, exist_ok=True)
    tgt = text_dir / f"page-{page:03d}.txt"
    subprocess.run([_which("pdftotext"), "-f", str(page), "-l", str(page), "-layout",
                    str(pdf), str(tgt)], check=True, capture_output=True)
    return tgt


def _nonspace_len(path: Path) -> int:
    try:
        return len(re.sub(r"\s+", "", path.read_text(encoding="utf-8", errors="replace")))
    except Exception:
        return 0


def _outline_hint(text_files: list[Path], limit: int = 200) -> list[str]:
    hints: list[str] = []
    for tf in text_files:
        if not tf or not tf.exists():
            continue
        for ln in tf.read_text(encoding="utf-8", errors="replace").splitlines():
            s = ln.strip()
            if 2 <= len(s) <= 40 and _HEADING_HINT.match(s):
                hints.append(s)
                if len(hints) >= limit:
                    return hints
    return hints


def _copy_images_as_pages(images: list[Path], img_dir: Path) -> list[Path]:
    img_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for i, src in enumerate(images, start=1):
        tgt = img_dir / f"page-{i:03d}{src.suffix.lower()}"
        shutil.copyfile(src, tgt)
        out.append(tgt)
    return out


def prepare(inputs: list[str], out_dir: Path, name: str | None,
            batch_size: int, dpi: int) -> dict:
    pdfs = [Path(os.path.expanduser(i)) for i in inputs
            if Path(os.path.expanduser(i)).suffix.lower() == ".pdf"]
    if len(pdfs) > 1:
        sys.exit("[error] multiple PDFs in one call is not supported — this skill processes one "
                 "document per run. Run prepare.py once per PDF (each becomes its own <stem>/ "
                 "output). Got: " + ", ".join(p.name for p in pdfs))
    if pdfs and len(inputs) > 1:
        sys.exit("[error] cannot mix a PDF with other inputs — pass a single PDF, or only images")
    single = len(pdfs) == 1
    pdf: Path | None = None
    images: list[Path] = []
    if single:
        pdf = Path(os.path.expanduser(inputs[0])).resolve()
        if not pdf.exists():
            sys.exit(f"[error] PDF not found: {pdf}")
        stem = name or pdf.stem
    else:
        images = _collect_images(inputs)
        if not images:
            sys.exit(f"[error] no PDF or images in: {inputs}")
        stem = name or (Path(os.path.expanduser(inputs[0])).resolve().name
                        if Path(os.path.expanduser(inputs[0])).is_dir() else images[0].parent.name)

    out_dir = (out_dir / _slug(stem)).expanduser().resolve()
    work = out_dir / "_work"
    img_dir, text_dir = work / "img", work / "text"
    for d in (out_dir, work, img_dir):
        d.mkdir(parents=True, exist_ok=True)

    pages: list[dict] = []
    if single:
        assert pdf is not None
        n = _pdf_page_count(pdf)
        imgs = _render_pdf(pdf, img_dir, dpi)
        for i in range(1, n + 1):
            tf = _extract_text(pdf, i, text_dir)
            chars = _nonspace_len(tf)
            img = imgs[i - 1] if i - 1 < len(imgs) else None
            pages.append({
                "page": i,
                "image": str(img) if img else None,
                "text": str(tf) if chars > 0 else None,
                "born_digital": chars >= BORN_DIGITAL_MIN_CHARS,
                "text_chars": chars,
            })
        source = str(pdf)
    else:
        imgs = _copy_images_as_pages(images, img_dir)
        for i, img in enumerate(imgs, start=1):
            pages.append({
                "page": i, "image": str(img), "text": None,
                "born_digital": False, "text_chars": 0,
            })
        source = f"{len(images)} images"

    text_files = [Path(p["text"]) for p in pages if p["text"]]
    outline = _outline_hint(text_files)

    batches = []
    for b, start in enumerate(range(0, len(pages), batch_size)):
        grp = pages[start:start + batch_size]
        batches.append({
            "index": b,
            "pages": [p["page"] for p in grp],
            "images": [p["image"] for p in grp],
            "texts": [p["text"] for p in grp],
            "born_digital": [p["born_digital"] for p in grp],
        })

    born_overall = sum(1 for p in pages if p["born_digital"]) >= max(1, len(pages) // 2)
    manifest = {
        "source": source,
        "stem": _slug(stem),
        "out_dir": str(out_dir),
        "work_dir": str(work),
        "page_count": len(pages),
        "born_digital": born_overall,
        "batch_size": batch_size,
        "batch_count": len(batches),
        "outline_hint": outline,
        "batches": batches,
    }
    (work / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


_SLUG = re.compile(r"[^a-zA-Z0-9_぀-ヿ一-鿿\-]")


def _slug(name: str, max_len: int = 80) -> str:
    s = _SLUG.sub("_", str(name).strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return (s[:max_len] or "document")[:max_len]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="+", help="a .pdf, a directory/glob/list of images")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT))
    ap.add_argument("--name", help="output stem (default: pdf stem / image dir name)")
    ap.add_argument("--batch-size", type=int, default=6, help="pages per batch (default 6)")
    ap.add_argument("--dpi", type=int, default=150)
    args = ap.parse_args()
    manifest = prepare(args.input, Path(args.out_dir), args.name, args.batch_size, args.dpi)
    # Print a compact view (never dump page text); full manifest is on disk.
    view = {k: v for k, v in manifest.items() if k not in ("batches", "outline_hint")}
    view["outline_hint_count"] = len(manifest["outline_hint"])
    view["manifest_path"] = str(Path(manifest["work_dir"]) / "manifest.json")
    print(json.dumps(view, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
