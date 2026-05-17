# xlsx skill — framework design (iter5)

**STATUS: deferred. Not implemented.**
iter5 used a surgical `xlsx_materialize.py` patch (+ merge forward-fill into data rows) instead of this framework. Fresh-LLM eval on the patched artifact was sufficient (4.5/5 factual questions on 法人契約チェックシート). Keep this doc as a reference for iter6+ if new corpus shapes force the family-script approach. If 6 months pass without adoption, delete.

## Problem

The current pipeline is a monolithic heuristic: `xlsx_classify.py` has 10+ hand-tuned features scoring candidate header rows, and `xlsx_materialize.py` is decoupled from classify's output (ignores `header_rows`, always uses row 1). Adding one feature to fix one sheet regresses another. Score-tuning is approaching overfit.

## New architecture

```
shape_probe (primitive)  →  family_router  →  <family>.classify()  →  <family>.materialize()
                                  ↓ no match
                              default family (current heuristic)
```

- **Primitives** (framework): cell scan, merge resolution, forward-fill, shape probe, materialize helpers (SQLite writer, markdown table writer).
- **Family scripts**: per-structural-pattern handlers. Each owns its own classify + materialize for one shape of spreadsheet.
- **Router**: runs shape probe → asks each family for match confidence → dispatches to the winner. Falls back to the default family if no match clears threshold.

## Shape probe output (per sheet)

Target size: 500–1500 bytes per sheet. Goal: enough for a family to decide match confidence without loading the full sheet.

```json
{
  "name": "プランコード",
  "max_row": 3862,
  "max_col": 11,
  "nonempty_density": 0.62,
  "first_rows": [
    {"idx": 1, "widths_nb": 1, "lens": [12], "merge_flag": "banner"},
    {"idx": 20, "widths_nb": 4, "lens": [0, 300, 181, 548, 172], "merge_flag": null},
    {"idx": 22, "widths_nb": 8, "lens": [0, 28, 28, 33, 28, 28, 33, 2, 2], "merge_flag": "v-merge"}
  ],
  "merges": {"count": 18, "max_rowspan": 2, "banner_rows": [1], "label_col_merges": []},
  "long_cells": {"rows": [20], "max_len": 548, "per_row_counts": {"20": 4}},
  "deep_sample": {"rows_30_230_median_width": 8, "width_histogram": {"8": 165, "10": 20, "9": 15}},
  "structural_hints": ["spec_block_above_data", "multi_tier_header_candidate"]
}
```

- `first_rows`: compact view of rows 1..~30 — widths, cell lengths (not values), merge role. Lens not values → no 5KB spec cells leak into context.
- `merges`: summary only, never per-cell.
- `long_cells`: location and count of ≥150-char cells. Rows above data, with ≥2 long cells, = spec block signal.
- `deep_sample`: width histogram of mid-sheet rows, median width = typical data row.
- `structural_hints`: coarse tags a family can pattern-match on.

## Family script interface

Location: `~/.claude/skills/xlsx/families/<name>.py`.

```python
NAME = "row1_db"
DESCRIPTION = "Simple DB: header at row 1, data rows 2..N, uniform width"

def matches(probe: dict) -> float:
    """Confidence [0.0, 1.0] that this family fits. Families return 0 when
    their signature doesn't match; router picks argmax above threshold (0.6)."""

def classify(wb, sheet_name: str, probe: dict, filename: str) -> dict:
    """Same output schema as the current xlsx_classify.py classify_sheet().
    Returns {name, path, header_rows, data_rows, content_type, ...}."""

def materialize(wb, sheet_name: str, classify_result: dict, output_path: str) -> dict:
    """Write the LLM-facing artifact. Each family owns its output format:
      - row1_db → SQLite, columns from row 1
      - multi_tier_header → SQLite, columns from concatenated header rows
      - notes_preamble → Markdown free text
      - rules_table → SQLite, columns from spec-block-following header, one
        row per atomic rule (decomposing 1 cell with multiple conditions)
    Returns {format, row_count, path}."""
```

Family authors only concern themselves with one structural family. No global feature interference.

## Cache / routing

