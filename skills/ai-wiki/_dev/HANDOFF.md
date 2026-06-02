# ai-wiki 引き継ぎ資料 (2026-04-24 v5 完了)

本書 1 枚で次の session (または fresh Claude) が作業を再開できる状態にする。詳細は本書から各 doc へジャンプすること。

---

## 0. 最新状況 (2026-04-24 Phase v5 完了、concept 完全廃止)

**Phase v5 完了**: 三浦さんの design reversal (「user が読むのは tree だけ」) を反映し、concepts/ 層を全削除。user が読む content は narrative tree のみで、詰まった箇所は friction-driven note で後発生成する形に確定。

### v5 で削除されたもの

| 削除 scope | 内容 |
|---|---|
| vault dirs | `concepts/`, `entities/`, `maps/` |
| scripts | `extract.py`, `resolve.py`, `projection.py`, `enrich.py`, `digest.py`, `coverage.py`, `drill.py`, `research.py`, `tree_parser.py` |
| prompts | `enrich_concept.md`, `enrich_verify.md` |
| dispatcher commands | `enrich`, `project`, `coverage`, `drill`, `research`, `ingest --from-digest` |
| corpus / tests | `concept-v1-shell.md`, `concept-v2-enriched.md`, `map-sample.md`, `mini-digest.md`, `arxiv-sample.md`, + 関連 regression tests |

### v5 の vault 構造

```
~/ai-wiki/
├── narratives/           # 主コンテンツ (forest)
├── sources/              # 原典 (不可侵)
├── notes/                # friction driven、最初の note 発生時に作成
├── reps/                 # drill reps (現状未使用、将来用)
├── .narrative-qa/ / .narrative-gaps/  # QuestEval 隠し metadata
├── index.md / log.md / manifest.json / ignore.json / hot-cache.md
```

### v5 dispatcher command 一覧

| command | 用途 |
|---|---|
| `ingest <arxiv:X \| md>` | sources/ へ原典保存 |
| `status` | vault 統計 |
| `lint` | dead_link 検出 + index.md 再生成 |
| `pillars [--top-n N]` | narrative wikilink 頻度 top-N |
| `narratives` | forest 検証 + _index.md 再生成 |
| `narrative-draft <md>` | source md → narrative tree |
| `narrative-split <slug> --section <H2>` | narrative の 1 章を別 tree に切出 |
| `coverage-narrative <slug>` | QuestEval gap report |
| `pipeline [--arxiv X]` | ingest → lint → narratives の 3 stage |

### テスト状態

- **120 passed + 3 live skipped** (opt-in via `AI_WIKI_LLM_LIVE=1`)
- v5 core test: `scripts/tests/test_v5_core.py` (vault / schema / pillars / pipeline / ingest)
- v3-2 継続: `scripts/tests/test_narrative.py`, `_dev/tests/test_narrative_schema.py`
- v4-1〜v4-5: `test_llm.py`, `test_narrative_draft.py`, `test_coverage_qa.py`
  (mode C 削除で `test_narrative_mode_c.py` は除去済、v5-5 で test_narrative_draft に slug conflict + new flow test 追加)

### 次 session の着手

**コア model は確定**。以下の順で empirical 検証に進む:

1. 三浦さんが `~/ai-wiki/narratives/ols-chapter-3.md` を実運用 (retention / exploration AC §12.9)
   — 旧 pilot `causal-inference-keio.md` は v5-5 empirical test 時に source mismatch 回避のため削除、ols-chapter-3 を新 pilot として確立
2. 詰まった箇所で Claude 対話 → 必要に応じて `notes/<slug>.md` 新規作成
3. 別 domain で 2 本目の narrative 試作 (`narrative-draft` で format 汎用性検証)
4. 興味ある arxiv paper を手動で `ingest arxiv:<id>` → `narrative-draft` で深掘り試験

Claude Code 側で新規作業はなく、**user の study 中に違和感が湧いた時の修正対応が主フロー**。notes/ format 規約 (frontmatter 等) は最初の note 発生時に決める (§13.5)。

---

## 0.1 (過去) 2026-04-24 Phase v4 完了、LLM-in-script 実装済

**Phase v4 完了**: LLM 呼び出しを `scripts/llm.py` 境界に内包、対話依存を最小化。

### v4 で追加された capability (全て user 任意 invoke)

