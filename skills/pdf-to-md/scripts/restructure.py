#!/usr/bin/env python3
"""Layout-aware heading reconstruction for MinerU slide-deck output.

MinerU converts presentation PDFs by tagging every slide title as a level-1
heading (`text_level == 1`) and emitting them all as `#` in the markdown. That
flat structure has two downstream pathologies (seen in lecture decks):

  1. Every slide title is `#` — no document title vs. section distinction, so a
     consumer (e.g. ai-wiki) cannot tell the deck title from a slide title.
  2. Body lines on busy slides get mis-tagged as headings, and a multi-slide
     topic repeats the same title across N slides (e.g. "基礎的考え" ×8).

This module uses the layout signal MinerU *also* exports
(`<stem>_content_list.json`: per-block `text_level`, `bbox`, `page_idx`) to
reconstruct a sane hierarchy **without an LLM**:

  - The first slide title (reading order) becomes the document title `#`.
  - The first heading of every other page becomes a slide section `##`.
  - Any *additional* heading on the same page is a mis-tagged body line and is
    demoted to a paragraph.
  - Runs of consecutive identical `##` titles (a topic spanning several slides)
    collapse into a single section, bodies concatenated.

It is deliberately conservative: it only fires when the source looks like a flat
slide deck (every heading at `text_level == 1`) and the markdown headings align
1:1 in order with the JSON heading blocks. For a genuinely hierarchical PDF
(MinerU already emitting mixed levels) it is a no-op, leaving MinerU's structure
untouched.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def _norm_title(s: str) -> str:
    """Normalize a heading for duplicate comparison: drop all whitespace
    (incl. full-width spaces) so OCR spacing jitter — "管理される「" vs
    "管理される 「" — does not defeat the consecutive-duplicate collapse."""
    return re.sub(r"\s+", "", s.replace("　", " ")).strip()


def load_heading_blocks(content_list: list[dict]) -> list[dict]:
    """Ordered level-1 heading blocks with (page_idx, height, text)."""
    out: list[dict] = []
    for b in content_list:
        if b.get("text_level") != 1:
            continue
        bb = b.get("bbox") or [0, 0, 0, 0]
        height = (bb[3] - bb[1]) if len(bb) == 4 else 0.0
        out.append(
            {
                "page": b.get("page_idx", 0),
                "height": float(height),
                "text": (b.get("text") or "").strip(),
            }
        )
    return out


def _is_flat_deck(content_list: list[dict]) -> bool:
    """True iff every heading MinerU detected is level-1 (no hierarchy of its
    own). A structured PDF that already carries level-2/3 headings is left
    alone — its structure is trustworthy and must not be flattened."""
    levels = {b.get("text_level") for b in content_list if b.get("text_level")}
    return levels == {1}


def restructure_markdown(md_text: str, content_list: list[dict]) -> tuple[str, dict]:
    """Reconstruct heading levels in ``md_text`` from layout signal.

    Returns ``(new_md, summary)``. ``summary['applied']`` is False (and
    ``new_md is md_text``) whenever the source is not a flat slide deck or the
    markdown/JSON headings do not align — the safe no-op path.
    """
    summary: dict = {"applied": False}

    if not content_list or not _is_flat_deck(content_list):
        summary["reason"] = "not a flat slide deck (MinerU hierarchy kept)"
        return md_text, summary

    blocks = load_heading_blocks(content_list)
    lines = md_text.splitlines()
    heading_idxs = [i for i, ln in enumerate(lines) if _HEADING_RE.match(ln)]

    # Order-align markdown headings with JSON heading blocks. Bail on any
    # mismatch (count or text) — a drifted alignment must never silently
    # mangle the document.
    if len(heading_idxs) != len(blocks):
        summary["reason"] = (
            f"heading count mismatch (md={len(heading_idxs)}, json={len(blocks)})"
        )
        return md_text, summary
    for li, blk in zip(heading_idxs, blocks):
        m = _HEADING_RE.match(lines[li])
        assert m  # guaranteed by construction
        if _norm_title(m.group(2)) != _norm_title(blk["text"]):
            summary["reason"] = "heading text mismatch between md and json"
            return md_text, summary

    if not blocks:
        summary["reason"] = "no headings"
        return md_text, summary

    # --- decide a level for each heading, in reading order ---
    # first-of-page → section title; the very first → document title; any extra
    # heading on a page → demote to body (mis-tagged content line).
    seen_pages: set = set()
    decisions: list[str] = []  # "doc" | "section" | "body"
    for idx, blk in enumerate(blocks):
        page = blk["page"]
        first_on_page = page not in seen_pages
        seen_pages.add(page)
        if idx == 0:
            decisions.append("doc")
        elif first_on_page:
            decisions.append("section")
        else:
            decisions.append("body")

    demoted = sum(1 for d in decisions if d == "body")

    # --- rewrite heading lines ---
    decision_by_line = dict(zip(heading_idxs, decisions))
    text_by_line = {li: _HEADING_RE.match(lines[li]).group(2) for li in heading_idxs}  # type: ignore
    rewritten: list[str] = []
    last_section_norm: str | None = None
    merged_runs = 0
    for i, ln in enumerate(lines):
        if i not in decision_by_line:
            rewritten.append(ln)
            continue
        decision = decision_by_line[i]
        text = text_by_line[i]
        if decision == "doc":
            rewritten.append(f"# {text}")
            last_section_norm = None
        elif decision == "section":
            norm = _norm_title(text)
            if norm == last_section_norm:
                # consecutive duplicate slide title → collapse: drop the heading
                # line, keep its body under the already-open section.
                merged_runs += 1
                continue
            rewritten.append(f"## {text}")
            last_section_norm = norm
        else:  # body — strip the heading marker, keep text as a paragraph
            rewritten.append(text)
            # a demoted line does not break a duplicate run

    new_md = "\n".join(rewritten)
    if md_text.endswith("\n"):
        new_md += "\n"

    sections_after = sum(1 for ln in rewritten if ln.startswith("## "))
    summary.update(
        {
            "applied": True,
            "headings_before": len(blocks),
            "doc_title": blocks[0]["text"],
            "sections_after": sections_after,
            "demoted_to_body": demoted,
            "merged_duplicate_runs": merged_runs,
        }
    )
    return new_md, summary


def restructure_md_file(md_path: str | Path, content_list_path: str | Path | None = None) -> dict:
    """Apply :func:`restructure_markdown` to a MinerU ``.md`` in place.

    The original MinerU markdown is preserved as ``<stem>.raw.md`` before the
    structured version overwrites ``<stem>.md``. No-op (no backup, no write)
    when restructuring does not apply. Returns the summary dict augmented with
    the paths involved.
    """
    md_path = Path(md_path)
    if content_list_path is None:
        content_list_path = md_path.with_name(f"{md_path.stem}_content_list.json")
    content_list_path = Path(content_list_path)

    if not md_path.exists():
        return {"applied": False, "reason": f"md not found: {md_path}"}
    if not content_list_path.exists():
        return {"applied": False, "reason": f"content_list not found: {content_list_path}"}

    md_text = md_path.read_text(encoding="utf-8")
    try:
        content_list = json.loads(content_list_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"applied": False, "reason": f"content_list JSON error: {e}"}

    new_md, summary = restructure_markdown(md_text, content_list)
    if not summary.get("applied"):
        return summary

    raw_path = md_path.with_name(f"{md_path.stem}.raw.md")
    raw_path.write_text(md_text, encoding="utf-8")
    md_path.write_text(new_md, encoding="utf-8")
    summary["md_path"] = str(md_path)
    summary["raw_backup"] = str(raw_path)
    return summary
