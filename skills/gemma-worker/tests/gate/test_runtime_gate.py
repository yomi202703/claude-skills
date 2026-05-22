from __future__ import annotations

import pytest

from gemma_worker.gate.runtime_gate import compute_metrics, to_verdict


def test_compute_metrics_empty():
    m = compute_metrics(artifacts=[], spans=[], elapsed_ms_per_iter=[], audit_layer_2=[])
    assert m["task_success"] == 0.0
    assert m["evidence_coverage"] == 0.0
    assert m["p95_latency_ms"] == 0


def test_compute_metrics_with_artifacts():
    m = compute_metrics(
        artifacts=[{"file": "a", "evidence": "x"}, {"file": "b", "evidence": "y"}],
        spans=[{"attributes": {"gen_ai.response.finish_reason": "stop"}}],
        elapsed_ms_per_iter=[100, 200, 300],
        audit_layer_2=[],
    )
    assert m["task_success"] == 1.0
    assert m["evidence_coverage"] == 1.0
    assert m["safety_pass_rate"] == 1.0
    assert m["context_preservation"] == 1.0


def test_compute_metrics_safety_failure():
    m = compute_metrics(
        artifacts=[{"file": "a", "evidence": "x"}],
        spans=[
            {"attributes": {"gen_ai.response.finish_reason": "stop"}},
            {"attributes": {"gen_ai.response.finish_reason": "content_filter"}},
        ],
        elapsed_ms_per_iter=[100],
        audit_layer_2=[],
    )
    assert m["safety_pass_rate"] == 0.5


def test_compute_metrics_context_truncation():
    m = compute_metrics(
        artifacts=[{"file": "a", "evidence": "x"}],
        spans=[
            {"attributes": {"gen_ai.response.finish_reason": "length"}},
            {"attributes": {"gen_ai.response.finish_reason": "stop"}},
        ],
        elapsed_ms_per_iter=[100],
        audit_layer_2=[],
    )
    assert m["context_preservation"] == 0.5


def test_compute_metrics_audit_violations():
    m = compute_metrics(
        artifacts=[],
        spans=[],
        elapsed_ms_per_iter=[],
        audit_layer_2=[
            {"axis": 5, "severity": "high"},
            {"axis": 5, "severity": "low"},
            {"axis": 6, "severity": "medium"},
        ],
    )
    assert m["axis_05_violations"] == 2
    assert m["axis_06_violations"] == 1


@pytest.mark.parametrize(
    "metrics,expected",
    [
        (
            {"task_success": 0.85, "context_preservation": 0.95, "p95_latency_ms": 10000,
             "safety_pass_rate": 0.98, "evidence_coverage": 0.90,
             "axis_05_violations": 0, "axis_06_violations": 0},
            "PROMOTE",
        ),
        (
            {"task_success": 0.70, "context_preservation": 0.95, "p95_latency_ms": 10000,
             "safety_pass_rate": 0.98, "evidence_coverage": 0.90,
             "axis_05_violations": 0, "axis_06_violations": 0},
            "HOLD",
        ),
        (
            {"task_success": 0.30, "context_preservation": 0.95, "p95_latency_ms": 10000,
             "safety_pass_rate": 0.98, "evidence_coverage": 0.90,
             "axis_05_violations": 0, "axis_06_violations": 0},
            "ROLLBACK",
        ),
        (
            {"task_success": 0.95, "context_preservation": 0.95, "p95_latency_ms": 22000,
             "safety_pass_rate": 0.98, "evidence_coverage": 0.90,
             "axis_05_violations": 0, "axis_06_violations": 0},
            "ROLLBACK",
        ),
        (
            {"task_success": 0.95, "context_preservation": 0.95, "p95_latency_ms": 17000,
             "safety_pass_rate": 0.98, "evidence_coverage": 0.90,
             "axis_05_violations": 0, "axis_06_violations": 0},
            "HOLD",
        ),
        (
            {"task_success": 0.95, "context_preservation": 0.95, "p95_latency_ms": 10000,
             "safety_pass_rate": 0.98, "evidence_coverage": 0.90,
             "axis_05_violations": 3, "axis_06_violations": 0},
            "ROLLBACK",
        ),
        (
            {"task_success": 0.95, "context_preservation": 0.95, "p95_latency_ms": 10000,
             "safety_pass_rate": 0.98, "evidence_coverage": 0.90,
             "axis_05_violations": 1, "axis_06_violations": 0},
            "HOLD",
        ),
        (
            {"task_success": 0.80, "context_preservation": 0.90, "p95_latency_ms": 15000,
             "safety_pass_rate": 0.95, "evidence_coverage": 0.80,
             "axis_05_violations": 0, "axis_06_violations": 0},
            "PROMOTE",
        ),
        (
            {"task_success": 0.799, "context_preservation": 0.95, "p95_latency_ms": 10000,
             "safety_pass_rate": 0.98, "evidence_coverage": 0.90,
             "axis_05_violations": 0, "axis_06_violations": 0},
            "HOLD",
        ),
    ],
)
def test_to_verdict_dimensions(metrics, expected):
    assert to_verdict(metrics) == expected


def test_to_verdict_empty_metrics():
    assert to_verdict({}) == "HOLD"
