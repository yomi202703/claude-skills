"""Stage B: cluster events (from A1+A2) into per-problem timelines.

Single gemma call sees ALL events at once and is asked to:
- Group events that discuss the same underlying problem
- Order each group by date → that's the problem's timeline
- Assign a `kind` to each event (提起 / 分析 / 決定 / 実装 / 再発 / 未解決)
- Use the LATEST decision to override older ones (no flag — just pick the latest)
- Set tentative latest_state (open / resolved) from final event
- Park truly unclustered events in unclassified_events

If events exceed a threshold, batch into chunks and merge (V2). MVP: single
batch up to ~200 events.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

from improver.execute.gemma_subagent import gemma_subagent

logger = logging.getLogger(__name__)

_BATCH_SIZE = int(os.environ.get("PROBLEMS_CONSOLIDATE_BATCH_SIZE", "80"))
# Merge is disabled by default — investigation showed it over-merges related-but-distinct
# problems (e.g. F006 with F010). Grouping is now a render-side concern (see render.py).
# Set MERGE_SIMILARITY < 1.0 to re-enable Python title-similarity merge,
# or PROBLEMS_MERGE_VIA_GEMMA=true to re-enable gemma merge.
_MERGE_SIMILARITY = float(os.environ.get("PROBLEMS_CONSOLIDATE_MERGE_SIMILARITY", "999"))
_MERGE_VIA_GEMMA = os.environ.get("PROBLEMS_MERGE_VIA_GEMMA", "false").lower() not in ("0", "false", "no")


_MERGE_PROMPT = (
    "You are reviewing a list of PROBLEM CLUSTERS that were independently extracted "
    "by parallel batches from the same project. Some clusters describe the SAME "
    "underlying issue but with different wording, scope, or angle.\n\n"
    "Your job: identify equivalence groups — sets of clusters that should be merged "
    "into one problem because they discuss the same root issue.\n\n"
    "Merge rules:\n"
    "- Merge if clusters describe the SAME phenomenon (even if phrased differently).\n"
    "  Examples to merge:\n"
    "  - 'F008/F009 overlap' + 'F008,F009,F013 definition ambiguity' → same issue family\n"
    "  - 'OCR truncation in footer' + 'document footer noise' → same root\n"
    "- DO NOT merge if clusters are about related but distinct issues.\n"
    "  Examples to keep separate:\n"
    "  - 'F013 boundary' vs 'F009 boundary' → different fields, separate\n"
    "  - 'OCR layout failure' vs 'OCR character recognition' → different failure modes\n"
    "- When merging, choose the title of the most specific/longest cluster as the "
    "  canonical title.\n\n"
    "Output JSON: {\n"
    '  "groups": [\n'
    '    {"member_ids": ["<problem_id>", ...], "canonical_title": "<one of the member titles>"}\n'
    "  ]\n"
    "}\n"
    "Only include groups with 2+ members. Singletons stay as-is and need not appear."
)


def _format_problem_brief(p: dict[str, Any]) -> str:
    pid = p["problem_id"]
    title = p["title"]
    latest = (p.get("latest_summary") or "").strip()[:200]
    state = p.get("latest_state", "?")
    return f"id={pid} state={state}\n  title: {title}\n  latest: {latest}"


async def _gemma_merge_problems(problems: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ask gemma to identify equivalence groups across batches, then merge them.

    Returns a new list with merged problems (and singletons preserved as-is).
    """
    if len(problems) < 2:
        return problems

    blocks = [_format_problem_brief(p) for p in problems]
    task = (
        _MERGE_PROMPT
        + "\n\n--- PROBLEM CLUSTERS ---\n"
        + "\n\n".join(blocks)
        + "\n\nReturn ONLY the JSON object."
    )
    max_tokens = int(os.environ.get("PROBLEMS_MERGE_MAX_TOKENS", "2048"))
    res = await gemma_subagent(task=task, kind="list", inputs=[], max_tokens=max_tokens)
    if res.get("status") != "ok":
        logger.warning("merge gemma failed: %s — keeping clusters as-is", res.get("error"))
        return problems
    data = res.get("data") or {}
    groups = data.get("groups") or []

    by_id: dict[str, dict[str, Any]] = {p["problem_id"]: p for p in problems}
    grouped_ids: set[str] = set()
    merged_out: list[dict[str, Any]] = []

    for g in groups:
        if not isinstance(g, dict):
            continue
        member_ids = [str(m) for m in (g.get("member_ids") or []) if str(m) in by_id]
        # Skip degenerate or already-grouped members
        member_ids = [m for m in member_ids if m not in grouped_ids]
        if len(member_ids) < 2:
            continue
        canonical_title = str(g.get("canonical_title") or "").strip()
        members = [by_id[m] for m in member_ids]
        # Pick canonical title — prefer the one matching exactly, else the longest title
        title = canonical_title
        if not title or title not in {m["title"] for m in members}:
            title = max((m["title"] for m in members), key=len)
        # Merge timelines (sort by date), dedupe by (date, summary)
        all_events: list[dict[str, Any]] = []
        seen_keys: set[tuple[str, str]] = set()
        all_used_global: list[int] = []
        for m in members:
            for ev in m.get("timeline") or []:
                key = (ev.get("date", ""), (ev.get("summary") or "")[:80])
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                all_events.append(ev)
            all_used_global.extend(m.get("_used_indices_global", []))
        all_events.sort(key=lambda e: e.get("date") or "")
        any_open = any(m.get("latest_state") == "open" for m in members)
        # Pick the member that owns the latest event in the MERGED timeline
        # (the old code picked based on each member's own last event, which is
        # not guaranteed to be the latest in the union).
        if all_events:
            last_ev_date = all_events[-1].get("date") or ""
            owner = next(
                (m for m in members
                 if any((ev.get("date") or "") == last_ev_date
                        and (ev.get("summary") or "")[:80] == (all_events[-1].get("summary") or "")[:80]
                        for ev in (m.get("timeline") or []))),
                members[-1],
            )
        else:
            owner = members[-1]
        merged_out.append({
            "problem_id": _make_problem_id(title, sorted(set(all_used_global))[:3] or [0]),
            "title": title,
            "timeline": all_events,
            "latest_state": "open" if any_open else owner.get("latest_state", "resolved"),
            "latest_summary": owner.get("latest_summary", ""),
            "code_evidence": [],
            "discrepancy_analysis": None,
            "_used_indices_global": all_used_global,
            "_merged_from": [m["problem_id"] for m in members],
        })
        grouped_ids.update(member_ids)

    # Preserve singletons not in any group
    for p in problems:
        if p["problem_id"] not in grouped_ids:
            merged_out.append(p)

    return merged_out


