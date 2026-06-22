"""Tests for assemble.py — the faithfulness gate and stitching back matter.

Run: pytest ~/.claude/skills/pdf-to-md/scripts/tests/ -q
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import assemble  # noqa: E402


# ---------- core() content normalization ----------

def test_core_strips_separators_and_normalizes_width():
    # full-width digits/letters NFKC-fold; dots/dashes/spaces dropped; kana/kanji kept
    assert assemble.core("１．はじめに … ―  1") == assemble.core("1.はじめに-1")
    assert assemble.core("ＡＢＣ") == "ABC"
    assert assemble.core("第１章　総則") == "第章総則"  # digits dropped, kanji/kana kept


def test_core_is_order_of_glyphs_only():
    assert assemble.core("a-b-c") == "abc"
    assert assemble.core("（取扱）") == "取扱"


# ---------- faithfulness: char-multiset coverage ----------

def test_faithfulness_full_coverage_despite_reformatting():
    # md reorders + adds separators/headers but keeps all content chars → coverage 1.0
    tl = "当社の行為規範原則\n法令遵守態勢の重要性"
    md = "## 当社の行為規範原則\n\n本文 — 法令遵守態勢の重要性 (1)\n"
    fa = assemble.faithfulness(tl, md)
    assert fa["coverage"] == 1.0
    assert fa["char_deficit"] == 0


def test_faithfulness_detects_omission():
    tl = "第一条 秘密保持義務 第二条 利益相反取引の禁止"
    md = "第一条 秘密保持義務"  # dropped the second clause
    fa = assemble.faithfulness(tl, md)
    assert fa["coverage"] < 1.0
    assert fa["char_deficit"] > 0


def test_faithfulness_2d_regroup_still_full_coverage():
    # text layer linearizes a 2-box figure row-wise; md regroups by box → same chars
    tl = "独立部署による厳正な 事前チェック体制整備"
    md = "厳正な事前チェック体制整備\n独立部署による"
    assert assemble.faithfulness(tl, md)["coverage"] == 1.0


# ---------- continuation markers + concat ----------

def test_concat_drops_continuation_markers(tmp_path):
    a = tmp_path / "chunk_00.md"
    b = tmp_path / "chunk_01.md"
    a.write_text("body a\n<!-- continues-to-next -->", encoding="utf-8")
    b.write_text("<!-- continues-from-previous -->\nbody b", encoding="utf-8")
    out = assemble._concat_chunks([a, b])
    assert "continues-" not in out
    assert "body a" in out and "body b" in out


# ---------- running header/footer strip ----------

def test_strip_removes_constant_recurring_page_chrome():
    # Incrementing page numbers differ each page, so they are NOT caught here — those are
    # stripped per-page by the transcription subagents. assemble only nets a CONSTANT
    # recurring page-pattern footer (e.g. "- 0 -") that slipped through identically.
    md = "\n".join(["- 0 -", "# 第1章", "x", "- 0 -", "y", "- 0 -", "z", "- 0 -"])
    out, removed = assemble._strip_running_artifacts(md, chunk_count=8)
    assert "- 0 -" in removed
    assert "# 第1章" in out and "x" in out and "y" in out  # heading + body kept


def test_strip_preserves_recurring_CONTENT():
    # E2E regression: a clause repeated across sections is real content, NOT chrome —
    # page-number-only strip must never remove it (this once dropped faithfulness to 99.6%).
    clause = "別に定める社内ルールに従う。"
    md = "\n".join(["# H", clause, "a", clause, "b", clause, "c", clause])
    out, removed = assemble._strip_running_artifacts(md, chunk_count=8)
    assert removed == []
    assert out.count(clause) == 4


def test_strip_never_touches_code_fences():
    # page numbers inside a code fence (e.g. a transcribed figure) survive; bare ones go.
    md = "\n".join(["```", "12", "12", "12", "```", "12", "12", "12", "12"])
    out, _removed = assemble._strip_running_artifacts(md, chunk_count=8)
    assert out.count("12") == 3  # only the fenced ones remain


def test_strip_noop_when_no_recurrence():
    md = "# H\n\nunique body line\n\nanother line\n"
    out, removed = assemble._strip_running_artifacts(md, chunk_count=4)
    assert removed == []
    assert out.strip() == md.strip()