| capability | コマンド | 動作 |
|---|---|---|
| 自動 enrich | `dispatcher.py enrich --execute` | shell concept を Claude CLI で自動 edge/body 生成、CoVe、commit |
| narrative 自動生成 | `dispatcher.py narrative-draft <md>` | md → size 適応 (single/chunked/hierarchical) → CoVe → QuestEval coverage → commit |
| pipeline | `dispatcher.py pipeline` | 5 stages (ingest→enrich→project→lint→narratives) chain 実行 |
| coverage gap report | `dispatcher.py coverage-narrative <slug> --source <md>` | QuestEval 型で narrative の情報漏れを QA 判定 |

### 絶対原則 (user 2026-04-23 指示)

1. **API 呼び出し禁止** — Anthropic SDK / HTTP API 全て禁止
2. **Claude Code CLI のみ** — `claude -p --model opus --output-format json` subprocess
3. **schedule / cron / hook なし** — 全て user-triggered、cadence を外部埋め込みしない
4. **pre-commit review gate なし** — schema lint 通過即 commit、semantic 検証は user の study 中に
5. **md 入力のみ** — PDF parse 層は実装せず
6. **1 往復 review** — 違和感感知 → Claude Code に指示、script は fallback なし

### 実装済 infra (scripts/)

- `llm.py` (v4-1): `call_claude()` subprocess wrapper + prompt template loader
- `enrich.py` 拡張 (v4-2): `execute_enrich()` with CoVe
- `narrative_draft.py` (v4-3): md → tree、size 適応、自動 coverage 統合
- `pipeline.py` (v4-4): orchestrator、fail 境界を stage ごとに制御
- `coverage_qa.py` (v4-5): QuestEval 型、`.narrative-qa/` `.narrative-gaps/` 隠し metadata
- `prompts/` (v4-1〜5): 8 prompt templates (enrich×2、narrative×4、coverage×2)
- test suite: **290 passed + 3 live skipped** (opt-in via `AI_WIKI_LLM_LIVE=1`)

### user 介入の 3 capability + study

```
(1) kickoff:  dispatcher.py pipeline          (user 任意)
              dispatcher.py narrative-draft   (user 任意)
              dispatcher.py drill             (user 任意)

(2) study:    ~/ai-wiki/ を Obsidian で読む / drill 応答
              違和感・情報不足を感知

(3) edit:     違和感が湧いたら Claude Code に指摘 → 修正
              `.narrative-gaps/<slug>.md` の report も修正 hint として参照可
```

### 次 session の着手

v3-2 pilot 実運用 (user-side) + v4 infra 実運用検証が主。Claude Code 側で新規作業はなく、user の study 中に違和感が湧いた時の修正対応が主フロー。

iter-v2-4 (drill sweet spot) は v3-2 実運用結果を踏まえ判断。

---

## 0.1 (過去) 2026-04-23 Phase v3-1 完了

**Phase v3-1 完了**: pilot narrative tree 構築 + 書式原則の確立。

### 完了したこと

1. **Pilot tree 作成**: `~/ai-wiki/narratives/causal-inference-keio.md` (184 行)
   - 題材: 慶應・頼慶泰・計量経済学各論・因果推論 (LS1/LS2、確率論復習 + OLS)
   - single-spine 問題駆動型、ROOT = 「X の Y への影響を有限データから測る」

2. **書式原則の結晶化** (4 つの iteration で導出):
   - 原則 1: ノードは概念対象単位で束ねる
   - 原則 2: 道具は使う箇所で登場 (独立の道具箱なし)
   - 原則 3: エッジは問題駆動 (「次の章」ではなく「動機づけた」)
   - 原則 4: 直読可能性を basis とする (AI 仲介前提にしない)

3. **構造原則の確定**:
   - forest 構造 (peer な独立 tree 集合、階層なし)
   - tree is working hypothesis (出典・引用・信頼度なし)
   - 固定辞書 ([?][★][◯][✕][∥][⛔][!][∴][⤴][⤵][⟳][↺])

4. **Docs 反映完了**:
   - REQUIREMENTS.md §12.11-§12.16
   - SPEC.md §11 (narrative tree 書式仕様、10 sub-sections)
   - ALTERNATIVES.md カテゴリ H (棄却案 H1-H7)
   - CHANGELOG.md iter-v3-1

5. **棄却された書式** (ALT H 参照):
   - TOC 型 / 歴史時系列 / 3-branch 並列 / 過剰圧縮 / source pointer / cross-check / 階層大 tree

