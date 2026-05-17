# ai-wiki CHANGELOG

Iteration-by-iteration 「なぜそうしたか」の記録。短文主義。詳細は IMPROVE.md 本編と ALTERNATIVES.md 参照。

## 2026-04-19

- **iter 0**: REQUIREMENTS v1 + SPEC v0 起草。D1-D7 決定。task DAG 登録。

## 2026-04-20

- **iter-S1**: Vault I/O + stage1 arxiv ingest + dispatcher CLI。20 tests。
- **iter-S2**: drill/coverage 移植。slug-keyed reps、wikilink-aware drill rule。v2 の `leaf wikilink = 常に drillable` で v2 原則から外れた (原 v2 は leaf を除外) — ai-wiki では wikilink が concept atom なので判断。
- **iter-S3**: extract + resolve 実装。sentence-transformers 依存回避、stdlib-only 完遂。single-word capitalized の threshold 分離で noise 爆発を収束。
- **iter-S4**: pillars + lint + index auto-regen。E2E smoke で orphan bug 検出 → stage 4 で source body への wikilink backfill を追加。
- **iter-S5 (DROPPED)**: obsidian-wiki (Ar9av) の調査結果、agent が file read するだけで retrieval 不要と判断。`/wiki-query` を削除。
- **iter-S6**: ai-digest parser + `--from-digest` batch ingest。manifest.pending queue は採用せず runtime parse + skip で疎結合に。
- **iter-S7**: 3-round arxiv research。Round 2 の seed は source title (concept display より広く related が当たる)。
- **iter-S8**: SKILL.md 執筆 + deploy + Fresh-Claude cold check。cold check で output schema 未記載の指摘、`## Output contract` 節追加。
- **iter: 精査 sweep**: dead code (ingest.py の TYPE_CHECKING, main()) 除去、dispatcher.py の query stub 除去、docs の stale references (hot-cache / venv) 修正、IMPROVE.md の重複 snapshot 削除。
- **iter: 実データテスト**: 本番 vault ~/ai-wiki/ へ ~/ai-digest/2026-04-19.md を ingest、19 sources + 46 concepts 生成。orphan 0、top pillar = llm/rl。user フィードバックで v1 の限界 (flat structure、body 空、階層なし) が顕在化。
- **iter-v2-0 (Phase 1)**: v2 paradigm shift を設計台帳に記録。Tree → Graph 正規 + projection 方式。ALTERNATIVES.md 新設、REQUIREMENTS §11 追加、SPEC §10 に v2 placeholder。
- **iter-v2-infra**: self-improvement loop 用の _dev 構造整備。corpus (5 files)、pytest-regressions 金型 (7 baselines)、hypothesis property tests (6)、hook_check.sh、pyproject.toml 更新。112 tests total pass。

- **iter-v2-1 (2026-04-20)**: v2 edge schema 決定 (SPEC §10.1)。候補 3 案 (inline prefix / YAML list / hybrid) を harness 基準で比較、**A (inline prefix, Obsidian Dataview 互換)** 採用。`parse_concept_edges()` を vault.py に実装、`_dev/tests/test_v2_schema.py` で golden baseline + 10 cases 固定。127 tests pass。決定要因: B は Obsidian Graph view で edge 描画不能、C は parse path 2 通りで一貫性欠如。
  - **Hook fired event**: pytest-regressions の first-run で Hook が block 発動 → 正しい挙動 (harness-as-ground-truth)。Hook 再走らせで baseline 確認、127 pass 継続。
  - **Token spike log**: なし (API call 小)

- **iter-v2-2 (2026-04-20)**: `/wiki-enrich` 仕様確定 (SPEC §10.2)。候補 3 案 (single-pass / batch / 2-pass) 比較、**A (single-pass per concept)** 採用。
  - 役割分担: Python は shell 列挙 + context packaging のみ、実 enrich は SKILL.md procedure で Claude が edit
  - `scripts/enrich.py` + `dispatcher.py enrich` + SKILL.md の「Enrich procedure」節 + `_dev/tests/test_enrich_listing.py` (12 cases、golden 1 件)
  - 実データ smoke: `~/ai-wiki/` 46 shell concepts を正しく列挙、source_refs 紐付け確認
  - 139 tests pass
  - **Hook fired events**: fixture 欠如 (vault fixture が _dev/tests/conftest.py に無かった) を hook が即検出 → fixture 追加で解消。first-run baseline は 2 回目で pass、既存 pattern。

