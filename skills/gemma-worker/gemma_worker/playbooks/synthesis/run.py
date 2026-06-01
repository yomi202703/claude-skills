from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gemma_worker.client.base import Provider
from gemma_worker.playbooks._common import (
    extract_targets_from_task,
    iter_target_files,
    parse_json_tolerant,
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

SUBGROUP_SYSTEM = (
    "Given per-file summaries from one subdirectory, identify the top 3 themes "
    "specific to that subgroup. Output strict JSON: "
    '{"subgroup": "<dir or label>", "themes": ["<theme>", ...], '
    '"standout": ["<phrase>", ...]}'
)

TIER2_THRESHOLD = 10


def _per_file_prompt(path: Path, content: str) -> str:
    return f"File: {path}\n----- BEGIN -----\n{content[:8000]}\n----- END -----"


def _subgroup_label(summary: dict[str, Any]) -> str:
    f = summary.get("file") or ""
    p = Path(f)
    parents = list(p.parents)
    return str(parents[0]) if parents else "(root)"


def _subgroup_prompt(label: str, group_summaries: list[dict[str, Any]]) -> str:
    lines = [f"- {s.get('file')}: {s.get('summary', '').strip()}" for s in group_summaries]
    bullet = "\n".join(lines)
    return (
        f"Subgroup: {label}\n"
        "Per-file summaries in this subgroup:\n"
        f"{bullet}\n\n"
        "Return JSON: subgroup, themes (up to 3), standout."
    )


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


def _global_prompt_from_subgroups(subgroup_themes: list[dict[str, Any]]) -> str:
    lines = []
    for sg in subgroup_themes:
        themes = ", ".join(sg.get("themes", []))
        lines.append(f"- {sg.get('subgroup')}: {themes}")
    bullet = "\n".join(lines)
    return (
        "Subgroup-level themes (already aggregated from per-file summaries):\n"
        f"{bullet}\n\n"
        "Return JSON array of up to 5 CROSS-SUBGROUP themes. Each entry:\n"
        '{"file": "(global)", "line": 0, "evidence": "<theme spanning '
        'multiple subgroups>", "severity": "high|medium|low", "why": '
        '"<one-line implication>"}'
    )


def _extract_artifact_json_paths(task: str) -> list[Path]:
    out: list[Path] = []
    for token in task.split():
        token = token.strip().strip(",.;:'\"`")
        if not token.endswith(".json"):
            continue
        p = Path(token).expanduser()
        if p.exists() and p.is_file():
            out.append(p.resolve())
    return out


def _artifact_streams_as_pseudo_summaries(json_paths: list[Path]) -> list[dict[str, Any]]:
    """Treat each prior-run JSON as one pseudo per-file summary.

    Each prior playbook run becomes a single 'summary' entry whose body lists
    its findings. This lets synthesis run its existing global pass over a set
    of prior runs without changing the per-file LLM pass for the source-file
    case.
    """
    summaries: list[dict[str, Any]] = []
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
        if not items:
            continue
        playbook = next(
            (str(i.get("playbook")) for i in items if isinstance(i, dict) and i.get("playbook")),
            "unknown",
        )
        head = []
        for item in items[:8]:
            if not isinstance(item, dict):
                continue
            axis = item.get("axis", "?")
            ev = str(item.get("evidence", ""))[:140]
            head.append(f"{axis}: {ev}")
        summary = f"prior-run from playbook={playbook} with {len(items)} findings. " + " | ".join(head)
        summaries.append({
            "file": f"{p.name} ({playbook})",
            "summary": summary,
            "standout": [str(i.get("axis")) for i in items[:5] if isinstance(i, dict) and i.get("axis")],
        })
    return summaries


async def run(
    *,
    task: str,
    client: Provider,
    pool: WorkerPool,
    store: Store,
    reflexion: list[str],
) -> list[dict[str, Any]]:
    artifact_paths = _extract_artifact_json_paths(task)
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
    summaries.extend(_artifact_streams_as_pseudo_summaries(artifact_paths))
    if not summaries:
        return []

    subgroup_artifacts: list[dict[str, Any]] = []
    if len(summaries) > TIER2_THRESHOLD:
        groups: dict[str, list[dict[str, Any]]] = {}
        for s in summaries:
            groups.setdefault(_subgroup_label(s), []).append(s)

        async def subgroup_pass(label: str, group: list[dict[str, Any]]) -> dict[str, Any] | None:
            r = await client.call(
                system=SUBGROUP_SYSTEM,
                user=_subgroup_prompt(label, group),
                want_json=True,
            )
            if r.status != "ok" or not isinstance(r.json, dict):
                return None
            return {
                "subgroup": str(r.json.get("subgroup") or label),
                "themes": [str(t).strip() for t in (r.json.get("themes") or []) if str(t).strip()],
                "standout": [str(t).strip() for t in (r.json.get("standout") or []) if str(t).strip()],
            }

        for label, group in groups.items():
            sg = await subgroup_pass(label, group)
            if sg:
                subgroup_artifacts.append(sg)

        overview = await client.call(
            system=GLOBAL_SYSTEM,
            user=_global_prompt_from_subgroups(subgroup_artifacts),
            want_json=True,
        )
    else:
        overview = await client.call(
            system=GLOBAL_SYSTEM,
            user=_global_prompt(summaries),
            want_json=True,
        )
    artifacts: list[dict[str, Any]] = []
    for sg in subgroup_artifacts:
        artifacts.append({
            "playbook": "synthesis",
            "axis": "subgroup_theme",
            "kind": "subgroup_theme",
            "file": sg["subgroup"],
            "line": 0,
            "evidence": "; ".join(sg.get("themes", [])),
            "severity": "low",
            "why": "tier-2 subgroup synthesis",
            "standout": sg.get("standout", []),
        })
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