### 追加完了 (2026-04-23 後半、iter-v3-2 / Phase v3-4 + v3-5 前倒し)

- `scripts/narrative.py` 新規 (validate / lint / forest index, 220 行)
- `scripts/vault.py` 拡張 ("narrative" kind サポート、narratives/ subdir)
- `scripts/dispatcher.py` に `narratives` コマンド追加
- 32 unit tests + 6 corpus regression tests (`_dev/tests/test_narrative_schema.py`)
- 156 → 290 tests pass (+3 opt-in live)
- `_dev/corpus/narrative-pilot.md` = canonical 例として固定
- `~/.claude/skills/ai-wiki/` へ deploy 済み
- `dispatcher.py narratives` 動作確認: pilot 1 本 ok:true、forest index 生成

### 次 session の着手 (Phase v3-2)

**pilot tree を user 実運用**:
- 三浦さんが causal-inference-keio.md を read/use
- retention AC (drill cue として機能するか) / exploration AC (迷子防止・前進感) を empirical 検証
- 疑問が湧いた箇所で source (LS1/LS2 PDF) 検証 → 誤りがあれば tree 修正
- 使用感で format 原則の妥当性を再確認
- 必要に応じて `python3 ~/.claude/skills/ai-wiki/scripts/dispatcher.py narratives` で lint / index 再生成

**Phase v3-3 以降の判断材料**:
- per-concept file (§12.5): narrative tree と共存/置換/廃止のどれが妥当か
- cardinality cap (§12.6): 実運用で 0-5 の上限が問題になるか

iter-v2-4 (drill sweet spot) はさらに後ろ倒し、v3 schema 確定後に再評価。

---

## 1. このプロジェクトは何か

**ai-wiki** = 個人の AI 研究知識 vault + Claude Code skill。

- **vault**: `~/ai-wiki/` (Obsidian 互換 markdown)
- **project source**: `/Users/ivymee/Projects/ai-wiki/` (本書の所在地)
- **deployed skill**: `~/.claude/skills/ai-wiki/` (source と同期)

### 設計思想 (継承)

- **mcp-study v2**: 採点なし count-based drill、coverage 保証、決定的 term extraction
- **Karpathy LLM Wiki (obsidian-wiki, Ar9av)**: 4-stage pipeline (Ingest → Extract → Resolve → Schema)、emergent schema、LLM is the maintainer
- **v3 narrative tree (Karpathy LLM Wiki の divergence)**: problem-driven single-spine、forest 構造、working hypothesis (出典・cross-check なし)

### なぜ良い tree ができるのか (設計理由 — 2026-06-03 言語化)

`narrative-draft` の品質は「うまい執筆プロンプト」ではなく **4 つの forcing function の合成**。1 ツリー = ~7 LLM call のフィードバックループの産物なので、prompt 1 枚を読んでも仕組みが見えない。一番効いているのは 4。

1. **ダメ既定動作の明示禁止** — LLM に教科書を要約させると放置すれば必ず**目次型 (topic grouping)** を吐く。`narrative_single.md` はこれを名指しで禁止し「各サブ問題は前の答えから必然的に生じる問題で繋ぐ (spine)」を強制。足すより**禁じる**のが効く。
2. **閉じた記号辞書 = 役割分類の強制** — `[?][★][✕][⟳]…` は飾りでなく forcing function。`[★]`(採用解) を貼るには「何の問題を解き・どの候補が敗れたか」を確定せねば貼れない。ラベリングが弁証法構造への commit を矯正する。
3. **生成と検証の分離 (CoVe)** — `narrative_cove.md` が別パスで draft だけを context に 4 原則を再点検。生成器が滑った目次化を、まっさらな文脈の検証器が拾う。
4. **独立した recall ループ (本当のエンジン)** — `coverage_qa.iterate_and_fix`: ① gen が **source から** (ツリーからではない) 本質的問いを ~50 生成 → ② check が**ツリー本文だけで** (source も外部知識も禁止) covered/partial/missing 判定 → ③ fix が gap を**最小介入で** (spine と順序は凍結) 埋める → 95% 被覆まで最大 3 周。問いが source 由来=**外部の物差し**だから「それっぽいが中身が薄いツリー」が 95% ゲートで弾かれて充填される。`--no-coverage` はこのエンジンを切る=質は 1〜3 だけに落ちる。

   **(2026-06-03 改良 — deep-strict で外部実証して実装)**: ループには2つの楽観バイアスがあった。
   - **採点者＝生成者問題**: opus が opus 自身の出力を採点していた=self-preference / in-context reward hacking (arxiv 2407.04549, 2506.02592)。→ **check の judge を別モデル(sonnet, `coverage_qa.DEFAULT_JUDGE_MODEL`)に分離**。生成と fix は opus 維持。faithfulness が既にやっていた手を coverage にも適用 (`--judge-model` 共用)。バイアス是正＋コスト減を同時取り。
   - **teaching-to-the-test 問題**: fix を駆動したのと同じ QA で 95% を測る=循環採点 (arxiv 2311.01964)。→ **収束後に独立した hold-out QA を生成して最終ツリーを再採点** (`holdout_coverage_pct`)。これが正直な out-of-sample 値、`coverage_pct` は最適化済みの in-sample 値。hold-out は計測専用で fix には絶対使わない。`--no-holdout` で無効化可。

