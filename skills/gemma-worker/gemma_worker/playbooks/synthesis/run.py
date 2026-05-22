from __future__ import annotations

from pathlib import Path
from typing import Any

from gemma_worker.client.base import Provider
from gemma_worker.playbooks._common import (
    extract_targets_from_task,
    iter_target_files,
    read_safe,
    run_per_file,
)
from gemma_worker.queue.worker_pool import WorkerPool
from gemma_worker.store.sqlite_store import Store

PER_FILE_SYSTEM = (
    "Summarize this single file in 2-3 sentences focused on its responsibility "
    "and any standout properties. Output strict JSON: "
    '{"file": "<path>", "summary": "<2-3 sentence summary>", '
    '"standout": ["<short phrase>", ...]}'
)

GLOBAL_SYSTEM = (
    "Given multiple per-file summaries, identify the top 5 highest-impact "
    "themes/issues/opportunities for the codebase as a whole. Output JSON array."
)


def _per_file_prompt(path: Path, content: str) -> str:
    return f"File: {path}\n----- BEGIN -----\n{content[:8000]}\n----- END -----"


def _global_prompt(summaries: list[dict[str, Any]]) -> str:
    lines = [f"- {s.get('file')}: {s.get('summary', '').strip()}" for s in summaries]
    bullet = "\n".join(lines)
    return (
        "Per-file summaries:\n"
        f"{bullet}\n\n"
        "Return JSON array of up to 5 themes. Each entry:\n"
        '{"file": "(global)", "line": 0, "evidence": "<theme>", '
        '"severity": "high|medium|low", "why": "<one-line implication>"}'
    )


async def run(
    *,
    task: str,
    client: Provider,
    pool: WorkerPool,
    store: Store,
    reflexion: list[str],
) -> list[dict[str, Any]]:
    files = iter_target_files(extract_targets_from_task(task), max_files=80)

    async def per_file(p: Path) -> dict[str, Any] | None:
        content = read_safe(p)
        if not content:
            return None
        r = await client.call(system=PER_FILE_SYSTEM, user=_per_file_prompt(p, content), want_json=True)
        if r.status != "ok" or not isinstance(r.json, dict):
            return None
        return {
            "file": r.json.get("file") or str(p),
            "summary": str(r.json.get("summary", "")).strip(),
            "standout": [str(x).strip() for x in (r.json.get("standout") or []) if str(x).strip()],
        }

    results = await run_per_file(files=files, pool=pool, builder=per_file)
    summaries = [r for r in results if isinstance(r, dict)]
    if not summaries:
        return []

    overview = await client.call(
        system=GLOBAL_SYSTEM,
        user=_global_prompt(summaries),
        want_json=True,
    )
    artifacts: list[dict[str, Any]] = []
    for s in summaries:
        artifacts.append({
            "playbook": "synthesis",
            "axis": "file_summary",
            "kind": "file_summary",
            "file": s["file"],
            "line": 0,
            "evidence": s["summary"],
            "severity": "low",
            "why": "per-file synthesis",
            "standout": s.get("standout", []),
        })
    if overview.status == "ok" and isinstance(overview.json, list):
        for item in overview.json:
            if not isinstance(item, dict):
                continue
            artifacts.append({
                "playbook": "synthesis",
                "axis": "global_theme",
                "kind": "global_theme",
                "file": item.get("file") or "(global)",
                "line": int(item.get("line", 0) or 0),
                "evidence": str(item.get("evidence", "")).strip(),
                "severity": str(item.get("severity", "low")).strip().lower(),
                "why": str(item.get("why", "")).strip(),
            })
    return artifacts