- Per run: memoize probe dict per sheet.
- Family matching: synchronous, each `matches()` is cheap (reads only the probe, not the workbook).
- Selection: `argmax(family.matches(probe))` over loaded families; if max < 0.6, fall back to `default` family.
- Persistent cache (later iter): hash(probe) → chosen family name. Skipped in iter5; revisit when families stabilize.

## Fallback strategy

Iter5 scope: default family = the current `xlsx_classify.py` + a patched `xlsx_materialize.py` that finally honors `header_rows`. This keeps correctness for unknown shapes while new families are seeded.

Future (iter6+): when no family matches confidently, emit a stub + shape probe to the LLM, ask it to write a new `families/<name>.py`, save, retry. Voyager-style skill-library growth.

## Initial families to seed (task 11)

Minimum coverage for the current corpus:

1. **`row1_db`** — row 1 header, uniform data below (matches db_small, db_large, huge, 補償基準DB 5 sheets, 正解データ 4 sheets, ペットネーム, 対象, QA・資料提供依頼 passなし)
2. **`multi_tier_header`** — 2-row header at top (matches 基本情報一覧 [3, 4], 法人契約チェックシート [9, 10] if header is at top)
3. **`spec_block_then_table`** — spec preamble rows + real table header after (matches プランコード [22] both versions)
4. **`notes_preamble`** — all-prose sheet, no table (matches 各シートについて)
5. **`rules_table`** — structured checklist with merged rule rows (matches 法人契約チェックシート); includes 1:1 atomic decomposition downstream

`structured_small`, `structured_large`, `multi_sheet` from the synthetic corpus fit into 1–3 above.

## Dispatcher: `xlsx_process.py`

New entry script that replaces the implicit `classify → materialize` split in the skill's user-facing flow.

```
xlsx_process.py <file.xlsx> [--out-dir DIR]
  → per sheet: probe → family select → classify → materialize
  → emits manifest, per-sheet SQLite / markdown, routing log
```

Keeps the existing `xlsx_classify.py` and `xlsx_materialize.py` callable as the default family implementation.

## Testing strategy

Primary quality bar: **a fresh, cache-cleared Claude Code instance must be able to answer factual questions about an xlsx from the materialized artifact alone.** Pareto target: (downstream answer accuracy) × (tokens consumed by the pipeline + artifact context).

- **pytest-regressions** golden files per family: one fixture sheet per family, golden = classify+materialize output (routing stability check, not the real quality bar)
- **hypothesis** property: every family's `matches()` returns [0.0, 1.0]; classify output schema matches; materialize writes non-empty file.
- **LLM eval subagent** (new): fresh subagent is given the materialized artifact only, asked N factual questions derived from the xlsx (pre-computed answer key). Score = correct answers / N. Run once at iter end; target ≥90% on each family's representative file.
- **Corpus E2E**: run dispatcher on all 11 corpus files, compare against golden dispatcher outputs (routing decision + materialize content hash).

## Autonomy rules

Per `feedback_selfimprove_loop_hygiene.md` rule 0: decide design trade-offs (thresholds, family granularity, fallback policy, etc.) without asking. Default decisions for the questions that came up in design review:

- **Fallback default family**: yes, keep current heuristic alive as `families/default.py`. No error-raise on unknown shapes.
- **Selection rule**: `argmax(matches)` with threshold 0.6. If top-2 are within 0.05, fall back to default (safe side).
- **Family granularity**: start at 5 families listed above; split only if corpus E2E + LLM eval exposes conflation.
- **Synthetic corpus sheets**: fold into the 5 families where they fit; don't create synthetic-only families.

## Migration order

1. [done task 7] Harness migrated to pytest-regressions + hypothesis
2. [task 9] `xlsx_shape_probe.py` primitive
3. [task 10] `xlsx_process.py` dispatcher + family loader + fallback to current pipeline
4. [task 11] Seed 5 family scripts + associated golden tests
5. [task 12] E2E verification on 11-file corpus; materialize quality checked end-to-end
6. [task 13] SKILL.md / IMPROVE.md rewrite

## Out of scope for iter5

- LLM-written family generation (iter6 Voyager-style)
- Persistent cache hash(probe) → family
- Cross-run learning / refinement
- New corpus additions
