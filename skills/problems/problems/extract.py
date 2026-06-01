"""Stage A: 2-lens parallel extraction (A1 progress, A2 problem) per doc.

Each doc is sent to gemma TWICE with different system prompts:
- A1 (progress lens): work/decisions/implementation occurrences
- A2 (problem lens):  defects/gaps/inconsistencies/concerns occurrences

Output is a flat list of events tagged with `lens`. Downstream (consolidate.py)
will cluster these into per-problem timelines.

Why 2 lenses: progress and problems are entangled but biased differently.
Running both reduces the chance of missing items that appear from only one
perspective (e.g., a refactor without explicit problem statement, or a
problem reported without progress yet).
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from improver.execute.gemma_subagent import gemma_subagent

logger = logging.getLogger(__name__)

Lens = Literal["progress", "problem"]


@dataclass
class Event:
    doc: str
    date: str           # ISO8601 — derived from doc mtime
    lens: Lens
    title: str          # ≤80 chars
    summary: str        # rich prose
    line_hint: int | None = None
    doc_mtime: float | None = None


@dataclass
class ExtractResult:
    events: list[Event] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    docs_scanned: int = 0


_A1_PROMPT = (
    "Read the document and extract ONLY occurrences of actual PROGRESS that "
    "happened: work done, decisions reached, implementations completed, "
    "hypotheses verified or rejected.\n"
    "Each occurrence is a SUMMARY paragraph (1-3 sentences) using PAST or "
    "PRESENT-PERFECT tense describing what happened and why.\n"
    "One document may produce multiple occurrences — each is independent.\n\n"
    "STRICT EXCLUSION rules — DO NOT extract:\n"
    "- Specifications, rules, instructions, or step-by-step procedures "
    "(\"the column must be X\", \"call this function with Y\"). These are "
    "DEFINITIONS, not progress events.\n"
    "- Future intentions or to-do lists (\"we will implement\", \"plan to add\").\n"
    "- Mere descriptions of existing structure (\"the directory contains\", \n"
    "  \"the table has these columns\").\n"
    "- Imperative sentences directed at someone (\"do X\", \"output Y\").\n"
    "- Section headings, bullet enumerations of options, boilerplate.\n"
    "- Documents that are pure instruction/prompt templates with no actual\n"
    "  events to report — in that case, return {\"events\": []}.\n\n"
    "INCLUDE only:\n"
    "- Tasks COMPLETED (\"implemented X\", \"switched from Y to Z\")\n"
    "- Decisions REACHED (\"we adopted the §6 revision\", \"hypothesis rejected\")\n"
    "- Observed results (\"first run produced 49% F006, second run 7.6%\")\n"
    "- Method changes that have been APPLIED (not proposed)\n\n"
    "When you mention a file path or symbol in the summary, wrap it in "
    "backticks.\n\n"
    "Be conservative — when in doubt, do NOT extract. Empty output is better "
    "than spec-as-progress noise.\n\n"
    "Output JSON: "
    '{"events": [{"title": "<≤80 chars heading>", "summary": "<rich prose, past tense>", '
    '"line_hint": <int or null>}]}'
)

_A2_PROMPT = (
    "Read the document and extract EVERY occurrence of a PROBLEM POINT — "
    "anything that is wrong, broken, inconsistent, ambiguous, concerning, "
    "or undecided.\n"
    "Each occurrence is a SUMMARY paragraph (1-3 sentences) describing:\n"
    "  - what the problem is\n"
    "  - what the cause is (if known)\n"
    "  - what the current understanding is\n"
    "  - what has been decided about it (if anything)\n"
    "  - what remains open\n"
    "One document may produce multiple problems — each is independent.\n\n"
    "Include:\n"
    "- Defects, accuracy gaps (\"F013 variance 15.7pp\")\n"
    "- Inconsistencies, semantic overlap (\"F008/F009 95% duplicate\")\n"
    "- Missing definitions / ambiguous boundaries\n"
    "- Open questions, undecided policy items\n"
    "- Things waiting on external input\n"
    "- Risks, concerns, hypotheses not yet verified\n\n"
    "EXCLUDE:\n"
    "- Things that were merely DONE or implemented (those are progress, not problems)\n"
    "- Pure specifications or rules with no concern attached\n"
    "- Section headings, bare directory listings, boilerplate\n\n"
    "When you mention a file path or symbol name, wrap it in backticks.\n\n"
    "Output JSON: "
    '{"events": [{"title": "<≤80 chars heading>", "summary": "<rich prose>", '
    '"line_hint": <int or null>}]}'
)


_LENS_PROMPT: dict[Lens, str] = {"progress": _A1_PROMPT, "problem": _A2_PROMPT}

# Reuse improver's chunking thresholds — same constants
_CHUNK_THRESHOLD_BYTES = int(os.environ.get("IMPROVER_DOC_CHUNK_THRESHOLD", "10000"))
_CHUNK_MAX_BYTES = int(os.environ.get("IMPROVER_DOC_CHUNK_MAX_BYTES", "8000"))


def _split_markdown(text: str, *, max_bytes: int = _CHUNK_MAX_BYTES) -> list[tuple[str, int]]:
    """Split markdown into chunks at H2/H3 boundaries. Returns [(text, line_offset)]."""
    if len(text.encode("utf-8")) <= max_bytes:
        return [(text, 1)]
    parts = re.split(r"(?m)^(?=## )", text)
    chunks: list[tuple[str, int]] = []
    cur_line = 1
    buf = ""
    buf_start = 1
    for part in parts:
        if not part:
            continue
        if len(part.encode("utf-8")) > max_bytes:
            if buf:
                chunks.append((buf, buf_start))
                buf = ""
            # Sub-split by H3
            sub_parts = re.split(r"(?m)^(?=### )", part)
            sub_buf = ""
            sub_buf_start = cur_line
            sub_line = cur_line
            for sp in sub_parts:
                if not sp:
                    continue
                if len(sub_buf.encode("utf-8")) + len(sp.encode("utf-8")) > max_bytes and sub_buf:
                    chunks.append((sub_buf, sub_buf_start))
                    sub_buf = sp
                    sub_buf_start = sub_line
                else:
                    if not sub_buf:
                        sub_buf_start = sub_line
                    sub_buf += sp
                sub_line += sp.count("\n")
            if sub_buf:
                chunks.append((sub_buf, sub_buf_start))
            buf_start = cur_line + part.count("\n")
        elif len(buf.encode("utf-8")) + len(part.encode("utf-8")) > max_bytes and buf:
            chunks.append((buf, buf_start))
            buf = part
            buf_start = cur_line
        else:
            if not buf:
                buf_start = cur_line
            buf += part
        cur_line += part.count("\n")
    if buf:
        chunks.append((buf, buf_start))
    return chunks


async def _call_lens_on_chunk(
    *, lens: Lens, chunk: str, line_offset: int, doc_path: str
) -> tuple[list[dict[str, Any]], str | None]:
    """One gemma call for one (lens, chunk) pair. Returns (events_raw, error_or_None)."""
    system = _LENS_PROMPT[lens]
    task = f"{system}\n\n--- DOCUMENT: {doc_path} ---\n{chunk}"
    res = await gemma_subagent(
        task=task,
        kind="list",   # generic JSON list output; system prompt above overrides
        inputs=[],
        max_tokens=int(os.environ.get("PROBLEMS_EXTRACT_MAX_TOKENS", "4096")),
    )
    if res.get("status") != "ok":
        return [], f"{doc_path} [{lens}]: {res.get('error', 'extract failed')}"
    data = res.get("data") or {}
    items_raw = data.get("events") or data.get("items") or []
    out: list[dict[str, Any]] = []
    for it in items_raw:
        if not isinstance(it, dict):
            continue
        title = str(it.get("title", "")).strip()
        summary = str(it.get("summary", "") or it.get("text", "")).strip()
        if not summary:
            continue
        line_hint = it.get("line_hint")
        if isinstance(line_hint, int):
            line_hint = line_hint + line_offset - 1
        else:
            line_hint = None
        out.append({"title": title[:120] or summary[:80], "summary": summary, "line_hint": line_hint})
    return out, None


async def _extract_one_doc(
    *, repo: Path, doc_path: str, mtime: float
) -> tuple[list[Event], list[str]]:
    """Extract events for one doc, both lenses, with chunking. Returns (events, errors)."""
    abs_path = repo / doc_path
    try:
        text = abs_path.read_text(encoding="utf-8")
    except OSError as e:
        return [], [f"{doc_path}: read failed: {e}"]

    size = len(text.encode("utf-8"))
    chunks = _split_markdown(text) if size > _CHUNK_THRESHOLD_BYTES else [(text, 1)]
    date_iso = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

    # Build tasks: (lens, chunk) cross product
    coros = []
    plan: list[tuple[Lens, int]] = []   # (lens, chunk_offset)
    for lens in ("progress", "problem"):
        for chunk_text, line_offset in chunks:
            coros.append(_call_lens_on_chunk(lens=lens, chunk=chunk_text, line_offset=line_offset, doc_path=doc_path))
            plan.append((lens, line_offset))

    results = await asyncio.gather(*coros, return_exceptions=True)

    events: list[Event] = []
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()  # (lens, summary_normalized) to dedupe within doc
    for (lens, _offset), res in zip(plan, results):
        if isinstance(res, Exception):
            errors.append(f"{doc_path} [{lens}]: {type(res).__name__}: {res}")
            continue
        items, err = res  # type: ignore[misc]
        if err:
            errors.append(err)
        for it in items:
            summ = it["summary"].strip()
            key = (lens, _norm(summ))
            if key in seen:
                continue
            seen.add(key)
            events.append(Event(
                doc=doc_path,
                date=date_iso,
                lens=lens,
                title=it["title"],
                summary=summ,
                line_hint=it.get("line_hint"),
                doc_mtime=mtime,
            ))
    return events, errors


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower())[:200]


async def extract_all(repo: str | Path) -> ExtractResult:
    """Run A1+A2 across all docs in parallel. Reuses improver's doc walker."""
    from improver.discover.doc_state import _list_docs

    repo_path = Path(repo).resolve()
    docs = _list_docs(repo_path)
    max_docs = int(os.environ.get("IMPROVER_MAX_DOCS", "50"))
    docs = docs[:max_docs]

    sem_n = int(os.environ.get("PROBLEMS_DOC_CONCURRENCY", "3"))
    sem = asyncio.Semaphore(sem_n)

    async def one(d) -> tuple[list[Event], list[str]]:
        async with sem:
            return await _extract_one_doc(repo=repo_path, doc_path=d.path, mtime=d.mtime)

    results = await asyncio.gather(*[one(d) for d in docs])
    out = ExtractResult(docs_scanned=len(docs))
    for ev_list, errs in results:
        out.events.extend(ev_list)
        out.errors.extend(errs)
    return out


def serialize(result: ExtractResult) -> dict[str, Any]:
    return {
        "events": [asdict(e) for e in result.events],
        "errors": result.errors,
        "docs_scanned": result.docs_scanned,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
    }


__all__ = ["Event", "ExtractResult", "extract_all", "serialize"]
