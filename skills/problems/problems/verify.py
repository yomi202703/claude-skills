"""Stage C: verify each problem against actual code/state.

For each problem from stage B:
1. Extract referenced symbols/files (from backtick-quoted tokens in timeline)
2. ripgrep them against the repo to see what actually exists
3. Send (timeline + code_evidence) to gemma → confirm latest_state, flag discrepancies

Output augments each problem with `code_evidence[]` and may flip
`latest_state` to "discrepancy" when doc and code disagree.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from improver.execute.gemma_subagent import gemma_subagent

logger = logging.getLogger(__name__)

_BACKTICK_TOKEN_RE = re.compile(r"`([^`\n]{2,100})`")
_PATH_LIKE_RE = re.compile(r"^[A-Za-z0-9_\-./]+\.(py|md|yaml|yml|sql|sh|tsv|json|toml|js|ts)(:\d+)?$")
_SYMBOL_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{2,80}$")


def _extract_refs(timeline: list[dict[str, Any]]) -> list[str]:
    """Pull backtick-quoted tokens that look like paths or symbols from timeline."""
    refs: list[str] = []
    seen: set[str] = set()
    for ev in timeline:
        text = (ev.get("summary") or "") + " " + (ev.get("title") or "")
        for tok in _BACKTICK_TOKEN_RE.findall(text):
            tok = tok.strip()
            if not tok or tok in seen:
                continue
            # path-like or symbol-like
            base = tok.split(":")[0]
            if _PATH_LIKE_RE.match(tok) or _SYMBOL_RE.match(base):
                seen.add(tok)
                refs.append(tok)
    return refs[:8]  # cap refs per problem


def _ripgrep(repo: Path, token: str, *, max_hits: int = 5) -> list[dict[str, Any]]:
    """Run ripgrep for token. Returns list of {file, line, snippet}."""
    if shutil.which("rg") is None:
        return []
    base = token.split(":")[0]
    pattern = re.escape(base)
    try:
        res = subprocess.run(
            ["rg", "-n", "--no-heading", "--max-count", str(max_hits),
             "--max-filesize", "500K", pattern, str(repo)],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    hits: list[dict[str, Any]] = []
    for line in (res.stdout or "").splitlines()[:max_hits]:
        # format: <file>:<line>:<snippet>
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        file_, ln_str, snippet = parts
        try:
            ln = int(ln_str)
        except ValueError:
            continue
        try:
            rel = str(Path(file_).resolve().relative_to(repo))
        except ValueError:
            rel = file_
        hits.append({"file": rel, "line": ln, "snippet": snippet.strip()[:160]})
    return hits


def _build_code_evidence(repo: Path, problems: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """For each problem, collect ripgrep results. Returns {problem_id: [evidence]}."""
    out: dict[str, list[dict[str, Any]]] = {}
    for prob in problems:
        refs = _extract_refs(prob["timeline"])
        evidence: list[dict[str, Any]] = []
        for ref in refs:
            hits = _ripgrep(repo, ref)
            for h in hits:
                evidence.append({"ref": ref, "file": h["file"], "line": h["line"], "snippet": h["snippet"]})
        out[prob["problem_id"]] = evidence[:15]  # cap total per problem
    return out


_VERIFY_PROMPT = (
    "You are verifying whether each PROBLEM listed below is actually still open "
    "or has been resolved, based on:\n"
    "  - the problem's TIMELINE (events extracted from docs)\n"
    "  - CODE EVIDENCE (ripgrep hits for symbols/files mentioned in the timeline)\n\n"
    "For each problem, decide:\n"
    "  - 'open': the problem is still active, doc and code agree it's not resolved\n"
    "  - 'resolved': the problem is solved, doc and code agree\n"
    "  - 'discrepancy': doc and code DISAGREE\n"
    "      e.g. doc says 'still open' but the referenced symbol exists in code with a fix\n"
    "      e.g. doc says 'decided to do X' but no trace of X in code\n\n"
    "Also return a short `verification_note` (1-2 sentences) citing what you saw.\n\n"
    "NOTE: do NOT classify blocking/escalation here — that is the `/constraints` skill's job.\n\n"
    "Output JSON: {\n"
    '  "verdicts": [\n'
    '    {"problem_id": "<str>", "latest_state": "open|resolved|discrepancy",\n'
    '     "verification_note": "<short>"}\n'
    "  ]\n"
    "}"
)


def _format_problem_for_verify(prob: dict[str, Any], evidence: list[dict[str, Any]]) -> str:
    lines = [f"PROBLEM_ID: {prob['problem_id']}",
             f"TITLE: {prob['title']}",
             f"TENTATIVE_LATEST_STATE: {prob.get('latest_state', '?')}",
             "TIMELINE:"]
    for ev in prob["timeline"]:
        date = (ev.get("date") or "")[:10]
        kind = ev.get("kind", "?")
        doc = ev.get("doc", "?")
        summ = (ev.get("summary") or "").strip()
        lines.append(f"  - [{date}] ({kind}) {doc}")
        lines.append(f"      {summ}")
    lines.append("CODE_EVIDENCE:")
    if not evidence:
        lines.append("  (none — no referenced symbols found in code)")
    else:
        for ev in evidence:
            lines.append(f"  - {ev['file']}:{ev['line']}  [ref=`{ev['ref']}`]  {ev['snippet']}")
    return "\n".join(lines)


async def _call_verify(problems: list[dict[str, Any]], evidence_map: dict[str, list]) -> dict[str, Any]:
    blocks = [_format_problem_for_verify(p, evidence_map.get(p["problem_id"], [])) for p in problems]
    task = (
        _VERIFY_PROMPT
        + "\n\n--- PROBLEMS ---\n"
        + "\n\n".join(blocks)
        + "\n\nReturn ONLY the JSON object."
    )
    max_tokens = int(os.environ.get("PROBLEMS_VERIFY_MAX_TOKENS", "4096"))
    res = await gemma_subagent(task=task, kind="list", inputs=[], max_tokens=max_tokens)
    if res.get("status") != "ok":
        raise RuntimeError(f"verify gemma error: {res.get('error')}")
    data = res.get("data") or {}
    if not isinstance(data, dict):
        raise RuntimeError("verify returned non-object JSON")
    return data


async def verify(repo: str | Path, b_output: dict[str, Any]) -> dict[str, Any]:
    """Stage C entry. Augments problems with code_evidence and confirmed latest_state.

    Returns same shape as input b_output but with augmented `problems`.
    """
    repo_path = Path(repo).resolve()
    problems = b_output.get("problems") or []
    if not problems:
        return {**b_output, "verified_at": datetime.now(tz=timezone.utc).isoformat()}

    # 1. ripgrep refs from each problem's timeline (synchronous, fast)
    loop = asyncio.get_event_loop()
    evidence_map = await loop.run_in_executor(None, _build_code_evidence, repo_path, problems)

    # 2. one gemma call to confirm/flip latest_state
    try:
        verdict_data = await _call_verify(problems, evidence_map)
    except Exception as e:
        logger.warning("verify gemma call failed: %s — keeping tentative states", e)
        verdict_data = {"verdicts": []}

    verdicts_by_id: dict[str, dict[str, Any]] = {}
    for v in verdict_data.get("verdicts") or []:
        if isinstance(v, dict) and v.get("problem_id"):
            verdicts_by_id[v["problem_id"]] = v

    out_problems: list[dict[str, Any]] = []
    for prob in problems:
        pid = prob["problem_id"]
        evidence = evidence_map.get(pid, [])
        new_prob = {**prob, "code_evidence": evidence}
        v = verdicts_by_id.get(pid)
        if v:
            state = str(v.get("latest_state", prob.get("latest_state", "open"))).lower()
            if state not in ("open", "resolved", "discrepancy"):
                state = prob.get("latest_state", "open")
            new_prob["latest_state"] = state
            note = str(v.get("verification_note", "")).strip()
            if note:
                # append as a synthetic timeline event
                new_prob["timeline"] = list(new_prob["timeline"]) + [{
                    "date": datetime.now(tz=timezone.utc).isoformat(),
                    "doc": "(verify stage)",
                    "lens": "verify",
                    "kind": "解説",
                    "title": "verification note",
                    "summary": note,
                    "line_hint": None,
                }]
        out_problems.append(new_prob)

    return {
        **b_output,
        "problems": out_problems,
        "verified_at": datetime.now(tz=timezone.utc).isoformat(),
    }


__all__ = ["verify"]
