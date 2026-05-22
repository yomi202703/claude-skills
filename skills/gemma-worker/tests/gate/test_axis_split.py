from __future__ import annotations

from gemma_worker.gate.runtime_gate import (
    axis_breakdown,
    compute_metrics,
    split_findings_and_escalations,
)


def _artifact(axis: str, evidence: str = "ev") -> dict:
    return {"playbook": "deadcode", "axis": axis, "file": "x.py", "line": 1,
            "evidence": evidence, "severity": "low", "why": "..."}


def test_split_separates_escalations():
    artifacts = [
        _artifact("axis-01-unused-export"),
        _artifact("escalation"),
        _artifact("tool:vulture"),
        _artifact("tool_runner_error"),
    ]
    findings, escalations = split_findings_and_escalations(artifacts)
    assert len(findings) == 2
    assert len(escalations) == 2
    assert {f["axis"] for f in findings} == {"axis-01-unused-export", "tool:vulture"}


def test_axis_breakdown_counts():
    artifacts = [
        _artifact("axis-01-unused-export"),
        _artifact("axis-01-unused-export"),
        _artifact("tool:vulture"),
    ]
    breakdown = axis_breakdown(artifacts)
    assert breakdown == {"axis-01-unused-export": 2, "tool:vulture": 1}


def test_metrics_escalation_only_counts_as_success():
    artifacts = [_artifact("escalation"), _artifact("escalation")]
    m = compute_metrics(artifacts=artifacts, spans=[],
                       elapsed_ms_per_iter=[], audit_layer_2=[])
    assert m["task_success"] == 1.0
    assert m["finding_count"] == 0
    assert m["escalation_count"] == 2


def test_metrics_empty_returns_zero():
    m = compute_metrics(artifacts=[], spans=[],
                       elapsed_ms_per_iter=[], audit_layer_2=[])
    assert m["task_success"] == 0.0
    assert m["finding_count"] == 0
    assert m["escalation_count"] == 0


def test_metrics_count_findings_only():
    artifacts = [
        _artifact("axis-01-unused-export"),
        _artifact("tool:vulture"),
        _artifact("escalation"),
    ]
    m = compute_metrics(artifacts=artifacts, spans=[],
                       elapsed_ms_per_iter=[], audit_layer_2=[])
    assert m["task_success"] == 1.0
    assert m["finding_count"] == 2
    assert m["escalation_count"] == 1
    assert m["axis_breakdown"]["axis-01-unused-export"] == 1
    assert m["axis_breakdown"]["tool:vulture"] == 1
