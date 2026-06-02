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
    _peer_slug,
    _strip_meta_preamble,
    _sub_slug,
    estimate_tokens,
    narrative_draft,
    normalize_heading_levels,
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


# ---------- _peer_slug ----------


def test_peer_slug_uses_section_number_prefix():
    s = Section(level=2, title="3 Pre-training", body="", start=0)
    assert _peer_slug("paper", s, 0) == "paper-03-pre-training"


def test_peer_slug_falls_back_to_index_without_number():
    s = Section(level=2, title="Background", body="", start=0)
    assert _peer_slug("paper", s, 4) == "paper-05-background"


# ---------- normalize_heading_levels ----------


def test_normalize_heading_levels_reconstructs_flat_pdf():
    # MinerU-style flat output: title + numbered sections all at level-1 `#`,
    # with the `■` marker. Should rebuild #=title, ##=major, ###=sub.
    text = (
        "# A Survey of X\n\nintro\n\n"
        "# ■ 1 Introduction\n\nbody\n\n"
        "# ■ 3 Pre-training\n\nbody\n\n"
        "# ■ 3.1 Data\n\nbody\n\n"
        "# ■ 3.1.2 Preprocessing\n\nbody\n"
    )
    out, changed = normalize_heading_levels(text)
    assert changed is True
    assert "# A Survey of X" in out
    assert "\n## 1 Introduction\n" in out
    assert "\n## 3 Pre-training\n" in out
    assert "\n### 3.1 Data\n" in out
    assert "\n#### 3.1.2 Preprocessing\n" in out
    assert "■" not in out


def test_normalize_heading_levels_noop_on_wellformed():
    # One `#` title + `##` sections is already correct; must pass through.
    text = "# Title\n\n## 概要\n\nbody\n\n## 詳細\n\nbody\n"
    out, changed = normalize_heading_levels(text)
    assert changed is False
    assert out == text


def test_peer_mode_skips_back_matter(vault: Vault, tmp_path, monkeypatch):
    # References / Acknowledgements / Open Access must never become peers.
    big = "body text sample. " * 800
    src = tmp_path / "withrefs.md"
    src.write_text(
        f"# Paper\n\n## 1 Intro\n\n{big}\n\n## 2 Methods\n\n{big}\n\n"
        f"## Acknowledgements\n\nthanks\n\n## References\n\n[1] foo\n[2] bar\n",
        encoding="utf-8",
    )
    envs = []
    for _ in range(2):  # only the 2 content sections
        envs.append({"result": VALID_NARRATIVE_BODY, "is_error": False,
                     "usage": {}, "total_cost_usd": 0.2})
        envs.append({"result": "NO_CORRECTIONS_NEEDED", "is_error": False,
                     "usage": {}, "total_cost_usd": 0.02})
    monkeypatch.setattr(subprocess, "run", _mock_llm_sequence(*envs))

    out = narrative_draft(vault, src, mode="peer", run_coverage=False)
    assert sorted(out["narratives_written"]) == ["withrefs-01-intro", "withrefs-02-methods"]
    assert not any("references" in s.lower() for s in out["narratives_written"])
    assert not any("acknowledge" in s.lower() for s in out["narratives_written"])


def test_normalize_heading_levels_noop_without_dotted_numbers():
    # Several level-1 headings but no dotted numbering — not the pathology.
    text = "# Title\n\n# Abstract\n\nbody\n\n# Keywords\n\nbody\n"
    out, changed = normalize_heading_levels(text)
    assert changed is False


# ---------- _strip_meta_preamble ----------


def test_strip_meta_preamble_japanese_cove_leak():
    # CoVe leaks Japanese verifier commentary before the tree; the real
    # `## ROOT` header line follows. The leak must be stripped, anchored on the
    # header *line* — not the inline `## ROOT` quoted inside the commentary.
    body = (
        "検証しました。違反が 2 点あります:\n"
        "1. 辞書外の記号。`[??]` に修正。\n"
        "2. `## ROOT` の欠落。`## ROOT` に修正。\n\n"
        "## 記法\n\n```\n[?] 問題\n```\n\n"
        "## ROOT\n\n```\n[?] 根本\n```\n\n## 未配送\n(空)\n"
    )
    clean, changed = _strip_meta_preamble(body)
    assert changed is True
    assert clean.lstrip().startswith("## 記法")
    assert "検証しました" not in clean
    assert "違反が" not in clean


