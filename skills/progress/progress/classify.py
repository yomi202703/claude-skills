"""Single gemma call to classify each problem's progress status.

Inputs: problems + optional constraints + git log + artifact dirs.
Output: per-problem {status, evidence_quote, evidence_source, completion_date, reason}.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from improver.execute.gemma_subagent import gemma_subagent

logger = logging.getLogger(__name__)


_PROMPT = (
    "You are classifying the PROGRESS STATUS of each PROBLEM listed below.\n\n"
    "Inputs:\n"
    "  - PROBLEMS (id, title, latest_state, recent timeline summary)\n"
    "  - GIT LOG (last N commits — hash, date, subject)\n"
    "  - ARTIFACT DIRS (non-empty output/build directories that exist in repo)\n"
    "  - CONSTRAINTS (optional — problems already classified as blocked by /constraints)\n\n"
    "For each problem, choose EXACTLY ONE status:\n\n"
    "  - 'done':\n"
    "      Implementation/decision completed.\n"
    "      Signals: '実装完了', '✓ resolved', '完了', 'fixed', git commit explicitly\n"
    "      referencing the problem, artifact file/dir exists for it.\n"
    "      Use when latest_state=resolved AND there is concrete completion evidence.\n\n"
    "  - 'undone':\n"
    "      Still active, we can work on it now (= pure actionable backlog).\n"
    "      DEFAULT for open problems with no special signal.\n\n"
    "  - 'dropped':\n"
    "      Explicitly decided NOT to do, permanently.\n"
    "      Signals: '対象外', 'やらない', '棄却', '廃止', 'won\\'t fix'.\n"
    "      Must be STRONG explicit decision, not just lowered priority.\n\n"
    "  - 'deferred':\n"
    "      We INTENTIONALLY lowered priority but might come back.\n"
    "      Signals: '優先度を下げ', '後回し', '保留', '次フェーズ', '現時点では着手しない'.\n"
    "      Distinguish from 'dropped' (permanent) and 'undone' (no signal).\n"
    "      Distinguish from 'pending_escalation' (we plan to ask, not we plan to wait).\n\n"
    "  - 'superseded':\n"
    "      Replaced by a different approach.\n"
    "      Signals: 'v1 → v2', '<old method> から <new method> へ移行',\n"
    "      'これに代わって <X> を採用'.\n\n"
    "  - 'pending_escalation':\n"
    "      WE intend to escalate to client/external but NO formal escalation\n"
    "      package has been sent yet. The problem is 'we want to ask but haven't asked'.\n"
    "      Signals: '次回 MTG で論点', '要件定義打合せでご相談する', '客先で確認する予定',\n"
    "      '要件定義の最優先論点として確定'\n"
    "      Distinguish from /constraints (which tracks ALREADY-SENT escalations).\n\n"
    "JUDGMENT RULES:\n"
    "- Be conservative. Default to 'undone' if signal is weak.\n"
    "- 'dropped' requires explicit decision language, not vague mention.\n"
    "- 'pending_escalation' requires explicit intent-to-escalate language. If the\n"
    "  problem is ALREADY blocked by /constraints, you may still classify as\n"
    "  pending_escalation if applicable, but 'undone' is also fine — they overlap.\n"
    "- If latest_state=='resolved' but no concrete completion evidence in git/artifacts,\n"
    "  classify as 'done' anyway (trust /problems verify stage).\n"
    "- If latest_state=='discrepancy', classify as 'undone' (the conflict needs resolution).\n"
    "- evidence_quote: verbatim from timeline summary, git commit subject, or doc reference (≤200 chars).\n"
    "- evidence_source: doc path, commit hash, or artifact dir path.\n"
    "- completion_date: ISO date if applicable (commit date / artifact mtime / decision date).\n"
    "- reason: one-line plain-language explanation.\n\n"
    "Output JSON: {\n"
    '  "progress": [\n'
    '    {"problem_id": "<id>",\n'
    '     "status": "done|undone|dropped|deferred|superseded|pending_escalation",\n'
    '     "evidence_quote": "<verbatim ≤200 chars>",\n'
    '     "evidence_source": "<doc|commit|dir>",\n'
    '     "completion_date": "YYYY-MM-DD" | null,\n'
    '     "reason": "<one line>"}\n'
    "  ]\n"
    "}\n\n"
    "MUST return an entry for EVERY problem listed. Length of `progress` array == length of PROBLEMS input."
)


def _format_problems(problems: list[dict[str, Any]]) -> str:
    lines = ["PROBLEMS:"]
    for p in problems:
        pid = p.get("problem_id", "?")
        title = p.get("title", "")
        state = p.get("latest_state", "?")
        latest = (p.get("latest_summary") or "").strip()[:200]
        lines.append(f"- [{pid}] ({state}) {title}")
        if latest:
            lines.append(f"    latest: {latest}")
    return "\n".join(lines)


def _format_git_log(commits: list[dict[str, str]]) -> str:
    if not commits:
        return "GIT LOG: (not a git repo or empty)"
    lines = ["GIT LOG (most recent first):"]
    for c in commits[:50]:
        lines.append(f"  {c['hash']}  {c['date']}  {c['subject']}")
    return "\n".join(lines)


def _format_artifacts(dirs: list[str]) -> str:
    if not dirs:
        return "ARTIFACT DIRS: (none found)"
    return "ARTIFACT DIRS (non-empty):\n" + "\n".join(f"  {d}" for d in dirs[:30])


def _format_decision_docs(docs: list[dict[str, str]]) -> str:
    if not docs:
        return "DECISION DOCS: (no docs with decision-language found)"
    lines = ["DECISION DOCS (docs containing dropped/defer/escalate-intent language):"]
    for d in docs[:15]:
        lines.append(f"\n--- {d['path']} (date={d.get('date') or '?'}, matched=\"{d['matched_keyword']}\") ---")
        lines.append(d["excerpt"][:1500])
    return "\n".join(lines)


def _format_constraints(constraints: list[dict[str, Any]] | None) -> str:
    if not constraints:
        return "CONSTRAINTS: (none — /constraints not run or no entries)"
    blocked = [c for c in constraints if c.get("kind")]
    if not blocked:
        return "CONSTRAINTS: (no blocked entries)"
    lines = ["CONSTRAINTS (already-blocked by /constraints):"]
    for c in blocked:
        pid = c["problem_id"]
        kind = c["kind"]
        lines.append(f"  [{pid}] {kind} (owner={c.get('owner', '?')})")
    return "\n".join(lines)


async def classify_progress(
    problems: list[dict[str, Any]],
    git_commits: list[dict[str, str]],
    artifact_dirs: list[str],
    constraints: list[dict[str, Any]] | None = None,
    decision_docs: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """One gemma call → per-problem progress status."""
    if not problems:
        return {"progress": [], "git_log_excerpt": git_commits,
                "artifact_dirs_found": artifact_dirs,
                "decision_docs_found": decision_docs or [],
                "generated_at": datetime.now(tz=timezone.utc).isoformat()}

    task = (
        _PROMPT + "\n\n"
        + _format_constraints(constraints) + "\n\n"
        + _format_git_log(git_commits) + "\n\n"
        + _format_artifacts(artifact_dirs) + "\n\n"
        + _format_decision_docs(decision_docs or []) + "\n\n"
        + _format_problems(problems) + "\n\nReturn ONLY the JSON object."
    )

    max_tokens = int(os.environ.get("PROGRESS_MAX_TOKENS", "6144"))
    res = await gemma_subagent(task=task, kind="list", inputs=[], max_tokens=max_tokens)
    if res.get("status") != "ok":
        raise RuntimeError(f"progress gemma error: {res.get('error')}")
    data = res.get("data") or {}
    if not isinstance(data, dict):
        raise RuntimeError("progress returned non-object JSON")

    valid_statuses = {"done", "undone", "dropped", "deferred", "superseded", "pending_escalation"}
    out: list[dict[str, Any]] = []
    for p in data.get("progress") or []:
        if not isinstance(p, dict) or not p.get("problem_id"):
            continue
        status = str(p.get("status") or "undone").lower()
        if status not in valid_statuses:
            status = "undone"
        out.append({
            "problem_id": p["problem_id"],
            "status": status,
            "evidence_quote": str(p.get("evidence_quote") or "")[:200],
            "evidence_source": str(p.get("evidence_source") or "")[:300],
            "completion_date": str(p.get("completion_date") or "")[:10] or None,
            "reason": str(p.get("reason") or "")[:200],
        })

    return {
        "progress": out,
        "git_log_excerpt": git_commits[:20],  # cap stored copy
        "artifact_dirs_found": artifact_dirs,
        "decision_docs_found": decision_docs or [],
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }


__all__ = ["classify_progress"]
