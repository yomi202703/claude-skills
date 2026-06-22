---
name: xlsx-router
description: Convert an existing business .xlsx into a faithful, LLM-readable artifact for reading/extraction (NOT authoring). Each sheet becomes structure-preserving HTML (merges→rowspan/colspan, static colors→inline style, date serials→ISO, shape/textbox text→anchored notes); oversized sheets go to SQLite; layout/diagram sheets to PNG. A self-verify gate guarantees no source cell is dropped. Use when asked to read, extract from, summarize, or convert/ingest a spreadsheet (.xlsx/.xlsm) for an LLM — especially complex Japanese business workbooks with merged cells, multi-tier headers, transposed layouts, or embedded drawings. Not for creating or editing spreadsheets.
---

# XLSX → LLM-native converter

Produce an artifact faithful to the source AND directly LLM-readable. The converter writes a faithful structural copy — it does NOT guess headers, split choice cells, or collapse merges; the consuming LLM interprets it.

## Workflow

1. Convert (one call = triage + faithful write + self-verify):
   ```bash
   python3 ~/.claude/skills/xlsx-router/scripts/xlsx_to_html.py <file.xlsx> --out-dir data/<workbook_slug>
   ```
   Prints a per-sheet manifest and writes one `.html` per HTML-path sheet. Fields: `path` (`html`|`sqlite`), `faithful` (must be `N/N` — else the command exits non-zero, a real defect to fix), `has_drawings`, `suggests_image`.

2. Act per sheet from the manifest — don't re-decide what it settled:
   - `html` → the `.html` IS the artifact; read it to answer/present. Reconstruct headers, merged-label groups (rowspan/colspan), and transposed layouts straight from the HTML.
   - `sqlite` → too large for context. Peek at the top rows, then materialize — pass `--header-rows N` only if the header isn't row 1 (spec block above the table):
     ```bash
     python3 ~/.claude/skills/xlsx-router/scripts/xlsx_read.py <file.xlsx> --sheet "<sheet>" --range A1:<last_col>25
     python3 ~/.claude/skills/xlsx-router/scripts/xlsx_materialize.py <file.xlsx> \
       --out data/<workbook_slug>/<sheet_slug>.sqlite --tables "<sheet>" [--header-rows 22]
     ```
   - `suggests_image` → drawings present; their text is already in the HTML as `〔図形: …〕`. Render a PNG (`xlsx_visual.py`, see `docs/p6_visual.md`) ONLY when meaning depends on layout the annotations can't convey (arrows, overlap, conditional-format color). Expensive — one sheet at a time.

3. Multi-sheet: process every sheet; write `_manifest.md` from `templates/manifest.md` (see `docs/multi_sheet.md`). Never ask "which sheet" or "which format".

## Notes

- Triage is deterministic: HTML vs SQLite by `used_cells > 20000`; image by the drawing flag. The only judgment left to you is whether a flagged sheet truly needs a PNG.
- Known gap: conditional-formatting color isn't stored in cell values — use the image path if such color carries meaning.
- Hygiene: one file at a time; never print raw cell values (use `len`/`type`/first ~20 chars); trust the manifest, don't eyeball huge HTML.

## Scripts

- `xlsx_to_html.py` — faithful HTML + triage + self-verify (entry point)
- `xlsx_materialize.py` — huge sheet → SQLite
- `xlsx_drawings.py` — shape/pic/connector extraction, feeds HTML notes (`docs/drawings.md`)
- `xlsx_visual.py` — sheet → PNG (`docs/p6_visual.md`)
- `xlsx_read.py` — ad-hoc range read with merges
- `xlsx_verify.py <xlsx> <sqlite>` — xlsx ↔ SQLite fidelity check (positional args; ratio compares whole-workbook vs one table)
- `xlsx_primitives.py` — shared helpers

Downstream consumer: a fresh, cache-cleared LLM — it must answer from the artifact alone, without the original xlsx.
