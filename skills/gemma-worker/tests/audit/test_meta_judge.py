from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path("/Users/ivymee/.claude/skills/ai-pipeline-audit/scripts/meta_judge.py")


def test_meta_judge_agreement():
    sys.path.insert(0, str(SCRIPT.parent))
    from meta_judge import reconcile

    finals, disagreements = reconcile(
        cheap=["valid", "valid", "invalid"],
        expensive=["valid", "valid", "invalid"],
        tiebreaker=None,
    )
    assert finals == ["valid", "valid", "invalid"]
    assert disagreements == []


def test_meta_judge_disagreement_no_tiebreaker():
    sys.path.insert(0, str(SCRIPT.parent))
    from meta_judge import reconcile

    finals, disagreements = reconcile(
        cheap=["valid", "valid"],
        expensive=["invalid", "valid"],
        tiebreaker=None,
    )
    assert finals == ["uncertain", "valid"]
    assert len(disagreements) == 1
    assert disagreements[0].finding_index == 0
    assert disagreements[0].final == "uncertain"


def test_meta_judge_tiebreaker_majority():
    sys.path.insert(0, str(SCRIPT.parent))
    from meta_judge import reconcile

    finals, disagreements = reconcile(
        cheap=["valid"],
        expensive=["invalid"],
        tiebreaker=["valid"],
    )
    assert finals == ["valid"]
    assert len(disagreements) == 1
    assert disagreements[0].final == "valid"


def test_meta_judge_filter_findings():
    sys.path.insert(0, str(SCRIPT.parent))
    from meta_judge import filter_findings

    findings = [{"id": 1}, {"id": 2}, {"id": 3}]
    verdicts = ["valid", "invalid", "uncertain"]
    kept = filter_findings(findings, verdicts, keep=("valid",))
    assert kept == [{"id": 1}]


def test_meta_judge_cli(tmp_path):
    input_path = tmp_path / "in.json"
    input_path.write_text(json.dumps({
        "findings": [{"id": 1}, {"id": 2}],
        "cheap": ["valid", "invalid"],
        "expensive": ["valid", "valid"],
        "tiebreaker": [None, "valid"],
    }))
    result = subprocess.run(
        ["python", str(SCRIPT), "--input", str(input_path)],
        capture_output=True, text=True, check=True,
    )
    parsed = json.loads(result.stdout)
    assert parsed["verdicts"] == ["valid", "valid"]
    assert parsed["kept"] == [{"id": 1}, {"id": 2}]


def test_verdict_mapper_cli(tmp_path):
    SCRIPT2 = Path("/Users/ivymee/.claude/skills/ai-pipeline-audit/scripts/verdict_mapper.py")
    input_path = tmp_path / "metrics.json"
    input_path.write_text(json.dumps({
        "task_success": 0.85,
        "context_preservation": 0.95,
        "p95_latency_ms": 10000,
        "safety_pass_rate": 0.98,
        "evidence_coverage": 0.90,
        "axis_05_violations": 0,
        "axis_06_violations": 0,
    }))
    result = subprocess.run(
        ["python", str(SCRIPT2), "--metrics-json", str(input_path)],
        capture_output=True, text=True, check=True,
    )
    parsed = json.loads(result.stdout)
    assert parsed["verdict"] == "PROMOTE"
