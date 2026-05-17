# Header-Row Detection in Spreadsheets: Prior Art & Recommendations

## Key findings

- No mainstream library truly auto-detects the header row. pandas `read_excel`/`read_csv` default `header=0` (row 1) and leave detection to the user; there is an open issue (pandas #24440) explicitly requesting auto-detection, still unresolved. Power Query's "promote headers" is a one-shot rule (first non-empty row; only promotes if values are text/number) — it does not skip title banners.
- The strongest classical signal in the literature is **type/format consistency between row R and rows R+1..R+k**: a header row is predominantly string-valued while the rows beneath share a consistent numeric/date/categorical type per column. Chen & Cafarella (WebTables) and Adelfio & Samet (VLDB'13 "Schema Extraction for Tabular Data on the Web") formalized this; Random Forests on such features hit ~97% accuracy (Fan, Kim, Giles AAAI'12).
- Microsoft's **TableSense** (AAAI'19) and **SpreadsheetLLM / SheetCompressor** (2024) both treat a sheet as a 2-D grid with "structural anchor" rows/cols — rows where the type/format pattern abruptly changes are anchor candidates and become the table's top border (i.e. the header row). SpreadsheetLLM's table-detection prompt explicitly excludes titles/comments from the `A2:D5`-style range.
- **DeExcelerator** (CIKM'13) classifies each cell as header / attribute / metadata / data / derived via a heuristics pipeline using color, indentation, and type-signature cues — splits header vs data correctly in 78% of real-world sheets. **TabbyXL** (2019) takes a similar rule-based path and is the closest public analog to the current skill's scoring heuristic.
- Known failure modes for "row 1 = header": (a) title banners (【タイトル】), (b) horizontally-merged header bands, (c) multi-tier/nested headers (pandas supports via `header=[0,1]`, readxl needs a two-read trick, tidyxl exposes cells individually), (d) interleaved ※-notes and blank separator rows. All are documented failure cases in the Power Query docs and readxl multi-header vignette.

## Algorithmic approaches (ranked by relevance to this skill)

1. **Type-consistency delta (Adelfio & Samet / Cafarella)** — for each candidate row R, compute per-column type (string/int/float/date/empty) of R vs majority type of R+1..R+k. Header rows score high when R is mostly string AND rows below share a non-string majority type. Cheap, explainable, O(rows×cols). Best bang-for-buck.
2. **Structural anchor rows (TableSense / SheetCompressor)** — identify rows where the type/format vector flips vs neighbours; those are table boundaries. First anchor after top-of-sheet = header. Requires no labels; works on merged + banner-heavy sheets.
3. **Formatting features (Fan et al. AAAI'12)** — bold, font size, alignment, fill color, border. openpyxl exposes all of these via `cell.font.bold`, `cell.font.size`, `cell.alignment`, `cell.fill.fgColor`. Combine with type features in a Random Forest for best reported accuracy (97.4%).
4. **Uniqueness & length signals** — header cells are short labels, non-empty, highly unique across columns (low row-internal repetition, high inter-row distinctiveness). Good tie-breaker.
5. **LLM-based (SpreadsheetLLM / GPT-3 irregular-sheet parsing, Harris 2022)** — encode compressed sheet, ask model for header range. Highest ceiling but adds latency/cost and hallucination risk; best as fallback when heuristic confidence is low.
6. **CNN on cell-grid image (TableSense)** — highest accuracy (91% recall / 86% precision EoB-2) but heavyweight; not proportionate for one skill.

## Library prior art (short notes)

- **pandas `read_excel`/`read_csv`**: `header=0` default, no detection. Supports `header=[0,1]` for multi-row headers and `skiprows=callable` for custom logic. (pandas docs + pandas-dev#24440).
- **openpyxl**: no built-in header logic; exposes `cell.data_type` (`s`/`n`/`d`/`b`/`f`), `cell.font.bold`, `ws.merged_cells.ranges` — all needed primitives for heuristic classifiers.
- **Power Query `Table.PromoteHeaders`**: promotes row 1 only; ignores non-text/number cells; no title-banner handling — manual fix required.
- **R readxl**: single-header only; multi-header idiom is "read twice" (once for names, once with `skip=`). **tidyxl**: returns one row per cell with full style metadata — the closest R equivalent of the signals openpyxl gives you.
- **Camelot/Tabula (PDF)**: header inference is not their core job — they find table bounding boxes via line detection (Lattice) or text alignment (Network/Stream); header is typically "top row of detected table."
- **Excel ListObject (Ctrl+T)**: requires user-selected range; detection is contiguous-non-blank-region around the active cell, not semantic.
- **DeExcelerator / TabbyXL**: rule-based pipelines that explicitly label header vs metadata vs data cells — the most direct academic ancestor of your current skill.

## Recommendation for this skill

Replace the single-pass score with a **two-stage classifier**:

**Stage 1 — Candidate pruning** (keep current heuristics, cheap):
- Drop rows containing 【】, ※ at line start, or whose non-empty cell count ≤ 1 (banner).
- Drop rows fully inside a horizontal merge spanning > 50% of used columns.
- Drop rows below the first all-numeric row (data region).

**Stage 2 — Ranked scoring** (new, per surviving candidate row R, look-ahead k=3 rows):

| Feature | Weight | How to compute via openpyxl |
|---|---|---|
| Fraction of string cells in R | + | `cell.data_type == 's'` |
| Fraction of non-string cells in R+1..R+k | + | same |
| Per-column type flip R→R+1 (majority vote) | ++ | type vectors |
| R cells bold / larger font than R+1 | + | `cell.font.bold`, `cell.font.sz` |
| Uniqueness of R values (no duplicates across cols) | + | `len(set)==len(row)` |
| Mean cell-string length in R ≤ 15 chars | + | `len(str(v))` |
| Fraction of empty cells in R | − | `cell.value is None` |
| R is inside a vertical merge | − | `ws.merged_cells` check |

Pick the row with the highest weighted sum; if top two rows are contiguous AND both high-string, emit a **multi-tier header** spanning both (mirrors pandas `header=[r,r+1]`). Carry forward the value of any horizontally-merged parent cell to its children (standard unpivot step — see tidyxl/unpivotr idiom).

**Fallback**: if top-candidate confidence < threshold, call the LLM with a SheetCompressor-style compressed encoding (anchor rows + inverse index) and ask for the header range. This is the SpreadsheetLLM recipe and keeps token cost low.

This keeps the current rule-based guardrails (critical for Japanese 【】/※ conventions) but replaces the ad-hoc score with features whose effectiveness is backed by published benchmarks, and gives a principled escalation path to an LLM only when the cheap classifier is uncertain.

## Sources

- [SpreadsheetLLM: Encoding Spreadsheets for Large Language Models (arxiv 2407.09025)](https://arxiv.org/abs/2407.09025)
- [SpreadsheetLLM EMNLP'24 PDF](http://zmy.io/files/emnlp24-SheetEncoder.pdf)
- [TableSense: Spreadsheet Table Detection with CNNs (AAAI'19)](https://www.microsoft.com/en-us/research/uploads/prod/2019/01/TableSense_AAAI19.pdf)
- [TableSense arxiv 2106.13500](https://arxiv.org/abs/2106.13500)
- [Table Header Detection and Classification (Fan, Kim, Giles, AAAI'12)](https://clgiles.ist.psu.edu/pubs/AAAI2012-table-header.pdf)
- [Schema Extraction for Tabular Data on the Web (Adelfio & Samet, VLDB'13)](http://www.cs.umd.edu/~hjs/pubs/spreadsheets-vldb13.pdf)
- [WebTables: Exploring the Power of Tables on the Web (Cafarella et al., VLDB'08)](https://sirrice.github.io/files/papers/webtables-vldb08.pdf)
- [DeExcelerator (Eberius et al., CIKM'13)](https://dl.acm.org/doi/10.1145/2505515.2508210)
- [TabbyXL: Rule-Based Spreadsheet Data Extraction](https://link.springer.com/chapter/10.1007/978-3-030-30275-7_6)
- [pandas.read_excel docs](https://pandas.pydata.org/docs/reference/api/pandas.read_excel.html)
- [pandas auto-detect header issue #24440](https://github.com/pandas-dev/pandas/issues/24440)
- [Power Query Table.PromoteHeaders](https://learn.microsoft.com/en-us/powerquery-m/table-promoteheaders)
- [Power Query: Promote or demote headers](https://learn.microsoft.com/en-us/power-query/table-promote-demote-headers)
- [readxl: Multiple Header Rows vignette](https://readxl.tidyverse.org/articles/multiple-header-rows.html)
- [tidyxl: Read untidy Excel files](https://nacnudus.github.io/tidyxl/)
- [Camelot: How It Works](https://camelot-py.readthedocs.io/en/master/user/how-it-works.html)
- [openpyxl styles docs](https://openpyxl.readthedocs.io/en/stable/styles.html)
- [Parsing Irregular Spreadsheets with GPT-3 (Harris, TDS 2022)](https://medium.com/data-science/parsing-irregular-spreadsheet-tables-in-humanitarian-datasets-with-some-help-from-gpt-3-57efb3d80d45)
- [Hierarchical structure in complex tables with VLLMs (arxiv 2511.08298)](https://arxiv.org/html/2511.08298)
- [Orthogonal Hierarchical Decomposition for Table Understanding (arxiv 2602.01969)](https://arxiv.org/html/2602.01969)