- **iter-v2-3 (2026-04-20)**: `/wiki-project` 仕様確定 + 実装 (SPEC §10.3)。Graph から 3 projection (tree / contrast / prereq) を生成。
  - **Multi-parent trade-off**: 候補 A (primary-parent) / B (multi-appearance) / C (hybrid) → **A 採用**。tree は drill-optimized view、graph 情報 substrate は concept 自身と Obsidian Graph view。
  - **Script 分割**: 候補 A (separate) / B (unified) / C (lazy) → **B 採用** (1 module 3 functions、dispatcher `--kind tree|contrast|prereq|all`)。
  - Tree algorithm: primary parent で DFS、implicit root (vault に無い parent) + 未分類 (orphan) 両方 handle。
  - Contrast: 無向 pair dedup (片方向宣言でも成立)。
  - Prereq: Kahn topo-sort、cycle を末尾 section に分離。
  - `scripts/projection.py` + `dispatcher.py project` + `_dev/tests/test_projection.py` (18 cases、golden 1 件)。
  - 実データ smoke: 46 shell concepts 全 orphan → `maps/ai-root.md` の 未分類 下に正しく配置。enrich 後は parent 付与で枝移動する構造。
  - 156 tests pass。deploy drift 無し。
  - **Hook fired**: first-run baseline (既知 pattern)、2 回目で通過。

## 2026-04-22

- **iter-v3-0 (Phase 1 docs)**: v3 paradigm shift を提起、REQUIREMENTS.md §12 起草。iter-v2-4 凍結。
  - **Trigger**: user (三浦さん) と v2 実装レビュー中に per-concept file design の妥当性質問 → WAIS-IV profile (PRI 130 / VCI 108 / WMI 118 / PSI 98) 共有 → 2-purpose 学習観 (retention / exploration) 明示化 → narrative tree 提案
  - **§12 sections**: 背景 / profile / 2-purpose / narrative tree / per-concept file 再評価 / cardinality 再評価 / iter-v2-4 との関係 / 決定プロセス / acceptance criteria / Phase 分割
  - **ALTERNATIVES.md**: カテゴリ G 追加 (G1 per-concept file 再評価、G2 cardinality cap 再評価、G3 narrative-by-prose 不採用、G4 drill 排除 不採用)
  - **HANDOFF.md**: §0 最新状況追加
  - **意思決定**: 設計論継続 < 実データで 1 本試作。first tree の domain は次 session で user 選定
  - **実装への影響**: iter-v2-4 の A/B/C/D 案は前提が変わるため書き直し候補。v2 の SPEC §10.1-10.3 (edge schema / enrich / projection) は v3 と互換なので残存
  - **Token spike log**: なし (docs のみ)

## 2026-04-23

