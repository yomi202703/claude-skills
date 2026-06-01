"""Single gemma call to classify each problem's blocking_constraint.

Sees ALL problems + ALL escalation packages in one prompt so it can detect
cross-problem topic sharing (e.g. one escalation package covers F008/F009/F013
even if those are 3 separate problems in problems.json).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from improver.execute.gemma_subagent import gemma_subagent

from constraints.scan import read_package_excerpt  # noqa: F401

logger = logging.getLogger(__name__)


_PROMPT = (
    "You are classifying which PROBLEMS are currently BLOCKED on an external\n"
    "party (so we cannot work on them right now).\n\n"
    "Inputs:\n"
    "  - A list of PROBLEMS (id, title, recent timeline summary)\n"
    "  - A list of ESCALATION PACKAGES (recent docs prepared for external review:\n"
    "    '_<name>版_*.md' or meeting transcripts) with excerpts\n"
    "  - A list of RESPONSE CANDIDATES (docs dated AFTER any escalation package\n"
    "    that contain response-language like '決定しました', 'ご回答', 'approved').\n"
    "    Use these to determine if an escalation has been ACKNOWLEDGED/RESPONDED.\n\n"
    "For each problem, decide ONE of:\n"
    "  - null                : we can work on it now (no escalation in flight)\n"
    "  - 'client_response'   : waiting on customer/client decision\n"
    "                          signal: topic appears in an escalation package's\n"
    "                                  'ご相談点' / 'ご確認いただきたい' / '客先で決定' section\n"
    "  - 'external_review'   : someone else (named person, not client) is working on it\n"
    "                          signal: '人手レビュー中', '<name>さん作業中', '依頼済', '回答待ち'\n\n"
    "AND set `ack`:\n"
    "  - true: a response candidate clearly addresses this problem's topic\n"
    "  - false: no response candidate found (or response doesn't address topic)\n"
    "  - null: kind is null (not blocked), so ack is N/A\n\n"
    "IMPORTANT: Use the escalation packages as the primary signal. A problem's\n"
    "title may match a topic in a package even if the problem's own timeline\n"
    "doesn't mention escalation (the package was prepared LATER than the\n"
    "problem's earliest timeline). Cross-reference by topic name.\n\n"
    "Example: if problem title says 'F008/F009 semantic overlap' and an\n"
    "escalation package's §5 lists 'F008/F009 統合判断' under 'ご相談点',\n"
    "classify as client_response with escalation_doc = that package.\n\n"
    "Do NOT classify as blocked if:\n"
    "  - problem is about postponement (we chose to defer) — that's a progress state, not a constraint\n"
    "  - problem is just 'open' with no escalation evidence\n"
    "  - escalation package mentions topic only as background, not as action item\n\n"
    "Output JSON: {\n"
    '  "classifications": [\n'
    '    {"problem_id": "<id>",\n'
    '     "kind": null | "client_response" | "external_review",\n'
    '     "owner": "<name|client|external>" (omit if kind=null),\n'
    '     "since": "YYYY-MM-DD" (escalation doc date; omit if kind=null),\n'
    '     "escalation_doc": "<path from package list>" (omit if kind=null),\n'
    '     "evidence_quote": "<verbatim ≤200 chars from package>" (omit if kind=null),\n'
    '     "ack": true | false | null,\n'
    '     "ack_doc": "<path from response candidates>" | null (only if ack=true)\n'
    "    }\n"
    "  ]\n"
    "}\n\n"
    "MUST return an entry for EVERY problem listed above, including ones with kind=null.\n"
    "The output `classifications` array length MUST equal the input PROBLEMS list length.\n"
    "Do not skip problems — null is a valid, expected verdict for actionable problems."
)


def _format_problems(problems: list[dict[str, Any]]) -> str:
    lines = ["PROBLEMS:"]
    for p in problems:
        pid = p.get("problem_id", "?")
        title = p.get("title", "")
        latest = (p.get("latest_summary") or "").strip()[:200]
        state = p.get("latest_state", "?")
        lines.append(f"- [{pid}] ({state}) {title}")
        if latest:
            lines.append(f"    latest: {latest}")
    return "\n".join(lines)


def _format_packages(repo: str, packages: list[dict[str, Any]], *, max_packages: int = 8) -> str:
    """Show up to N most recent packages with excerpts."""
    lines = ["ESCALATION PACKAGES (most recent first):"]
    for pkg in packages[:max_packages]:
        path = pkg["path"]
        owner = pkg.get("owner") or "-"
        date = pkg.get("date") or "?"
        kind = pkg.get("kind")
        excerpt = read_package_excerpt(repo, path, max_chars=6000)
        lines.append(f"\n--- {path}  [{kind}, owner={owner}, date={date}] ---")
        lines.append(excerpt)
    if len(packages) > max_packages:
        lines.append(f"\n_(... {len(packages)-max_packages} older packages not shown)_")
    return "\n".join(lines)


def _format_responses(responses: list[dict[str, Any]]) -> str:
    if not responses:
        return "RESPONSE CANDIDATES: (none — no later docs with response-language found)"
    lines = ["RESPONSE CANDIDATES (docs dated after escalation containing response-language):"]
    for r in responses[:10]:
        lines.append(f"\n--- {r['path']} (date={r['date']}, matched=\"{r['matched_keyword']}\") ---")
        lines.append(r["excerpt"][:800])
    return "\n".join(lines)


def _days_ago(date_iso: str | None) -> int | None:
    if not date_iso:
        return None
    try:
        dt = datetime.strptime(date_iso, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return (datetime.now(tz=timezone.utc) - dt).days


async def classify_constraints(
    repo: str,
    problems: list[dict[str, Any]],
    packages: list[dict[str, Any]],
    responses: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """One gemma call → per-problem constraint judgment."""
    if not problems:
        return {"constraints": [], "escalation_packages_found": packages,
                "response_candidates_found": responses or [],
                "generated_at": datetime.now(tz=timezone.utc).isoformat()}

    # Only consider open / discrepancy problems (resolved problems aren't blocked)
    candidates = [p for p in problems if p.get("latest_state") != "resolved"]

    task = (
        _PROMPT
        + "\n\n"
        + _format_packages(repo, packages)
        + "\n\n"
        + _format_responses(responses or [])
        + "\n\n"
        + _format_problems(candidates)
        + "\n\nReturn ONLY the JSON object."
    )

    max_tokens = int(os.environ.get("CONSTRAINTS_MAX_TOKENS", "6144"))
    res = await gemma_subagent(task=task, kind="list", inputs=[], max_tokens=max_tokens)
    if res.get("status") != "ok":
        raise RuntimeError(f"constraints gemma error: {res.get('error')}")
    data = res.get("data") or {}
    if not isinstance(data, dict):
        raise RuntimeError("constraints returned non-object JSON")

    out: list[dict[str, Any]] = []
    for c in data.get("classifications") or []:
        if not isinstance(c, dict) or not c.get("problem_id"):
            continue
        kind = c.get("kind")
        if kind not in ("client_response", "external_review", None):
            continue
        entry: dict[str, Any] = {"problem_id": c["problem_id"], "kind": kind}
        if kind is not None:
            entry["owner"] = str(c.get("owner") or "?")[:40]
            entry["since"] = str(c.get("since") or "")[:10] or None
            entry["escalation_doc"] = c.get("escalation_doc")
            entry["evidence_quote"] = str(c.get("evidence_quote") or "")[:200]
            entry["last_sent_days_ago"] = _days_ago(entry["since"])
            ack_raw = c.get("ack")
            entry["ack"] = bool(ack_raw) if ack_raw in (True, False) else None
            entry["ack_doc"] = c.get("ack_doc") if entry["ack"] else None
        out.append(entry)

    return {
        "constraints": out,
        "escalation_packages_found": packages,
        "response_candidates_found": responses or [],
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }


__all__ = ["classify_constraints"]
