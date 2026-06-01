from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gemma_worker.client.base import Provider
from gemma_worker.playbooks._common import parse_json_tolerant, read_safe, run_per_file
from gemma_worker.queue.worker_pool import WorkerPool
from gemma_worker.store.sqlite_store import Store

REBUT_SYSTEM = (
    "You are an asymmetric devil's advocate. Given a single finding produced "
    "by an earlier audit, your job is to find the strongest counter-evidence "
    "AGAINST the finding being valid. You do not give balanced review. You do "
    "not concede when the finding is reasonable — you look for the case where "
    "it is wrong, missing context, or based on a misreading. "
    "Output strict JSON: "
    '{"original_axis": "<copied from input>", "rebuttal": "<2-3 sentence '
    'counter-case>", "counter_strength": "strong|moderate|weak", '
    '"counter_evidence": "<short quote or reference if available>"}. '
    "If after honest effort no counter-case exists, return "
    '{"original_axis": "...", "rebuttal": "", "counter_strength": "none", '
    '"counter_evidence": ""}.'
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


def _rebut_prompt(finding: dict[str, Any]) -> str:
    return (
        "Original finding (verbatim JSON):\n"
        f"{json.dumps(finding, ensure_ascii=False)}\n\n"
        "Find the strongest counter-case. Do not concede. Do not be polite."
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

    async def rebut(finding: dict[str, Any]) -> dict[str, Any] | None:
        r = await client.call(
            system=REBUT_SYSTEM,
            user=_rebut_prompt(finding),
            want_json=True,
        )
        if r.status != "ok" or not isinstance(r.json, dict):
            return None
        return {
            "playbook": "devils_advocate",
            "axis": "rebuttal",
            "kind": "rebuttal",
            "file": finding.get("file", "(unknown)"),
            "line": int(finding.get("line", 0) or 0),
            "evidence": str(r.json.get("rebuttal", "")).strip(),
            "severity": str(finding.get("severity", "low")).strip().lower(),
            "why": str(r.json.get("counter_evidence", "")).strip(),
            "counter_strength": str(r.json.get("counter_strength", "weak")).strip().lower(),
            "rebuts_axis": finding.get("axis"),
            "rebuts_playbook": finding.get("playbook"),
        }

    results = await run_per_file(
        files=findings,  # type: ignore[arg-type]
        pool=pool,
        builder=rebut,
    )
    return [r for r in results if isinstance(r, dict)]
