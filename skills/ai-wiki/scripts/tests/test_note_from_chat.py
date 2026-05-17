"""Tests for note_from_chat.py (offline, subprocess mocked)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from note_from_chat import (  # noqa: E402
    _patch_narrative_with_wikilink,
    _section_header_to_anchor,
    detect_chat_export,
    note_from_chat,
)
from vault import Page, Vault  # noqa: E402


# ---------- detect_chat_export ----------


def test_detect_explicit_markers():
    text = "あなたの入力: hello\n\nClaudeが返答しました: hi\n\n13:25\n"
    is_chat, score, hits = detect_chat_export(text)
    assert is_chat
    assert score >= 0.4
    assert any("あなたの入力" in h for h in hits)


def test_detect_broken_latex_only():
    """Many short lines (broken LaTeX export pattern)."""
    text = "\n".join(["x", "=", "1", "+", "2", "y", "=", "3", "z", "=", "4"] * 5)
    is_chat, score, hits = detect_chat_export(text)
    assert is_chat
    assert any("broken-latex" in h for h in hits)


def test_detect_clean_markdown_not_chat():
    text = "# Title\n\nThis is a clean piece of markdown with normal prose. " * 10
    is_chat, score, _ = detect_chat_export(text)
    assert not is_chat
    assert score < 0.4


# ---------- _section_header_to_anchor ----------


def test_section_header_to_anchor():
    assert _section_header_to_anchor("## 1. Foo") == "1. Foo"
    assert _section_header_to_anchor("### 2. Bar baz") == "2. Bar baz"
    assert _section_header_to_anchor("##  ROOT  ") == "ROOT"


# ---------- _patch_narrative_with_wikilink ----------


NARRATIVE_BODY = """intro

## 記法

```
[?] x
```

## 1. First section

body of first
"""


def _make_narrative(vault: Vault, slug: str, body: str = NARRATIVE_BODY) -> Page:
    page = Page(
        kind="narrative",
        slug=slug,
        meta={
            "type": "narrative",
            "slug": slug,
            "title": slug,
            "status": "pilot",
            "created": "2026-04-30",
            "updated": "2026-04-30",
        },
        body=body,
    )
    vault.write(page)
    return page


def test_patch_inserts_after_h2(vault: Vault):
    _make_narrative(vault, "foo")
    ok, msg = _patch_narrative_with_wikilink(
        vault, "foo", "## 1. First section", "↺ note: [[my-note]]"
    )
    assert ok, msg
    page = vault.read("narrative", "foo")
    assert page is not None
    assert "↺ note: [[my-note]]" in page.body
    # Confirm the new line appears after the H2 (not at top)
    idx_h2 = page.body.index("## 1. First section")
    idx_link = page.body.index("[[my-note]]")
    assert idx_link > idx_h2


def test_patch_idempotent(vault: Vault):
    _make_narrative(vault, "foo")
    _patch_narrative_with_wikilink(
        vault, "foo", "## 1. First section", "↺ note: [[my-note]]"
    )
    ok, msg = _patch_narrative_with_wikilink(
        vault, "foo", "## 1. First section", "↺ note: [[my-note]]"
    )
    assert not ok
    assert "already" in msg


def test_patch_unknown_section(vault: Vault):
    _make_narrative(vault, "foo")
    ok, msg = _patch_narrative_with_wikilink(
        vault, "foo", "## 99. Nonexistent", "↺ note: [[my-note]]"
    )
    assert not ok
    assert "not found" in msg


def test_patch_unknown_narrative(vault: Vault):
    ok, msg = _patch_narrative_with_wikilink(
        vault, "missing", "## 1. X", "↺ note: [[a]]"
    )
    assert not ok
    assert "not found" in msg


# ---------- note_from_chat (LLM mocked) ----------


CHAT_EXPORT = """あなたの入力: モーメントとは?
13:25
Claudeが返答しました: モーメントは...
モーメントは

