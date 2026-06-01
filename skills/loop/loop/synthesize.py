"""Briefing synthesis with evidence grounding.

Reads .loop/problems.json (required) and .loop/code_audit.json (optional)
from disk and produces a single evidence-grounded briefing. No in-process
calls to other skills — Claude Code is responsible for generating the
input files by invoking `problems` and `gemma-worker` separately.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from improver.execute.gemma_subagent import gemma_subagent

logger = logging.getLogger(__name__)

_EVIDENCE_ID_RE = re.compile(r"\[([A-Z]\d+(?:\s*,\s*[A-Z]\d+)*)\]")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。.!?])\s+|\n+")


def _trim(s: str, n: int) -> str:
    s = (s or "").strip().replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def _build_evidence_map(
    problems_data: dict[str, Any],
    code_audit_data: dict[str, Any] | None,
    limit: int,
) -> tuple[dict[str, dict], list[str]]:
    """ID convention:
        O{n} = open problem, D{n} = discrepancy problem, R{n} = recently resolved,
        A{n} = code audit artifact
    """
    evidence: dict[str, dict] = {}
    lines: list[str] = []

    def _add(prefix: str, snippet: str, **extra) -> str | None:
        if len(evidence) >= limit:
            return None
        idx = sum(1 for k in evidence if k.startswith(prefix)) + 1
        eid = f"{prefix}{idx}"
        entry = {"id": eid, "snippet": _trim(snippet, 120), **extra}
        evidence[eid] = entry
        lines.append(f"{eid}: {entry['snippet']}")
        return eid

    # Per-problem timeline from `problems` skill
    problems = problems_data.get("problems") or []
    state_order = {"discrepancy": 0, "open": 1, "resolved": 2}
    problems_sorted = sorted(problems, key=lambda p: state_order.get(p.get("latest_state", "open"), 1))

    problems_cap = 20
    for p in problems_sorted[:problems_cap]:
        state = p.get("latest_state", "open")
        prefix = "D" if state == "discrepancy" else ("R" if state == "resolved" else "O")
        latest_summary = p.get("latest_summary", "") or (p.get("title", ""))
        latest_date = ""
        tl = p.get("timeline") or []
        if tl:
            latest_date = (tl[-1].get("date") or "")[:10]
        _add(prefix,
             f"[{state}] {p.get('title','')} — {_trim(latest_summary, 90)} (latest {latest_date})",
             ref=p.get("problem_id"),
             state=state)
    # Tell the LLM how many were dropped, so the briefing can warn about it
    dropped_problems = max(0, len(problems_sorted) - problems_cap)
    if dropped_problems:
        lines.append(
            f"[TRUNCATION] {dropped_problems} additional problems not shown "
            f"(top {problems_cap} by state-priority cited only)"
        )

    # Code audit artifacts — accept either gemma-worker raw shape (`artifacts`)
    # OR the loop's previous normalized shape (`findings`).
    if code_audit_data:
        arts = code_audit_data.get("artifacts") or code_audit_data.get("findings") or []
        audit_cap = 15
        for art in arts[:audit_cap]:
            if not isinstance(art, dict):
                continue
            why = (art.get("why") or art.get("evidence") or art.get("message")
                   or art.get("rationale") or "")
            kind = art.get("kind") or art.get("playbook") or "audit"
            file_ = art.get("file") or art.get("path") or ""
            line_ = art.get("line")
            loc = f"{file_}:{line_}" if (file_ and line_) else file_
            _add("A",
                 f"[{kind}] {loc}: {_trim(why, 80)}",
                 ref=loc or file_)
        dropped_audit = max(0, len(arts) - audit_cap)
        if dropped_audit:
            lines.append(
                f"[TRUNCATION] {dropped_audit} additional code-audit findings not shown "
                f"(top {audit_cap} cited only)"
            )

    return evidence, lines


def _build_prompt(
    evidence_lines: list[str],
    problems_data: dict[str, Any],
    code_audit_data: dict[str, Any] | None,
) -> str:
    problems = problems_data.get("problems") or []
    open_n = sum(1 for p in problems if p.get("latest_state") == "open")
    res_n = sum(1 for p in problems if p.get("latest_state") == "resolved")
    disc_n = sum(1 for p in problems if p.get("latest_state") == "discrepancy")
    a_arts = []
    if code_audit_data:
        a_arts = code_audit_data.get("artifacts") or code_audit_data.get("findings") or []
    a_count = len(a_arts)

    schema = (
        '{\n'
        '  "narrative": "<markdown. 2-4 short paragraphs covering: open problems (esp. discrepancies), '
        'recently resolved items, and any code-audit concerns. Every factual sentence ends with '
        'at least one evidence citation in brackets, e.g. [O3] or [D1,A2]>",\n'
        '  "headline": "<one sentence summary of the current state>"\n'
        '}'
    )
    parts = [
        f"## SIGNAL COUNTS",
        f"problems: {len(problems)} total ({open_n} open / {res_n} resolved / {disc_n} discrepancy)",
        f"code audit artifacts: {a_count} (A1..)",
        "",
        "## EVIDENCE (cite these IDs)",
        "  prefixes: O=open, D=discrepancy, R=resolved, A=code-audit",
        *(evidence_lines or ["(no evidence collected)"]),
        "",
        "## INSTRUCTIONS",
        "Write a project briefing in the schema below.",
        "- Use ONLY the EVIDENCE above. Never invent files, commits, or features.",
        "- Every factual sentence in `narrative` must cite ≥1 evidence ID in brackets.",
        "- Prioritize discrepancies (D*) and open problems (O*) over resolved (R*).",
        "- If a category has no evidence, write '(none)'.",
        "- Tone: factual, concise. No prescriptions. The reader will decide what to do.",
        "",
        "JSON schema:",
        schema,
    ]
    return "\n".join(parts)


def _split_sentences(narrative: str) -> list[str]:
    out: list[str] = []
    for raw in _SENTENCE_SPLIT_RE.split(narrative or ""):
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        s = re.sub(r"^[-*+]\s+", "", s).strip()
        if s:
            out.append(s)
    return out


def _check_grounding(narrative: str, evidence_ids: set[str]) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    unknown: list[str] = []
    for sent in _split_sentences(narrative):
        matches = _EVIDENCE_ID_RE.findall(sent)
        if not matches:
            missing.append(sent[:120])
            continue
        for group in matches:
            for tok in (t.strip() for t in group.split(",")):
                if tok and tok not in evidence_ids:
                    unknown.append(tok)
    return missing, unknown


async def _call(prompt: str, max_tokens: int) -> dict[str, Any]:
    return await gemma_subagent(
        task=prompt,
        kind="briefing",
        inputs=[],
        max_tokens=max_tokens,
    )


async def synthesize(
    problems_data: dict[str, Any],
    code_audit_data: dict[str, Any] | None = None,
    drill_notes: str | None = None,
    constraints_data: dict[str, Any] | None = None,
    progress_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build briefing JSON from already-loaded data. Always returns a dict; on
    failure the narrative falls back to a deterministic summary."""
    evidence_limit = int(os.environ.get("LOOP_BRIEFING_EVIDENCE_LIMIT", "60"))
    max_tokens = int(os.environ.get("LOOP_BRIEFING_MAX_TOKENS", "3072"))
    strict = os.environ.get("LOOP_BRIEFING_GROUNDING_STRICT", "true").lower() not in ("0", "false", "no")

    evidence, lines = _build_evidence_map(problems_data, code_audit_data, evidence_limit)
    prompt = _build_prompt(lines, problems_data, code_audit_data)

    a_arts = []
    if code_audit_data:
        a_arts = code_audit_data.get("artifacts") or code_audit_data.get("findings") or []

    briefing: dict[str, Any] = {
        "narrative": "",
        "headline": "",
        "evidence_table": [
            {"id": e["id"], "snippet": e["snippet"], "ref": e.get("ref")}
            for e in evidence.values()
        ],
        "problems": problems_data.get("problems", []),
        "unclassified_events": problems_data.get("unclassified_events", []),
        "code_audit_findings": a_arts,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "signal_counts": {
            "problems": len(problems_data.get("problems") or []),
            "code": len(a_arts),
            "constraints_blocked": sum(
                1 for c in (constraints_data or {}).get("constraints", [])
                if c.get("kind")
            ),
        },
        "drill_notes": (drill_notes.strip() if isinstance(drill_notes, str) and drill_notes.strip() else None),
        "constraints": (constraints_data or {}).get("constraints") or [],
        "escalation_packages_found": (constraints_data or {}).get("escalation_packages_found") or [],
        "progress": (progress_data or {}).get("progress") or [],
    }

    if not evidence:
        briefing["narrative"] = "_(no evidence collected — run `problems run` and/or `gemma-worker` first)_"
        briefing["headline"] = "no signals"
        return briefing

    # Attempt 1
    res = await _call(prompt, max_tokens)
    data, fail = _validate(res, set(evidence), strict=False)

    # Attempt 2 if grounding failed (strict)
    if data is None and res.get("status") == "ok" and strict:
        retry = prompt + f"\n\nPrevious attempt failed: {fail}\nFix the issues and output ONLY the JSON object."
        res2 = await _call(retry, max_tokens)
        data, fail = _validate(res2, set(evidence), strict=True)

    if data is None:
        logger.warning("briefing synth failed: %s; falling back to deterministic summary", fail)
        briefing["narrative"] = _fallback_narrative(problems_data, code_audit_data, evidence)
        briefing["headline"] = "synthesis fallback (no LLM)"
        briefing["synth_error"] = fail
        return briefing

    briefing["narrative"] = data.get("narrative", "")
    briefing["headline"] = data.get("headline", "")
    return briefing


