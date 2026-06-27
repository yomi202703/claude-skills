#!/usr/bin/env python3
"""pdf-to-md assemble (Claude-native pipeline — no MinerU).

Stitch per-batch markdown chunks (written by transcription subagents) into the
final document, then run the faithfulness gate. Mechanical back matter only.

Design: _dev/REDESIGN_2026-06.md. Steps:
  1. concat chunks in batch order, drop cross-batch continuation markers (join seamless)
  2. conservative running-header/footer/page-number backstop strip
  3. faithfulness gate — char-multiset content coverage (primary, hard) against the
     concatenated text layer with recurring header/footer chrome removed (the same chrome
     the subagents strip, so correctly-dropped footers are not counted as missing); a
     line-level locator (secondary, with the actual missing text) runs only when a deficit
     exists; 2D-figure line mismatches are expected and do not fail (char-multiset is truth)
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


_DIGITS = re.compile(r"\d+")


def _norm_chrome(line: str) -> str:
    """Match key for running header/footer detection: NFKC, drop digits (page numbers
    vary) and all whitespace, keep the rest. Footer lines that differ only by their page
    number collapse to a single key (e.g. '… PAGE 14' / '… PAGE 15' → same key)."""
    return re.sub(r"\s+", "", _DIGITS.sub("", unicodedata.normalize("NFKC", line)))


def _page_text_lines(manifest: dict) -> list[list[str]]:
    pages = []
    for b in manifest["batches"]:
        for t in b["texts"]:
            if t and Path(t).exists():
                pages.append(Path(t).read_text(encoding="utf-8", errors="replace").splitlines())
    return pages


def _detect_textlayer_chrome(pages: list[list[str]], edge: int = 2) -> set[str]:
    """Recurring header/footer lines in the per-page text layer — the SAME running chrome
    the transcription subagents are contracted to strip ("Strip running headers/footers/
    page numbers"). A line qualifies only if it (a) sits in the top-`edge` or bottom-`edge`
    NON-EMPTY lines of its page AND (b) its digit-stripped key recurs on >= threshold pages.
    Positional gating keeps recurring *body* content safe — a clause repeated mid-section is
    never at a page edge, so it never qualifies. Without this the gate grounds against a
    text layer that still contains footers the output correctly dropped, counts them as
    missing content, and false-FAILs footer-heavy / slide-style docs (decisions G1)."""
    counts: Counter = Counter()
    for lines in pages:
        ne = [l for l in lines if l.strip()]
        if not ne:
            continue
        band = ne[:edge] + ne[-edge:]
        # candidate only if the line carries content chars — a pure page-number line
        # ("- 14 -") contributes 0 to the coverage metric, so it is never worth a key.
        for k in {_norm_chrome(l) for l in band if len(core(l)) >= 2}:
            counts[k] += 1
    threshold = max(3, (len(pages) + 1) // 2)
    return {k for k, c in counts.items() if c >= threshold}


def _strip_edge_chrome(lines: list[str], chrome: set[str], edge: int = 2) -> list[str]:
    """Drop only the page-edge lines whose key is in `chrome`; body lines untouched."""
    if not chrome:
        return lines
    ne_idx = [i for i, l in enumerate(lines) if l.strip()]
    band = set(ne_idx[:edge] + ne_idx[-edge:])
    return [l for i, l in enumerate(lines) if not (i in band and _norm_chrome(l) in chrome)]


def _textlayer_ground_truth(manifest: dict) -> tuple[str | None, list[str]]:
    """The text layer to gate against, with recurring header/footer chrome removed so the
    gate measures real body-content loss — not boilerplate the subagents were told to strip.
    Returns (cleaned_concatenation, sorted list of excluded chrome keys) or (None, []) when
    there is no text layer (image-only)."""
    pages = _page_text_lines(manifest)
    if not pages:
        return None, []
    chrome = _detect_textlayer_chrome(pages)
    cleaned = "\n".join("\n".join(_strip_edge_chrome(p, chrome)) for p in pages)
    return cleaned, sorted(chrome)


def faithfulness(textlayer: str, md: str) -> dict:
    tl, m = Counter(core(textlayer)), Counter(core(md))
    total = sum(tl.values())
    deficit = sum((tl - m).values())
    coverage = 1.0 - (deficit / total) if total else 1.0
    return {"textlayer_chars": total, "md_chars": sum(m.values()),
            "char_deficit": deficit, "coverage": round(coverage, 4)}


def locate_gaps(manifest: dict, md: str, chrome: set[str] | None = None) -> list[dict]:
    """Per-page content-core line coverage — only for locating WHERE content dropped when
    the char-multiset gate shows a deficit. Running header/footer chrome is excluded (same
    set the gate excludes) so gaps point at TRUE body loss, and each gap carries the actual
    missing line text so the user can tell footer noise from real omission at a glance
    (decisions G2). 2D-figure line mismatches are expected and not real loss."""
    md_core = core(md)
    chrome = chrome or set()
    gaps = []
    for b in manifest["batches"]:
        for page, tpath in zip(b["pages"], b["texts"]):
            if not tpath or not Path(tpath).exists():
                continue
            raw = _strip_edge_chrome(
                Path(tpath).read_text(encoding="utf-8", errors="replace").splitlines(), chrome)
            units = [(l.strip(), core(l)) for l in raw]
            units = [(r, c) for r, c in units if len(c) >= 4]
            if not units:
                continue
            missing = [r for r, c in units if c not in md_core]
            if missing:
                gaps.append({"page": page, "missing_lines": len(missing), "total_lines": len(units),
                             "line_coverage": round(1 - len(missing) / len(units), 3),
                             "missing_samples": [m[:60] for m in missing[:3]]})
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

    textlayer, chrome = _textlayer_ground_truth(manifest)
    if textlayer is None:
        result["faithfulness"] = {"mode": "image-only",
                                  "note": "no text layer — coverage gate N/A (softer assurance)"}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    fa = faithfulness(textlayer, md)
    result["faithfulness"] = {"mode": "born-digital", **fa}
    if chrome:
        result["faithfulness"]["textlayer_chrome_excluded"] = chrome
    if fa["coverage"] < args.min_coverage:
        result["faithfulness"]["gaps"] = locate_gaps(manifest, md, set(chrome))
        result["faithfulness"]["status"] = "FAIL"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(2)
    result["faithfulness"]["status"] = "ok"
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
