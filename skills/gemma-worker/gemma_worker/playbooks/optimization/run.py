from __future__ import annotations

from pathlib import Path
from typing import Any

from gemma_worker.client.base import Provider
from gemma_worker.playbooks._axis_runner import run_axes
from gemma_worker.playbooks._common import (
    CODE_FILE_EXTENSIONS,
    extract_targets_from_task,
    iter_target_files,
)
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
    return await run_axes(
        playbook_name="optimization",
        axes_dir=AXES_DIR,
        files=files,
        client=client,
        pool=pool,
        reflexion=reflexion,
    )