_CONSOLIDATE_PROMPT = (
    "You are organizing a list of EVENTS extracted from project docs.\n"
    "Each event is one occurrence (a paragraph) describing either progress or a problem.\n\n"
    "Your job: CLUSTER events that discuss the SAME underlying problem (by topic, "
    "not by exact wording), build a per-problem TIMELINE in chronological order, "
    "and decide each cluster's current state.\n\n"
    "Rules:\n"
    "1. Same problem may be discussed across multiple docs with different wording — "
    "   merge them. Different problems in the same doc stay separate.\n"
    "2. When a newer decision/event overrides an older one, both stay in the timeline "
    "   but `latest_state` reflects the newer one.\n"
    "3. Assign one `kind` per event from this set:\n"
    "   - 提起 (problem first raised)\n"
    "   - 分析 (investigation / hypothesis / root-cause work)\n"
    "   - 決定 (a decision was made — including 'rejected hypothesis')\n"
    "   - 実装 (something was built / applied)\n"
    "   - 再発 (the problem reappeared after seeming resolved)\n"
    "   - 未解決 (the problem is still open at the time of this event)\n"
    "4. `latest_state` is:\n"
    "   - 'resolved' if the latest event in the timeline is 決定 or 実装 marking closure\n"
    "   - 'open' otherwise\n"
    "5. Events that don't clearly belong to any cluster go into `unclassified_events`.\n"
    "6. Each cluster gets a short `title` (≤80 chars) summarizing the underlying problem.\n"
    "7. `latest_summary` is 1-2 sentences describing the current state, citing the latest event.\n\n"
    "Output JSON: {\n"
    '  "problems": [\n'
    '    {\n'
    '      "title": "<≤80 chars>",\n'
    '      "timeline": [\n'
    '        {"event_idx": <int, the index into the input EVENTS list>,\n'
    '         "kind": "提起|分析|決定|実装|再発|未解決"}\n'
    '      ],\n'
    '      "latest_state": "open|resolved",\n'
    '      "latest_summary": "<1-2 sentences>"\n'
    '    }\n'
    '  ],\n'
    '  "unclassified_event_indices": [<int>, ...]\n'
    "}"
)


