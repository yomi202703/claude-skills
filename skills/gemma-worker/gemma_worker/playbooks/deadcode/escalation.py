from __future__ import annotations

from typing import Any


def make_escalation_artifact(reason: str, detection_count: int) -> dict[str, Any]:
    return {
        "playbook": "deadcode",
        "axis": "escalation",
        "file": "deadcode_skill_handoff",
        "line": 0,
        "evidence": (
            f"Detected {detection_count} candidate deletions across axes/runners. "
            "gemma-worker does NOT delete code; that requires the standalone "
            "`deadcode` skill which runs language-specific lenses, performs a "
            "git safety commit, batch-deletes with typecheck, and uses bisect "
            "against the test suite to recover from bad deletions."
        ),
        "severity": "low",
        "why": reason,
        "next_action": (
            "Invoke the `deadcode` skill (~/.claude/skills/deadcode/) on the same "
            "target. It will re-detect with its own tools and apply deletions "
            "with safety guarantees."
        ),
    }
