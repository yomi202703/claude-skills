# P1 — DB-like small sheet → direct Markdown

Read the whole sheet and emit a Markdown table.

## Command

```bash
python3 ~/.claude/skills/xlsx/scripts/xlsx_read.py <file> --sheet "<name>" --format json
```

## Output

- Markdown table `| col | col | ... |`
- One row per source row, **every row**
- Top line: `> auto-selected: P1 (db/small, <sheet>, <rows>行×<cols>列)`
- Save to `<output_dir>/<sheet_slug>.md` (single-sheet workbooks may save directly at project root as `<workbook_slug>.md`)