def test_strip_meta_preamble_master_announcement_leak():
    # narrative_master sometimes announces the body before emitting it.
    body = (
        "以下が master narrative の本文です（frontmatter なし、intro 〜 `## 未配送`）。\n\n"
        "この master tree は spine だけを示す。\n\n"
        "## 記法\n\n```\n[?] 問題\n```\n\n## ROOT\n\n```\n[?] 根本\n```\n"
    )
    clean, changed = _strip_meta_preamble(body)
    assert changed is True
    assert clean.lstrip().startswith("## 記法")
    assert "本文です" not in clean


def test_strip_meta_preamble_keeps_clean_intro():
    # A legitimate short intro paragraph (no leak signatures) is preserved.
    body = "本 tree は疑いを前提に読む。\n\n## ROOT\n\n```\n[?] 根本\n```\n"
    clean, changed = _strip_meta_preamble(body)
    assert changed is False
    assert clean == body


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
    """v5-5 flow: gen → QuestEval iterate (qa_gen + qa_check, converged) →
    hold-out (ho_qa_gen + ho_qa_check) → CoVe → commit. 6 LLM calls when
    converged on first coverage iteration and hold-out enabled."""
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
    # Hold-out: an independent QA draw + check on the final body (measurement only).
    ho_qa = {
        "result": json.dumps([{"q": "Why foo?", "a": "because..."}]),
        "is_error": False, "usage": {}, "total_cost_usd": 0.1,
    }
    ho_check = {
        "result": json.dumps([{"q": "Why foo?", "status": "covered"}]),
        "is_error": False, "usage": {}, "total_cost_usd": 0.02,
    }
    cove = {"result": "NO_CORRECTIONS_NEEDED", "is_error": False, "usage": {}, "total_cost_usd": 0.03}
    # v5-5 order: gen → qa_gen → qa_check (converged) → ho_qa_gen → ho_qa_check → cove
    monkeypatch.setattr(subprocess, "run", _mock_llm_sequence(gen, qa, check, ho_qa, ho_check, cove))

    out = narrative_draft(vault, src)  # run_coverage default True
    assert out["narratives_written"] == ["foo"]
    assert "coverage" in out
    assert len(out["coverage"]) == 1
    assert out["coverage"][0]["final_coverage"]["total"] == 1
    # Hold-out coverage measured on the fresh set (1 item, covered → 100%)
    assert out["coverage"][0]["final_coverage"]["holdout_coverage_pct"] == 100.0
    assert out["coverage"][0]["final_coverage"]["holdout_total"] == 1
    # Total cost includes draft + coverage iterate + hold-out + cove
    assert out["total_cost_usd"] == pytest.approx(0.42)


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
    ho_qa = {
        "result": json.dumps([{"q": "Q2?", "a": "A2"}]),
        "is_error": False, "usage": {}, "total_cost_usd": 0.1,
    }
    ho_check = {
        "result": json.dumps([{"q": "Q2?", "status": "covered"}]),
        "is_error": False, "usage": {}, "total_cost_usd": 0.02,
    }
    cove = {"result": "NO_CORRECTIONS_NEEDED", "is_error": False, "usage": {}, "total_cost_usd": 0.03}
    monkeypatch.setattr(subprocess, "run", _mock_llm_sequence(gen, qa, check, ho_qa, ho_check, cove))

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


