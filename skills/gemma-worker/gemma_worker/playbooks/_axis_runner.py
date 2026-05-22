from __future__ import annotations

from pathlib import Path
from typing import Any, Awaitable, Callable

from gemma_worker.client.base import Provider
from gemma_worker.playbooks._common import read_safe, run_per_file
from gemma_worker.queue.worker_pool import WorkerPool


async def run_axes(
    *,
    playbook_name: str,
    axes_dir: Path,
    files: list[Path],
    client: Provider,
    pool: WorkerPool,
    reflexion: list[str],
    extra_user_prefix: Callable[[Path, str], str] | None = None,
) -> list[dict[str, Any]]:
    axis_files = sorted(axes_dir.glob("axis-*.md"))
    if not axis_files:
        return []
    reflexion_block = (
        "\n\nPrior reflexion guidance:\n- " + "\n- ".join(reflexion[-3:])
        if reflexion else ""
    )

    async def per_file(path: Path) -> list[dict[str, Any]]:
        content = read_safe(path)
        if not content:
            return []
        results: list[dict[str, Any]] = []
        for axis_path in axis_files:
            axis_id = axis_path.stem
            axis_prompt = axis_path.read_text(encoding="utf-8")
            user = (
                (extra_user_prefix(path, content) if extra_user_prefix else "")
                + f"File path: {path}\n"
                + f"----- BEGIN FILE -----\n{content}\n----- END FILE -----\n\n"
                + "Return a JSON array. Each entry: "
                '{"file": "<path>", "line": <int>, "evidence": "<short quote>", '
                '"severity": "high|medium|low", "why": "<one-line>"}. '
                "If nothing matches this axis, return []."
            )
            r = await client.call(
                system=axis_prompt + reflexion_block,
                user=user,
                want_json=True,
            )
            if r.status != "ok" or not isinstance(r.json, list):
                continue
            for item in r.json:
                if not isinstance(item, dict):
                    continue
                core_keys = {"file", "line", "evidence", "severity", "why"}
                entry = {
                    "playbook": playbook_name,
                    "axis": axis_id,
                    "file": item.get("file") or str(path),
                    "line": int(item.get("line", 0) or 0),
                    "evidence": str(item.get("evidence", "")).strip(),
                    "severity": str(item.get("severity", "low")).strip().lower(),
                    "why": str(item.get("why", "")).strip(),
                }
                for k, v in item.items():
                    if k not in core_keys and k not in {"playbook", "axis"}:
                        entry[k] = v
                results.append(entry)
        return results

    out = await run_per_file(files=files, pool=pool, builder=per_file)
    flat: list[dict[str, Any]] = []
    for r in out:
        if isinstance(r, list):
            flat.extend(r)
    return flat


async def run_tool_runners(
    *,
    playbook_name: str,
    runners: list[Callable[[list[Path]], Awaitable[list[dict[str, Any]]]]],
    files: list[Path],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for runner in runners:
        try:
            items = await runner(files)
        except Exception as e:
            out.append({
                "playbook": playbook_name,
                "axis": "tool_runner_error",
                "file": "(runner)",
                "line": 0,
                "evidence": f"{type(e).__name__}: {e}",
                "severity": "low",
                "why": "tool runner crashed; LLM-only fallback applies",
            })
            continue
        out.extend(items)
    return out
