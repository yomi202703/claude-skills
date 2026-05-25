from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any, Iterable

from gemma_worker.client.base import Provider
from gemma_worker.queue.worker_pool import WorkerPool, gather_with_pool

DEFAULT_FILE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".kt",
    ".rb", ".php", ".cs", ".swift", ".m", ".mm", ".scala", ".cpp", ".hpp",
    ".c", ".h", ".sh", ".bash", ".zsh", ".sql", ".md", ".rst",
}

# Code-only subset for playbooks whose axes assume executable source files
# (deadcode / inconsistency / gap / optimization). Pass this explicitly to
# `iter_target_files(...)` to enforce SKILL.md's "content target = code only"
# applicability tag at runtime, rather than relying on the LLM to no-op on
# prose files (which produces false positives — see the meta-audit).
CODE_FILE_EXTENSIONS = DEFAULT_FILE_EXTENSIONS - {".md", ".rst"}

# Directory names to skip when walking targets. These are dependency / build /
# cache / VCS dirs that auditing them burns LLM calls on 3rd-party code which
# the user is not responsible for. A single .venv typically contains 30-50
# packages × 5-20 files each → 1000s of files; running 4-6 critique axes per
# file produces 10k+ wasted LLM calls in cross-repo audit scenarios.
DEFAULT_EXCLUDE_DIRS = {
    ".venv", "venv", ".env",
    "node_modules",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
    ".git", ".hg", ".svn",
    "dist", "build", "target", ".next", ".nuxt", ".output",
    "site-packages",  # belt-and-suspenders for venv installs under unusual paths
}


def iter_target_files(
    targets: Iterable[str | Path],
    *,
    extensions: set[str] | None = None,
    max_files: int = 500,
    exclude_dirs: set[str] | None = None,
) -> list[Path]:
    exts = extensions if extensions is not None else DEFAULT_FILE_EXTENSIONS
    excludes = exclude_dirs if exclude_dirs is not None else DEFAULT_EXCLUDE_DIRS
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
            # Skip any path that has an excluded directory name in its parts.
            # This catches both top-level (.venv/) and nested (vendor/.venv/).
            if excludes and any(part in excludes for part in child.parts):
                continue
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


def parse_json_tolerant(content: str) -> Any | None:
    """Parse JSON tolerating leading non-JSON noise (e.g. warnings on stderr
    that were merged into stdout by a `2>&1` redirect).
    Returns None if no JSON object/array can be located.
    """
    if not content:
        return None
    import json as _json

    for start_char in ("{", "["):
        idx = content.find(start_char)
        if idx == -1:
            continue
        try:
            return _json.loads(content[idx:])
        except _json.JSONDecodeError:
            continue
    return None


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
    """Resolve scan targets from a task string.

    Returns explicit path tokens from `task` (anything that looks like a path
    and exists on disk). If the task contains no such token, falls back to
    `$GEMMA_WORKER_PROJECT_ROOT` if set, then to the git repository root, then
    to the current working directory — mirroring how an interactive tool like
    Claude Code treats "the open repo" as the implicit scope. This lets a
    bare task like `"audit refactor consistency"` work without the caller
    having to enumerate paths.
    """
    candidates: list[str] = []
    for token in task.split():
        # Trailing punctuation only — stripping `.` from both ends destroys
        # relative paths like `./foo.py` / `../bar.py` (the leading `.` would
        # be eaten, leaving a non-existent absolute path).
        token = token.strip().rstrip(",;:'\"`")
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
    if candidates:
        return candidates
    return [_default_scan_root()]


def _default_scan_root() -> str:
    """Pick an implicit scan root when the task names no paths.

    Order: `$GEMMA_WORKER_PROJECT_ROOT` → `git rev-parse --show-toplevel` → cwd.
    """
    env = os.environ.get("GEMMA_WORKER_PROJECT_ROOT")
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return str(p.resolve())
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
        ).strip()
        if out and Path(out).exists():
            return out
    except Exception:
        pass
    return str(Path.cwd().resolve())
