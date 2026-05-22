from __future__ import annotations

import json
import subprocess
from pathlib import Path

from gemma_worker.gate.audit_gate import _parse_axes, render_invocation_payload


def test_parse_axes_ok():
    assert _parse_axes("1,2,3,4") == [1, 2, 3, 4]
    assert _parse_axes("5") == [5]


def test_parse_axes_reject_unknown():
    import pytest
    with pytest.raises(ValueError):
        _parse_axes("99")


def test_render_substitutes_target_only(tmp_path):
    payload = render_invocation_payload(
        target=str(tmp_path / "f.py"),
        trace=None,
        intent=None,
        axes=[1, 2, 3, 4],
    )
    for body in payload["prompts"].values():
        assert "$TARGET" not in body or "missing axis prompt" in body


def test_render_substitutes_trace_for_axis5(tmp_path):
    payload = render_invocation_payload(
        target=None,
        trace=str(tmp_path / "trace.json"),
        intent=None,
        axes=[5],
    )
    body = payload["prompts"][5]
    assert "$TRACE" not in body or "missing axis prompt" in body


def test_render_substitutes_both_for_axis6(tmp_path):
    payload = render_invocation_payload(
        target=None,
        trace=str(tmp_path / "trace.json"),
        intent="find unused exports",
        axes=[6],
    )
    body = payload["prompts"][6]
    assert "$TRACE" not in body and "$INTENT" not in body or "missing axis prompt" in body


def test_audit_gate_cli(tmp_path):
    script = Path("/Users/ivymee/.claude/skills/gemma-worker/gemma_worker/gate/audit_gate.py")
    target = tmp_path / "f.py"
    target.write_text("def foo(): pass\n")
    result = subprocess.run(
        ["uv", "run", "--project", "/Users/ivymee/.claude/skills/gemma-worker",
         "python", "-m", "gemma_worker.gate.audit_gate",
         "--file", str(target), "--axes", "1,2,3,4", "--output", "json"],
        capture_output=True, text=True, check=True,
    )
    parsed = json.loads(result.stdout)
    assert parsed["axes"] == [1, 2, 3, 4]
    assert parsed["target"] == str(target)
    assert set(parsed["prompts"].keys()) == {"1", "2", "3", "4"}
