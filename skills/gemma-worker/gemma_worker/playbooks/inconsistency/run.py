from __future__ import annotations

from pathlib import Path
from typing import Any

from gemma_worker.client.base import Provider
from gemma_worker.playbooks._axis_runner import run_axes, run_tool_runners
from gemma_worker.playbooks._common import (
    extract_targets_from_task,
    iter_target_files,
)
from gemma_worker.playbooks.inconsistency.escalation import make_escalation_artifact
from gemma_worker.playbooks.inconsistency.runners.ruff import run_ruff
from gemma_worker.queue.worker_pool import WorkerPool
from gemma_worker.store.sqlite_store import Store

AXES_DIR = Path(__file__).parent / "axes"


async def run(
    *,
    task: str,
    client: Provider,
    pool: WorkerPool,
    store: Store,
    reflexion: list[str],
) -> list[dict[str, Any]]:
    targets = extract_targets_from_task(task)
    files = iter_target_files(targets)

    axis_findings = await run_axes(
        playbook_name="inconsistency",
        axes_dir=AXES_DIR,
        files=files,
        client=client,
        pool=pool,
        reflexion=reflexion,
    )

    runner_findings = await run_tool_runners(
        playbook_name="inconsistency",
        runners=[run_ruff],
        files=files,
    )

    artifacts = axis_findings + runner_findings
    confirmed = [a for a in artifacts if a.get("axis") not in {"escalation", "tool_runner_error"}]
    if confirmed:
        artifacts.append(make_escalation_artifact(detection_count=len(confirmed)))
    return artifacts
