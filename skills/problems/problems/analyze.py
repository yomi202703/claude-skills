"""Stage D: analyze why doc and code disagree (only for discrepancy-flagged problems).

For each problem with latest_state='discrepancy', call gemma to classify the
root cause and write an explanation. Adds `discrepancy_analysis` text + a
synthetic 解説 event to the timeline.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from improver.execute.gemma_subagent import gemma_subagent

logger = logging.getLogger(__name__)


_ANALYZE_PROMPT = (
    "The following PROBLEMS are flagged as 'discrepancy' — the docs and the code "
    "give different signals about whether they are resolved.\n\n"
    "For each problem, analyze WHY they disagree. Classify the root cause as one of:\n"
    "  - 'doc_stale': code has the fix but doc was never updated\n"
    "  - 'doc_optimistic': doc claims resolution but no code trace exists\n"
    "  - 'partial_fix': code partially addresses but doc still lists open\n"
    "  - 'unrelated_evidence': the ripgrep hits are for unrelated usage\n"
    "  - 'ambiguous': insufficient signal to decide\n"
    "Write a 1-3 sentence explanation citing what you saw in the timeline and "
    "code evidence.\n\n"
    "Output JSON: {\n"
    '  "analyses": [\n'
    '    {"problem_id": "<str>", "root_cause": "<one of the labels above>",\n'
    '     "explanation": "<1-3 sentences>"}\n'
    "  ]\n"
    "}"
)


def _format_problem(prob: dict[str, Any]) -> str:
    lines = [f"PROBLEM_ID: {prob['problem_id']}",
             f"TITLE: {prob['title']}",
             f"FLAGGED_STATE: {prob.get('latest_state')}",
             "TIMELINE:"]
    for ev in prob["timeline"]:
        date = (ev.get("date") or "")[:10]
        kind = ev.get("kind", "?")
        summ = (ev.get("summary") or "").strip()
        lines.append(f"  - [{date}] ({kind}) {summ}")
    lines.append("CODE_EVIDENCE:")
    if not prob.get("code_evidence"):
        lines.append("  (none)")
    else:
        for ev in prob["code_evidence"]:
            lines.append(f"  - {ev['file']}:{ev['line']}  ref=`{ev['ref']}`  {ev['snippet']}")
    return "\n".join(lines)


async def _call_analyze(discrepancy_problems: list[dict[str, Any]]) -> dict[str, Any]:
    blocks = [_format_problem(p) for p in discrepancy_problems]
    task = (
        _ANALYZE_PROMPT
        + "\n\n--- DISCREPANCY PROBLEMS ---\n"
        + "\n\n".join(blocks)
        + "\n\nReturn ONLY the JSON object."
    )
    max_tokens = int(os.environ.get("PROBLEMS_ANALYZE_MAX_TOKENS", "3072"))
    res = await gemma_subagent(task=task, kind="list", inputs=[], max_tokens=max_tokens)
    if res.get("status") != "ok":
        raise RuntimeError(f"analyze gemma error: {res.get('error')}")
    data = res.get("data") or {}
    if not isinstance(data, dict):
        raise RuntimeError("analyze returned non-object JSON")
    return data


async def analyze(c_output: dict[str, Any]) -> dict[str, Any]:
    """Stage D entry. Augments discrepancy-flagged problems with root-cause analysis."""
    problems = c_output.get("problems") or []
    discrepancy = [p for p in problems if p.get("latest_state") == "discrepancy"]
    if not discrepancy:
        return {**c_output, "analyzed_at": datetime.now(tz=timezone.utc).isoformat()}

    try:
        raw = await _call_analyze(discrepancy)
    except Exception as e:
        logger.warning("analyze gemma call failed: %s — leaving discrepancies unanalyzed", e)
        return {**c_output, "analyzed_at": datetime.now(tz=timezone.utc).isoformat()}

    analyses_by_id: dict[str, dict[str, Any]] = {}
    for a in raw.get("analyses") or []:
        if isinstance(a, dict) and a.get("problem_id"):
            analyses_by_id[a["problem_id"]] = a

    out_problems: list[dict[str, Any]] = []
    now_iso = datetime.now(tz=timezone.utc).isoformat()
    for prob in problems:
        if prob.get("latest_state") != "discrepancy":
            out_problems.append(prob)
            continue
        a = analyses_by_id.get(prob["problem_id"])
        if not a:
            out_problems.append(prob)
            continue
        root = str(a.get("root_cause", "ambiguous"))
        expl = str(a.get("explanation", "")).strip()
        new_prob = {**prob, "discrepancy_analysis": {"root_cause": root, "explanation": expl}}
        new_prob["timeline"] = list(new_prob["timeline"]) + [{
            "date": now_iso,
            "doc": "(analyze stage)",
            "lens": "analyze",
            "kind": "解説",
            "title": f"discrepancy: {root}",
            "summary": expl,
            "line_hint": None,
        }]
        out_problems.append(new_prob)

    return {
        **c_output,
        "problems": out_problems,
        "analyzed_at": now_iso,
    }


__all__ = ["analyze"]
