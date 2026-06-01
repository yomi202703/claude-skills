from __future__ import annotations

from pathlib import Path
from typing import Any

from gemma_worker.client.base import Provider
from gemma_worker.playbooks._axis_runner import run_axes, run_tool_runners
from gemma_worker.playbooks._common import (
    CODE_FILE_EXTENSIONS,
    extract_targets_from_task,
    iter_target_files,
)
from gemma_worker.playbooks.deadcode.escalation import make_escalation_artifact
from gemma_worker.playbooks.deadcode.runners.ts_prune import run_ts_prune
from gemma_worker.playbooks.deadcode.runners.vulture import run_vulture
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
    files = iter_target_files(targets, extensions=CODE_FILE_EXTENSIONS)

    axis_findings = await run_axes(
        playbook_name="deadcode",
        axes_dir=AXES_DIR,
        files=files,
        client=client,
        pool=pool,
        reflexion=reflexion,
    )

    runner_findings = await run_tool_runners(
        playbook_name="deadcode",
        runners=[run_vulture, run_ts_prune],
        files=files,
    )

    artifacts = axis_findings + runner_findings
    confirmed = [a for a in artifacts if a.get("axis") != "escalation"]
    if confirmed:
        artifacts.append(make_escalation_artifact(
            reason="deadcode candidates detected; specialized deletion skill recommended",
            detection_count=len(confirmed),
        ))
    return artifacts
