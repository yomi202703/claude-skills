from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gemma_worker.client.base import Provider
from gemma_worker.playbooks._common import parse_json_tolerant, read_safe, run_per_file
from gemma_worker.queue.worker_pool import WorkerPool
from gemma_worker.store.sqlite_store import Store

STEELMAN_SYSTEM = (
    "You construct steelman arguments. Given a single finding produced by an "
    "earlier audit, your job is to build the STRONGEST POSSIBLE CASE for the "
    "opposite conclusion — not to weaken the finding, but to articulate the "
    "best version of the position that contradicts it. "
    "You write as a thoughtful advocate for the opposite verdict, not as a "
    "neutral reviewer. Length: longer than a rebuttal — give a multi-step "
    "case. "
    "Output strict JSON: "
    '{"original_axis": "<copied>", "opposite_verdict": "<what verdict the '
    'steelman argues for>", "argument": "<4-6 sentence case for the opposite '
    'verdict, structured as premises → conclusion>", "supporting_basis": '
    '"<short quotes or references>", "argument_strength": "strong|moderate|'
    'weak"}. '
    "If after honest effort no coherent opposite case exists, return "
    '"argument_strength": "none" with empty argument.'
)


def _extract_artifact_paths(task: str) -> list[Path]:
    out: list[Path] = []
    for token in task.split():
        token = token.strip().rstrip(",.;:'\"`")
        if not token.endswith(".json"):
            continue
        p = Path(token).expanduser()
        if p.exists() and p.is_file():
            out.append(p.resolve())
    return out


def _load_findings(json_paths: list[Path]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for p in json_paths:
        content = read_safe(p, max_bytes=2_000_000)
        if not content:
            continue
        data = parse_json_tolerant(content)
        if data is None:
            continue
        items: list[Any]
        if isinstance(data, dict) and isinstance(data.get("artifacts"), list):
            items = data["artifacts"]
        elif isinstance(data, list):
            items = data
        else:
            continue
        for item in items:
            if isinstance(item, dict) and item.get("axis") and item.get("evidence"):
                findings.append(item)
    return findings


def _steelman_prompt(finding: dict[str, Any]) -> str:
    return (
        "Original finding (verbatim JSON):\n"
        f"{json.dumps(finding, ensure_ascii=False)}\n\n"
        "Construct the strongest case for the OPPOSITE verdict. Write as a "
        "thoughtful advocate, not a neutral reviewer."
    )


async def run(
    *,
    task: str,
    client: Provider,
    pool: WorkerPool,
    store: Store,
    reflexion: list[str],
) -> list[dict[str, Any]]:
    json_paths = _extract_artifact_paths(task)
    findings = _load_findings(json_paths)
    if not findings:
        return []

    async def steelman(finding: dict[str, Any]) -> dict[str, Any] | None:
        r = await client.call(
            system=STEELMAN_SYSTEM,
            user=_steelman_prompt(finding),
            want_json=True,
        )
        if r.status != "ok" or not isinstance(r.json, dict):
            return None
        return {
            "playbook": "steelman",
            "axis": "opposite_case",
            "kind": "steelman",
            "file": finding.get("file", "(unknown)"),
            "line": int(finding.get("line", 0) or 0),
            "evidence": str(r.json.get("argument", "")).strip(),
            "severity": str(finding.get("severity", "low")).strip().lower(),
            "why": str(r.json.get("opposite_verdict", "")).strip(),
            "supporting_basis": str(r.json.get("supporting_basis", "")).strip(),
            "argument_strength": str(r.json.get("argument_strength", "weak")).strip().lower(),
            "opposes_axis": finding.get("axis"),
            "opposes_playbook": finding.get("playbook"),
        }

    results = await run_per_file(
        files=findings,  # type: ignore[arg-type]
        pool=pool,
        builder=steelman,
    )
    return [r for r in results if isinstance(r, dict)]