- **iter-v3-1 (Phase v3-1 実行)**: first narrative tree 構築と、narrative tree 書式の経験則的確立。
  - **Domain 選定**: user 指定の計量経済学 LS1/LS2 PDF (慶應・頼慶泰、因果推論、確率論復習 + OLS、148 頁)。「時系列ごとに記載」= 学習順序の時系列として narrative 化
  - **Pilot file**: `~/ai-wiki/narratives/causal-inference-keio.md` (184 行、single-spine 問題駆動)
  - **新ディレクトリ**: `~/ai-wiki/narratives/` を vault に追加 (v3 schema)

  **4 つの書式 iteration で原則が結晶化**:
  - **v1 (450 行) 目次型**: source page タグ + 歴史メモ + 自己評価節。user 「ただの目次では?」で棄却 → ALT H1
  - **v2 (205 行) 3-branch 並列**: 確率論 / 漸近理論 / OLS を並列 branch。user 「接続がない」で棄却 → ALT H3
  - **v3 (184 行) single-spine 問題駆動**: 道具は使用箇所で登場、ROOT → sub-problem の連鎖。**採用**
  - **v4 (99 行) 過剰圧縮**: claim-as-heading + 表 + 英略。user 「人間可読性が恐ろしく下がった」で棄却 → ALT H4

  **確立された narrative tree 原則** (REQUIREMENTS §12.11-§12.14, SPEC §11):
  1. forest 構造 (peer な独立 tree の集合、階層なし)
  2. ノードは概念対象単位で束ねる (フルランク/多重共線性の件)
  3. 道具は使う箇所で登場、独立の道具箱章を作らない (3-branch 解体の件)
  4. 問題駆動エッジ (「次の章」ではなく「動機づけた/対立した」)
  5. 直読可能性を basis とする (v4 過剰圧縮の教訓)
  6. 固定辞書 ([?][★][◯][✕][∥][⛔][!][∴][⤴][⤵][⟳][↺])
  7. Working hypothesis (出典・引用・信頼度・cross-check を全て削除)

  **Docs 反映**:
  - REQUIREMENTS.md §12.11-§12.16 追記 (forest / 4 原則 / 固定辞書 / working hypothesis / Phase v3-1 実装結果)
  - SPEC.md §11 新設 (narrative tree 書式仕様、10 sub-sections)
  - ALTERNATIVES.md カテゴリ H 追加 (H1-H7 の棄却案台帳)

  **Memory 保存**:
  - `user_cognitive_profile.md` (WAIS-IV)
  - `user_learning_theory.md` (2-purpose + narrative tree substrate)
  - `project_ai_wiki_context.md` (v3 方向性)

  **Token spike log**: なし (docs + pilot tree のみ、実装コードは触らず)

- **iter-v3-2 (narrative infra 実装、2026-04-23)**: Phase v3-4 + v3-5 を user 判断で前倒し実装。
  - **新規 module**: `scripts/narrative.py` (220 lines): 固定辞書 (`FIXED_BRACKETED_SYMBOLS`), `validate_frontmatter`, `validate_page`, `detect_undefined_symbols`, `list_narratives`, `forest_index_markdown`, `narratives_summary`
  - **vault.py 拡張**: `SUBDIRS` に `"narratives"` 追加、`_page_path` の kind に `"narrative" → "narratives"` マッピング追加
  - **dispatcher.py**: `narratives` コマンド追加 (引数は `--vault` のみ)
  - **新テスト**: `scripts/tests/test_narrative.py` (32 unit tests) + `_dev/tests/test_narrative_schema.py` (6 corpus regression, golden baseline 3)
  - **新 corpus**: `_dev/corpus/narrative-pilot.md` (pilot tree のコピー、canonical 例)
  - **SKILL.md**: `narratives` コマンドを command table と output contract に追記、vault layout に `narratives/` 追加
  - **Tests**: 156 → **194 passed** (+38)
  - **Bug fix**: `list_narratives` が `_index.md` を narrative 扱いしていた件、`_` prefix system file を除外するよう修正 + regression test 追加
  - **Deploy**: `~/.claude/skills/ai-wiki/` に全ファイル sync 済
  - **実動作確認**: `python3 dispatcher.py narratives` → pilot 1 本が ok:true で列挙、forest index 自動生成
  - **Hook fired events**: pytest-regressions first-run baseline 作成で 1 回 block → 2 回目 pass (既知 pattern)
  - **Token spike log**: なし (実装と tests のみ、API call なし)

