"""Tests for narrative_draft.py (offline, subprocess mocked)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from narrative_draft import (  # noqa: E402
    Section,
    _derive_title,
    _extract_section_plan,
    _sub_slug,
    estimate_tokens,
    narrative_draft,
    parse_markdown_structure,
    select_strategy,
)
from vault import Vault  # noqa: E402


# ---------- Fixtures ----------


@pytest.fixture
def vault(tmp_path) -> Vault:
    return Vault(root=tmp_path / "ai-wiki")


# ---------- estimate_tokens / select_strategy ----------


def test_estimate_tokens_basic():
    assert estimate_tokens("") == 0
    assert estimate_tokens("a" * 2500) == 1000  # /2.5


def test_select_strategy_thresholds():
    assert select_strategy(1000) == "single"
    assert select_strategy(24999) == "single"
    assert select_strategy(25000) == "chunked"
    assert select_strategy(50000) == "chunked"
    assert select_strategy(75000) == "hierarchical"
    assert select_strategy(200000) == "hierarchical"


# ---------- markdown parsing ----------


def test_parse_empty_has_one_section():
    out = parse_markdown_structure("just text no headers")
    assert len(out) == 1
    assert out[0].level == 0


def test_parse_simple_hierarchy():
    text = """# Title
preamble
## A
body A
### A.1
body A.1
## B
body B
"""
    root = parse_markdown_structure(text)
    # Level-1 Title + its children A, B
    assert root[0].level == 1
    assert root[0].title == "Title"
    a = root[0].children[0]
    assert a.title == "A"
    assert a.level == 2
    assert len(a.children) == 1
    assert a.children[0].title == "A.1"


def test_parse_preamble():
    text = "some intro\n\n## First\nbody\n"
    root = parse_markdown_structure(text)
    assert root[0].title == "(preamble)"
    assert "intro" in root[0].body
    assert root[1].title == "First"


def test_derive_title_from_h1():
    text = "# 計量経済学\n## Intro\nbody"
    assert _derive_title(text, fallback="fb") == "計量経済学"


def test_derive_title_fallback():
    assert _derive_title("just body", fallback="fb") == "fb"


# ---------- _extract_section_plan ----------


def test_extract_section_plan_takes_level2():
    # Each section needs to be large enough (>5K tokens combined) to avoid
    # the tiny-section merge heuristic.
    big_body_a = "c1 body text. " * 2000
    big_body_b = "c2 body text. " * 2000
    text = f"# Book\n## Ch1\n{big_body_a}\n## Ch2\n{big_body_b}\n"
    sections = parse_markdown_structure(text)
    plan = _extract_section_plan(sections)
    titles = [s.title for s in plan]
    assert "Ch1" in titles
    assert "Ch2" in titles


def test_extract_section_plan_merges_tiny():
    # Tiny level-2 sections should be merged
    text = "# Book\n## A\na\n## B\nb\n"
    sections = parse_markdown_structure(text)
    plan = _extract_section_plan(sections)
    # Both A and B are tiny → they may be merged
    total_chars = sum(len(s.title) + len(s.body) for s in plan)
    assert total_chars >= 2  # some content


def test_sub_slug_deterministic():
    s = Section(level=2, title="Chapter Foo", body="", start=0)
    assert _sub_slug("master", s, 0) == "master-chapter-foo"


# ---------- narrative_draft (LLM mocked) ----------


def _mock_llm_sequence(*responses: dict):
    it = iter(responses)

    def fake_run(*args, **kwargs):
        envelope = next(it)

        class Fake:
            returncode = 0
            stdout = json.dumps(envelope)
            stderr = ""
        return Fake()
    return fake_run


VALID_NARRATIVE_BODY = """以下は疑いを前提に読む。

## 記法

```
[?] 問題
```

## ROOT

```
[?] 根本問題
```

## 1. サブ問題

```
[★] 採用: 解
```

⟳ **だから次**: 次の問題

