# P2 — DB-like large sheet → SQLite materialize

Convert to SQLite, report only schema + row count + 5-row sample.

## Command

```bash
python3 ~/.claude/skills/xlsx-router/scripts/xlsx_materialize.py <file.xlsx> \
  --out <output_dir>/<sheet_slug>.sqlite --tables "<sheet_name>"
```

## Output

- SQLite file at the target path
- In the chat, emit a short Markdown summary **only**, not the full data:
  - `> auto-selected: P2 (db/large, <sheet>, <rows>行×<cols>列)`
  - Schema (`.schema`)
  - Row count
  - 5-row sample
  - Example query

## Query example

```bash
sqlite3 <output_dir>/<sheet_slug>.sqlite "SELECT ... FROM <table>"
```