- **iter-v4-0 (docs-first 設計、2026-04-23 夜)**: v4 paradigm の設計を確定、実装前に全方針を docs 化。
  - **Trigger**: user 違和感「対話がメインなのは違和感、人間の介入が多すぎる」
  - **path 選定**: α (orchestrator のみ) / β (LLM を script に) / γ (narrative 限定) を比較、**β 採用**
  - **絶対原則** (user 2026-04-23 指示):
    - API 使用禁止 (Anthropic SDK / HTTP API)
    - Claude Code CLI (`claude -p`) のみ
    - Opus 4.7
    - schedule / cron / hook 禁止、user 任意起動のみ
    - pre-commit review gate なし、生成後 study 中に修正
    - 入力 markdown 限定 (PDF parse 層実装せず)
    - 1 往復 review、failure fallback なし
  - **coverage 手段**: sudachi 不採用 (user 経験「完全成功事例ではない」)、QuestEval 型 + CoVe 併用
  - **size 適応**: 25K / 75K token 境界で single/chunked/hierarchical 自動選択、300+ 頁 教材は forest split
  - **Hard rule #4 改訂**: stdlib-only 原則は維持、LLM 境界 (`scripts/llm.py`) のみ `claude -p` subprocess 許可
  - **Docs 反映**:
    - REQUIREMENTS.md §13 (v4 paradigm、11 sub-sections)
    - SPEC.md §12 (LLM 境界 API 契約、9 sub-sections)
    - ALTERNATIVES.md カテゴリ I (棄却案 I1-I8、path α/γ、API、sudachi、PDF、review gate、scheduler、regression pin)
  - **`claude -p` 動作確認**: Opus 4.7 / JSON output / 1M context window 利用可、1 call ~$0.058 (cache 効果あり)
  - **次 phase**: v4-1 (scripts/llm.py) 着手

- **iter-v4-1 (llm.py 基盤、2026-04-23 夜)**: Claude CLI subprocess wrapper 実装。
  - `scripts/llm.py` (280 行): `call_claude()` / `CallResult` dataclass / `_extract_json_block()` (fenced/nested/bare 対応) / `PromptTemplate` loader + placeholder 置換 / `call_with_template()` / `log_call()`
  - `scripts/prompts/` ディレクトリ新設
  - CLI args: `claude -p --model <alias> --output-format json --no-session-persistence`、stdin 経由で prompt
  - error handling: timeout / non-zero exit / JSON parse fail を is_error で返す
  - prompt cache: CC 内部 cache に委任 (CLI から直接制御不可)
  - 23 unit tests (全 subprocess mocked) + 実 CLI smoke test 成功
  - Deploy, 217 tests pass

- **iter-v4-2 (enrich --execute、2026-04-23 夜)**: LLM-driven auto-enrich 実装。
  - `scripts/prompts/enrich_concept.md` + `enrich_verify.md` (v1.0)
  - `enrich.py` 拡張: `execute_enrich()` / `enrich_one_concept()` / `_validate_llm_output()` (halluc slug / self-ref / body 長さ検出)
  - CoVe 1 周: 初版生成 → verifier → 必要なら修正
  - dispatcher `--execute` flag 追加、`--no-cove` / `--dry-run` / `--limit` サポート
  - 21 unit tests、238 tests pass
  - 実データ smoke: `cmc` concept を 1 件 enrich、parent + related 4 edge + 2 文 body、$0.11、source 保持確認

- **iter-v4-3 (narrative-draft、2026-04-24)**: md → narrative tree 自動生成。
  - `scripts/narrative_draft.py` (340 行): `parse_markdown_structure()` / `estimate_tokens()` / `select_strategy()` / `_generate_single()` / `_generate_hierarchical()` / `_extract_section_plan()` / `_cove_verify()` / `_validate_and_commit()`
  - 4 prompt templates: `narrative_single` / `narrative_section` / `narrative_master` / `narrative_cove`
  - size 適応: 25K tokens 未満 = single、25K-75K = chunked、75K+ = hierarchical (`##` 毎に sub + master orchestrator)
  - dispatcher `narrative-draft` command (`--slug`/`--title`/`--no-cove`/`--dry-run`/`--force-strategy`)
  - 20 unit tests、258 tests pass
  - 実 vault dry-run: LS1.txt = single strategy 選択、pilot md (1.5K tokens) = single

- **iter-v4-4 (pipeline orchestrator、2026-04-24)**: 5 stages chain 実装。
  - `scripts/pipeline.py` (110 行): `run_pipeline()` = ingest (optional) → enrich --execute → project → lint+update_index → narratives
  - fail mode: ingest 失敗は fatal (後続 stop)、enrich 失敗は continue、決定的 stage 失敗は他 stage に影響せず
  - dispatcher `pipeline` command、user-triggered only (cron/hook 一切実装せず、REQUIREMENTS §13.4)
  - 10 unit tests、268 tests pass
  - 実 vault dry-run: 5 stages 全成功、enrich 残 45 shell 検出

