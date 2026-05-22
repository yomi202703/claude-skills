from __future__ import annotations

from typing import Any, Literal

Verdict = Literal["PROMOTE", "HOLD", "ROLLBACK"]


THRESHOLDS: dict[str, dict[str, float]] = {
    "task_success":          {"promote": 0.80, "hold": 0.56},
    "context_preservation":  {"promote": 0.90, "hold": 0.63},
    "p95_latency_ms":        {"promote": 15000.0, "hold": 21000.0},
    "safety_pass_rate":      {"promote": 0.95, "hold": 0.67},
    "evidence_coverage":     {"promote": 0.80, "hold": 0.56},
    "axis_05_violations":    {"promote": 0.0, "hold": 2.0},
    "axis_06_violations":    {"promote": 0.0, "hold": 2.0},
}

UPPER_BOUND_METRICS = {"p95_latency_ms", "axis_05_violations", "axis_06_violations"}


def _p95(values: list[int]) -> int:
    if not values:
        return 0
    s = sorted(values)
    idx = max(0, int(0.95 * (len(s) - 1)))
    return s[idx]


def split_findings_and_escalations(
    artifacts: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    escalations: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for a in artifacts:
        axis = str(a.get("axis", ""))
        if axis == "escalation" or axis == "tool_runner_error":
            escalations.append(a)
        else:
            findings.append(a)
    return findings, escalations


def axis_breakdown(artifacts: list[dict[str, Any]]) -> dict[str, int]:
    breakdown: dict[str, int] = {}
    for a in artifacts:
        axis = str(a.get("axis", "(none)"))
        breakdown[axis] = breakdown.get(axis, 0) + 1
    return breakdown


def compute_metrics(
    *,
    artifacts: list[dict[str, Any]],
    spans: list[dict[str, Any]],
    elapsed_ms_per_iter: list[int],
    audit_layer_2: list[dict[str, Any]],
) -> dict[str, Any]:
    findings, escalations = split_findings_and_escalations(artifacts)
    has_findings = len(findings) > 0
    has_escalations = len(escalations) > 0
    task_success = 1.0 if (has_findings or has_escalations) else 0.0

    scored = findings if findings else escalations
    with_evidence = sum(1 for a in scored if a.get("evidence"))
    evidence_coverage = (with_evidence / len(scored)) if scored else 0.0

    safety_failures = sum(
        1 for s in spans
        if (s.get("attributes", {}) or {}).get("gen_ai.response.finish_reason") in
        ("content_filter", "policy_violation")
    )
    safety_pass_rate = 1.0 if not spans else 1.0 - safety_failures / max(1, len(spans))

    finish_reasons = [
        (s.get("attributes", {}) or {}).get("gen_ai.response.finish_reason")
        for s in spans
    ]
    cp_failures = sum(1 for r in finish_reasons if r in ("length", "truncated"))
    context_preservation = 1.0 if not spans else 1.0 - cp_failures / max(1, len(spans))

    p95_latency_ms = _p95(elapsed_ms_per_iter)

    axis_05 = sum(1 for f in audit_layer_2 if f.get("axis") == 5)
    axis_06 = sum(1 for f in audit_layer_2 if f.get("axis") == 6)

    return {
        "task_success": round(task_success, 4),
        "context_preservation": round(context_preservation, 4),
        "p95_latency_ms": p95_latency_ms,
        "safety_pass_rate": round(safety_pass_rate, 4),
        "evidence_coverage": round(evidence_coverage, 4),
        "axis_05_violations": axis_05,
        "axis_06_violations": axis_06,
        "finding_count": len(findings),
        "escalation_count": len(escalations),
        "axis_breakdown": axis_breakdown(findings),
    }


def _classify_dim(metric: str, value: float) -> Verdict:
    th = THRESHOLDS[metric]
    if metric in UPPER_BOUND_METRICS:
        if value <= th["promote"]:
            return "PROMOTE"
        if value <= th["hold"]:
            return "HOLD"
        return "ROLLBACK"
    if value >= th["promote"]:
        return "PROMOTE"
    if value >= th["hold"]:
        return "HOLD"
    return "ROLLBACK"


def to_verdict(metrics: dict[str, Any]) -> Verdict:
    per_dim: list[Verdict] = []
    for key in THRESHOLDS:
        if key not in metrics:
            continue
        per_dim.append(_classify_dim(key, float(metrics[key])))
    if not per_dim:
        return "HOLD"
    if any(v == "ROLLBACK" for v in per_dim):
        return "ROLLBACK"
    if all(v == "PROMOTE" for v in per_dim):
        return "PROMOTE"
    return "HOLD"