> 補足: 良さは天才的設計図でなく**反復の堆積**に宿る (prompt は v1.0→v2.0 と版を重ね、log.md は実出力を見て矯正を足した履歴)。だから定期的に冗長・dead code・二重管理の棚卸しが要る。検証の経緯は `~/.claude/plans/deep-run-ai-wiki-proposals.md`。

### 哲学 (Hard rules — 違反禁止)

1. 採点しない (retrieval practice の原則)
2. Source は不可侵 (sources/ は上書き禁止、再 ingest は no-op)
3. 決定的部分は決定的 (extract/resolve/lint/pillars/projection/narrative validator 全部 pure Python)
4. **stdlib-only** (sentence-transformers / sudachipy / numpy 等の重 dep を入れない)
5. Wikilinks が主通貨 (`[[slug]]`)
6. `/wiki-query` は無い (agent 直読みで代替)
7. **narrative tree = working hypothesis** (v3 原則、REQUIREMENTS §12.14): 出典・引用・信頼度・cross-check は書かない

---

## 2. 現状 (2026-04-23 時点)

### 実装完了

| Phase | 内容 | 状態 |
|---|---|---|
| v1 S1-S8 | Vault I/O, ingest, drill, coverage, extract, resolve, lint, pillars, ai-digest 統合, research, Fresh-Claude check | ✅ deploy 済 |
| v1 精査 sweep | dead code 除去、docs drift 修正 | ✅ |
| v1 実データテスト | `~/ai-digest/2026-04-19.md` → 19 sources + 46 concepts 自動生成 | ✅ |
| v2 Phase 1 | docs 整理 (REQUIREMENTS §11, SPEC §10 placeholder, ALTERNATIVES.md 新設) | ✅ |
| v2 Phase 2 infrastructure | _dev/corpus, _dev/tests 拡張 (pytest-regressions + hypothesis), hook_check.sh, CHANGELOG, knowledge | ✅ |
| v2 Phase 2 iter-v2-1 | edge schema (inline prefix notation) 確定 | ✅ SPEC §10.1 |
| v2 Phase 2 iter-v2-2 | `/wiki-enrich` 仕様 (single-pass) 確定 + enrich.py + SKILL.md procedure | ✅ SPEC §10.2 |
| v2 Phase 2 iter-v2-3 | `/wiki-project` (tree / contrast / prereq) 実装 | ✅ SPEC §10.3 |
| **v3-1** (2026-04-22〜04-23) | pilot narrative 構築、4 原則 + forest + working hypothesis + 固定辞書 確定 | ✅ REQUIREMENTS §12.11-§12.15, SPEC §11 |
| **v3-2** (2026-04-23) | narrative.py + dispatcher + lint/pillars 統合 + regression tests | ✅ SPEC §11.9-§11.11 |

### テスト状態 (2026-04-24 v4 deploy)

- **290 tests passing + 3 live-CLI tests skipped** (opt-in via `AI_WIKI_LLM_LIVE=1`)
- 構成:
  - `scripts/tests/` = unit tests (全 mock 化、subprocess は LLM 呼ばない)
    - `test_llm.py` (23), `test_enrich_execute.py` (21), `test_narrative.py` (32)
    - `test_narrative_draft.py` (22), `test_coverage_qa.py` (17)
    - `test_pipeline.py` (10), `test_e2e_pipeline.py` (3), `test_llm_live.py` (3 opt-in)
    - `test_vault.py` (20), `test_ingest_stage1.py` (14), `test_drill.py` (11), 他
  - `_dev/tests/` = corpus-driven + property + schema regression
    - `test_corpus_regressions.py` (7), `test_properties.py` (6)
    - `test_v2_schema.py` (15), `test_enrich_listing.py` (12)
    - `test_projection.py` (17), `test_narrative_schema.py` (6 + 3 golden)

