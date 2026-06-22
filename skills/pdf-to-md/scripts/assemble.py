#!/usr/bin/env python3
"""pdf-to-md assemble (Claude-native pipeline — no MinerU).

Stitch per-batch markdown chunks (written by transcription subagents) into the
final document, then run the faithfulness gate. Mechanical back matter only.

Design: _dev/REDESIGN_2026-06.md. Steps:
  1. concat chunks in batch order, drop cross-batch continuation markers (join seamless)
  2. conservative running-header/footer/page-number backstop strip
  3. faithfulness gate — char-multiset content coverage (primary, hard) against the
     concatenated text layer; line-level locator (secondary) only when a deficit exists;
     2D-figure line mismatches are expected and do not fail (char-multiset is the truth)
  4. write <out_dir>/<stem>.md

Faithfulness gate is born-digital only (text layer = ground truth). Image-only inputs
have no text layer → coverage N/A, reported as softer assurance.

Usage:
  python3 assemble.py --manifest <work>/manifest.json [--chunks-dir DIR] [--min-coverage 0.995]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

_NAT = re.compile(r"(\d+)")
_CONT_MARKER = re.compile(r"<!--\s*continues-(from-previous|to-next)\s*-->")


def _natkey(p: Path):
    return [int(s) if s.isdigit() else s.lower() for s in _NAT.split(p.name)]


def core(s: str) -> str:
    """Content-core normalization (the validated faithfulness metric): NFKC, then keep
    only kana / kanji / latin letters. Drops separators, dot-leaders, digits, punctuation,
    whitespace — so legitimate reformatting and 2D-figure regrouping don't cause false
    misses. Comparison is position-insensitive (multiset)."""
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"[^ぁ-んァ-ヶ一-龥A-Za-z]+", "", s)


def _concat_chunks(chunk_paths: list[Path]) -> str:
    parts = []
    for p in chunk_paths:
        txt = _CONT_MARKER.sub("", p.read_text(encoding="utf-8", errors="replace")).strip("\n")
        parts.append(txt)
    return "\n\n".join(parts) + "\n"


_PAGE_NUM = re.compile(
    r"^\s*[-–—]?\s*(?:p\.?|page|ページ)?\s*\d{1,4}(?:\s*[-–—/]\s*\d{1,4})?\s*[-–—]?\s*$",
    re.IGNORECASE)


def _strip_running_artifacts(md: str, chunk_count: int) -> tuple[str, list[str]]:
    """Narrow backstop: remove ONLY recurring page-number-like chrome lines that slipped
    through (the transcription subagents already strip per-page headers/footers). It must
    NOT touch real content — recurring *content* (e.g. a clause repeated across sections)
    is left alone, so it never reduces faithfulness coverage. Code fences are untouched."""
    lines = md.splitlines()
    in_fence = False
    counts: Counter = Counter()
    for ln in lines:
        if ln.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        s = ln.strip()
        if s and _PAGE_NUM.match(s):
            counts[s] += 1
    threshold = max(3, (chunk_count + 1) // 2)
    chrome = {s for s, c in counts.items() if c >= threshold}
    if not chrome:
        return md, []
    out, removed, in_fence = [], [], False
    for ln in lines:
        if ln.strip().startswith("```"):
            in_fence = not in_fence
            out.append(ln)
            continue
        if not in_fence and ln.strip() in chrome:
            removed.append(ln.strip())
            continue
        out.append(ln)
    return "\n".join(out) + ("\n" if md.endswith("\n") else ""), sorted(chrome)


def _textlayer_concat(manifest: dict) -> str | None:
    texts = [Path(t) for b in manifest["batches"] for t in b["texts"] if t]
    if not texts:
        return None
    return "\n".join(t.read_text(encoding="utf-8", errors="replace") for t in texts if t.exists())


def faithfulness(textlayer: str, md: str) -> dict:
    tl, m = Counter(core(textlayer)), Counter(core(md))
    total = sum(tl.values())
    deficit = sum((tl - m).values())
    coverage = 1.0 - (deficit / total) if total else 1.0
    return {"textlayer_chars": total, "md_chars": sum(m.values()),
            "char_deficit": deficit, "coverage": round(coverage, 4)}


def locate_gaps(manifest: dict, md: str) -> list[dict]:
    """Per-page content-core line coverage — only for locating WHERE content dropped
    when the char-multiset gate shows a deficit. 2D-figure mismatches expected."""
    md_core = core(md)
    gaps = []
    for b in manifest["batches"]:
        for page, tpath in zip(b["pages"], b["texts"]):
            if not tpath or not Path(tpath).exists():
                continue
            units = [core(l) for l in Path(tpath).read_text(encoding="utf-8", errors="replace").splitlines()]
            units = [u for u in units if len(u) >= 4]
            if not units:
                continue
            missed = sum(1 for u in units if u not in md_core)
            if missed:
                gaps.append({"page": page, "missing_lines": missed, "total_lines": len(units),
                             "line_coverage": round(1 - missed / len(units), 3)})
    return sorted(gaps, key=lambda g: g["line_coverage"])[:15]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--chunks-dir", help="dir of chunk_*.md (default: <work>/chunks)")
    ap.add_argument("--min-coverage", type=float, default=0.995,
                    help="hard gate: minimum char-multiset content coverage (born-digital)")
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    work = Path(manifest["work_dir"])
    chunks_dir = Path(args.chunks_dir) if args.chunks_dir else work / "chunks"
    chunk_paths = sorted(chunks_dir.glob("chunk_*.md"), key=_natkey)
    if not chunk_paths:
        sys.exit(f"[error] no chunk_*.md in {chunks_dir} — run the transcription step first")
    if len(chunk_paths) != manifest["batch_count"]:
        print(f"[warn] {len(chunk_paths)} chunks but {manifest['batch_count']} batches expected",
              file=sys.stderr)

    md = _concat_chunks(chunk_paths)
    md, removed = _strip_running_artifacts(md, len(chunk_paths))

    out_md = Path(manifest["out_dir"]) / f"{manifest['stem']}.md"
    out_md.write_text(md, encoding="utf-8")

    result = {"out_md": str(out_md), "chunks": len(chunk_paths),
              "stripped_running_lines": removed}

    textlayer = _textlayer_concat(manifest)
    if textlayer is None:
        result["faithfulness"] = {"mode": "image-only",
                                  "note": "no text layer — coverage gate N/A (softer assurance)"}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    fa = faithfulness(textlayer, md)
    result["faithfulness"] = {"mode": "born-digital", **fa}
    if fa["coverage"] < args.min_coverage:
        result["faithfulness"]["gaps"] = locate_gaps(manifest, md)
        result["faithfulness"]["status"] = "FAIL"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(2)
    result["faithfulness"]["status"] = "ok"
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