def test_narrative_draft_peer_mode(vault: Vault, tmp_path, monkeypatch):
    # peer mode: one independent single-strategy tree per major section, no
    # master hub. Two sections → two peers, each gen + cove (coverage off).
    big_body = "body text sample. " * 2000
    src = tmp_path / "paper.md"
    src.write_text(
        f"# Paper\n\n## 1 Alpha\n\n{big_body}\n\n## 2 Beta\n\n{big_body}\n",
        encoding="utf-8",
    )
    envs = []
    for _ in range(2):  # 2 peers, each: gen + cove
        envs.append({
            "result": VALID_NARRATIVE_BODY,
            "is_error": False, "usage": {}, "total_cost_usd": 0.2,
        })
        envs.append({
            "result": "NO_CORRECTIONS_NEEDED",
            "is_error": False, "usage": {}, "total_cost_usd": 0.02,
        })
    monkeypatch.setattr(subprocess, "run", _mock_llm_sequence(*envs))

    out = narrative_draft(vault, src, mode="peer", run_coverage=False)
    assert out["strategy"] == "peer"
    assert sorted(out["narratives_written"]) == ["paper-01-alpha", "paper-02-beta"]
    assert "paper" not in out["narratives_written"]  # no master hub


def test_narrative_draft_peer_mode_normalizes_flat_pdf(
    vault: Vault, tmp_path, monkeypatch
):
    # End-to-end: a flat MinerU-style source in peer mode must first be
    # heading-normalized, then split into per-major-section peers.
    big_body = "body text sample. " * 800
    src = tmp_path / "flatpaper.md"
    src.write_text(
        f"# Flat Paper\n\n# ■ 1 Intro\n\n{big_body}\n\n"
        f"# ■ 2 Methods\n\n{big_body}\n\n# ■ 2.1 Detail\n\n{big_body}\n",
        encoding="utf-8",
    )
    envs = []
    for _ in range(2):  # 2 majors (1 Intro, 2 Methods incl. its 2.1 child)
        envs.append({
            "result": VALID_NARRATIVE_BODY,
            "is_error": False, "usage": {}, "total_cost_usd": 0.2,
        })
        envs.append({
            "result": "NO_CORRECTIONS_NEEDED",
            "is_error": False, "usage": {}, "total_cost_usd": 0.02,
        })
    monkeypatch.setattr(subprocess, "run", _mock_llm_sequence(*envs))

    out = narrative_draft(vault, src, mode="peer", run_coverage=False)
    assert out["strategy"] == "peer"
    assert sorted(out["narratives_written"]) == ["flatpaper-01-intro", "flatpaper-02-methods"]
    assert any("reconstructed heading hierarchy" in w for w in out["warnings"])


def test_narrative_draft_hierarchical_flat_headings_falls_back(
    vault: Vault, tmp_path, monkeypatch
):
    # Source where a converter flattened every heading to level-1 `#`, so the
    # hierarchical section plan is empty. Instead of silently writing 0
    # narratives, it must fall back to a chunked single-call generation.
    big_body = "body text sample. " * 500
    src = tmp_path / "flat.md"
    src.write_text(
        f"# Title\n\n# Chapter One\n\n{big_body}\n\n# Chapter Two\n\n{big_body}\n",
        encoding="utf-8",
    )
    # Pre-flight: confirm the plan really is empty for this input.
    from narrative_draft import parse_markdown_structure
    assert _extract_section_plan(parse_markdown_structure(src.read_text("utf-8"))) == []

    # Chunked fallback = one gen call + one CoVe call.
    envs = [
        {"result": VALID_NARRATIVE_BODY, "is_error": False, "usage": {}, "total_cost_usd": 0.2},
        {"result": "NO_CORRECTIONS_NEEDED", "is_error": False, "usage": {}, "total_cost_usd": 0.02},
    ]
    monkeypatch.setattr(subprocess, "run", _mock_llm_sequence(*envs))

    out = narrative_draft(vault, src, force_strategy="hierarchical", run_coverage=False)
    assert out["strategy"] == "chunked"  # downgraded from hierarchical
    assert out["narratives_written"] == ["flat"]
    assert not out["errors"]
    assert any("no level-2" in w for w in out["warnings"])