- **iter-v4-5 (coverage_qa、2026-04-24)**: QuestEval 型 gap report 実装。
  - `scripts/coverage_qa.py` (240 行): `generate_qa_set()` / `save_qa_set()` / `load_qa_set()` / `check_coverage()` / `write_gap_report()` / `run_coverage()`
  - 2 prompt templates: `coverage_qa_gen` (30-50 QA 生成) / `coverage_qa_check` (covered/partial/missing 判定)
  - 隠し metadata: `~/ai-wiki/.narrative-qa/<slug>.json` (QA cache) / `~/ai-wiki/.narrative-gaps/<slug>.md` (gap report)
  - narrative 本体には **一切 source pointer を書かない** (working hypothesis 原則 §12.14 維持)
  - dispatcher `coverage-narrative` command
  - 17 unit tests、285 tests pass

- **iter-v4-6 (coverage 統合 + integration tests、2026-04-24)**:
  - `narrative_draft` に coverage 自動統合 (`run_coverage=True` default)
  - hierarchical 時 master を coverage 対象から除外 (navigation hub、content claims なし)
  - `test_llm_live.py`: opt-in live CLI tests、`AI_WIKI_LLM_LIVE=1` で enable
  - `test_e2e_pipeline.py`: seeded vault で full pipeline 検証 (mock LLM)
  - 既存 test を `run_coverage=False` で明確化、coverage 統合専用 test を追加
  - 290 tests pass + 3 live skipped

- **iter-v4-7 (deploy + docs、2026-04-24)**:
  - SKILL.md に v4 commands 全追加 (command table / output contract / procedure / 祖先 note)
  - CHANGELOG.md に iter-v4-1 から iter-v4-7 までの narrative を記載
  - HANDOFF.md §0 を v4 完了状態に更新
  - 全ファイル `~/.claude/skills/ai-wiki/` に sync 済
  - user 介入は 3 capability (pipeline / narrative-draft / drill) + study 中の修正指示のみ

## Phase v4 完了状態 (2026-04-24)

- 290 tests passing, 3 live tests skipped (opt-in)
- 全コマンド実 vault で動作確認済
- hard rule #4 (stdlib-only) は llm.py 境界で緩和、他 script は変更なし維持
- Anthropic SDK / API direct call 0 箇所 (grep 確認)

## これから (v3 継続)
- **Phase v3-2**: pilot tree (causal-inference-keio) を三浦さんが実運用、retention/exploration AC 検証
- **Phase v3-3**: 実データ検証を踏まえ §12.5 (per-concept file) / §12.6 (cardinality) 決定
- **Phase v3-4**: narrative regression test (`_dev/tests/test_narrative_schema.py`) 実装、lint 拡張
- **Phase v3-5**: `vault.py` に narratives/ I/O 追加、forest index 自動生成
- **Phase v3-6 以降**: 別 domain で 2 本目の narrative tree 試作 (format 汎用性検証)

## (凍結) v2 Phase 2 残件
- iter-v2-4 drill sweet spot: v3 方針確定後に再評価
- iter-v2-5 migration: per-concept file 維持の場合のみ意味あり、v3 評価待ち
- iter-v2-6 test plan: v3 AC と統合して再設計

## 根拠文献

- `~/.claude/selfimprove/knowledge/loop_design.md`: Reflexion / Voyager / CRITIC 等
- `~/.claude/selfimprove/PREREQS.md`: tool 一覧 + pre-flight
- `docs/ALTERNATIVES.md`: 不採用案台帳
- `_dev/IMPROVE.md`: iter 詳細 (本書は narrative、IMPROVE.md は protocol)

## 2026-04-24

