# P6 — Visual fallback (render sheet to PNG, read via Read tool)

Triggered when:
- the `xlsx_to_html` manifest sets `suggests_image: true` for a sheet
  (drawings present) AND the HTML's `〔図形: …〕` annotations don't capture
  the layout meaning, OR
- the caller explicitly wants the visual path for a specific sheet.

This is the **last resort** for sheets whose semantic content lives in
layout, not cells: forms where cells + arrows + shape labels form a
single composite meaning, product diagrams, flow charts, annotated
screenshots.

## Pipeline

`xlsx_visual.py` runs:
1. `soffice --headless --convert-to pdf:calc_pdf_Export` (LibreOffice 26.x)
2. poppler's `pdftoppm -png -r <dpi>` renders each PDF page → PNG (default 150 DPI)

Two modes:
- **workbook** (default): one PDF for the whole workbook; all pages
  end up under `<out_dir>/pages/page_NN.png`. Fast but sheet → page
  boundary must be inferred.
- **`--per-sheet`**: produces a one-sheet-only xlsx in a tempdir per
  sheet and converts each separately, so `<out_dir>/<sheet>/page_NN.png`
  is unambiguous. Slower; use when sheet-level grouping matters.

## When to invoke

Do NOT render every workbook — it's the most expensive tier. Trigger
visual rendering only when:
- the HTML (with its `〔図形: …〕` shape annotations) doesn't answer the
  question, OR
- the manifest's `suggests_image` is true for a sheet AND the question is
  about that sheet, OR
- the sheet's meaning lives in layout the cells + annotations can't convey
  (arrows, overlap, conditional-format color).

## How Claude Code should use the output

1. **Read images one at a time**, only those relevant to the current
   question. A sheet rendered at 150 DPI produces ~1.5k–2k input tokens
   per page image.
2. **Start with `--per-sheet` for the specific sheet you need**,
   not the whole workbook, unless the workbook is small.
3. **Combine with Tier A output.** Shape text (from `<sheet>_drawings`
   in SQLite) is still the most compact representation. Only reach for
   the rendered PNG when text alone isn't enough.
4. **Page ordering = natural reading order of that sheet.** Rows run
   left-to-right, then top-to-bottom; wide sheets split vertically
   across multiple pages.

## Common failure modes

- **Very wide or very tall sheets** produce dozens of pages.
  `ペットネーム` (7472 rows) would render to ~50+ pages — don't do it
  unless necessary. Use Tier A + the SQLite table instead.
- **DPI tradeoff**: 150 DPI is readable for Japanese but large; 100 DPI
  halves token cost but small-point text becomes unreadable.
- **soffice zombie processes**: LibreOffice sometimes leaves background
  soffice processes; if conversions start failing, `pkill soffice`.

## Why per-sheet mode uses zip-level editing (do NOT change)

`_single_sheet_xlsx` in `xlsx_visual.py` rebuilds the per-sheet xlsx by
rewriting `xl/workbook.xml` directly via `zipfile`. It intentionally does
**not** use `openpyxl.load_workbook().save()` for this because openpyxl
silently discards shapes / text boxes / grouped drawings on save
("DrawingML support is incomplete and limited to charts and images only").
That is exactly the content this tier exists to preserve — the
product-code labels, step-number markers (①②③...), annotation arrows,
etc. If you ever refactor this function, verify with a roundtrip test:
the shape count before and after must match.
