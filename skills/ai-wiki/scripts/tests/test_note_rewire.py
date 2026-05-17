"""Tests for note_rewire.py (offline, subprocess mocked)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from note_rewire import _gather_notes_by_study, note_rewire  # noqa: E402
from vault import Page, Vault  # noqa: E402


# ---------- _gather_notes_by_study ----------


def _add_note(vault: Vault, slug: str, study: str | None, body: str = "body\n") -> None:
    meta: dict = {"type": "note", "slug": slug, "title": slug}
    if study:
        meta["study"] = study
    vault.write(Page(kind="note", slug=slug, meta=meta, body=body))


def _add_narrative(vault: Vault, slug: str, body: str) -> None:
    vault.write(Page(
        kind="narrative",
        slug=slug,
        meta={
            "type": "narrative", "slug": slug, "title": slug, "status": "pilot",
            "created": "2026-04-30", "updated": "2026-04-30",
        },
        body=body,
    ))


def test_gather_notes_filters_by_study(vault: Vault):
    _add_note(vault, "a", study="foo")
    _add_note(vault, "b", study="bar")
    _add_note(vault, "c", study=None)  # no study field — ignored
    out = _gather_notes_by_study(vault, study_filter=None)
    assert set(out.keys()) == {"foo", "bar"}
    assert "c" not in [s for slugs in out.values() for s, _ in slugs]


def test_gather_notes_with_filter(vault: Vault):
    _add_note(vault, "a", study="foo")
    _add_note(vault, "b", study="bar")
    out = _gather_notes_by_study(vault, study_filter="foo")
    assert set(out.keys()) == {"foo"}


# ---------- note_rewire (LLM mocked) ----------


def _mock_llm(*envelopes: dict):
    it = iter(envelopes)

    def fake_run(*a, **kw):
        env = next(it)

        class Fake:
            returncode = 0
            stdout = json.dumps(env)
            stderr = ""
        return Fake()
    return fake_run


def test_rewire_no_notes(vault: Vault):
    out = note_rewire(vault)
    assert out["proposals"] == []
    assert any("no notes" in w for w in out["warnings"])


def test_rewire_skip_when_narrative_missing(vault: Vault):
    _add_note(vault, "a", study="foo")
    out = note_rewire(vault)
    assert out["proposals"] == []
    assert len(out["skipped"]) == 1
    assert "not yet built" in out["skipped"][0]["reason"]


def test_rewire_proposes_anchor_dry_run(vault: Vault, monkeypatch):
    _add_narrative(vault, "foo", "intro\n\n## 1. A\n\nbody\n")
    _add_note(vault, "foo-x", study="foo", body="note about A\n")
    env = {
        "result": json.dumps({
            "anchors": [
                {
                    "note_slug": "foo-x",
                    "narrative_slug": "foo",
                    "section_header": "## 1. A",
                    "wikilink_line": "↺ 補論: [[foo-x]] — about A",
                    "rationale": "obvious match",
                }
            ],
            "skipped": [],
        }),
        "is_error": False,
        "usage": {},
        "total_cost_usd": 0.05,
    }
    monkeypatch.setattr(subprocess, "run", _mock_llm(env))
    out = note_rewire(vault, study_filter="foo")
    assert len(out["proposals"]) == 1
    assert out["proposals"][0]["section_header"] == "## 1. A"
    assert out["applied"] == []  # dry run
    # Narrative was not modified
    page = vault.read("narrative", "foo")
    assert page is not None
    assert "[[foo-x]]" not in page.body


def test_rewire_apply_patches_narrative(vault: Vault, monkeypatch):
    _add_narrative(vault, "foo", "intro\n\n## 1. A\n\nbody\n")
    _add_note(vault, "foo-x", study="foo", body="note about A\n")
    env = {
        "result": json.dumps({
            "anchors": [
                {
                    "note_slug": "foo-x",
                    "narrative_slug": "foo",
                    "section_header": "## 1. A",
                    "wikilink_line": "↺ 補論: [[foo-x]] — about A",
                    "rationale": "match",
                }
            ],
            "skipped": [],
        }),
        "is_error": False, "usage": {}, "total_cost_usd": 0.05,
    }
    monkeypatch.setattr(subprocess, "run", _mock_llm(env))
    out = note_rewire(vault, apply=True)
    assert len(out["applied"]) == 1
    page = vault.read("narrative", "foo")
    assert page is not None
    assert "[[foo-x]]" in page.body


def test_rewire_skipped_passthrough(vault: Vault, monkeypatch):
    _add_narrative(vault, "foo", "intro\n\n## 1. A\n")
    _add_note(vault, "foo-x", study="foo")
    env = {
        "result": json.dumps({
            "anchors": [],
            "skipped": [{"note_slug": "foo-x", "reason": "no good fit"}],
        }),
        "is_error": False, "usage": {}, "total_cost_usd": 0.02,
    }
    monkeypatch.setattr(subprocess, "run", _mock_llm(env))
    out = note_rewire(vault)
    assert len(out["skipped"]) == 1
    assert out["skipped"][0]["reason"] == "no good fit"


def test_rewire_llm_error(vault: Vault, monkeypatch):
    _add_narrative(vault, "foo", "intro\n\n## 1. A\n")
    _add_note(vault, "foo-x", study="foo")

    def fake_run(*a, **kw):
        class Fake:
            returncode = 1
            stdout = ""
            stderr = "boom"
        return Fake()
    monkeypatch.setattr(subprocess, "run", fake_run)
    out = note_rewire(vault)
    assert out["errors"]
    assert "LLM error" in out["errors"][0]