def _format_events_for_prompt(events: list[dict[str, Any]]) -> str:
    """Format events as a numbered list for gemma to reference by index."""
    lines: list[str] = []
    for i, ev in enumerate(events):
        date_short = (ev.get("date") or "")[:10]
        lens = ev.get("lens", "?")
        title = (ev.get("title") or "").strip()
        summary = (ev.get("summary") or "").strip()
        doc = ev.get("doc", "?")
        lines.append(f"[{i}] ({date_short} {lens} {doc}) {title}")
        lines.append(f"    {summary}")
    return "\n".join(lines)


def _make_problem_id(title: str, indices: list[int]) -> str:
    """Stable id from normalized title + first index. Re-runs may differ if title shifts."""
    norm = re.sub(r"\s+", " ", title.lower())[:80]
    h = hashlib.sha1((norm + "\x1f" + str(sorted(indices)[:3])).encode("utf-8")).hexdigest()
    return h[:8]


async def _call_consolidate(events: list[dict[str, Any]]) -> dict[str, Any]:
    events_block = _format_events_for_prompt(events)
    task = (
        _CONSOLIDATE_PROMPT
        + "\n\n--- EVENTS (numbered, reference by index) ---\n"
        + events_block
        + "\n\nReturn ONLY the JSON object."
    )
    max_tokens = int(os.environ.get("PROBLEMS_CONSOLIDATE_MAX_TOKENS", "8192"))
    res = await gemma_subagent(task=task, kind="list", inputs=[], max_tokens=max_tokens)
    if res.get("status") != "ok":
        raise RuntimeError(f"consolidate gemma error: {res.get('error')}")
    data = res.get("data") or {}
    if not isinstance(data, dict):
        raise RuntimeError("consolidate returned non-object JSON")
    return data


def _build_timeline(
    *,
    cluster: dict[str, Any],
    events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[int]]:
    """Materialize a cluster's timeline entries from event indices. Sort by date."""
    raw_tl = cluster.get("timeline") or []
    entries: list[dict[str, Any]] = []
    used: list[int] = []
    for item in raw_tl:
        if not isinstance(item, dict):
            continue
        idx = item.get("event_idx")
        kind = item.get("kind") or "未解決"
        if not isinstance(idx, int) or idx < 0 or idx >= len(events):
            continue
        ev = events[idx]
        entries.append({
            "date": ev.get("date"),
            "doc": ev.get("doc"),
            "lens": ev.get("lens"),
            "kind": kind,
            "title": ev.get("title"),
            "summary": ev.get("summary"),
            "line_hint": ev.get("line_hint"),
        })
        used.append(idx)
    entries.sort(key=lambda e: e.get("date") or "")
    return entries, used


async def _consolidate_one_batch(
    events: list[dict[str, Any]], offset: int = 0
) -> tuple[list[dict[str, Any]], set[int]]:
    """Run B on one batch. Returns (problems_with_local_indices, used_local_indices).

    `offset` is added back to indices when merging across batches.
    """
    raw = await _call_consolidate(events)
    problems_raw = raw.get("problems") or []

    out_problems: list[dict[str, Any]] = []
    all_used: set[int] = set()
    for cluster in problems_raw:
        if not isinstance(cluster, dict):
            continue
        title = str(cluster.get("title", "")).strip()[:120]
        timeline, used = _build_timeline(cluster=cluster, events=events)
        if not timeline:
            continue
        latest_state = str(cluster.get("latest_state", "open")).lower()
        if latest_state not in ("open", "resolved"):
            latest_state = "open"
        latest_summary = str(cluster.get("latest_summary", "")).strip()
        # Track used indices with offset for cross-batch dedup
        offset_used = [u + offset for u in used]
        out_problems.append({
            "problem_id": _make_problem_id(title or timeline[0]["summary"][:60], offset_used),
            "title": title or timeline[0]["title"] or timeline[0]["summary"][:60],
            "timeline": timeline,
            "latest_state": latest_state,
            "latest_summary": latest_summary,
            "code_evidence": [],
            "discrepancy_analysis": None,
            "_used_indices_global": offset_used,
        })
        all_used.update(offset_used)
    return out_problems, all_used


