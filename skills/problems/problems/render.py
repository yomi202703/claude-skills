"""Render problems.json → human-readable markdown.

Grouping strategy (case A, no data merge):
  - Data preserves every problem as-is (no consolidation across batches)
  - Render-side groups problems by shared tokens (F-numbers, key domain terms)
  - Each group lists its members; singletons go to a final section
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any


_STATE_BADGE = {
    "open": "🔴 open",
    "resolved": "✅ resolved",
    "discrepancy": "⚠️  discrepancy",
}

# Topic anchors for grouping. All F-numbers collapse to one "Field definition" family
# (members are still distinct problems, this just controls the display section).
# Matched against TITLE only (summary causes false positives like "daily activity reports"
# being mentioned in a Solicitor-Chart-Sync problem).
_TOPIC_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Field definition", re.compile(r"\bF\d{2,3}\b")),
    ("OCR",              re.compile(r"\bOCR\b", re.IGNORECASE)),
    ("並列パイプライン",  re.compile(r"並列|Parallel\b", re.IGNORECASE)),
    ("集合研修",          re.compile(r"集合研修|group training", re.IGNORECASE)),
    ("名寄せ・紐付け",     re.compile(r"名寄せ|matching|name normalization", re.IGNORECASE)),
    ("Schema/スキーマ",   re.compile(r"\bschema\b|スキーマ", re.IGNORECASE)),
    ("Chunking",         re.compile(r"chunk(?:ing)?|チャンク", re.IGNORECASE)),
    ("Hallucination",    re.compile(r"hallucin|phantom", re.IGNORECASE)),
    ("日報・記述品質",     re.compile(r"activity report|日報|report description|reporter\b", re.IGNORECASE)),
    ("Ground Truth/検証", re.compile(r"ground truth|\bGT\b|validation dataset", re.IGNORECASE)),
    ("要件定義",          re.compile(r"requirement|要件", re.IGNORECASE)),
    ("Solicitor Chart",  re.compile(r"solicitor|recruiter chart|募集人カルテ", re.IGNORECASE)),
    ("MS Primary (他案件)", re.compile(r"MS Primary|MSプライマリー", re.IGNORECASE)),
    ("Audio data",       re.compile(r"\baudio\b|音声", re.IGNORECASE)),
    ("AI bias",          re.compile(r"AI bias|contamination|injection", re.IGNORECASE)),
]


def _topic_anchors(title: str) -> list[str]:
    """Return list of topic anchor labels found in TITLE only (not summary).

    F-numbers all collapse to one "Field definition" anchor.
    """
    found: list[str] = []
    for label, pat in _TOPIC_PATTERNS:
        if pat.search(title or ""):
            found.append(label)
    return found


def _group_problems(problems: list[dict[str, Any]]) -> tuple[
    list[tuple[str, list[dict[str, Any]]]],  # named groups
    list[dict[str, Any]],                     # singletons
]:
    """Group problems by shared anchor. A problem joins the FIRST anchor it shares with another.

    Returns (groups, singletons) where:
      groups: list of (group_label, members) for groups with 2+ members
      singletons: problems with no shared anchor with any other problem
    """
    # 1. Compute anchors per problem (TITLE ONLY — summary causes false positives)
    anchors_per: dict[str, list[str]] = {}
    for p in problems:
        anchors_per[p["problem_id"]] = _topic_anchors(p.get("title", ""))

    # 2. Count how many problems mention each anchor
    anchor_count: dict[str, int] = defaultdict(int)
    for anchors in anchors_per.values():
        for a in anchors:
            anchor_count[a] += 1

    # 3. Assign each problem to its strongest shared anchor (highest count, anchor count ≥ 2)
    assigned: dict[str, str | None] = {}
    for pid, anchors in anchors_per.items():
        # filter to anchors shared with at least one other problem
        shared = [a for a in anchors if anchor_count[a] >= 2]
        if not shared:
            assigned[pid] = None
            continue
        # pick anchor with highest count (most "central"); ties broken by anchor order
        shared.sort(key=lambda a: (-anchor_count[a], anchors.index(a)))
        assigned[pid] = shared[0]

    # 4. Build group buckets.
    # Note: if two problems share the same problem_id (shouldn't happen but the
    # 8-char sha1 prefix has non-zero collision risk), the dict comprehension
    # would lose data. Detect and keep first-wins, log warning.
    by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    singletons: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for p in problems:
        pid = p["problem_id"]
        if pid in by_id:
            import logging
            logging.getLogger(__name__).warning(
                "duplicate problem_id %s — keeping first, dropping later (title=%s)",
                pid, p.get("title", "")[:60],
            )
            continue
        by_id[pid] = p
    for pid, label in assigned.items():
        if label is None:
            singletons.append(by_id[pid])
        else:
            by_label[label].append(by_id[pid])

    # 5. Sort group labels by member count desc, label asc
    groups = sorted(by_label.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    return groups, singletons


def _group_member_sort_key(prob: dict[str, Any]) -> tuple[int, float]:
    state_order = {"discrepancy": 0, "open": 1, "resolved": 2}
    return (state_order.get(prob.get("latest_state", "open"), 1), -_latest_date_score(prob))


def render_markdown(data: dict[str, Any]) -> str:
    problems = data.get("problems") or []
    unclassified = data.get("unclassified_events") or []
    stats = data.get("stats") or {}
    generated_at = data.get("generated_at") or data.get("analyzed_at") or data.get("verified_at") or ""

    lines: list[str] = []
    lines.append("# Problems")
    lines.append(f"_generated {generated_at}_")
    lines.append("")
    lines.append(
        f"**Stats**: {stats.get('problems_out', len(problems))} problems "
        f"({len([p for p in problems if p.get('latest_state')=='open'])} open / "
        f"{len([p for p in problems if p.get('latest_state')=='resolved'])} resolved / "
        f"{len([p for p in problems if p.get('latest_state')=='discrepancy'])} discrepancy), "
        f"{stats.get('events_in', 0)} events processed, "
        f"{len(unclassified)} unclassified."
    )
    lines.append("")

    # ===== Index / grouping overview =====
    groups, singletons = _group_problems(problems)
    if groups:
        lines.append("## Topic groups (display only — data is not merged)")
        for label, members in groups:
            lines.append(f"- **{label}** ({len(members)})")
            for p in sorted(members, key=_group_member_sort_key):
                pid = p["problem_id"]
                state = p.get("latest_state", "open")
                title = p.get("title", "")
                lines.append(f"  - `[{pid}]` _{state}_ {title}")
        if singletons:
            lines.append(f"- **Singletons** ({len(singletons)})")
            for p in sorted(singletons, key=_group_member_sort_key):
                pid = p["problem_id"]
                state = p.get("latest_state", "open")
                title = p.get("title", "")
                lines.append(f"  - `[{pid}]` _{state}_ {title}")
        lines.append("")

    # ===== Full per-problem detail (grouped order) =====
    lines.append("## Problem detail")
    lines.append("")
    ordered: list[tuple[str, dict[str, Any]]] = []  # (group_label, problem)
    for label, members in groups:
        for p in sorted(members, key=_group_member_sort_key):
            ordered.append((label, p))
    for p in sorted(singletons, key=_group_member_sort_key):
        ordered.append(("(singleton)", p))

    current_label: str | None = None
    for label, prob in ordered:
        if label != current_label:
            current_label = label
            lines.append(f"### Group: {label}")
            lines.append("")

        pid = prob.get("problem_id", "?")
        state = prob.get("latest_state", "open")
        badge = _STATE_BADGE.get(state, state)
        title = prob.get("title", "(no title)")
        lines.append(f"#### [{pid}] {title}")
        lines.append(f"_{badge}_")
        if prob.get("latest_summary"):
            lines.append("")
            lines.append(f"> {prob['latest_summary']}")
        lines.append("")

        # Timeline
        lines.append("**Timeline**:")
        for ev in prob.get("timeline", []):
            date = (ev.get("date") or "")[:10]
            kind = ev.get("kind", "?")
            doc = ev.get("doc", "?")
            lens = ev.get("lens", "?")
            summary = (ev.get("summary") or "").replace("\n", " ").strip()
            lines.append(f"- **{date}** _{kind}_ ({lens}) `{doc}`")
            lines.append(f"  - {summary}")
        lines.append("")

        ce = prob.get("code_evidence") or []
        if ce:
            lines.append("**Code evidence**:")
            for e in ce[:8]:
                lines.append(f"- `{e['file']}:{e['line']}` (ref `{e['ref']}`) — {e['snippet']}")
            if len(ce) > 8:
                lines.append(f"- _(... {len(ce)-8} more)_")
            lines.append("")

        da = prob.get("discrepancy_analysis")
        if da:
            lines.append("**Discrepancy**:")
            lines.append(f"- root_cause: `{da.get('root_cause', '?')}`")
            lines.append(f"- {da.get('explanation', '')}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # ===== Unclassified events (tail) =====
    if unclassified:
        unclass_cap = 30
        lines.append(f"## Unclassified events ({len(unclassified)})")
        lines.append("_These events did not cluster into any specific problem._")
        if len(unclassified) > unclass_cap:
            lines.append(
                f"_Showing first {unclass_cap}, {len(unclassified) - unclass_cap} more truncated._"
            )
        lines.append("")
        for ev in unclassified[:unclass_cap]:
            date = (ev.get("date") or "")[:10]
            lens = ev.get("lens", "?")
            doc = ev.get("doc", "?")
            title = ev.get("title", "")
            summary = (ev.get("summary") or "").replace("\n", " ").strip()
            lines.append(f"- **{date}** ({lens}) `{doc}` — {title}")
            lines.append(f"  - {summary}")
        if len(unclassified) > 30:
            lines.append(f"- _(... {len(unclassified)-30} more)_")
        lines.append("")

    return "\n".join(lines) + "\n"


def _latest_date_score(prob: dict[str, Any]) -> float:
    """For sort: epoch-like score from latest timeline entry."""
    tl = prob.get("timeline") or []
    if not tl:
        return 0.0
    last = tl[-1].get("date") or ""
    try:
        from datetime import datetime
        return datetime.fromisoformat(last.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return 0.0


__all__ = ["render_markdown"]
