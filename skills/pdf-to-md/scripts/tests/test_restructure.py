"""Tests for restructure.py (layout-aware heading reconstruction)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import restructure  # noqa: E402


def _blk(text, level=1, page=0, h=80.0):
    return {"type": "text", "text": text, "text_level": level,
            "page_idx": page, "bbox": [0, 0, 100, h]}


# ---------- flat slide deck: the core transform ----------


def test_flat_deck_reconstructs_doc_and_sections():
    md = "# Deck Title\n\nintro\n\n# Slide A\n\nbody a\n\n# Slide B\n\nbody b\n"
    cl = [
        _blk("Deck Title", page=0),
        _blk("Slide A", page=1),
        _blk("Slide B", page=2),
    ]
    new, s = restructure.restructure_markdown(md, cl)
    assert s["applied"] is True
    assert s["doc_title"] == "Deck Title"
    assert "# Deck Title" in new
    assert "## Slide A" in new
    assert "## Slide B" in new
    # exactly one document title
    assert new.count("\n# ") + new.startswith("# ") == 1


def test_demotes_extra_heading_on_same_page():
    # Two headings on page 1: first is the slide title, second is a mis-tagged
    # body line and must be demoted to a paragraph.
    md = "# Title\n\n# Real Slide\n\n# stray body line\n\nbody\n"
    cl = [
        _blk("Title", page=0),
        _blk("Real Slide", page=1),
        _blk("stray body line", page=1, h=30.0),
    ]
    new, s = restructure.restructure_markdown(md, cl)
    assert s["applied"] is True
    assert s["demoted_to_body"] == 1
    assert "## Real Slide" in new
    assert "## stray body line" not in new
    assert "stray body line" in new  # kept as body


def test_collapses_consecutive_duplicate_titles():
    md = (
        "# T\n\n# Topic\n\nslide1\n\n# Topic\n\nslide2\n\n# Topic\n\nslide3\n"
    )
    cl = [
        _blk("T", page=0),
        _blk("Topic", page=1),
        _blk("Topic", page=2),
        _blk("Topic", page=3),
    ]
    new, s = restructure.restructure_markdown(md, cl)
    assert s["merged_duplicate_runs"] == 2
    assert new.count("## Topic") == 1
    # all three slide bodies survive
    for b in ("slide1", "slide2", "slide3"):
        assert b in new


def test_duplicate_collapse_ignores_whitespace_jitter():
    md = "# T\n\n# 管理される「人間」\n\na\n\n# 管理される 「人間」\n\nb\n"
    cl = [
        _blk("T", page=0),
        _blk("管理される「人間」", page=1),
        _blk("管理される 「人間」", page=2),  # OCR space jitter
    ]
    new, s = restructure.restructure_markdown(md, cl)
    assert s["merged_duplicate_runs"] == 1
    assert new.count("## ") == 1


# ---------- safety / no-op paths ----------


def test_hierarchical_doc_is_left_untouched():
    # MinerU already emitted level-2 headings → trustworthy hierarchy, no-op.
    md = "# Paper\n\n## Section 1\n\nbody\n\n## Section 2\n\nbody\n"
    cl = [
        _blk("Paper", level=1, page=0),
        _blk("Section 1", level=2, page=0),
        _blk("Section 2", level=2, page=1),
    ]
    new, s = restructure.restructure_markdown(md, cl)
    assert s["applied"] is False
    assert new == md


def test_heading_count_mismatch_is_noop():
    md = "# A\n\n# B\n\nbody\n"
    cl = [_blk("A", page=0)]  # only one block, md has two headings
    new, s = restructure.restructure_markdown(md, cl)
    assert s["applied"] is False
    assert "mismatch" in s["reason"]
    assert new == md


def test_heading_text_mismatch_is_noop():
    md = "# A\n\n# B\n\nbody\n"
    cl = [_blk("A", page=0), _blk("DIFFERENT", page=1)]
    new, s = restructure.restructure_markdown(md, cl)
    assert s["applied"] is False
    assert new == md


def test_empty_content_list_is_noop():
    md = "# A\n\nbody\n"
    new, s = restructure.restructure_markdown(md, [])
    assert s["applied"] is False
    assert new == md


# ---------- file-level entry: backup + in-place rewrite ----------


def test_restructure_md_file_backs_up_and_rewrites(tmp_path):
    base = tmp_path / "deck"
    md = base.with_suffix(".md")
    md.write_text("# T\n\n# Slide\n\nbody\n", encoding="utf-8")
    cl_path = tmp_path / "deck_content_list.json"
    cl_path.write_text(
        json.dumps([_blk("T", page=0), _blk("Slide", page=1)]), encoding="utf-8"
    )
    s = restructure.restructure_md_file(md, cl_path)
    assert s["applied"] is True
    assert (tmp_path / "deck.raw.md").exists()
    assert "## Slide" in md.read_text(encoding="utf-8")
    # raw backup preserves the original flat markdown
    assert "# Slide" in (tmp_path / "deck.raw.md").read_text(encoding="utf-8")


def test_restructure_md_file_missing_content_list_is_noop(tmp_path):
    md = tmp_path / "deck.md"
    md.write_text("# T\n\nbody\n", encoding="utf-8")
    s = restructure.restructure_md_file(md)
    assert s["applied"] is False
    assert not (tmp_path / "deck.raw.md").exists()
