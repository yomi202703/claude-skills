from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

PLAYBOOKS = (
    "deadcode",
    "inconsistency",
    "gap",
    "research",
    "optimization",
    "synthesis",
    "critique",
    "devils_advocate",
    "steelman",
    "auto",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="gemma-worker",
        description="Provider-agnostic LLM worker orchestrator.",
    )
    p.add_argument("task", help="Natural-language task description")
    p.add_argument(
        "--playbook",
        choices=PLAYBOOKS,
        default="auto",
        help="Playbook to dispatch to; 'auto' lets the supervisor choose.",
    )
    p.add_argument(
        "--output",
        choices=("json", "text"),
        default="json",
        help="Output format (json for machine, text for human).",
    )
    p.add_argument(
        "--max-iterations",
        type=int,
        default=3,
        help="Maximum reflexion iterations before forcing a HOLD/ROLLBACK verdict.",
    )
    p.add_argument(
        "--priority",
        choices=("high", "normal", "low"),
        default="normal",
        help="Queue priority for the worker pool.",
    )
    p.add_argument(
        "--exclude-dirs",
        default=None,
        help=(
            "Comma- or colon-separated directory names to skip when walking "
            "the scan root, e.g. `_data,_archive,outputs`. Merged with the "
            "built-in defaults (.venv, node_modules, .git, build, dist, ...). "
            "Use this to keep project-specific PII / legacy / generated dirs "
            "out of the LLM call stream. Also honored via "
            "$GEMMA_WORKER_EXCLUDE_DIRS."
        ),
    )
    return p.parse_args(argv)


async def _run(ns: argparse.Namespace) -> dict[str, Any]:
    from gemma_worker.supervisor import run_supervisor

    return await run_supervisor(
        task=ns.task,
        playbook=ns.playbook,
        max_iterations=ns.max_iterations,
        priority=ns.priority,
    )


def main(argv: list[str] | None = None) -> int:
    ns = parse_args(argv)
    if ns.exclude_dirs:
        # Surface the flag as an env var so `iter_target_files` (which is
        # called deep inside each playbook) picks it up without threading
        # the value through every playbook signature.
        os.environ["GEMMA_WORKER_EXCLUDE_DIRS"] = ns.exclude_dirs
    try:
        result = asyncio.run(_run(ns))
    except KeyboardInterrupt:
        return 130
    if ns.output == "json":
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        verdict = result.get("verdict", "?")
        sys.stdout.write(f"verdict: {verdict}\n")
        for item in result.get("artifacts", []):
            sys.stdout.write(f"  - {item}\n")
    return 0 if result.get("verdict") in ("PROMOTE", "HOLD") else 2


if __name__ == "__main__":
    raise SystemExit(main())