def load_inputs(
    repo: str | Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any] | None,
    str | None,
    dict[str, Any] | None,
    dict[str, Any] | None,
]:
    """Read .loop/problems.json (required), code_audit.json, drill_notes.md,
    constraints.json, progress.json (all optional).

    Returns (problems_data, code_audit_data, drill_notes, constraints_data, progress_data).
    Raises FileNotFoundError if problems.json is missing.
    """
    loop_dir = Path(repo).resolve() / ".loop"
    problems_path = loop_dir / "problems.json"
    if not problems_path.is_file():
        raise FileNotFoundError(
            f"{problems_path} not found. Run `problems run --repo {repo}` first."
        )
    problems_data = json.loads(problems_path.read_text(encoding="utf-8"))

    code_audit_path = loop_dir / "code_audit.json"
    code_audit_data: dict[str, Any] | None = None
    if code_audit_path.is_file():
        try:
            code_audit_data = json.loads(code_audit_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            logger.warning("code_audit.json exists but is not valid JSON: %s — ignoring", e)

    drill_notes_path = loop_dir / "drill_notes.md"
    drill_notes: str | None = None
    if drill_notes_path.is_file():
        text = drill_notes_path.read_text(encoding="utf-8").strip()
        if text:
            drill_notes = text

    constraints_path = loop_dir / "constraints.json"
    constraints_data: dict[str, Any] | None = None
    if constraints_path.is_file():
        try:
            constraints_data = json.loads(constraints_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            logger.warning("constraints.json exists but is not valid JSON: %s — ignoring", e)

    progress_path = loop_dir / "progress.json"
    progress_data: dict[str, Any] | None = None
    if progress_path.is_file():
        try:
            progress_data = json.loads(progress_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            logger.warning("progress.json exists but is not valid JSON: %s — ignoring", e)

    return problems_data, code_audit_data, drill_notes, constraints_data, progress_data


async def synthesize_from_files(repo: str | Path) -> dict[str, Any]:
    """Top-level entry: read signal files and synthesize."""
    (problems_data, code_audit_data, drill_notes,
     constraints_data, progress_data) = load_inputs(repo)
    return await synthesize(problems_data, code_audit_data, drill_notes,
                             constraints_data, progress_data)


def _validate(
    result: dict, evidence_ids: set[str], *, strict: bool
) -> tuple[dict | None, str | None]:
    if result.get("status") != "ok":
        return None, f"gemma error: {result.get('error')}"
    data = result.get("data")
    if not isinstance(data, dict) or not data.get("narrative"):
        return None, "missing narrative"
    missing, unknown = _check_grounding(data.get("narrative", ""), evidence_ids)
    if strict and (missing or unknown):
        return None, f"grounding: {len(missing)} uncited / {len(set(unknown))} unknown ids"
    return data, None


def _fallback_narrative(
    problems_data: dict[str, Any],
    code_audit_data: dict[str, Any] | None,
    evidence: dict,
) -> str:
    """Deterministic, evidence-grounded fallback used when LLM synthesis fails."""
    lines: list[str] = []
    problems = problems_data.get("problems") or []
    a_arts = []
    if code_audit_data:
        a_arts = code_audit_data.get("artifacts") or code_audit_data.get("findings") or []
    open_n = sum(1 for p in problems if p.get("latest_state") == "open")
    res_n = sum(1 for p in problems if p.get("latest_state") == "resolved")
    disc_n = sum(1 for p in problems if p.get("latest_state") == "discrepancy")
    lines.append(f"Signals: {len(problems)} problems ({open_n} open / {res_n} resolved / {disc_n} discrepancy), {len(a_arts)} code-audit artifacts.")
    lines.append("")
    lines.append("Top items by prefix:")
    for prefix in ("D", "O", "R", "A"):
        sample = [e for k, e in evidence.items() if k.startswith(prefix)][:3]
        for e in sample:
            lines.append(f"- [{e['id']}] {e['snippet']}")
    return "\n".join(lines)


__all__ = ["synthesize", "synthesize_from_files", "load_inputs"]