### Hook

`~/.claude/settings.json` に ai-wiki の `hook_check.sh` を登録済。**全 skill 内 edit で自動 pytest**、regression 即検知。

---

## 3. 未完了タスク (明示的に持ち越し)

### v2 Phase 2 の残り

#### ⚠️ iter-v2-4: drill (SPEC §10.4) — **scope 縮小決定済、未記述**

**経緯**: 当初は `--mode tree|contrast|prereq|related` の 4 モード設計を提案 → user 指摘で撤回。

**新方針**:
- drill mode は **追加しない** (free recall の本旨は 1 cue で全 relation 想起、mode で cue を絞ると効果減)
- graph の 4 edge type (parent/related/contrasts/prereq) は **projection / visualization / lint** 用途であって drill 用途ではない

**ただし解けていない問題**: **drill の「上位概念 sweet spot」問題**
- 高すぎる cue (e.g. `AI について`) → 範囲無限で挫折
- 低すぎる cue (leaf concept) → 定義の cued recall に縮退、free recall にならない
- 中間の深さが sweet spot だが、map 構造の深さと「意味的抽象度」が常に一致するとは限らない

**候補対策** (会話中に提示、未決定):
- A. Enrich 時に LLM が **scoped map 複数** (`maps/rl-focus.md` 等) を生成
- B. `drill --root <slug>` で subtree だけ drill (既存 map を流用)
- C. concept に `drill_eligible: mid-level|leaf|abstract` tag、mid-level だけ drill
- D. `drill --depth 2..3` で深さ filter

**次 session の最初の決定**: A/B/C/D (または組合せ) のどれを採用するか user と合意してから SPEC §10.4 を書く。

#### iter-v2-5: migration (SPEC §10.5) — 未着手

v1 で生成済みの `~/ai-wiki/concepts/*.md` (46 件、全 shell) に enrich を適用する手順。

- SKILL.md の Enrich procedure を Claude が走らせるだけ (既に仕様定義済)
- 実行: `/wiki-enrich` → list shell → Claude が 1 concept ずつ edit
- 想定所要時間: 46 concepts × 数秒 = 2-5 分
- 終了後に `/wiki-project` で projection 再生成、`/wiki-lint` で dead_link 検出

**判断不要の機械的作業**。user 承認のみで走らせられる。

#### iter-v2-6: v2 test 計画 (SPEC §10.6) — 未着手

Phase 3 の E2E + regression gate を何で測るか。

- v1 の 99 tests を **regression** として走らせる (既に 290 tests gate に組込み済)
- v2 の corpus golden (enrich 後の concept page 状態) を lock
- 実データ vault (~/ai-wiki/) での Fresh-Claude cold check を再走

### Phase 3 (実装 + 本番適用) — 未着手

Phase 2 の全 SPEC が固まった後に:

1. `/wiki-enrich` を本番 vault で実行 (iter-v2-5 migration に該当)
2. `/wiki-project` を本番で走らせて `maps/ai-root.md` 等を生成
3. ユーザが `/wiki-drill` で想起訓練
4. Fresh-Claude cold check で v2 も自己充足か確認

---

## 4. 開いている設計判断 (次 session で user と decide 要)

### 4.1 drill sweet spot (最優先)

上記 iter-v2-4 の A/B/C/D のどれ？ **これが決まらないと Phase 3 実装 でも drill の UX が決まらない**。

### 4.2 scoped map の自動生成は enrich の仕事か、別コマンドか

もし 4.1 で A 採用なら、scoped map を作るのは:
- `/wiki-enrich` の副作用として? (enrich 1 concept ごとに親子関係を決めるついでに)
- `/wiki-project` の新モード? (`--kind scoped`)
- 新コマンド `/wiki-scope <topic>`?

### 4.3 Phase 3 の自己改善 loop 運用

290 tests + hook が既にあるので、Phase 3 実装中も regression 即検知は機能する。しかし:
- enrich は LLM 出力、golden baseline で pin できない (生成ばらつき)
- Schema check (parse_concept_edges が 0 以上の edge を返すか) 程度で十分か、もっと semantic check 要か

