from __future__ import annotations

from typing import Any


def make_escalation_artifact(detection_count: int) -> dict[str, Any]:
    return {
        "playbook": "inconsistency",
        "axis": "escalation",
        "file": "code_consistency_skill_handoff",
        "line": 0,
        "evidence": (
            f"Detected {detection_count} potential inconsistencies across axes/runners. "
            "For AI-codegen-specific anti-patterns (robustness theater, phantom flexibility, "
            "drift, duplication, residue debt), the standalone `code-consistency` skill has "
            "5 specialized axes with literature-backed prompts and a self-tune mechanism."
        ),
        "severity": "low",
        "why": "deeper audit recommended for AI-generated code",
        "next_action": "Invoke `code-consistency` skill on the same target.",
    }
