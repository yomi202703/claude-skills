# Multi-sheet handling

When a workbook has 2+ sheets, process every sheet independently. **Never ask "which sheet". Never present a menu.**

## Pipeline

1. Classifier assigns a path (P1-P5) per sheet — just execute each.
2. Create output directory at `<project>/data/<workbook_slug>/`.
   - `workbook_slug` = filename (no extension) sanitized: spaces/brackets/slashes → `_`, collapse runs, trim to 64 chars. The classifier already computes this.
3. Each sheet's output → `<workbook_slug>/<sheet_slug>.<ext>`.
4. Always write `_manifest.md` at the workbook folder root (see `manifest.md` template).
5. Report to user:
   - Output directory path
   - Manifest path
   - One-line summary per sheet

## Do not ask the user for output destination

Unless:
- `data/` doesn't make sense for the current project (check CLAUDE.md / conventions)
- Workbook folder already exists with recent outputs → ask whether to overwrite

## Reporting to user

When done, in chat, tell the user:
- **Absolute path to `_manifest.md`** (the entry point)
- Absolute path to the output directory
- One-line summary per sheet (path, output file name, row count)

## Cross-sheet relationship detection (heuristic)

While processing, run these cheap checks:

- **Shared column names** (case-insensitive, trimmed): FK candidate
- **Shared ID patterns** (same regex across sheets): potential join key even if column names differ
- **Reference-master pattern**: one sheet has small unique set of values for a column; another sheet's values are a subset → master/detail candidate

Record findings in `_manifest.md` under `Detected relationships (heuristic)`. Label every finding as heuristic — user must confirm before building JOINs. **If nothing is found, write `なし` in that section. Do not omit the section.**