---

## 5. 次 session の再開チェックリスト

### まず読むもの (順序)

1. **本書** (HANDOFF.md) — 全体像
2. `docs/REQUIREMENTS.md` §11 — v2 paradigm shift の動機と方向性
3. `docs/SPEC.md` §10.1-10.3 — 既に決まった仕様
4. `docs/ALTERNATIVES.md` — 不採用案の台帳 (「なぜやらないか」を確認)
5. `_dev/history/CHANGELOG.md` — iter 毎の narrative

### 環境確認 (cold start 時)

```bash
cd /Users/ivymee/Projects/ai-wiki
pytest -q           # 156 pass を確認
ruff check scripts/  # clean
ls ~/ai-wiki/       # 実 vault 存在確認 (46 concepts + 19 sources)
ls ~/.claude/skills/ai-wiki/  # deploy 先確認
```

### 最初の意思決定ポイント

**iter-v2-4 の drill sweet spot 問題** (§4.1) を user と合意。候補 A/B/C/D を示して選んでもらう。

### 自己改善 loop 再開時の hygiene

`~/.claude/selfimprove/README.md` + `feedback_selfimprove_loop_hygiene.md` (memory) の 3 rule:

1. Sequential sample processing — 1 decision point ずつ、skip 不可
2. Token spike 即記録 — _dev/history/token_spikes_<date>.md へ
3. 各 decision point で **"is this meta?"** 問い — 抽象化の空回り防止

loop_design.md の Reflexion shape:
- 候補 N 案 propose → harness-gate → winner accept → regression lock

### Hook の既知 pattern

- `pytest-regressions` の first-run で必ず 1 回 block される (baseline 作成)
- 対処: 同じ pytest を 2 回目走らせれば pass (baseline 既存なので)
- 新 regression test 追加時は必ず発生、慌てない

---

## 6. v2 vs v1 の本質的違い (summary for fresh Claude)

| | v1 (deployed) | v2 (Phase 2 詳細設計中) |
|---|---|---|
| concept body | 空 (出典 link のみ) | 1-3 文 + typed edges |
| 概念関係 | backlink count のみ | parent / related / contrasts / prereq の 4 種 |
| ツリー | user 手書き (maps/) or 無し | LLM enrich → auto projection で生成 |
| drill cue | leaf-level (cued recall に縮退) | 上位概念 (free recall を狙う) |
| user のタッチポイント | ingest/drill/lint 等多数 | drill 解答のみを目標 |
| 拡張 dep | なし | なし (stdlib only 維持) |

---

## 7. 作業 backlog (優先順、2026-04-23 更新)

1. **[Phase v3-2]** user による pilot tree 実運用、retention/exploration AC 検証 — **進行中**
2. **[Phase v3-3]** 実運用結果を踏まえ §12.5 (per-concept file) / §12.6 (cardinality) の確定判断
3. [iter-v3-6] 別 domain で 2 本目の narrative tree 試作 → format 汎用性検証
4. [iter-v2-4] drill sweet spot 決定 → SPEC §10.4 (v3 schema 確定後に再評価、scope 変わる可能性)
5. [iter-v2-5] migration 仕様 → SPEC §10.5 (per-concept file が残るなら必要、廃止なら不要)
6. [iter-v2-6] v2 test 計画 → SPEC §10.6
7. [Phase 3] Fresh-Claude cold check (v2+v3 統合版)
8. [nice-to-have] Obsidian + InfraNodus plugin 導入検証 (user 側作業、ALTERNATIVES §F1)
9. [nice-to-have] narrative tag-based forest grouping (SPEC §11.9 将来拡張)

---

## 8. 本プロジェクトで絶対に忘れないこと

- **user は active study が目的** (passive 参照ではない) → narrative tree の読みやすさ + friction note の結晶化が最終評価指標
- **hook is ground truth**: pytest が通らなければ edit は reject。自己採点禁止
- **Phase 1 vs 2 vs 3**: docs → design → impl の順序。飛ばすと後で破綻
- **不採用案は ALTERNATIVES.md に残す**: 同じ議論を繰り返さない

---

## 9. 連絡

- project 作者: 三浦義人 (yo.mi202703@gmail.com)
- session context: 本 Claude Code session で v1 → v2 Phase 2 iter-v2-3 まで進行。user がここで一旦停止。
- 次 session で iter-v2-4 から再開。

**EOF — 作業お疲れさまでした。**
