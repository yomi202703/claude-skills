# Merge interpretation rules

`xlsx_read.py --include-merges` returns entries like:
```json
{ "range": "B10:B59", "value": "新契約", "rows": [10, 59], "cols": [2, 2] }
```

Apply these rules in order. The classifier output includes `header_row_index` and `data_rows` — use those to bound your analysis.

## Rule 1 — Auto forward-fill (vertical label column)

Apply automatically when ALL hold:
- Single column (`cols[0] == cols[1]`)
- Value is short (≤ ~20 chars, no line breaks)
- Value looks like a label/category, not a sentence
- Range is in first ~5 columns OR column header is `区分` / `分類` / `帳票` / `項目` / `カテゴリ` / similar

**Action**: copy value into all cells within the range.

## Rule 2 — Auto header span (horizontal header row)

Apply automatically when ALL hold:
- Single row (`rows[0] == rows[1]`)
- Row index equals or is within 1 of `header_row_index` from classifier
- Value is short (≤ ~20 chars)
- NOT a title banner (see Rule 2c below)

**Action**: treat as multi-column header. Do not duplicate into data cells.

## Rule 2b — Short-label span across logical columns (NEW)

When a data-area row contains a merge whose value is a **short label** (≤ ~20 chars, not a sentence) and spans multiple logical columns that normally carry distinct data:

Example: `D11:G11 = "契約者名"` in a checksheet where D is the 項目 column and F, G are additional sub-columns.

**Action**: attribute the value to the LEFT-MOST logical column only. When reading F or G later, verify the cell's anchor — if it is the same merge, treat that column as empty for this row (do not duplicate the label).

## Rule 2d — Short-label span on BOTH axes (new)

A merge that spans multiple rows AND multiple columns (`rows[0] != rows[1]` AND `cols[0] != cols[1]`) with a short label value (≤ ~10 chars, often a number or sub-index like `"2"`, `"Ⅱ"`, or a grouping label like `"野村證券以外"`).

Example: `E19:G20 = "2"` — a sub-index that visually groups a 2×3 block.

**Action**: attribute the value to the top-left cell only. Inside the rectangle, clear all other cells. In the output, capture the value as a separate grouping field (e.g. `項目_補足`, `sub_category`, or similar) rather than duplicating it across rows.

## Rule 2c — Title banner (skip)

When a merge spans ≈all used columns in a row above the data area and contains decorative title text (often with 【】, ※, or sheet-title keywords):

**Action**: ignore entirely. Do not use as header, do not forward-fill. The classifier already excludes these from `header_row_index`; if you encounter one below the header while building output, still skip it.

## Rule 3 — Long-text span (visual spill)

If the value is a full sentence (long string, punctuation, or line breaks) and the range spans either axis, treat as a single value on the top-left cell. Do not duplicate across the range.

## Rule 4 — Decorative / blank

When `value` is `None` or the merge only covers padding (often seen as `AA10:AF10` in chart-like areas), ignore. **Important**: a None-valued merge on a column that earlier had a populated forward-fill merge does NOT continue the earlier fill — it marks the end of that fill region.

## Rule 5 — Ambiguous

If no rule matches cleanly, state your assumption in the output header and proceed. Do not ask up front unless the whole transformation hinges on it.

---

## Cell value quirks to handle explicitly

### Choice cells (separators)
A cell carrying a set of options may use any of these delimiters — split on ALL of them:
- `\n` (newline, in-cell line break): `"はい\n非該当"` → `["はい", "非該当"]`
- `/` (half-width slash): `"はい/いいえ"` → `["はい", "いいえ"]`
- `／` (full-width slash): `"はい／非該当"` → `["はい", "非該当"]`

If a neighbor cell holds the remainder (e.g. current cell `"はい\n非該当"`, next cell `"いいえ"`), the full choice set is the union `["はい", "非該当", "いいえ"]`.

Preserve the raw cell value in a `source_text` field when the split is non-trivial.

### Full-width whitespace
Values may contain `　` (U+3000). Do not normalize silently — preserve in `source_text` but you may strip when using the value for matching / ID generation.

### Newlines inside 特記事項
Free-text cells often contain `\n` (bullet points with ・, numbered lists, etc.). Preserve as a single string with literal `\n`. Downstream consumers must NOT treat `\n` as a record separator.

### 日付シリアル値（date serials returned as raw numbers）
`xlsx_read.py` / openpyxl convert a cell to a Python datetime **only when its number_format is a date format**. A cell that holds a date serial but is formatted General (or numeric) comes back as a plain `int` — e.g. `46163` instead of `2026-05-20`. This is common when one date column is properly formatted and a sibling column (`回答日`, `確認日`, etc.) is not, so the two look like different types in the same sheet.

There is no way to know from the value alone whether `46163` is "the number 46163" or a date — so **do NOT blanket-convert numbers in the read layer**. Apply this heuristic instead:

- A number in the Excel serial range (≈ 40000–60000 ⇒ years 2009–2064; or 1–60000 with caution) **whose column header implies a date** (`日付`, `日`, `年月日`, `確認日`, `作成日`, `date`, …) **and whose sibling date column converted cleanly** → treat as a date serial.
- Convert with the 1900 date system: `datetime.date(1899, 12, 30) + datetime.timedelta(days=n)` (the −2 offset absorbs Excel's 1900 leap-year bug). For the rare 1904-based workbook, use `datetime.date(1904, 1, 1) + timedelta(days=n)`.
- State the assumption in the output provenance header (e.g. `I列「回答日」: Excelシリアル値→ISO日付に変換`). Do not silently mutate values you are unsure about — leave them as numbers and note the ambiguity.

Mirror image: a datetime cell whose time is `00:00:00` (date-only) should be emitted as `YYYY-MM-DD`, not `YYYY-MM-DD 00:00:00`.
