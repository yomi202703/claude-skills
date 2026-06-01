# P3 — Structured small sheet → direct LLM generation

Read with merges, apply merge rules, emit target format directly.

## Command

```bash
python3 ~/.claude/skills/xlsx-router/scripts/xlsx_read.py <file> --sheet "<name>" \
  --range A{header_rows[0]}:{last_col}{data_rows[1]} --include-merges --format json
```

Use `header_rows` (list — may be multi-tier) and `data_rows` from the classifier to bound the range. Start at `header_rows[0]`, stop at `data_rows[1]` (classifier already excludes trailing blanks).

## Format decision (by `content_type`)

- `rules` → **YAML** rule set (stable IDs R001…, list fields, flattened merges)
- `table` → **Markdown** table (flattened merges)
- `document` → **Markdown** document (sections)
- `notes` → **Markdown** free-form (paragraphs / bullet list, preserve line order, no table structure)

Pick without asking.

## `notes` rendering

When `content_type=notes` (e.g. a sheet of guidance text, not a data table):
- Do NOT build a table.
- Iterate cells in row order, left-to-right, emit each non-empty string as a paragraph or bullet.
- Preserve 見出し markers (`■`, `●`, `1.`) as Markdown headings/bullets.
- Output goes to `<output_dir>/<sheet_slug>.md` with provenance header.

## Output

- Top line: `> auto-selected: P3 (structured/small/<content_type>, <sheet>, ...)`
- Save to `<output_dir>/<sheet_slug>.<ext>`
- **Emit every logical row** from `data_rows[0]` through `data_rows[1]` — no truncation

## Fidelity check (required)

Before reporting done, confirm no rows were silently dropped. Expected logical rows = `data_rows[1] - data_rows[0] + 1` (for `table`: Markdown body rows; for `rules`: number of `R###` entries; for transposed sheets: number of field records). Count what you emitted and compare:

```bash
# table example: body row count = matching lines minus the header + separator (2)
echo $(( $(grep -c '^|' <output_dir>/<sheet_slug>.md) - 2 ))
```

If the counts differ, locate the dropped rows before finishing — do not report success on a partial output.

## Merge handling

See `merges.md` for the 5 rules. Apply them before rendering.

## YAML rule set conventions

### Basic shape
```yaml
meta:
  title: ...
  version: ...
  前提: [...]  # preambles/notes extracted from banner rows or top meta area

rules:
  - id: R001
    区分: 新契約
    帳票: [申込書, 意向確認書]   # list when "／" joins multiple
    項目: 商品
    確認事項: ...
    選択肢: [はい, いいえ]
    特記事項: null
```

### Choice/selection field rules

The `選択肢` / `チェック` column needs consistent list form:

| Raw cell | Emit as |
|---|---|
| `"はい/いいえ"` | `[はい, いいえ]` |
| `"はい\n非該当"` + neighbor `"いいえ"` | `[はい, 非該当, いいえ]` |
| `"はい／非該当"` | `[はい, 非該当, いいえ]` if binary is the usual default, else `[はい／非該当, いいえ]` — prefer splitting unless ambiguous |
| `"OK/NG"` | `[OK, NG]` |
| Single value like `"取扱不可"` | keep as string |

When in doubt, split on `/`, `／`, and `\n`. Preserve a `source_text` field if the split might be wrong.

### IDs
Use `R001`, `R002`, ... zero-padded to at least 3 digits. Stable across runs (derived from source row order).

### Provenance
Top-of-file comment block (optional but recommended):
```yaml
# auto-selected: P3 (structured/small/rules)
# source: <filename>, sheet "<name>", header row <header_row_index>, data rows <first>..<last>
# merges applied: Rule 1 (forward-fill) on cols A,B; Rule 2 (header span) on row <h>; Rule 2b (label span) on D-G; …
```