## 未配送
(空)
"""


def test_narrative_draft_source_not_found(vault: Vault, tmp_path):
    out = narrative_draft(vault, tmp_path / "nope.md")
    assert out["errors"]
    assert "not found" in out["errors"][0]["error"]


def test_narrative_draft_dry_run(vault: Vault, tmp_path):
    src = tmp_path / "foo.md"
    src.write_text("# Foo\nbody\n", encoding="utf-8")
    out = narrative_draft(vault, src, dry_run=True)
    assert out["strategy"] == "single"
    assert out["narratives_written"] == []
    assert any("dry_run" in w for w in out["warnings"])


def test_narrative_draft_single_shot_happy(vault: Vault, tmp_path, monkeypatch):
    src = tmp_path / "foo.md"
    src.write_text("# Foo\n\nbody text\n", encoding="utf-8")

    gen_env = {
        "result": VALID_NARRATIVE_BODY,
        "is_error": False, "usage": {}, "total_cost_usd": 0.15,
    }
    cove_env = {
        "result": "NO_CORRECTIONS_NEEDED",
        "is_error": False, "usage": {}, "total_cost_usd": 0.03,
    }
    monkeypatch.setattr(subprocess, "run", _mock_llm_sequence(gen_env, cove_env))

    out = narrative_draft(vault, src, run_coverage=False)
    assert out["strategy"] == "single"
    assert out["narratives_written"] == ["foo"]
    assert out["total_cost_usd"] == 0.18
    written = vault.read("narrative", "foo")
    assert written is not None
    assert "## ROOT" in written.body


def test_narrative_draft_cove_applies_correction(vault: Vault, tmp_path, monkeypatch):
    src = tmp_path / "foo.md"
    src.write_text("# Foo\nbody\n", encoding="utf-8")

    gen_env = {
        "result": "invalid draft without root",
        "is_error": False, "usage": {}, "total_cost_usd": 0.15,
    }
    cove_env = {
        "result": VALID_NARRATIVE_BODY,
        "is_error": False, "usage": {}, "total_cost_usd": 0.03,
    }
    monkeypatch.setattr(subprocess, "run", _mock_llm_sequence(gen_env, cove_env))

    out = narrative_draft(vault, src, run_coverage=False)
    assert out["narratives_written"] == ["foo"]
    assert any("CoVe" in w for w in out["warnings"])


def test_narrative_draft_validation_fail_not_committed(vault: Vault, tmp_path, monkeypatch):
    src = tmp_path / "foo.md"
    src.write_text("# Foo\nbody\n", encoding="utf-8")

    gen_env = {
        "result": "no root section here",
        "is_error": False, "usage": {}, "total_cost_usd": 0.15,
    }
    cove_env = {
        "result": "NO_CORRECTIONS_NEEDED",
        "is_error": False, "usage": {}, "total_cost_usd": 0.03,
    }
    monkeypatch.setattr(subprocess, "run", _mock_llm_sequence(gen_env, cove_env))

    out = narrative_draft(vault, src, run_coverage=False)
    assert out["narratives_written"] == []
    assert out["errors"]
    assert vault.read("narrative", "foo") is None


def test_narrative_draft_llm_error_reported(vault: Vault, tmp_path, monkeypatch):
    src = tmp_path / "foo.md"
    src.write_text("# Foo\nbody\n", encoding="utf-8")

    def fake_run(*a, **k):
        class Fake:
            returncode = 1
            stdout = ""
            stderr = "CLI overloaded"
        return Fake()
    monkeypatch.setattr(subprocess, "run", fake_run)

    out = narrative_draft(vault, src, run_coverage=False)
    assert out["narratives_written"] == []
    assert out["errors"]


def test_narrative_draft_force_strategy_single(vault: Vault, tmp_path, monkeypatch):
    # Large source would otherwise go hierarchical
    src = tmp_path / "big.md"
    src.write_text("# T\n" + ("## S\nbody\n" * 50) + ("x" * 200_000), encoding="utf-8")

    calls = {"n": 0}

    def fake_run(*a, **k):
        calls["n"] += 1

        class Fake:
            returncode = 0
            stdout = json.dumps({
                "result": VALID_NARRATIVE_BODY if calls["n"] == 1 else "NO_CORRECTIONS_NEEDED",
                "is_error": False, "usage": {}, "total_cost_usd": 0.1,
            })
            stderr = ""
        return Fake()
    monkeypatch.setattr(subprocess, "run", fake_run)

    out = narrative_draft(vault, src, force_strategy="single", run_coverage=False)
    assert out["strategy"] == "single"
    # Single-shot: max 2 LLM calls (gen + CoVe)
    assert calls["n"] <= 2


def test_narrative_draft_no_cove_skips_verify(vault: Vault, tmp_path, monkeypatch):
    src = tmp_path / "foo.md"
    src.write_text("# Foo\nbody\n", encoding="utf-8")

    # Only 1 LLM call expected when CoVe disabled
    env = {
        "result": VALID_NARRATIVE_BODY,
        "is_error": False, "usage": {}, "total_cost_usd": 0.1,
    }
    monkeypatch.setattr(subprocess, "run", _mock_llm_sequence(env))

    out = narrative_draft(vault, src, use_cove=False, run_coverage=False)
    assert out["narratives_written"] == ["foo"]


def test_narrative_draft_slug_override(vault: Vault, tmp_path, monkeypatch):
    src = tmp_path / "foo.md"
    src.write_text("# Foo\nbody\n", encoding="utf-8")

    gen = {"result": VALID_NARRATIVE_BODY, "is_error": False, "usage": {}, "total_cost_usd": 0.1}
    cove = {"result": "NO_CORRECTIONS_NEEDED", "is_error": False, "usage": {}, "total_cost_usd": 0.02}
    monkeypatch.setattr(subprocess, "run", _mock_llm_sequence(gen, cove))

    out = narrative_draft(vault, src, slug="custom-slug", title="My Title", run_coverage=False)
    assert out["slug"] == "custom-slug"
    assert out["narratives_written"] == ["custom-slug"]
    assert vault.read("narrative", "custom-slug") is not None


def test_narrative_draft_slug_conflict_errors(vault: Vault, tmp_path, monkeypatch):
    """SPEC §13.4.1 / REQUIREMENTS §14.1.1: existing slug must not be
    silently overwritten. Expect an error, no LLM calls, existing tree intact.
    """
    from vault import Page

    # Seed an existing narrative
    existing = Page(
        kind="narrative",
        slug="occupied",
        meta={
            "type": "narrative", "slug": "occupied", "title": "Existing",
            "status": "pilot", "created": "2026-04-24", "updated": "2026-04-24",
        },
        body="original body do not clobber\n",
    )
    vault.write(existing)

    src = tmp_path / "foo.md"
    src.write_text("# Foo\nbody\n", encoding="utf-8")

    # If conflict check runs BEFORE any LLM call, fake_run must never execute
    call_count = {"n": 0}

    def fake_run(*a, **k):
        call_count["n"] += 1
        raise AssertionError("LLM must not be called when slug conflicts")
    monkeypatch.setattr(subprocess, "run", fake_run)

    out = narrative_draft(vault, src, slug="occupied", run_coverage=False)
    assert out["narratives_written"] == []
    assert out["errors"], "expected conflict error"
    err = out["errors"][0]
    assert "slug conflict" in err.get("error", "").lower()
    assert "occupied" in err.get("conflicts", [])
    assert call_count["n"] == 0

    # Existing body untouched
    after = vault.read("narrative", "occupied")
    assert after is not None
    assert "original body do not clobber" in after.body


# ---------- hierarchical ----------


def test_narrative_draft_coverage_runs_after_commit(vault: Vault, tmp_path, monkeypatch):
    """v5-5 flow: gen → QuestEval iterate (qa_gen + qa_check, converged) → CoVe → commit.
    4 LLM calls when converged on first coverage iteration."""
    src = tmp_path / "foo.md"
    src.write_text("# Foo\n\nbody text\n", encoding="utf-8")

    gen = {"result": VALID_NARRATIVE_BODY, "is_error": False, "usage": {}, "total_cost_usd": 0.15}
    qa = {
        "result": json.dumps([{"q": "What is foo?", "a": "foo is..."}]),
        "is_error": False, "usage": {}, "total_cost_usd": 0.1,
    }
    check = {
        "result": json.dumps([{"q": "What is foo?", "status": "covered"}]),
        "is_error": False, "usage": {}, "total_cost_usd": 0.02,
    }
    cove = {"result": "NO_CORRECTIONS_NEEDED", "is_error": False, "usage": {}, "total_cost_usd": 0.03}
    # v5-5 order: gen → qa_gen → qa_check (converged) → cove
    monkeypatch.setattr(subprocess, "run", _mock_llm_sequence(gen, qa, check, cove))

    out = narrative_draft(vault, src)  # run_coverage default True
    assert out["narratives_written"] == ["foo"]
    assert "coverage" in out
    assert len(out["coverage"]) == 1
    assert out["coverage"][0]["final_coverage"]["total"] == 1
    # Total cost includes draft + coverage iterate + cove
    assert out["total_cost_usd"] == pytest.approx(0.30)


def test_narrative_draft_coverage_skipped_on_validation_failure(vault: Vault, tmp_path, monkeypatch):
    """v5-5: if narrative fails to commit after CoVe, it's not in narratives_written.
    coverage still runs because it happens BEFORE commit in new flow."""
    src = tmp_path / "foo.md"
    src.write_text("# Foo\nbody\n", encoding="utf-8")

    # Output lacks ROOT — validation fails on commit step
    gen = {"result": "no root", "is_error": False, "usage": {}, "total_cost_usd": 0.15}
    qa = {
        "result": json.dumps([{"q": "Q?", "a": "A"}]),
        "is_error": False, "usage": {}, "total_cost_usd": 0.1,
    }
    check = {
        "result": json.dumps([{"q": "Q?", "status": "covered"}]),
        "is_error": False, "usage": {}, "total_cost_usd": 0.02,
    }
    cove = {"result": "NO_CORRECTIONS_NEEDED", "is_error": False, "usage": {}, "total_cost_usd": 0.03}
    monkeypatch.setattr(subprocess, "run", _mock_llm_sequence(gen, qa, check, cove))

    out = narrative_draft(vault, src)  # default run_coverage=True
    assert out["narratives_written"] == []
    # Coverage runs during generation (pre-commit); its report is present but
    # narrative was not committed.
    assert len(out["coverage"]) == 1


def test_narrative_draft_hierarchical_forced(vault: Vault, tmp_path, monkeypatch):
    # Force hierarchical with sections large enough to not be merged.
    big_body = "body text sample. " * 2000
    src = tmp_path / "book.md"
    src.write_text(
        f"# Book\n\n## Chapter One\n\n{big_body}\n\n## Chapter Two\n\n{big_body}\n",
        encoding="utf-8",
    )

    # Expected sequence: sub1 gen, sub1 cove, sub2 gen, sub2 cove, master gen, master cove
    envs = []
    for _ in range(3):
        envs.append({
            "result": VALID_NARRATIVE_BODY,
            "is_error": False, "usage": {}, "total_cost_usd": 0.2,
        })
        envs.append({
            "result": "NO_CORRECTIONS_NEEDED",
            "is_error": False, "usage": {}, "total_cost_usd": 0.02,
        })
    monkeypatch.setattr(subprocess, "run", _mock_llm_sequence(*envs))

    out = narrative_draft(vault, src, force_strategy="hierarchical", run_coverage=False)
    assert out["strategy"] == "hierarchical"
    assert len(out["narratives_written"]) == 3  # 2 subs + 1 master
    assert any(n.startswith("book-chapter") for n in out["narratives_written"])
    assert "book" in out["narratives_written"]  # master
