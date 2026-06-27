# XLSX Skill self-improvement changelog

## 2026-06-25 — theme / indexed 色の解決（色脱落バグ修正）

背景: ユーザ指摘「色を反映していない。色が重要なケースが多すぎる」。jibun-de で
corpus を実 resolve して裏取り。`_style_attr`/`_hex6` は ARGB 直指定 (color.type=="rgb")
しか拾えず、Excel の主流である theme 色（color.theme + tint）と legacy indexed を
全て None 扱いで落としていた。忠実性 hard ゲートは文字列のみ照合し色を見ないため
脱落が素通りしていた。

実証（非白 theme 塗りの脱落数 / corpus 全 resolve）:
- 正解データ20260415: 98 セル全損（色シグナルが light green #E2F0D9 のみ＝色情報が丸ごと不可視）
- transposed_field_major: 81（緑 #E2F0D9/#C5E0B4・黄 #FFF2CC・灰）
- 業務概要・QA: 1481（灰系セクション地色 + 青 #BDD7EE）
- 法人契約チェックシート: 0（theme 塗り 496 は全部白＝白除外が妥当。RGB 非白 53 は従来どおり出力）
- indexed は corpus に存在せず（0）

修正:
- `xlsx_to_html.py` に `_theme_palette`（`wb.loaded_theme` から theme1.xml を parse、
  SpreadsheetML の index 入れ替え lt1↔dk1 / lt2↔dk2 を考慮）+ `_apply_tint`（HLS 輝度）
  + `_resolve_color`（rgb / theme+tint / indexed の3形式を解決、indexed 64/65 は auto で除外）。
