# P4 — Structured large sheet → script generation

**Do not** emit the full output directly. Generate a transformation script that processes the full file mechanically.

## Steps

1. **Use classifier output for exact bounds.** The classifier reports:
   - `header_rows` — list of header row indices (multi-tier possible, e.g. `[9, 10]`); `header_row_index` = `header_rows[0]` is the primary
   - `data_rows` — `[first, last]` of actual data, trailing blanks excluded
   - `merged_count` — total merges

   If you must fall back to reading: read `A1:<last_col><max(header_rows)>` for the header AND the full merge list for the whole data range. A 10-row sample is insufficient to see late merges (e.g. `A121:A203` for a second category) — **always fetch the entire merge list**, not just merges intersecting the sample.

2. **Read header + a sample** from the data area:
   ```bash
   python3 ~/.claude/skills/xlsx/scripts/xlsx_read.py <file> --sheet "<name>" \
     --range A{header_rows[0]}:{last_col}{data_rows[0]+10} --include-merges --format json
   ```

3. **Analyze the schema**:
   - Which columns map to which output fields (using the detected header row)?
   - Which merges are forward-fill, header-span, label-span, long-text, or title-banner (see `merges.md`)?
   - Are there multi-line choice cells (newlines in values) that need list splitting?

4. **Write a Python transformation script** to `scripts/<basename>_to_<format>.py`:
   - Loads xlsx with `openpyxl`
   - Applies merge rules mechanically
   - Uses `data_rows` bounds to skip trailing blank rows — do NOT rely on `ws.max_row`
   - Emits target file for every row in `data_rows[0]` … `data_rows[1]`
   - Idempotent: re-running overwrites the output file, produces the same content if source unchanged
   - Deterministic output order (sort-stable)

5. **Execute**:
   ```bash
   python3 scripts/<basename>_to_<format>.py
   ```

6. **Report**:
   - Output path: `<output_dir>/<sheet_slug>.<ext>`
   - Row count (output) = `data_rows[1] - data_rows[0] + 1` (verify match)
   - Script path (for user to re-run later)
   - Top of the script should have a docstring: what it does, how merges were interpreted, idempotency guarantee

## Output format (default by content_type)

Pick without asking:
- `content_type: rules` → **JSONL** (one rule per line, easy to grep/diff/stream)
- `content_type: table` → **CSV** (flat, headered, Excel-compatible)
- `content_type: document` → **Markdown** with sections

Override only if the user explicitly requests another format.

## Key naming

When the source headers are Japanese (or any non-ASCII), **keep the original strings as keys** in the output (JSON/JSONL/YAML). Do not romanize.

Reason: fidelity to source, no divergence risk, simple grep. Downstream tooling handles UTF-8 fine.

Exception: if the user explicitly asks for ASCII keys (e.g. "for SQL schema"), emit both:
- Japanese keys as data
- A separate `source_headers` map: `{"kubun": "区分", "chohyo": "帳票", ...}`

## Idempotency contract

- Script overwrites the output file on each run (no appending)
- Same input xlsx → same output bytes (deterministic)
- Safe to commit the generated script to git as a reusable artifact

## Merge handling

See `merges.md`. Key points:
- Forward-fill vertical label columns (Rule 1)
- Skip title banners (Rule 2c)
- Attribute label spans to the left-most logical column (Rule 2b)
- Treat None-valued merges as fill-breakers (Rule 4)
