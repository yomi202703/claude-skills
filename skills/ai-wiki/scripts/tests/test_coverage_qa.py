"""Tests for coverage_qa.py (offline, subprocess mocked)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from coverage_qa import (  # noqa: E402
    DEFAULT_JUDGE_MODEL,
    CoverageStatus,
    QAItem,
    check_coverage,
    gap_report_path,
    generate_qa_set,
    iterate_and_fix,
    load_qa_set,
    qa_set_path,
    run_coverage,
    save_qa_set,
    write_gap_report,
    CoverageReport,
)
from vault import Page, Vault  # noqa: E402


# ---------- Fixtures ----------


@pytest.fixture
def vault(tmp_path) -> Vault:
    return Vault(root=tmp_path / "ai-wiki")


def _seed_narrative(vault: Vault, slug: str, body: str, title: str = "Test Title") -> None:
    meta = {
        "type": "narrative",
        "slug": slug,
        "title": title,
        "status": "pilot",
        "created": "2026-04-23",
        "updated": "2026-04-23",
    }
    vault.write(Page(kind="narrative", slug=slug, meta=meta, body=body))


def _mock_sequence(*responses: dict):
    it = iter(responses)

    def fake_run(*args, **kwargs):
        envelope = next(it)
        class Fake:
            returncode = 0
            stdout = json.dumps(envelope)
            stderr = ""
        return Fake()
    return fake_run


# ---------- QA save/load ----------


def test_save_and_load_qa_set(vault: Vault):
    items = [QAItem(q="Q1?", a="A1."), QAItem(q="Q2?", a="A2.")]
    save_qa_set(vault, "demo", items)
    loaded = load_qa_set(vault, "demo")
    assert len(loaded) == 2
    assert loaded[0].q == "Q1?"


def test_load_qa_missing_returns_empty(vault: Vault):
    assert load_qa_set(vault, "nonexistent") == []


def test_qa_set_path_under_hidden_dir(vault: Vault):
    p = qa_set_path(vault, "foo")
    assert ".narrative-qa" in str(p)


def test_gap_report_path_under_hidden_dir(vault: Vault):
    p = gap_report_path(vault, "foo")
    assert ".narrative-gaps" in str(p)


# ---------- generate_qa_set ----------


def test_generate_qa_set_parses_json_array(vault: Vault, monkeypatch):
    qa_json = json.dumps([
        {"q": "What is X?", "a": "X is foo."},
        {"q": "Why Y?", "a": "Because bar."},
    ])
    env = {
        "result": qa_json,
        "is_error": False, "usage": {}, "total_cost_usd": 0.1,
    }
    monkeypatch.setattr(subprocess, "run", _mock_sequence(env))
    items, cost = generate_qa_set(vault, "slug", "Title", "source text")
    assert len(items) == 2
    assert items[0].q == "What is X?"
    assert cost == 0.1


def test_generate_qa_set_skips_invalid_items(vault: Vault, monkeypatch):
    qa_json = json.dumps([
        {"q": "good", "a": "ok"},
        {"q": "", "a": "empty q"},
        "not a dict",
        {"q": "only q"},  # missing a
        {"q": "another", "a": "ok"},
    ])
    env = {"result": qa_json, "is_error": False, "usage": {}, "total_cost_usd": 0.1}
    monkeypatch.setattr(subprocess, "run", _mock_sequence(env))
    items, _ = generate_qa_set(vault, "slug", "t", "src")
    assert len(items) == 2


def test_generate_qa_set_llm_error(vault: Vault, monkeypatch):
    def err(*a, **k):
        class Fake:
            returncode = 1
            stdout = ""
            stderr = "boom"
        return Fake()
    monkeypatch.setattr(subprocess, "run", err)
    items, cost = generate_qa_set(vault, "slug", "t", "src")
    assert items == []


# ---------- check_coverage ----------


def test_check_coverage_happy(vault: Vault, monkeypatch):
    qa = [QAItem(q="Q1", a="A1"), QAItem(q="Q2", a="A2"), QAItem(q="Q3", a="A3")]
    judge_json = json.dumps([
        {"q": "Q1", "status": "covered", "note": ""},
        {"q": "Q2", "status": "partial", "note": "incomplete"},
        {"q": "Q3", "status": "missing", "note": "not found"},
    ])
    env = {"result": judge_json, "is_error": False, "usage": {}, "total_cost_usd": 0.05}
    monkeypatch.setattr(subprocess, "run", _mock_sequence(env))
    statuses, cost = check_coverage(vault, "slug", "narrative body", qa)
    assert len(statuses) == 3
    assert statuses[0].status == "covered"
    assert statuses[1].status == "partial"
    assert statuses[2].status == "missing"
    assert cost == 0.05


def test_check_coverage_empty_qa_shortcircuits(vault: Vault):
    # No LLM call should occur
    statuses, cost = check_coverage(vault, "slug", "body", [])
    assert statuses == []
    assert cost == 0.0


def test_check_coverage_invalid_status_defaults_missing(vault: Vault, monkeypatch):
    qa = [QAItem(q="Q1", a="A1")]
    env = {
        "result": json.dumps([{"q": "Q1", "status": "invalid_status"}]),
        "is_error": False, "usage": {}, "total_cost_usd": 0.01,
    }
    monkeypatch.setattr(subprocess, "run", _mock_sequence(env))
    statuses, _ = check_coverage(vault, "s", "body", qa)
    assert statuses[0].status == "missing"


def test_check_coverage_llm_failure_all_missing(vault: Vault, monkeypatch):
    qa = [QAItem(q="Q1", a="A1"), QAItem(q="Q2", a="A2")]

    def err(*a, **k):
        class Fake:
            returncode = 1
            stdout = ""
            stderr = "boom"
        return Fake()
    monkeypatch.setattr(subprocess, "run", err)
    statuses, _ = check_coverage(vault, "s", "body", qa)
    assert all(s.status == "missing" for s in statuses)


# ---------- write_gap_report ----------


def test_write_gap_report_creates_file(vault: Vault):
    items = [
        CoverageStatus(q="Q1 covered?", status="covered"),
        CoverageStatus(q="Q2 partial?", status="partial", note="only partly"),
        CoverageStatus(q="Q3 missing?", status="missing", note="not found"),
    ]
    report = CoverageReport(
        slug="demo",
        total=3, covered=1, partial=1, missing=1, coverage_pct=33.3,
        items=items, cost_usd=0.1,
    )
    path = write_gap_report(vault, "demo", report)
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "Q3 missing?" in content
    assert "Q2 partial?" in content
    assert "answered" not in content.lower() or "Q1" not in content  # covered items not listed


# ---------- run_coverage (full flow) ----------


def test_run_coverage_first_time_requires_source(vault: Vault):
    _seed_narrative(vault, "demo", "body")
    result = run_coverage(vault, slug="demo", source_path=None)
    assert "error" in result
    assert "source" in result["error"].lower()


def test_run_coverage_missing_narrative(vault: Vault):
    result = run_coverage(vault, slug="nope", source_path=None)
    assert "error" in result
    assert "not found" in result["error"]


def test_run_coverage_full_flow(vault: Vault, tmp_path, monkeypatch):
    _seed_narrative(vault, "demo", "narrative body with some content")

    src = tmp_path / "source.md"
    src.write_text("# Topic\n\nSome educational content.\n", encoding="utf-8")

    qa_env = {
        "result": json.dumps([
            {"q": "What is topic?", "a": "topic"},
            {"q": "Why bother?", "a": "because"},
        ]),
        "is_error": False, "usage": {}, "total_cost_usd": 0.1,
    }
    check_env = {
        "result": json.dumps([
            {"q": "What is topic?", "status": "covered"},
            {"q": "Why bother?", "status": "missing"},
        ]),
        "is_error": False, "usage": {}, "total_cost_usd": 0.05,
    }
    monkeypatch.setattr(subprocess, "run", _mock_sequence(qa_env, check_env))

    result = run_coverage(vault, slug="demo", source_path=src)
    assert result["total"] == 2
    assert result["covered"] == 1
    assert result["missing"] == 1
    assert result["coverage_pct"] == 50.0
    assert result["cost_usd"] == pytest.approx(0.15)

    # QA set was cached
    assert qa_set_path(vault, "demo").exists()
    # Gap report was written
    assert gap_report_path(vault, "demo").exists()


def test_run_coverage_uses_cached_qa(vault: Vault, monkeypatch):
    _seed_narrative(vault, "demo", "body")
    # Pre-seed QA cache
    save_qa_set(vault, "demo", [QAItem(q="cached Q", a="cached A")])

    # Only 1 LLM call expected (check only, QA gen skipped)
    check_env = {
        "result": json.dumps([{"q": "cached Q", "status": "covered"}]),
        "is_error": False, "usage": {}, "total_cost_usd": 0.03,
    }
    monkeypatch.setattr(subprocess, "run", _mock_sequence(check_env))

    result = run_coverage(vault, slug="demo", source_path=None)
    assert result["total"] == 1
    assert result["covered"] == 1


def test_run_coverage_regenerate_qa(vault: Vault, tmp_path, monkeypatch):
    _seed_narrative(vault, "demo", "body")
    save_qa_set(vault, "demo", [QAItem(q="old", a="old")])  # pre-seed cache

    src = tmp_path / "source.md"
    src.write_text("# Topic\nsource\n", encoding="utf-8")

    qa_env = {
        "result": json.dumps([{"q": "new Q", "a": "new A"}]),
        "is_error": False, "usage": {}, "total_cost_usd": 0.1,
    }
    check_env = {
        "result": json.dumps([{"q": "new Q", "status": "covered"}]),
        "is_error": False, "usage": {}, "total_cost_usd": 0.03,
    }
    monkeypatch.setattr(subprocess, "run", _mock_sequence(qa_env, check_env))

    result = run_coverage(vault, slug="demo", source_path=src, regenerate_qa=True)
    assert result["total"] == 1
    # Cache was updated
    cached = load_qa_set(vault, "demo")
    assert cached[0].q == "new Q"


# ---------- judge model separation + hold-out ----------


def _capturing_run(envelope: dict, captured: list):
    def fake_run(*args, **kwargs):
        captured.append(args[0])  # the cli argv list

        class Fake:
            returncode = 0
            stdout = json.dumps(envelope)
            stderr = ""
        return Fake()
    return fake_run


def test_check_coverage_uses_sonnet_judge_by_default(vault: Vault, monkeypatch):
    """The coverage judge must run on a DIFFERENT model from the opus generator
    (default sonnet) to dodge self-preference bias."""
    qa = [QAItem(q="Q1", a="A1")]
    env = {"result": json.dumps([{"q": "Q1", "status": "covered"}]),
           "is_error": False, "usage": {}, "total_cost_usd": 0.01}
    captured: list = []
    monkeypatch.setattr(subprocess, "run", _capturing_run(env, captured))

    check_coverage(vault, "slug", "body", qa)
    assert DEFAULT_JUDGE_MODEL == "sonnet"
    assert "--model" in captured[0]
    assert captured[0][captured[0].index("--model") + 1] == "sonnet"


def test_check_coverage_judge_model_override(vault: Vault, monkeypatch):
    qa = [QAItem(q="Q1", a="A1")]
    env = {"result": json.dumps([{"q": "Q1", "status": "covered"}]),
           "is_error": False, "usage": {}, "total_cost_usd": 0.01}
    captured: list = []
    monkeypatch.setattr(subprocess, "run", _capturing_run(env, captured))

    check_coverage(vault, "slug", "body", qa, judge_model="haiku")
    assert captured[0][captured[0].index("--model") + 1] == "haiku"


def test_iterate_and_fix_holdout_measures_on_independent_set(vault: Vault, monkeypatch):
    """Hold-out coverage is measured on a fresh QA set the fixer never saw, and
    is reported separately from the (optimized) in-sample coverage."""
    qa = {"result": json.dumps([{"q": "Q?", "a": "A"}]),
          "is_error": False, "usage": {}, "total_cost_usd": 0.1}
    check = {"result": json.dumps([{"q": "Q?", "status": "covered"}]),
             "is_error": False, "usage": {}, "total_cost_usd": 0.02}
    ho_qa = {"result": json.dumps([{"q": "Q2?", "a": "A2"}, {"q": "Q3?", "a": "A3"}]),
             "is_error": False, "usage": {}, "total_cost_usd": 0.1}
    # Hold-out: one of two covered → 50%, distinct from the 100% in-sample number.
    ho_check = {"result": json.dumps([
        {"q": "Q2?", "status": "covered"}, {"q": "Q3?", "status": "missing"}]),
        "is_error": False, "usage": {}, "total_cost_usd": 0.02}
    # Order: qa_gen → qa_check (converged) → ho_qa_gen → ho_qa_check
    monkeypatch.setattr(subprocess, "run", _mock_sequence(qa, check, ho_qa, ho_check))

    res = iterate_and_fix(
        vault, "slug", "Title", "narrative body", "source text",
        coverage_threshold=0.95, max_iterations=3,
    )
    rep = res.final_coverage
    assert rep.coverage_pct == 100.0          # in-sample (what fix optimized)
    assert rep.holdout_coverage_pct == 50.0   # honest out-of-sample
    assert rep.holdout_total == 2
    assert rep.holdout_covered == 1
    # The hold-out set is persisted separately from the training set.
    assert qa_set_path(vault, "slug", holdout=True).exists()
    assert qa_set_path(vault, "slug", holdout=True) != qa_set_path(vault, "slug")
    # Cost invariant: the nested report cost matches the returned cost.
    assert rep.cost_usd == res.cost_usd
    assert rep.cost_usd == pytest.approx(0.24)  # 0.1+0.02+0.1+0.02


def test_iterate_and_fix_holdout_disabled(vault: Vault, monkeypatch):
    """holdout=False: no hold-out set generated, no hold-out fields, no extra calls."""
    qa = {"result": json.dumps([{"q": "Q?", "a": "A"}]),
          "is_error": False, "usage": {}, "total_cost_usd": 0.1}
    check = {"result": json.dumps([{"q": "Q?", "status": "covered"}]),
             "is_error": False, "usage": {}, "total_cost_usd": 0.02}
    # Only qa_gen + qa_check — a 3rd mocked call would mean an unwanted hold-out call.
    monkeypatch.setattr(subprocess, "run", _mock_sequence(qa, check))

    res = iterate_and_fix(
        vault, "slug", "Title", "body", "source",
        coverage_threshold=0.95, max_iterations=3, holdout=False,
    )
    rep = res.final_coverage
    assert rep.coverage_pct == 100.0
    assert rep.holdout_coverage_pct is None
    assert rep.holdout_total == 0
    assert not qa_set_path(vault, "slug", holdout=True).exists()
    assert rep.cost_usd == res.cost_usd
