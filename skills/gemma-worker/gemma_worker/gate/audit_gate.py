from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

AUDIT_SKILL_DIR = Path(
    os.environ.get("AI_PIPELINE_AUDIT_DIR")
    or Path.home() / ".claude" / "skills" / "ai-pipeline-audit"
)

AXES = {
    1: "axis-01-prompt-bias.md",
    2: "axis-02-eval-integrity.md",
    3: "axis-03-prompt-overfitting.md",
    4: "axis-04-termination.md",
    5: "axis-05-reasoning-action.md",
    6: "axis-06-intent-execution.md",
}


def _parse_axes(spec: str) -> list[int]:
    out: list[int] = []
    for piece in spec.split(","):
        p = piece.strip()
        if not p:
            continue
        n = int(p)
        if n not in AXES:
            raise ValueError(f"unknown axis: {n}")
        out.append(n)
    return out


def render_invocation_payload(
    *,
    target: str | None,
    trace: str | None,
    intent: str | None,
    axes: list[int],
) -> dict:
    prompts: dict[int, str] = {}
    for n in axes:
        path = AUDIT_SKILL_DIR / "prompts" / AXES[n]
        if not path.exists():
            prompts[n] = f"# missing axis prompt: {path}"
            continue
        text = path.read_text(encoding="utf-8")
        if target is not None and "$TARGET" in text:
            text = text.replace("$TARGET", target)
        if trace is not None and "$TRACE" in text:
            text = text.replace("$TRACE", trace)
        if intent is not None and "$INTENT" in text:
            text = text.replace("$INTENT", intent)
        prompts[n] = text
    return {
        "axes": axes,
        "target": target,
        "trace": trace,
        "intent": intent,
        "prompts": prompts,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Render axis prompts for ai-pipeline-audit subagents."
    )
    ap.add_argument("--file", help="Path passed as $TARGET to axes 1-4.")
    ap.add_argument("--trace", help="Path or inline JSON passed as $TRACE to axes 5/6.")
    ap.add_argument("--intent", help="Original CEO task string passed as $INTENT to axis 6.")
    ap.add_argument("--axes", default="1,2,3,4",
                    help="Comma-separated axis numbers to render.")
    ap.add_argument("--output", choices=("json", "text"), default="json")
    ns = ap.parse_args(argv)

    axes = _parse_axes(ns.axes)
    payload = render_invocation_payload(
        target=ns.file, trace=ns.trace, intent=ns.intent, axes=axes,
    )
    if ns.output == "json":
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        for n, body in payload["prompts"].items():
            sys.stdout.write(f"===== axis {n} =====\n{body}\n\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