- `_style_attr(cell, palette)` 化。白 (#FFFFFF) 除外はノイズ抑制として継続。
- パレットは workbook に1度だけキャッシュ。
- golden 回帰を色込みで再生成（上記3ファイルの sha のみ変化、faithfulness は全件 100% 不変、
  spans/tr 不変＝構造非破壊を確認）。色の回帰ガードはこの決定論 golden に委ねる
  （runtime verify ゲートへの色チェック追加は白/近白除外で false fail を生むため見送り）。

## 2026-06-22 — 全面再設計 着手（設計 + 変換器ユニット）

背景: ユーザ要望「原典に忠実かつ AI ネイティブな変換 skill にしたい。最新の状態に」。
grill-me で存在意義から各分岐を確定、deep-strict で prior art を調査、bake-off で
最小検証してから実装。設計の全文は `_dev/REDESIGN_2026-06.md`。

### 確定した方針

- 成果物を「SQLite 既定」から「忠実な構造保存 HTML 既定 + SQLite(巨大)例外 +
  画像(layout)例外」へ収斂。AI ネイティブさは事前解釈でなくフォーマット由来。
- overfit した header 検出ヒューリスティック(detect_header_row + weight 群)は
  「修正」でなく「忠実 HTML により不要化→削除」。
- triage は Claude 常時レビュー(コスト許容との判断)+ 決定論が証拠(shape_probe)と
  安全網(verify/サイズ)。根拠 deep-strict: 構造把握は text≥image(TabVerse)、
  vision は layout 限定、hybrid/tiered が本番標準。
- テストは「決定論 golden(HTML 変換器)+ 忠実性 hard ゲート + eval(消費側回答品質)」。

### bake-off 結果（本実装ゼロ行の最小検証）

最難関3シートで LibreOffice html / xlsx2html / 手書き openpyxl を比較
（忠実性 / AI ネイティブ / トークン）。手書き openpyxl が決定的勝利:
忠実性 100%（既製2つは転置で6〜7%欠落）、トークン 4〜15倍小。
AI ネイティブ eval: fresh subagent が priming 無しで多段ヘッダ・転置を読解（3.5/4）。
詳細は REDESIGN_2026-06.md「bake-off 結果」。

### 実装（このイテレーション）

- `scripts/xlsx_to_html.py` 新規: 忠実な構造保存 HTML 変換器。
  結合→rowspan/colspan、静的色・塗り→inline style、日付シリアル→ISO(number_format
  準拠)、図形/シェイプ文字→アンカー注記(xlsx_drawings 統合)。解釈ゼロ。
  iter_rows ベースで高速(QA ワークブック31k+22kセル含め6s)。
  忠実性 self-verify hard ゲート(欠落で exit 2)。
- `_dev/tests/test_html_regression.py` 新規: 12 corpus ファイルの決定論 golden
  (faithful/spans/tr/sha256)+ 全 HTML 経路シート 100% 忠実の hard assertion。
  巨大シート(>20000セル, SQLite 経路)は golden 対象外として skip 記録。
- 全 corpus 検証: 29シート中の HTML 経路シートすべて 100% 忠実、fail ゼロ。
- harness: 30 passed（既存18 + 新規12）、34s。

### 完了（同セッション続き）

- triage を変換器に内蔵: `xlsx_to_html.py` が HTML↔SQLite をサイズ算術
  (>20000 used cells → SQLite)で決定、図形フラグ(`suggests_image`)を manifest 化、
  図形抽出を workbook 1回に集約。shape_probe は HTML が構造ビューを subsume するため
  不要と判断し新設不要（既存孤児は削除）。
- `SKILL.md` を新思想で全面書き直し（HTML 既定 / SQLite・画像例外 / manifest を
  信じ再判断しない / 忠実性は hard ゲート）。
- classify 一掃: `xlsx_classify.py`(697行)・`xlsx_shape_probe.py`・
  `test_classify_regression.py` + golden 12件を削除。`test_classify_properties.py`
  は `test_primitives_properties.py` にリネーム。harness は html golden + 忠実性
  hard assertion + primitives property に再編、18件・6.5s（旧30件・34s より高速）。
- `xlsx_materialize.py` rewire: overfit な classify 依存を断ち、既定は「先頭非空行=
  ヘッダ」。E2E で『巨大かつ spec ブロック』のプランコードが反例と判明
  （col_N 列名）→ `--header-rows` を追加し、Claude が上部を覗いてヘッダ行を渡せる
  ように（SQLite 版「Claude が分類器、機械が判断を honor」）。行22指定で列名が
  意味のある日本語に復旧。
- docs 再編: P1–P5 / merges / transposed の各 doc を削除、keep する
  drawings / multi_sheet / p6_visual / manifest テンプレを新語彙
  (manifest / path:html|sqlite / suggests_image)へ更新。
- 整理: 廃案の root `DESIGN.md`(iter5 framework)を `_dev/` へ退避、
  root の stray テストキャッシュ除去。shipping root は SKILL/docs/scripts/templates のみ。
- stale 参照の全体掃き出し: classifier / suggests_visual / header_confidence /
  P1–P5 / 削除スクリプト の参照ゼロを確認。

### E2E 検証（fresh-Claude skill-usage check, IMPROVE.md 必須項目）

新フローを統合素通しで検証。対象は新フロー未通しの実マルチシート 補償基準DB(5シート)。
- doer subagent（priming は「SKILL.md にスキルがある」のみ、手段=HTML/triage/header-rows は未教示）:
  SKILL.md だけで完走。3 HTML(100%忠実) + 2 SQLite(self-verify ok) + manifest、triage 正。
- consumer subagent（成果物のみ、xlsx 禁止）: 事実質問 3/3 正答。HTML 直読 + SQLite クエリ、
  Q2 の「対象」完全一致 vs 対象外/対象/対象外 の区別まで正確。
- 発見 defect 1件: `xlsx_verify.py` の引数形式が SKILL.md に無く doer が推測 → Scripts 行に
  位置引数 + ratio 注意を追記して修正。
- 結論: 設計自身の品質基準（fresh Claude が成果物だけで原典に答えられる）を満たすことを実証。

### 画像経路 E2E（追加検証）

suggests_image=true の HTML 経路シート（transposed_field_major の 正解データの確認）で画像経路を実通し。
- 実 defect 発見: `xlsx_visual.py` が PyMuPDF(`fitz`)依存で、当環境に未インストール → PDF→PNG が落ちる。
- 修正: `pdf_to_pngs` を poppler の `pdftoppm`（CLI、既インストール）シェルアウトに置換。
  壊れやすい C 拡張依存を排除。`docs/p6_visual.md` も追従。
- 検証: render 成功（22ページ＝転置で横長）、Read ツールが PNG をネイティブ読込（レイアウト＋黄色塗り視認）。
- 副次確認: 同シートの静的な黄色塗りを HTML 変換器が 38 セル `background:#FFFF00` として捕捉済み
  → 静的色は HTML 自己完結、画像は条件付き書式色／レイアウト専用という設計意図を実データで確認。

### 保留（トリガ待ち）

- spanning-label(区分=新契約 rowspan=50)の凡例 enrichment 層: 消費側の
  行数誤カウント観測が再現したら起動 [eval で再現するか]。
- 条件付き書式由来の色: openpyxl で取得不可 → 必要時は画像例外で拾う [当該シート発生時]。


## 2026-04-18 — Iteration 1 (initial self-improve run)

Baseline harness: 6/6 pass (synthetic corpus only, LLM paths never tested fresh).

Spawned 4 parallel subagents (clean context) to exercise P1–P4 paths on:
- corpus/structured_small.xlsx (P3)
- corpus/structured_large.xlsx (P4)
- corpus/multi_sheet.xlsx (multi)
- ~/Projects/MS/法人契約チェックシート_202507.xlsx (real, P4)

Common friction points found:
1. `header_row_index` not exposed — every subagent re-derived the header manually; 法人契約チェックシート needed row 9 (not row 1).
2. `ws.max_row` ≠ real data extent — trailing blank rows silently counted.
3. `merges.md` lacked: label spans across logical columns (Rule 2b), title-banner skip (Rule 2c), both-axis short-label merges (Rule 2d), None-value fill-breakers, choice-cell delimiters `/` `／` `\n`.
4. `p4_structured_large.md` didn't default an output format; key naming unspecified; idempotency contract implicit.
5. Manifest template missed `実ヘッダ行` and didn't require `なし` when no relationships found.

Changes applied:
- `scripts/xlsx_classify.py`: added `detect_header_row` (score-based, penalizes 【】※), `detect_data_rows` (trims trailing blanks), exposes `header_row_index`, `data_rows`, `data_row_count`.
- `docs/merges.md`: added Rule 2b, 2c, 2d; expanded choice-cell delimiter guidance; clarified None-value fill semantics.
- `docs/p4_structured_large.md`: default output format by content_type; Japanese keys preferred; explicit idempotency contract; use classifier bounds not `ws.max_row`.
- `docs/p3_structured_small.md`: choice-list split rules (raw → `[はい, いいえ]` etc.); optional provenance comment block.
- `docs/multi_sheet.md`: `なし` explicitly required when no relationships found; absolute manifest path in final report.
- `templates/manifest.md`: added `実ヘッダ行` column; `なし` example under relationships.

Regression: harness green (6/6) throughout; `path` assignments unchanged; hook fired after each edit.

Re-evaluation: 2 fresh subagents (real MS P3, corpus P4) confirmed:
- Classifier bounds correct in both
- Output row counts match (50, 200)
- Idempotency verified via shasum on the P4 script output
- Only residual ambiguity: 6 both-axis short-label merges (now covered by Rule 2d post-fix); `/` delimiter in choice cells (now covered post-fix)

Status: accepted. No rollbacks needed.

Notes for iteration 2:
- Consider adding a real-world corpus file (rubber-stamp cells, hidden rows, formulas) once such xlsx is available
- Consider exposing a `hint_column_map` in classifier output for known schemas (checklists)
- subagent reported 法人契約チェックシート `項目` column has multi-tier labels (`1/2`, `2/2` as form pages vs sub-labels) — not a skill bug, but documentation could mention it

---

## 2026-04-18 — Iteration 2 (knowledge-driven)

Spawned research subagent for header-detection SOTA. Written to `knowledge/header_detection.md` (cites SpreadsheetLLM, TableSense, Adelfio&Samet VLDB'13, Fan AAAI'12, Power Query, pandas).

Applied research recommendation: **two-stage header classifier** in `xlsx_classify.py`:
- Stage 1 (rule-based pruning): banners, 【】/※, <3 short-label cells
- Stage 2 (weighted scoring): type-flip (dominant, weight 2.5), str_frac, bold, uniqueness, label-length bonus, empty penalty, short-count bonus
- Multi-tier detection gated on hierarchy-merge evidence (not just contiguous-and-similar-score)

Exposed new classifier fields: `header_rows` (list, supports multi-tier), `header_confidence`, `header_features` (for debug).

Mid-refactor regression: intermediate edit states failed harness (classify_sheet expected dict but got int during partial edit). Hook correctly caught this and blocked further edits. After all related edits landed, harness green again.

Tuning iteration: initial weights caused `法人契約チェックシート` row 4 (`AC:` + `法人名:`) to beat row 9 by 0.03. Fixed by:
- Raising Stage 1 threshold from "≥2 non-empty" to "≥3 short-label cells"
- Adding absolute short-cell-count bonus (scales with actual label count)
- Tightening multi-tier gate (requires score ≥2.0, 90% match, AND hierarchy-merge evidence)

Verification via 2 fresh subagents on `structured_large.xlsx` and real MS checksheet:
- Both confirmed correct `header_row_index` and `data_rows` from classifier
- P4 subagent verified idempotency via shasum
- Only residual ambiguity: 6 both-axis short-label merges (led to Rule 2d in merges.md) and `/` vs `\n` choice separators (led to expanded choice separator doc)

Status: accepted. harness 6/6 pass. `法人契約チェックシート` now routes P3 with 50 correct rules (was misrouted to P4 briefly during tuning).

## 2026-04-18 — Infrastructure: shared selfimprove

Created `~/.claude/selfimprove/`:
- `knowledge/loop_design.md` (Reflexion, CRITIC, Voyager, Eureka, STOP synthesis)
- `templates/` (IMPROVE, harness, RUBRIC, generate_corpus)
- `bootstrap.py` (scaffold a new skill's selfimprove/)
- `README.md`

Migrated xlsx's `IMPROVE.md` to new protocol with:
- STOP safety rails (cannot edit harness / corpus / regressions / loop itself)
- Candidate competition (best-of-N with harness judge)
- Voyager promotion gate (≥2 distinct inputs)
- Reflexion memory (`reflections.jsonl`)
- Regression gate (failing inputs auto-added to `regressions/`)
- Convergence detector (5-iter cap, oscillation, diff-size explosion)

Added `regressions/` dir and empty `reflections.jsonl` to xlsx's selfimprove.

Next skill (pdf/pptx) can `python3 ~/.claude/selfimprove/bootstrap.py <name>` to scaffold.

---

## 2026-04-18 → 2026-04-19 — Iteration 4 (header detection on real MS corpus)

Corpus: added 5 real MS Primary Life xlsx files to corpus/. Regenerated baselines.

### Problems surfaced

- `プランコード` sheet's real header at row 22 was losing to a deep data row (r39) — widths and short-cell bonus both favored the false positive
- Sparse-trailing-column sheets (pass版 QA with max_col=42 but data ~8 wide) deflated `str_frac` etc. via max_column denominator
- `post_spec_block` heuristic (added mid-iter) fired on drug-info data rows containing a single 500-char cell

### Classify changes (scripts/xlsx_classify.py)

- `run_start_bonus` rewritten as `(forward_run_within_tol − backward_run_within_tol) * 0.1`, capped at +2.0. Rewards rows starting a consistent-width region while canceling mid-run rows.
- New feature `desc_contrast` (tiered 1.0 / 1.5 / 2.0 at ratio ≥ 1.8 / 2.5 / 3.0): bonus when candidate's mean string length exceeds the next 3 rows by ≥1.8×. Covers the Japanese descriptive-header-over-short-code-data pattern that type-flip misses.
- New feature `post_spec_block` (distance-weighted 1.25 → 0.25, weight 1.5): bonus when one of 5 rows above has **≥2 cells of ≥150 chars** (a spec/documentation block). The ≥2 requirement avoids false positives from single-long-text data columns.
- `n_cols_eff` normalization: when `max_column > typical_width * 2`, normalize `str_frac/bold_frac` by `max(this_w, typical_width)` instead of raw max_column. Fixes sparse-trailing-column deflation without affecting normal DB sheets.
- `short_cnt` bonus restored after brief removal, now scaled by `uniq_frac` and capped at 5 (down from 8) — reduces over-reward of short-code data rows while preserving the signal for DB headers.

Other files unchanged from iter3.

### Results on 5 real samples (header row detection)

- 業務概要・QA passなし (4 sheets): 4/4 correct — プランコード fixed from [39] → [22]
- 業務概要・QA pass版 (5 sheets): 4/5 — プランコード [39] → [23] (expected [22], off-by-one)
- 正解データ20260415 (4 sheets): 4/4
- 法人契約チェックシート_202507 (1 sheet): [9, 10] ✓ multi-tier
- 補償基準DB (5 sheets): 5/5 — 対象 sheet fixed from [24] → [1] after post_spec_block tightening

Harness: 11/11 pass maintained throughout.

### Critical downstream finding (open, not in this iter)

E2E subagent confirmed that `xlsx_materialize.py` **ignores `header_rows`** and always uses row 1 for SQLite column names. Breaks LLM-facing output on any sheet whose header ≠ row 1:
- 法人契約チェックシート: 32 columns all `col_N` (worst case)
- プランコード pass版: columns = banner text, data rows polluted with preamble
- 基本情報一覧 (both files), pass版 QA: wrong column names, shifted data

Classify accuracy improvements are a foundation but user-facing quality is still blocked on the materialize fix.

### Process lessons (from `token_spikes_20260419.md`)

- Two regressions on 補償基準DB required re-runs because `short_cnt` was removed without first checking which baselines depended on it. Fix: before deleting a feature, grep baselines for sheets that might rely on it.
- post_spec_block initial form fired on drug-info rows — didn't test "looks similar but shouldn't fire" case before wiring. Lesson: for every coarse feature, probe at least one counter-example before committing.
- Repeated inline score-replay heredocs cost extra tokens. Deferred: add `--debug-headers` flag to xlsx_classify.py for the next iteration.

Status: accepted. Classify changes locked in. Materialize fix remains open.

---

## 2026-04-19 — Iteration 5 (framework groundwork + materialize quality fix)

### Scope decisions

- Framework refactor (family scripts, shape-probe router) **evaluated and deferred** — meta-check determined that a focused materialize fix closed the user-facing quality gap without adding abstraction. Framework stays in `DESIGN.md` for a future iter if new corpus shapes force it.
- LLM-eval subagent adopted as the real quality bar, replacing classify-only baseline diff.

### Changes

- **Harness migrated to pytest + pytest-regressions + hypothesis.** 17 tests (12 regression golden files + 5 property tests). Hook updated. Old `harness.py` and `baseline/` removed. Hypothesis found and fixed a real bug in `sanitize_slug` (fallback "workbook" ignored `max_len`).
- **`xlsx_shape_probe.py` added** — compact structural fingerprint (density, first-row widths/lens, merges, long cells, deep-sample histogram, structural hints). Will feed any future family-routing layer. Size budget ~1-25KB per sheet depending on column count.
- **`xlsx_materialize.py` rewritten** to consume classify's `header_rows` and `data_rows`. Forward-fills merge anchors in both header labels (multi-tier concat with ` / `) and data rows (merged label columns like 区分 propagate to every spanned data row).
- **`DESIGN.md` added** — framework architecture for when it's needed.
- **`SKILL.md` updated** — explicit downstream-consumer = fresh Claude, scripts list refreshed.

### Prerequisites installed globally (2026-04-19)

`uv` 0.11.7, `ruff`, `pyright`, `pytest` (+ hypothesis + pytest-regressions + coverage + openpyxl injected). See `~/.claude/selfimprove/PREREQS.md`.

### Results — LLM-eval subagent on materialized artifacts

Representative files:
- `法人契約チェックシート_202507` (worst-case multi-tier, 32 cols) — fresh subagent answered 4.5/5 factual column-aware questions using sqlite3 alone (~19k tokens across 2 files, 5 questions combined).
- `補償基準DB 対象外_無条件` — 5/5 simple lookups.

Before iter5, the 法人契約チェックシート artifact had all `col_N` column names, making those questions unanswerable. Post-fix, column names are `区分___新契約`, `帳票等___申込書_意向確認書`, `項目___商品`, `確認事項___...`, `チェック欄___はい/いいえ`, `特記事項` — self-describing to a fresh LLM. Forward-fill into data rows additionally populated the `区分` column across all 49 rule rows with "新契約".

All 11 corpus files materialize cleanly (0 failures).

### Remaining known issue

- pass版 プランコード classify returns hdr=[23] (off-by-one vs expected [22]). Root cause in classify; cheap to fix only by adding more heuristic weight, which the meta-check flagged as premature. Deferred — will revisit if LLM-eval on that specific sheet drops below threshold.

### Process observations (vs iter4)

- Autonomy: after the "stop asking" course-correction, the rest of iter5 ran with zero design-trade-off questions to the user. Faster, fewer context-switches.
- Pareto framing prevented unnecessary framework build. iter4 would have added family_runner.py + 5 family scripts. iter5 replaced that with 1 surgical patch to materialize.py and its merge forward-fill. Same or better downstream quality at a fraction of the complexity.

Status: accepted.

---

## 2026-04-19 — Iter5.1 (low-confidence → notes rule + materialize skip)

Triggered by 6 new sample xlsx added to `xlsx_sample/` (not corpus). Per-file sequential test found that flow-diagram / prose sheets (no real table structure) returned `header_confidence=0.0` from classify but were still routed as `content_type=table`, producing SQLite with all-`col_N` columns — unusable for downstream LLM.

### Changes

- `xlsx_classify.py`: when `header_confidence < 1.5` and `content_type=="table"`, upgrade to `notes`. Lets these sheets route to P3 notes-rendering flow instead.
- `xlsx_materialize.py`: skip sheets with `content_type=="notes"` with a clear stderr warning pointing to the P3 notes flow. materialize is a SQLite-for-tables tool; emitting garbage tables for prose sheets is never useful.

### Verification

Tested all 6 new samples one-at-a-time (per sequential-processing rule):
- 5/6 files: clean tables with meaningful Japanese column names (7–30 cols, 12–8172 rows). All P1/P2 paths.
- `pw_モニタリング整理 のコピー.xlsx`: 2 table sheets now correctly materialize, 2 prose sheets correctly skipped with notes-flow pointer.

Harness 17/17 pass throughout — no existing corpus sheet hit the `conf<1.5 + table` threshold, so no baseline regeneration needed.

Rule cost: ~5 lines of code, no new heuristic features.
