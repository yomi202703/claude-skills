#!/usr/bin/env python3
"""Stage 2: cleaned md → chunked parallel Haiku compression → final md.

Splits the Stage 1 cleaned md by `## ターンN` headings, batches into chunks
of N turns with M-turn overlap (overlap is context-only — not output), runs
each chunk through Haiku 4.5 via claude -p in parallel, concatenates results.
"""
from __future__ import annotations

import argparse
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import NamedTuple

from llm import call_with_template


# Match a turn header line: "## ターン42: アシスタント"
_TURN_HEADER_RE = re.compile(r"^##\s+ターン(\d+)\s*:\s*(\S+)\s*$", re.MULTILINE)


class Turn(NamedTuple):
    num: int
    label: str
    body: str  # full text including the header line and trailing separator


def parse_turns(md_text: str) -> tuple[str, list[Turn]]:
    """Split cleaned md into (preamble, [turns]).

    preamble = everything before the first turn header (title, source line, etc.).
    Each Turn.body includes its `---` separator and `## ターンN: ...` header
    so concatenating body strings reconstructs the file.
    """
    matches = list(_TURN_HEADER_RE.finditer(md_text))
    if not matches:
        return md_text, []

    # Preamble: from start to the line containing the first `---` immediately before first header.
    first_header_start = matches[0].start()
    # Walk back to include the `---` separator above the first header (if present).
    preamble_end = first_header_start
    pre_text = md_text[:preamble_end]
    sep_match = re.search(r"\n---\s*\n\s*$", pre_text)
    if sep_match:
        preamble_end = sep_match.start() + 1  # keep the newline before `---`
    preamble = md_text[:preamble_end].rstrip() + "\n\n"

    turns: list[Turn] = []
    for i, m in enumerate(matches):
        # Body starts from the `---` separator above this header (or from the header itself if no sep).
        body_start_search = md_text.rfind("\n---", 0, m.start())
        if body_start_search != -1 and body_start_search >= preamble_end - 2:
            body_start = body_start_search + 1  # skip the leading newline
        else:
            body_start = m.start()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(md_text)
        # Walk back from body_end to before the next turn's `---` separator.
        if i + 1 < len(matches):
            sep = md_text.rfind("\n---", body_start, body_end)
            if sep != -1:
                body_end = sep + 1
        body = md_text[body_start:body_end]
        turns.append(Turn(num=int(m.group(1)), label=m.group(2), body=body))

    return preamble, turns


class Chunk(NamedTuple):
    chunk_id: int
    context_turns: list[Turn]   # output: NOT included
    target_turns: list[Turn]    # output: included


def make_chunks(turns: list[Turn], chunk_size: int, overlap: int) -> list[Chunk]:
    """Build chunks of `chunk_size` turns each, with `overlap` prior turns as context-only."""
    chunks: list[Chunk] = []
    i = 0
    cid = 0
    while i < len(turns):
        target = turns[i : i + chunk_size]
        ctx_start = max(0, i - overlap)
        context = turns[ctx_start:i]
        chunks.append(Chunk(chunk_id=cid, context_turns=context, target_turns=target))
        i += chunk_size
        cid += 1
    return chunks


def render_chunk_text(chunk: Chunk) -> str:
    """Render the chunk (context + target) as a single md string for the LLM."""
    parts = [t.body for t in chunk.context_turns + chunk.target_turns]
    return "".join(parts).rstrip() + "\n"


def compress_chunk(
    chunk: Chunk,
    *,
    model: str,
    template_path: Path,
    timeout: int,
) -> tuple[Chunk, str, dict]:
    """Run one chunk through the LLM. Returns (chunk, compressed_md_text, stats)."""
    context_start = chunk.context_turns[0].num if chunk.context_turns else chunk.target_turns[0].num
    context_prev_end = chunk.context_turns[-1].num if chunk.context_turns else chunk.target_turns[0].num - 1
    target_start = chunk.target_turns[0].num
    target_end = chunk.target_turns[-1].num

    placeholders = {
        "CONTEXT_START": context_start,
        "CONTEXT_PREV_END": context_prev_end,
        "TURN_START": target_start,
        "TURN_END": target_end,
        "CHUNK_TEXT": render_chunk_text(chunk),
    }

    result = call_with_template(
        template_path,
        placeholders,
        model=model,
        timeout=timeout,
    )

    stats = {
        "chunk_id": chunk.chunk_id,
        "target_start": target_start,
        "target_end": target_end,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "cost_usd": result.cost_usd,
        "duration_ms": result.duration_ms,
        "is_error": result.is_error,
        "error_message": result.error_message,
    }

    if result.is_error:
        # Fallback: keep target turns un-compressed.
        fallback = "".join(t.body for t in chunk.target_turns)
        return chunk, fallback, stats

    return chunk, result.text.strip() + "\n", stats