def _merge_similar_problems(problems: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge clusters whose titles are similar (≥_MERGE_SIMILARITY)."""
    merged: list[dict[str, Any]] = []
    used_idx: set[int] = set()
    for i, p in enumerate(problems):
        if i in used_idx:
            continue
        cluster_title = p["title"].lower()
        bucket = [p]
        for j in range(i + 1, len(problems)):
            if j in used_idx:
                continue
            other_title = problems[j]["title"].lower()
            ratio = SequenceMatcher(None, cluster_title, other_title).ratio()
            if ratio >= _MERGE_SIMILARITY:
                bucket.append(problems[j])
                used_idx.add(j)
        if len(bucket) == 1:
            merged.append(p)
            continue
        # Merge: concatenate timelines (sort by date), pick title from first
        all_events: list[dict[str, Any]] = []
        all_used_global: list[int] = []
        for b in bucket:
            all_events.extend(b["timeline"])
            all_used_global.extend(b.get("_used_indices_global", []))
        all_events.sort(key=lambda e: e.get("date") or "")
        # Prefer latest_state across bucket: open > resolved (anything still open wins)
        any_open = any(b.get("latest_state") == "open" for b in bucket)
        latest = bucket[-1]
        merged_p = {
            "problem_id": _make_problem_id(p["title"], sorted(set(all_used_global))[:3]),
            "title": p["title"],
            "timeline": all_events,
            "latest_state": "open" if any_open else latest.get("latest_state", "resolved"),
            "latest_summary": latest.get("latest_summary", ""),
            "code_evidence": [],
            "discrepancy_analysis": None,
            "_used_indices_global": all_used_global,
        }
        merged.append(merged_p)
    return merged


async def consolidate(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Run gemma B and materialize per-problem timelines.

    If events > _BATCH_SIZE, split into batches, run consolidate per batch in
    parallel, then merge similar problems across batches by title similarity.
    """
    if not events:
        return {
            "problems": [],
            "unclassified_events": [],
            "stats": {"events_in": 0, "problems_out": 0, "unclassified": 0, "batches": 0},
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        }

    n = len(events)
    if n <= _BATCH_SIZE:
        batches = [(events, 0)]
    else:
        batches = []
        for i in range(0, n, _BATCH_SIZE):
            batches.append((events[i:i + _BATCH_SIZE], i))
    logger.info("consolidate: %d events → %d batches", n, len(batches))

    # Run all batches in parallel
    sem = asyncio.Semaphore(int(os.environ.get("PROBLEMS_CONSOLIDATE_CONCURRENCY", "3")))

    async def one(batch: list[dict[str, Any]], offset: int):
        async with sem:
            return await _consolidate_one_batch(batch, offset)

    results = await asyncio.gather(*[one(b, o) for b, o in batches], return_exceptions=True)

    all_problems: list[dict[str, Any]] = []
    all_used: set[int] = set()
    for r in results:
        if isinstance(r, BaseException):
            logger.warning("consolidate batch failed: %s", r)
            continue
        probs, used = r  # type: ignore[misc]
        all_problems.extend(probs)
        all_used.update(used)

    # Merge near-duplicate problems across batches.
    # If multiple batches AND gemma-merge enabled, use 1 extra gemma call.
    # Else fall back to title-similarity (cheap, less accurate).
    if len(batches) > 1:
        if _MERGE_VIA_GEMMA:
            try:
                merged = await _gemma_merge_problems(all_problems)
            except Exception as e:
                logger.warning("gemma merge raised: %s — falling back to title similarity", e)
                merged = _merge_similar_problems(all_problems)
        else:
            merged = _merge_similar_problems(all_problems)
    else:
        merged = all_problems

    # Strip internal fields
    for p in merged:
        p.pop("_used_indices_global", None)
        p.pop("_merged_from", None)

    unclass_idxs = sorted(i for i in range(n) if i not in all_used)
    unclassified = [events[i] for i in unclass_idxs]

    return {
        "problems": merged,
        "unclassified_events": unclassified,
        "stats": {
            "events_in": n,
            "problems_out": len(merged),
            "unclassified": len(unclassified),
            "batches": len(batches),
        },
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }


__all__ = ["consolidate"]
