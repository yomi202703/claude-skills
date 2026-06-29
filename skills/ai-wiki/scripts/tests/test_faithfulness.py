"""Tests for faithfulness.py (offline, subprocess mocked).

The headline test the old mock-everything suite could never express: a tree
containing a deliberately synthesized causal edge must be FLAGGED by the
faithfulness pass. Generation mocks always returned a 'valid' body, so a
fabricated-edge regression was invisible. Here we assert it is caught.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import faithfulness  # noqa: E402
import narrative  # noqa: E402
import pytest  # noqa: E402
from narrative_draft import narrative_draft  # noqa: E402
from vault import Vault  # noqa: E402


@pytest.fixture
def vault(tmp_path) -> Vault:
    return Vault(root=tmp_path / "ai-wiki")


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


# Body with a known set of nodes: 1 fact ([?]), 1 fact ([★]), 1 edge (⟳ transition).
TREE_BODY = """イントロ。

## 記法

```
[?] 問題
```

## ROOT

```
[?] 根本問題: A という障害
```

## 1. 解

```
[★] 採用: B という解
```

⟳ **だから次の問題**: B は C を招く

## 未配送
(空)
"""


# ---------- extract_claims ----------


def test_extract_claims_classifies_edges_and_facts():
    claims = faithfulness.extract_claims(TREE_BODY)
    # legend (## 記法) is skipped; we expect the 3 content nodes
    assert len(claims) == 3
    edge = [c for c in claims if c.kind == "edge"]
    fact = [c for c in claims if c.kind == "fact"]
    assert len(edge) == 1            # the ⟳ transition
    assert len(fact) == 2            # the [?] root and [★] solution
    assert "C を招く" in edge[0].claim


def test_extract_claims_treats_inline_arrow_as_edge():
    body = "## ROOT\n\n```\n[★] X → Y を解く\n```\n"
    claims = faithfulness.extract_claims(body)
    assert claims and claims[0].kind == "edge"  # contains →


# ---------- judge_claims ----------


def test_judge_claims_maps_verdicts_in_order(vault, monkeypatch):
    claims = faithfulness.extract_claims(TREE_BODY)
    verdicts = [
        {"verdict": "supported", "evidence": "A という障害"},
        {"verdict": "unsupported", "evidence": ""},
        {"verdict": "source_silent", "evidence": ""},
    ]
    env = {"result": json.dumps(verdicts), "is_error": False, "usage": {}, "total_cost_usd": 0.05}
    monkeypatch.setattr(subprocess, "run", _mock_llm_sequence(env))

    out, cost, judge_ok = faithfulness.judge_claims(vault, "s", claims, "source text", judge_model="sonnet")
    assert [c.verdict for c in out] == ["supported", "unsupported", "source_silent"]
    assert cost == 0.05
    assert judge_ok is True


def test_judge_claims_failure_defaults_to_source_silent(vault, monkeypatch):
    claims = faithfulness.extract_claims(TREE_BODY)
    env = {"result": "not json", "is_error": False, "usage": {}, "total_cost_usd": 0.01}
    monkeypatch.setattr(subprocess, "run", _mock_llm_sequence(env))
    out, _, judge_ok = faithfulness.judge_claims(vault, "s", claims, "src")
    # On judge failure, nothing is claimed 'supported' and judge_ok flags the outage
    assert all(c.verdict == "source_silent" for c in out)
    assert all(c.errored for c in out)
    assert judge_ok is False


# ---------- judge_claims batching (300s-timeout cure) ----------


def _fact_claims(n: int):
    return [faithfulness.ClaimVerdict(claim=f"claim {i}", kind="fact", symbol="?",
                                      section="ROOT", verdict="source_silent") for i in range(n)]


def _verdicts_env(n: int, verdict: str = "supported", cost: float = 0.05):
    return {"result": json.dumps([{"verdict": verdict, "evidence": "e"} for _ in range(n)]),
            "is_error": False, "usage": {}, "total_cost_usd": cost}


def test_judge_claims_splits_into_batches(vault, monkeypatch):
    # A large claim set judged in one call is what hit the 300s timeout; it must
    # now be split across calls, concatenated in order.
    bs = faithfulness.FAITHFULNESS_BATCH_SIZE
    claims = _fact_claims(bs + 5)
    calls = {"n": 0}
    base = _mock_llm_sequence(_verdicts_env(bs, "supported", 0.05), _verdicts_env(5, "supported", 0.02))

    def counting(*a, **k):
        calls["n"] += 1
        return base(*a, **k)
    monkeypatch.setattr(subprocess, "run", counting)

    out, cost, judge_ok = faithfulness.judge_claims(vault, "s", claims, "src")
    assert len(out) == bs + 5
    assert all(c.verdict == "supported" and not c.errored for c in out)
    assert calls["n"] == 2
    assert judge_ok is True
    assert cost == pytest.approx(0.07)


def test_judge_claims_one_failed_batch_errors_only_its_slice(vault, monkeypatch):
    # A slow/failed batch errors only its own claims; the rest still get verdicts.
    bs = faithfulness.FAITHFULNESS_BATCH_SIZE
    claims = _fact_claims(bs + 5)
    bad = {"result": "not json", "is_error": False, "usage": {}, "total_cost_usd": 0.01}
    monkeypatch.setattr(subprocess, "run", _mock_llm_sequence(_verdicts_env(bs, "supported", 0.05), bad))

    out, _, judge_ok = faithfulness.judge_claims(vault, "s", claims, "src")
    assert all(c.verdict == "supported" and not c.errored for c in out[:bs])
    assert all(c.errored for c in out[bs:])
    assert judge_ok is False  # at least one claim errored


def test_run_minority_batch_failure_reports_partial_precision(vault, monkeypatch):
    # Errored claims are excluded from the precision denominator: a single failed
    # batch (minority) yields a real partial number, not N/A and not a false 100%.
    bs = faithfulness.FAITHFULNESS_BATCH_SIZE
    n_extra = 4  # total bs+1+4 facts → errored ratio stays < 0.5
    body = "## ROOT\n\n```\n[?] root\n```\n" + "".join(
        f"## S{i}\n\n```\n[★] fact {i}\n```\n" for i in range(bs + n_extra)
    )
    claims = faithfulness.extract_claims(body)
    assert len(claims) > bs  # forces ≥2 batches, all facts (no edges → no soundness call)
    # batch1 (bs claims) all supported; batch2 (remainder) fails.
    monkeypatch.setattr(subprocess, "run",
                        _mock_llm_sequence(_verdicts_env(bs, "supported", 0.05),
                                           {"result": "not json", "is_error": False, "usage": {}, "total_cost_usd": 0.01}))
    rep = faithfulness.run(vault, "s", body, "src", judge_model="sonnet")
    assert rep["judge_failed"] is False          # minority errored → still usable
    assert rep["errored"] == len(claims) - bs
    assert rep["fact_faithfulness_pct"] == 100.0  # over evaluated facts only
    assert rep["fact_faithfulness_pct"] is not None


# ---------- run() aggregation + report ----------


def test_run_aggregates_and_writes_report(vault, monkeypatch):
    verdicts = [
        {"verdict": "supported", "evidence": "A という障害"},
        {"verdict": "unsupported", "evidence": ""},
        {"verdict": "source_silent", "evidence": ""},
    ]
    env = {"result": json.dumps(verdicts), "is_error": False, "usage": {}, "total_cost_usd": 0.05}
    # the 1 source_silent edge is then put through the soundness pass
    soundness = {
        "result": json.dumps([{"i": 0, "verdict": "unsound", "reason": "B から C は follow しない"}]),
        "is_error": False, "usage": {}, "total_cost_usd": 0.03,
    }
    monkeypatch.setattr(subprocess, "run", _mock_llm_sequence(env, soundness))

    rep = faithfulness.run(vault, "slugX", TREE_BODY, "A という障害がある。", judge_model="sonnet")
    assert rep["total"] == 3
    assert rep["supported"] == 1
    assert rep["unsupported"] == 1
    assert rep["source_silent"] == 1
    assert rep["faithfulness_pct"] == pytest.approx(33.3, abs=0.1)
    assert rep["edge_source_silent"] == 1   # the ⟳ edge was synthesized
    # soundness pass judged that synthesized edge
    assert rep["soundness_total"] == 1
    assert rep["soundness_unsound"] == 1
    # report file exists and names the synthesized edge + the soundness verdict
    path = vault.root / rep["report_path"]
    assert path.exists()
    text = path.read_text("utf-8")
    assert "source_silent" in text
    assert "spine 健全性" in text and "unsound" in text


def test_run_judge_failure_reports_na_not_false_pass(vault, monkeypatch):
    # When the claim judge call fails, every claim defaults to source_silent,
    # which would naively read as 100% fact precision (no contradictions — because
    # none were checked). run() must instead report judge_failed + None pcts.
    bad = {"result": "not json", "is_error": False, "usage": {}, "total_cost_usd": 0.01}
    # soundness call (2nd) succeeds, proving the two are independent.
    soundness = {
        "result": json.dumps([{"i": 0, "verdict": "sound", "reason": "ok"}]),
        "is_error": False, "usage": {}, "total_cost_usd": 0.02,
    }
    monkeypatch.setattr(subprocess, "run", _mock_llm_sequence(bad, soundness))

    rep = faithfulness.run(vault, "slugY", TREE_BODY, "src text", judge_model="sonnet")
    assert rep["judge_failed"] is True
    assert rep["faithfulness_pct"] is None
    assert rep["fact_faithfulness_pct"] is None        # NOT 100.0
    # soundness was a separate call and still produced a real verdict
    assert rep["soundness_total"] == 1
    assert rep["soundness_sound"] == 1
    text = (vault.root / rep["report_path"]).read_text("utf-8")
    assert "判定不能" in text and "N/A" in text


# ---------- annotate_inferred ----------


def _items(*specs):
    # specs: (claim, kind, verdict)
    return [{"claim": c, "kind": k, "verdict": v} for c, k, v in specs]


def test_annotate_marks_only_flagged_edges():
    items = _items(
        ("⟳ **だから次の問題**: B は C を招く", "edge", "source_silent"),
        ("根本問題: A という障害", "fact", "supported"),          # fact: untouched
    )
    new_body, n = faithfulness.annotate_inferred(TREE_BODY, items)
    assert n == 1
    # the flagged transition line gained a trailing [~]
    line = next(l for l in new_body.splitlines() if l.startswith("⟳"))
    assert line.endswith("[~]")
    # the resulting body still validates (no undefined symbols, ROOT present)
    assert narrative.detect_undefined_symbols(new_body) == []


def test_annotate_is_idempotent():
    items = _items(("⟳ **だから次の問題**: B は C を招く", "edge", "source_silent"))
    once, n1 = faithfulness.annotate_inferred(TREE_BODY, items)
    twice, n2 = faithfulness.annotate_inferred(once, items)
    assert n1 == 1 and n2 == 0      # second pass marks nothing
    assert once == twice


def test_annotate_skips_supported_edges():
    items = _items(("⟳ **だから次の問題**: B は C を招く", "edge", "supported"))
    new_body, n = faithfulness.annotate_inferred(TREE_BODY, items)
    assert n == 0                   # supported edges are not marked


# ---------- [~] symbol now validates ----------


def test_inferred_edge_symbol_is_in_dictionary():
    assert "~" in narrative.FIXED_BRACKETED_SYMBOLS
    body = "## ROOT\n\n```\n[?] x\n```\n\n## 1. s\n\n```\n[~] 推論エッジ: 多分こう\n```\n"
    assert narrative.detect_undefined_symbols(body) == []  # no longer 'undefined'


# ---------- integration: the adversarial regression test ----------


def test_narrative_draft_faithfulness_flags_synthesized_edge(vault, tmp_path, monkeypatch):
    src = tmp_path / "foo.md"
    src.write_text("# Foo\n\nA という障害がある。B という解を採用する。\n", encoding="utf-8")

    gen = {"result": TREE_BODY, "is_error": False, "usage": {}, "total_cost_usd": 0.15}
    cove = {"result": "NO_CORRECTIONS_NEEDED", "is_error": False, "usage": {}, "total_cost_usd": 0.02}
    # faithfulness judge: root supported, solution supported, edge synthesized
    judge = {
        "result": json.dumps([
            {"verdict": "supported", "evidence": "A という障害がある"},
            {"verdict": "supported", "evidence": "B という解を採用する"},
            {"verdict": "source_silent", "evidence": ""},
        ]),
        "is_error": False, "usage": {}, "total_cost_usd": 0.04,
    }
    # soundness pass over the 1 synthesized edge
    soundness = {
        "result": json.dumps([{"i": 0, "verdict": "dubious", "reason": "因果の飛躍がある"}]),
        "is_error": False, "usage": {}, "total_cost_usd": 0.03,
    }
    # single strategy, coverage off: gen → cove → faithfulness judge → soundness
    monkeypatch.setattr(subprocess, "run", _mock_llm_sequence(gen, cove, judge, soundness))

    out = narrative_draft(
        vault, src, run_coverage=False, run_faithfulness=True, judge_model="sonnet",
    )
    assert out["narratives_written"] == ["foo"]
    assert len(out["faithfulness"]) == 1
    fr = out["faithfulness"][0]
    assert fr["edge_source_silent"] == 1            # synthesized edge caught
    assert fr["unsupported"] == 0                    # no fabricated facts
    assert fr["fact_faithfulness_pct"] == 100.0      # both facts supported
    assert fr["soundness_total"] == 1               # the edge went through soundness
    assert fr["soundness_dubious"] == 1
    assert any("synthesized spine edge" in w for w in out["warnings"])