_LEVEL_TEMPLATES = {
    "light": "compress_chunk_light.md",
    "medium": "compress_chunk_medium.md",
    "aggressive": "compress_chunk_aggressive.md",
}


def run_stage2(
    cleaned_md: Path,
    out_path: Path,
    *,
    chunk_size: int = 20,
    overlap: int = 2,
    model: str = "claude-haiku-4-5-20251001",
    parallelism: int = 6,
    timeout: int = 600,
    level: str = "light",
) -> dict:
    text = cleaned_md.read_text(encoding="utf-8")
    preamble, turns = parse_turns(text)
    if not turns:
        out_path.write_text(text, encoding="utf-8")
        return {"chunks": 0, "turns": 0, "warning": "no turns found, copied as-is"}

    chunks = make_chunks(turns, chunk_size, overlap)

    if level not in _LEVEL_TEMPLATES:
        raise ValueError(f"invalid level: {level} (expected one of {list(_LEVEL_TEMPLATES)})")
    template_name = _LEVEL_TEMPLATES[level]
    template_path = Path(__file__).resolve().parent / "prompts" / template_name
    if not template_path.exists():
        # Fallback to legacy filename
        legacy = Path(__file__).resolve().parent / "prompts" / "compress_chunk.md"
        if legacy.exists():
            template_path = legacy
        else:
            raise FileNotFoundError(f"prompt template not found: {template_path}")

    results: dict[int, tuple[Chunk, str, dict]] = {}
    all_stats: list[dict] = []

    with ThreadPoolExecutor(max_workers=parallelism) as ex:
        futures = {
            ex.submit(compress_chunk, c, model=model, template_path=template_path, timeout=timeout): c
            for c in chunks
        }
        for fut in as_completed(futures):
            chunk, compressed, stats = fut.result()
            results[chunk.chunk_id] = (chunk, compressed, stats)
            all_stats.append(stats)

    # Stitch in chunk order.
    ordered = [results[i] for i in range(len(chunks))]

    # Update preamble to record stage 2.
    preamble_lines = preamble.rstrip().splitlines()
    # Replace or append a "stage:" line.
    stage_line = f"> stages: stage1 + stage2 ({model}, level={level})"
    new_preamble_lines: list[str] = []
    stage_replaced = False
    for line in preamble_lines:
        if line.strip().startswith("> stage"):
            new_preamble_lines.append(stage_line)
            stage_replaced = True
        else:
            new_preamble_lines.append(line)
    if not stage_replaced:
        new_preamble_lines.append(stage_line)
    new_preamble = "\n".join(new_preamble_lines) + "\n\n"

    with out_path.open("w", encoding="utf-8") as f:
        f.write(new_preamble)
        for _, compressed, _ in ordered:
            body = compressed.strip()
            if not body.startswith("---"):
                f.write("---\n\n")
            f.write(body)
            f.write("\n\n")

    total_cost = sum(s.get("cost_usd", 0) for s in all_stats)
    total_in = sum(s.get("input_tokens", 0) for s in all_stats)
    total_out = sum(s.get("output_tokens", 0) for s in all_stats)
    errors = [s for s in all_stats if s.get("is_error")]

    return {
        "chunks": len(chunks),
        "turns": len(turns),
        "input_tokens": total_in,
        "output_tokens": total_out,
        "cost_usd": total_cost,
        "errors": errors,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage 2: chunked LLM compression")
    ap.add_argument("cleaned_md", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--chunk-size", type=int, default=20)
    ap.add_argument("--overlap", type=int, default=2)
    ap.add_argument("--model", default="claude-haiku-4-5-20251001")
    ap.add_argument("--parallelism", type=int, default=6)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--level", choices=["light", "medium", "aggressive"], default="light")
    args = ap.parse_args()

    if not args.cleaned_md.exists():
        print(f"error: cleaned md not found: {args.cleaned_md}", file=sys.stderr)
        return 1

    summary = run_stage2(
        args.cleaned_md,
        args.out,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        model=args.model,
        parallelism=args.parallelism,
        timeout=args.timeout,
        level=args.level,
    )
    import json as _json
    print(_json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary.get("errors") else 0


if __name__ == "__main__":
    sys.exit(main())
