---
name: xlsx-router
description: Efficient LLM-friendly xlsx processing. Uses a router script to classify each sheet and lazy-load only the relevant handling docs per case. The classifier returns one of P1-P5 (db-small / db-large / structured-small / structured-large / over-large), and may additionally attach `drawings.md` and/or `p6_visual.md` as overlay docs when a sheet carries shapes, pictures, or layout-dependent content. Drawings (shape text + images) are extracted deterministically and persisted alongside the SQLite output; a rendering fallback uses LibreOffice + PyMuPDF to turn sheets into PNGs that Claude Code reads natively.
---

# XLSX Skill (router)

## Workflow

1. **Classify**:
   ```bash
   python3 ~/.claude/skills/xlsx/scripts/xlsx_classify.py <file.xlsx>
   ```
   Output JSON lists `sheets[].path` (P1-P5), `sheets[].docs_to_read`, drawing signals (`has_drawings`, `shape_count`, `pic_count`, `suggests_visual`), plus workbook fields `all_docs_to_read`, `workbook_slug`, `output_dir_suggestion`, `multi_sheet`.

2. **Lazy-read docs**: read only files named in `all_docs_to_read` from `~/.claude/skills/xlsx/docs/`.

3. **Execute** each sheet's path as instructed by its doc. Write outputs under `<project>/data/<workbook_slug>/`.

4. **Multi-sheet**: follow `multi_sheet.md`, write `_manifest.md` from `~/.claude/skills/xlsx/templates/manifest.md`.

## Processing hygiene

1. **One file at a time, strictly sequential.** Business xlsx routinely contain 5KB+ multi-line strings per cell; parallel reads can flood context in seconds.
2. **Never print raw cell values in debug.** Use `len(v)`, `type(v)`, or first ~20 chars only.
3. **Dump to file, then grep.** Redirect classify output to `/tmp/x.json`, extract fields via inline `python3 -c`.
4. **Subagents for E2E.** Multi-file validation in ONE subagent returning a summary (≤500 words).

## When to ask (rarely)

Only when intent is ambiguous, the action is irreversible, or cost is high (P5 materialization). Never ask "which sheet" or "which format".

## Scripts

- `xlsx_classify.py` — router → P1-P5 + docs-to-read + drawing signals
- `xlsx_read.py` — range read with merge info
- `xlsx_materialize.py` — xlsx → SQLite with drawings tables
- `xlsx_drawings.py` — deterministic shape/pic/connector extraction. See `docs/drawings.md`.
- `xlsx_visual.py` — sheet → PNG fallback. See `docs/p6_visual.md`.
- `xlsx_verify.py` — fidelity check (xlsx ↔ SQLite). Regression guard after pipeline edits.

## Drawings & visual fallback

If `has_drawings` is true, read `docs/drawings.md` and the `<sheet_slug>_drawings` SQLite table. If `suggests_visual` is true, also read `docs/p6_visual.md` and render via `xlsx_visual.py`. Prefer Tier A (cheap) before Tier B (token cost per page).

## Downstream consumer

A fresh, cache-cleared Claude Code instance. Quality bar: it can answer factual questions from the SQLite alone.
