from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Iterable

from gemma_worker.client.base import Provider
from gemma_worker.queue.worker_pool import WorkerPool, gather_with_pool

DEFAULT_FILE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt",
    ".rb", ".php", ".cs", ".swift", ".m", ".mm", ".scala", ".cpp", ".hpp",
    ".c", ".h", ".sh", ".bash", ".zsh", ".sql", ".md", ".rst",
}


def iter_target_files(
    targets: Iterable[str | Path],
    *,
    extensions: set[str] | None = None,
    max_files: int = 500,
) -> list[Path]:
    exts = extensions if extensions is not None else DEFAULT_FILE_EXTENSIONS
    out: list[Path] = []
    for t in targets:
        p = Path(t).expanduser()
        if not p.exists():
            continue
        if p.is_file():
            if not exts or p.suffix.lower() in exts:
                out.append(p.resolve())
            continue
        for child in sorted(p.rglob("*")):
            if child.is_file() and (not exts or child.suffix.lower() in exts):
                out.append(child.resolve())
                if len(out) >= max_files:
                    return out
    return out


def read_safe(path: Path, *, max_bytes: int = 200_000) -> str:
    try:
        data = path.read_bytes()[:max_bytes]
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


async def run_per_file(
    *,
    files: list[Path],
    pool: WorkerPool,
    builder,
    priority: str = "normal",
) -> list[Any]:
    factories = [
        (lambda p=p: builder(p))
        for p in files
    ]
    if not factories:
        return []
    results = await gather_with_pool(pool, factories, priority=priority)
    return results


def extract_targets_from_task(task: str) -> list[str]:
    candidates: list[str] = []
    for token in task.split():
        token = token.strip().strip(",.;:'\"`")
        if not token:
            continue
        looks_like_path = (
            token.startswith("/")
            or token.startswith("~")
            or token.startswith("./")
            or "/" in token
            or token.endswith(tuple(DEFAULT_FILE_EXTENSIONS))
        )
        if not looks_like_path:
            continue
        p = Path(token).expanduser()
        if p.exists():
            candidates.append(str(p))
    return candidates