- **iter-v5-0 (paradigm reversal、2026-04-24)**: concepts/ 完全廃止 + ai-digest 独立化の docs-first 起草。
  - **Trigger**: user 発言「私が基本的に見るのはツリーだけな気がするんだよな。... obsidian上でも見えるような別ファイルを作成し、リンクでひもづける」+「ai-digestは今回の設計からは完全に独立させる方が良いかもな」
  - **認識転換**:
    - concept file = infrastructure (user は読まない) → file 形式である必要なし
    - user が読む content = narratives のみ
    - 詰まった箇所は dialogue → friction-driven note が発生時 notes/ に
    - ai-digest は週次 briefing で閉じる、橋渡しは user 選別のみ
  - **Docs 反映**:
    - REQUIREMENTS.md §14 (v5 paradigm) 新設: 2 reversal、core model、削除 scope、AC、rollback 条件
    - SPEC.md §13 (v5 core contract) 新設: vault 構造、残存 command、pipeline 3 stage、source 種別不問性
    - SPEC.md §2.1 / §2.2 / §2.4 / §10.1-10.3 に DEPRECATED 印
    - ALTERNATIVES.md カテゴリ J 追加 (J1-J7、per-concept / lazy / registry / digest / unified / entities / maps の 7 案を全て棄却理由付きで記録)
    - ALTERNATIVES.md G1/G2 を不採用 / 論点消滅に確定更新
  - **次 iter**: v5-1 code 削除 (extract/resolve/projection/enrich/digest)、v5-2 vault cleanup、v5-3 tests/deploy、v5-4 handoff 更新

- **iter-v5-1 (code 削除、2026-04-24)**: v5 paradigm の code 実装。
  - **削除 (scripts)**: extract.py / resolve.py / projection.py / enrich.py / digest.py / coverage.py / drill.py / research.py / tree_parser.py + 関連 prompts
  - **削除 (tests)**: test_extract / test_resolve / test_enrich_execute / test_digest / test_coverage / test_e2e_pipeline / test_drill / test_pipeline / test_schema / test_pillars / test_vault / test_ingest_stage1 / test_research / test_tree_parser / test_v2_schema / test_enrich_listing / test_projection / test_corpus_regressions / test_properties
  - **削除 (corpus)**: concept-v1-shell / concept-v2-enriched / map-sample / mini-digest / arxiv-sample
  - **簡素化**: vault.py (SUBDIRS `narratives,sources,reps`, PAGE_KINDS `narrative,source,note`), schema.py (dead_link + stats のみ), ingest.py (digest_md 検出削除、extract/resolve stage 除去), pipeline.py (3 stage), pillars.py (narrative-centric), dispatcher.py (9 commands)
  - **新規 test**: `scripts/tests/test_v5_core.py` (vault/schema/pillars/pipeline/ingest、19 test)
  - **結果**: 135 passed + 3 live skipped、hook_check regression なし

- **iter-v5-2 (vault cleanup、2026-04-24)**: `~/ai-wiki/` 実データ掃除。
  - 削除: `concepts/` (46 shell), `entities/` (空), `maps/` (projection 出力)
  - `manifest.json` の `pending` field 削除
  - 残存: `narratives/` (1), `sources/` (19), `reps/`, 他 system file
  - `dispatcher.py status` で smoke 確認: 1 narrative / 19 sources / 0 notes

- **iter-v5-3 (deploy + SKILL.md 更新、2026-04-24)**: `~/.claude/skills/ai-wiki/` に v5 を sync。
  - SKILL.md 全面書換 (v5 vault layout / 9 dispatcher commands / hard rules 7 項目)
  - HANDOFF.md §0 を v5 完了状態に更新
  - description を study-first 向けに書換 (ai-digest 参照削除、concepts 参照削除)

## Phase v5 完了状態 (2026-04-24)

- **135 tests passing, 3 live tests skipped (opt-in)**
- 全コマンド (9 個) 実 vault で動作確認済
- Anthropic SDK / API direct call 0 箇所 (grep 確認)、`claude -p` のみ
- ai-digest 参照 0 箇所 (code / docs / SKILL.md)
- `~/ai-wiki/` に concepts/ entities/ maps/ の痕跡なし