質量

×

距離

の量です。

あなたの入力: なるほど。
13:26
Claudeが返答しました: そうです。
そうです。
"""


def _mock_llm(*envelopes: dict):
    it = iter(envelopes)

    def fake_run(*args, **kwargs):
        env = next(it)

        class Fake:
            returncode = 0
            stdout = json.dumps(env)
            stderr = ""
        return Fake()

    return fake_run


@pytest.fixture
def chat_file(tmp_path) -> Path:
    p = tmp_path / "chat.md"
    p.write_text(CHAT_EXPORT, encoding="utf-8")
    return p


def test_note_from_chat_missing_file(vault: Vault, tmp_path):
    out = note_from_chat(vault, tmp_path / "nope.md", study="foo")
    assert out["errors"]
    assert "not found" in out["errors"][0]


def test_note_from_chat_not_a_chat_blocked(vault: Vault, tmp_path):
    p = tmp_path / "clean.md"
    p.write_text("# Clean\n\nNormal prose with no chat markers. " * 20, encoding="utf-8")
    out = note_from_chat(vault, p, study="foo")
    assert out["errors"]
    assert "chat export" in out["errors"][0]


def test_note_from_chat_force_via_no_detect_check(vault: Vault, tmp_path, monkeypatch):
    p = tmp_path / "clean.md"
    p.write_text("# Clean\n\nNormal prose. " * 20, encoding="utf-8")
    env = {
        "result": json.dumps({
            "slug": "foo-clean",
            "title": "Clean",
            "body": "## Q1. test\n\nbody\n",
            "summary": "test",
            "anchor": None,
        }),
        "is_error": False,
        "usage": {"input_tokens": 10, "output_tokens": 20},
        "total_cost_usd": 0.05,
    }
    monkeypatch.setattr(subprocess, "run", _mock_llm(env))
    out = note_from_chat(vault, p, study="foo", skip_detect_check=True)
    assert not out["errors"]
    assert out["note_slug"] == "foo-clean"


def test_note_from_chat_dry_run(vault: Vault, chat_file):
    out = note_from_chat(vault, chat_file, study="foo", dry_run=True)
    assert out["detected_as_chat"]
    assert out["note_slug"] is None
    assert any("dry_run" in w for w in out["warnings"])


def test_note_from_chat_happy_no_narrative(vault: Vault, chat_file, monkeypatch):
    env = {
        "result": json.dumps({
            "slug": "foo-moment",
            "title": "モーメントの直感",
            "body": "## Q1. モーメントとは?\n\nbody\n\n## 自分用まとめ\n要点\n",
            "summary": "moment intuition",
            "anchor": None,
        }),
        "is_error": False,
        "usage": {"input_tokens": 100, "output_tokens": 200},
        "total_cost_usd": 0.10,
    }
    monkeypatch.setattr(subprocess, "run", _mock_llm(env))
    out = note_from_chat(vault, chat_file, study="foo")
    assert not out["errors"], out
    assert out["note_slug"] == "foo-moment"
    assert out["related_narrative"] is None
    assert out["anchor"] is None
    assert vault.exists("note", "foo-moment")
    page = vault.read("note", "foo-moment")
    assert page is not None
    assert page.meta["type"] == "note"
    assert page.meta["study"] == "foo"
    assert "study" in page.meta


def test_note_from_chat_with_anchor_proposal_only(vault: Vault, chat_file, monkeypatch):
    _make_narrative(vault, "foo")
    env = {
        "result": json.dumps({
            "slug": "foo-moment",
            "title": "モーメントの直感",
            "body": "body\n",
            "summary": "test",
            "anchor": {
                "narrative_slug": "foo",
                "section_header": "## 1. First section",
                "wikilink_line": "↺ 直感的補論: [[foo-moment]] — moment hook",
                "rationale": "best fit",
            },
        }),
        "is_error": False,
        "usage": {},
        "total_cost_usd": 0.10,
    }
    monkeypatch.setattr(subprocess, "run", _mock_llm(env))
    out = note_from_chat(vault, chat_file, study="foo")
    assert out["anchor"] is not None
    assert out["anchor_applied"] is False
    # Narrative should NOT have been patched
    page = vault.read("narrative", "foo")
    assert page is not None
    assert "[[foo-moment]]" not in page.body


def test_note_from_chat_apply_anchor(vault: Vault, chat_file, monkeypatch):
    _make_narrative(vault, "foo")
    env = {
        "result": json.dumps({
            "slug": "foo-moment",
            "title": "モーメントの直感",
            "body": "body\n",
            "summary": "test",
            "anchor": {
                "narrative_slug": "foo",
                "section_header": "## 1. First section",
                "wikilink_line": "↺ 直感的補論: [[foo-moment]] — moment hook",
                "rationale": "best fit",
            },
        }),
        "is_error": False,
        "usage": {},
        "total_cost_usd": 0.10,
    }
    monkeypatch.setattr(subprocess, "run", _mock_llm(env))
    out = note_from_chat(vault, chat_file, study="foo", apply_anchor=True)
    assert out["anchor_applied"] is True
    page = vault.read("narrative", "foo")
    assert page is not None
    assert "[[foo-moment]]" in page.body


def test_note_from_chat_no_anchor_flag_strips_anchor(vault: Vault, chat_file, monkeypatch):
    _make_narrative(vault, "foo")
    env = {
        "result": json.dumps({
            "slug": "foo-moment",
            "title": "T",
            "body": "body\n",
            "summary": "x",
            "anchor": {
                "narrative_slug": "foo",
                "section_header": "## 1. First section",
                "wikilink_line": "↺ ...: [[foo-moment]]",
                "rationale": "x",
            },
        }),
        "is_error": False,
        "usage": {},
        "total_cost_usd": 0.05,
    }
    monkeypatch.setattr(subprocess, "run", _mock_llm(env))
    out = note_from_chat(vault, chat_file, study="foo", no_anchor=True, apply_anchor=True)
    assert out["anchor"] is None
    assert out["anchor_applied"] is False


def test_note_from_chat_slug_conflict(vault: Vault, chat_file, monkeypatch):
    # Pre-existing note with the same slug
    existing = Page(
        kind="note",
        slug="foo-moment",
        meta={"type": "note", "slug": "foo-moment", "title": "x", "study": "foo"},
        body="existing\n",
    )
    vault.write(existing)
    env = {
        "result": json.dumps({
            "slug": "foo-moment",
            "title": "T",
            "body": "body\n",
            "summary": "x",
            "anchor": None,
        }),
        "is_error": False,
        "usage": {},
        "total_cost_usd": 0.05,
    }
    monkeypatch.setattr(subprocess, "run", _mock_llm(env))
    out = note_from_chat(vault, chat_file, study="foo")
    assert out["errors"]
    assert "conflict" in out["errors"][0]


def test_note_from_chat_llm_error(vault: Vault, chat_file, monkeypatch):
    def fake_run(*a, **kw):
        class Fake:
            returncode = 1
            stdout = ""
            stderr = "boom"
        return Fake()
    monkeypatch.setattr(subprocess, "run", fake_run)
    out = note_from_chat(vault, chat_file, study="foo")
    assert out["errors"]
    assert "LLM error" in out["errors"][0]


def test_note_from_chat_missing_required_field(vault: Vault, chat_file, monkeypatch):
    env = {
        "result": json.dumps({"title": "only title"}),
        "is_error": False,
        "usage": {},
        "total_cost_usd": 0.01,
    }
    monkeypatch.setattr(subprocess, "run", _mock_llm(env))
    out = note_from_chat(vault, chat_file, study="foo")
    assert out["errors"]
    assert "missing required" in out["errors"][0]
