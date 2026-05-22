from __future__ import annotations

from typing import Any

from gemma_worker.client.base import Provider
from gemma_worker.queue.worker_pool import WorkerPool
from gemma_worker.store.sqlite_store import Store

DECOMPOSE_SYSTEM = (
    "Decompose a research request into 3-5 specific web search queries. "
    "Output strict JSON only."
)


async def run(
    *,
    task: str,
    client: Provider,
    pool: WorkerPool,
    store: Store,
    reflexion: list[str],
) -> list[dict[str, Any]]:
    decompose_prompt = (
        f"Research request: {task}\n\n"
        'Return JSON: {"queries": ["q1", "q2", ...], '
        '"escalate_to_ceo": true}\n'
        "escalate_to_ceo MUST be true (the worker cannot perform web fetches)."
    )
    decomp = await client.call(
        system=DECOMPOSE_SYSTEM, user=decompose_prompt, want_json=True
    )
    queries: list[str] = []
    if decomp.status == "ok" and isinstance(decomp.json, dict):
        raw_q = decomp.json.get("queries") or []
        queries = [str(q).strip() for q in raw_q if str(q).strip()]

    return [{
        "playbook": "research",
        "axis": "escalation",
        "file": "ceo_escalation",
        "line": 0,
        "evidence": (
            "Worker has no WebFetch/WebSearch tools. CEO (Claude Code) should run "
            "/deep or /deep-strict with the suggested queries."
        ),
        "severity": "low",
        "why": "research playbook escalates to CEO by design",
        "next_action": (
            "Invoke /deep or /deep-strict with the queries below. "
            "For high-stakes claims requiring corroboration, prefer /deep-strict."
        ),
        "queries": queries,
    }]