## これから (実運用検証フェーズ)
- **Phase v3-2 継続**: 三浦さんが pilot tree (causal-inference-keio) を実運用、retention/exploration AC 検証
- **Phase v5-eval**: 別 domain で 2 本目 narrative 試作 → format 汎用性検証
- **notes/ format 確定**: 最初の friction note 発生時に §13.5 を実装に合わせて pin

- **iter-v5-5 (QuestEval iterative remediation、2026-04-24)**: QuestEval を non-destructive gap report から **iterative tree remediation** に格上げ。
  - **Trigger**: user 指摘「初学者である user が根本的な抜け漏れに気づくとは思えない。最初からある程度網羅的な tree を用意しておくほうが リスクが少ない」
  - **認識転換**: §12.14 working-hypothesis 原則の "user-driven growth" 前提は user が gap を識別できる場合のみ成立。初学者 use case では崩れる → machine responsibility を "初期品質 floor を実運用閾値まで引き上げる" に再定義
  - **新 flow** (narrative-draft 1 実行あたり):
    1. 初版生成
    2. QuestEval iterate (最大 3 round)
       · 50 QA 生成 (旧 30 → 増量)、cache 再利用
       · coverage check → if < 95%、gap fix で tree 修正 → loop
    3. CoVe 最終 cleanup (revision で生じた矛盾除去)
    4. validate + commit
    5. 残 gap を `.narrative-gaps/<slug>.md` に最終 report
  - **Docs 反映**:
    - REQUIREMENTS §13.7 全面書換 (新 flow / 設計判断 / working-hypothesis 責務範囲明文化)
    - SPEC §13.7 新設 (iterate_and_fix API 契約)、§13.8 新設 (narrative-draft 新 flow)
    - CHANGELOG (本項)
  - **Prompts**:
    - `coverage_qa_gen.md` v2.0: 30 → 50 QA
    - `coverage_qa_fix.md` v1.0 新規: gap + existing body + source → revised body
  - **Code**:
    - `scripts/coverage_qa.py`: `iterate_and_fix()` / `_apply_gap_fix()` / `IterateResult` 追加、既存 `run_coverage()` は単独 mode として継続
    - `scripts/narrative_draft.py`: `_generate_single` / `_generate_hierarchical` flow 再構成 (iterate → cove → commit)、coverage 統合は各生成 function 内部に移動、外側の重複 coverage pass を削除
    - `scripts/dispatcher.py`: `--coverage-threshold` / `--max-iterations` flag 追加
  - **Tests**:
    - test_narrative_draft.py: 2 test を new flow (gen → qa_gen → qa_check → cove) に更新
    - 119 passed + 3 skipped
  - **Cost impact**: narrative 1 本あたり最大 +2 LLM call (~+$0.15-0.3)

- **iter-v5-5-validate (empirical end-to-end test、2026-04-24)**: v5-5 flow を実 source で初走行、成功を empirical に記録。
  - **source**: `~/Downloads/ols推定量.md` (240 行、~1500 tokens、計量経済学 第3章 OLS 推定量の統計的性質)
  - **target**: `~/ai-wiki/narratives/ols-chapter-3.md` (新規、旧 causal-inference-keio は削除済)
  - **結果**:
    - convergence: yes (2 iterations)
    - final coverage: **100%** (55/55 covered, 0 missing, 0 partial)
    - total cost: **$1.428** (iterate $1.04 = 73%、single-shot $0.32、CoVe $0.06)
    - 所要時間: 6.4 分
    - errors / warnings: 0 / 0
  - **品質**:
    - 4 原則全て準拠、固定辞書 11/12 使用 (`[↺]` のみ不使用 = 素材に派生系譜薄いため妥当)
    - halluc なし (source 照合済)
    - box-drawing + fenced block で Obsidian preview 不要
    - 意図的省略は `## 未配送` 節で明示 (α̂ 詳細 / BLUE / 8-10章拡張)
  - **判断**: v5-5 は robust に動作。pilot 運用への昇格を確定。`ols-chapter-3` を新 pilot として三浦さんが read/drill、retention/exploration AC empirical 検証フェーズへ移行。
