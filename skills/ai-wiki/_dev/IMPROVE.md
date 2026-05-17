# ai-wiki Self-Improvement Log

_自己改善 loop の iter 履歴。xlsx skill pattern (`~/.claude/selfimprove/PREREQS.md`) 準拠。_

## Harness

1. **Pytest (offline)**: `~/Projects/ai-wiki/scripts/tests/`
2. **Fresh-Claude cold check**: stage 完了時に subagent spawn して `/wiki-*` 実行させ、SKILL.md/SPEC の欠陥洗い出し
3. **Token spike log**: `_dev/history/token_spikes_<date>.md` に大きい tool output を記録

## Hygiene rules (feedback_selfimprove_loop_hygiene.md 準拠)

0. 設計判断は自走、meta issue のみ surface
1. Sequential sample processing (S1 完了 → S2 着手)
2. Token spike 発生時は即記録
3. 各 stage 完了後 fresh-Claude check
4. 各 decision point で "is this meta?" 問い

## Iterations

### iter 0 (2026-04-19) — Design phase closed, S1 着手
- REQUIREMENTS v1 + SPEC v0 committed (`c024e8a` → `d061ed2`)
- D1-D7 全決定済
- Task DAG 登録 (S1-S8、依存グラフ設定)
- S1 着手: vault I/O primitives + raw ingest skeleton

### iter-S1 (2026-04-20 完了)
- [x] skeleton dir 作成
- [x] vault.py: frontmatter parse, slug gen, wikilink parse, read/write primitives
- [x] ingest.py: stage 1 (raw save to sources/)、arxiv fetch 最小実装
- [x] dispatcher.py: argparse CLI、ingest command のみ動作
- [x] tests/test_vault.py (20 tests) 、tests/test_ingest_stage1.py (14 tests)
- [x] pyproject.toml (pytest config)
- [x] E2E smoke: `python dispatcher.py ingest arxiv:2604.14265` で sources/arxiv-2604.14265.md 生成確認

## S1 実装中の決定事項 (ログ)

- **frontmatter parse は stdlib only** — PyYAML 依存回避、flat key:value + inline list のみ対応 (SPEC §2 の schema は全 flat なので OK)
- **slug は ASCII 優先 + 日本語 retain** — `最適輸送` はそのまま slug 化、英訳 slug は後処理で alias 統合する運用
- **manifest status は raw → resolved 段階的** — S1 は全 "raw"、S3 完了時に resolve 済み source を "resolved" に遷移
- **arxiv re-ingest は no-op + warning** — source 不可侵原則、再 fetch 無し (上書き禁止)
- **test_ingest_stage1.py は fetch_arxiv_metadata を mock** — offline CI 可能、E2E smoke は手動 command で network 検証
- **pyright の pytest 未解決警告は IDE 側の venv 不整合** — 実 pytest (uv tool) で 34/34 pass、無視可

### iter-S2 (2026-04-20 完了)
- [x] `tree_parser.py` 移植 (stdlib only, v2 verbatim)
- [x] `drill.py` 実装 (slug-keyed reps, wikilink-aware)
- [x] `coverage.py` 実装 (wikilink-based gap detection、sudachipy 依存なし)
- [x] dispatcher.py に drill/coverage コマンド接続
- [x] test_tree_parser.py / test_drill.py / test_coverage.py (計 23 tests)
- [x] E2E smoke: drill(map & `*`) + coverage + status 全て SPEC 通り動作
- [x] ruff + pyright sweep: ruff all clean、pyright 0 errors (5 warns は pytest import の false-positive)

## S2 実装中の決定事項 (ログ)

- **Drillable rule は v2 から変更** — v2 rule (depth>=1 AND no-desc AND (has_children OR depth==1)) は leaf wikilink を弾く。ai-wiki では「wikilink ノード = concept atom」なので常に drill 対象に。plain-text ノードは v2 rule 継続 (scaffold category として drill)
- **coverage は wikilink ベースのみで S2 完結** — SPEC §3.8 の "抽出 concepts と照合" は S3 extract 後に実装。S2 では sources/ の wikilink と map の wikilink の集合差で mechanical gap を返す。sudachipy 依存先送り
- **map_path 正規化** — `"maps/ai-root.md"` / `"ai-root.md"` / `"ai-root"` 全て受容 (`maps/` 接頭と `.md` 接尾を剥がす)
- **`*` mode の reps は `reps/_all.json`** — v2 互換の shared 名前空間
- **prompt format の display** — wikilink が `[[slug|Display]]` の場合 Display 優先、なければ slug を表示。root_display は map root の term (plain or wikilink)
- **pyproject.toml に pyright + ruff config 追加** — `target-version=py39`, `select=[E,F,I,UP,B,SIM]`, `ignore=[E501]`
- **Pyright の pytest import 警告は残存** — pytest が `uv tool` 分離 env のため pyright が解決できない。false positive、CI では `reportMissingImports = "warning"` 設定で fail させない
- **ingest.py に Optional access guard 追加** — pyright が arxiv API パースの `find().text` の None 可能性を検出、安全化

### iter-S3 (2026-04-20 完了)

- [x] `extract.py` (stdlib-only): wikilink + katakana + 構造化 alpha (CamelCase / hyphenated / acronym)
- [x] `resolve.py` (string-match tiers): exact_slug / alias_match / normalized / fuzzy / new
- [x] `ingest.py` を 4-stage 化 (stage 1 → extract → resolve → schema)
- [x] test_extract.py (7 tests) / test_resolve.py (10 tests): 合計 74 tests 全 green
- [x] E2E smoke: `ingest arxiv:2604.14265` → concepts/ に 4 valid slug (llm/ogb/rl/vgf)、noise 除去成功
- [x] ruff + pyright sweep: clean

## S3 実装中の決定事項 (ログ)

- **Sentence-transformers 依存は見送り、S3.5 に分離** — 共用には他 skill (ai-digest) の venv 改変が必要で副作用大。stdlib-only 維持の方が deploy footprint と再現性で優位。Embedding merge は「より良い resolve」であって「必須」ではない
- **Extract を 3 層 signal に分解**:
  1. wikilink (authorial、min_count バイパス)
  2. katakana 3+ chars
  3. alpha: 構造化 (CamelCase/hyphenated/acronym) は min_count=1、単独大文字語は min_count=3 + stoplike 除外
- **当初の単独大文字語 rule は noise 爆発** — 最初のテスト smoke で `flow`/`code`/`existing`/`extensive` 等 12 件の誤検出。threshold 分離 + 固定 stoplike 追加で 4 valid concepts に収束
- **Resolve は決定的階層**: exact > alias > normalized > fuzzy(decision) > new。embedding は将来の tiebreaker として追加可能 (forward-compat な Resolution dataclass)
- **Fuzzy substring match は両側 len≥6 のみ** — 短い slug での誤マッチ ("ai" が "chain" に hit) 防止
- **Decision kind は ambiguous provenance で page 作成** — auto run を止めないが後で `/wiki-lint` で可視化できる handle
- **Ingest の alias_index は各 candidate 毎に rebuild** — 同一 source 内で新規作成した concept が後続 candidate の merge target になる semantics のため

## S3.5 候補 (follow-up、S4 着手前に判断)

1. **sudachipy 導入** — JP 複合名詞抽出 (現状 katakana のみ)。pkg size ~20MB、skill 独立 venv なら可
2. **Embedding-based merge tier** — `_build_alias_index` の後段で cosine sim > 0.85 を追加。torch/sentence-transformers は ai-digest venv 再利用か独立か要判断

### iter-S4 (2026-04-20 完了)

- [x] `pillars.py`: 全 kind 横断の backlink 集計 + top-N / emerging / decayed
- [x] `schema.py`: lint (orphan / dead_link / sparse) + index.md 自動再生成
- [x] dispatcher に lint/pillars 接続、ingest 完了時に auto update_index
- [x] test_pillars.py (5) / test_schema.py (6): 合計 85 tests 全 green
- [x] E2E smoke: ingest → lint → pillars → index.md 全仕様通り
- [x] Self-improvement hit: smoke で orphan bug 検出 → source の "## 抽出された概念" セクションを stage 4 で auto-populate する修正追加 → orphan 0 / backlink 正常

## S4 実装中の決定事項 (ログ)

- **Backlink 集計は全 kind 横断** (concept + entity + source + map) — どの方向からの参照も等価に count。top 判定は concept のみ
- **Emerging は `parent::[[X]]` の共有で判定** — 同一 parent を持つ recent concept が 2+ → pillar 化の予兆。今後 drill_eligible=true と組み合わせて精度向上可能
- **Decayed は backlinks > 0 AND updated < cutoff** — "有用だが古い" を可視化。0 backlink は orphan 側で扱うので重複しない
- **index.md は `<!-- auto-generated -->` ヘッダでガード** — 手動編集禁止を明示、再生成で完全上書き
- **Ingest の stage 4 で source body にも wikilink を戻す** — S4 smoke で検出した bug。`(S3 extract stage で populate 予定)` placeholder を `- [[slug]]` リストで置換。これなしでは concept→source のみで source→concept がなく全 concept が orphan 扱いになっていた
- **Sparse threshold は backlinks < 2** — v1 の粒度。将来、新規概念は sparse 検出を disable (引数で grace period) の余地

_(中間の S4 完了時点スナップショットは末尾の v1 完了テーブルに集約 — 削除)_

### iter-S5 (DROPPED 2026-04-20)

obsidian-wiki (Ar9av) 調査の結果、agent 主導の direct file read で代替できると判明。SPEC §3.2 + REQUIREMENTS §3, §8 を drop 表記に更新。

### iter-S6 (2026-04-20 完了)

- [x] `digest.py`: ai-digest md parser (Core/Adjacent/Notable 分類、arxiv URL 抽出、日付抽出)
- [x] `ingest.ingest_from_digest(...)` 追加、dispatcher に `--from-digest` / `--sections` / `--digest-root` 接続
- [x] `test_digest.py` (10 tests、stub fetch で offline 検証)
- [x] E2E: 実 `~/ai-digest/2026-04-19.md` で 10 arxiv sources + 25 concepts 自動生成、idempotent (2 回目は skipped)
- [x] ruff + pyright clean、pytest 94/94

## S6 実装中の決定事項 (ログ)

- **manifest.pending を使わず、実行時に毎回 parse + 既存 skip** — 設計を単純化。ai-digest skill 側に pending を書き込ませる連携は不要
- **arxiv URL 以外は silent skip** — digest 内の blog / GitHub リンクは v1 では対象外。将来の `/wiki-ingest --include-non-arxiv` 拡張は可能
- **--sections のデフォルトは core,adjacent** — Notable は SPEC の「Core 5 + Adjacent 5 を順次」に沿って除外
- **1 entry 失敗でも batch 継続** — errors list に記録して log.md に append、残り entry は処理続行
- **デジェスト内の複数 Run (## Core が複数回現れる)** も自然に処理される — section-tracker は "現在どのカテゴリか" だけを保持、Run 区切りは不要

### iter-S7 (2026-04-20 完了)

- [x] `research.py`: arxiv `search_query` API ラッパ + 3-round pipeline (topic seed / concept expansion / sparse strengthen)
- [x] `--auto` で ingest.ingest() 経由実行、default は dry-run
- [x] dispatcher に `research` コマンド接続、`--rounds`/`--top-k`/`--auto` flags
- [x] test_research.py (5 tests、mocked arxiv search)
- [x] Real arxiv smoke: `research "wasserstein gradient flow" --rounds 1 --top-k 3` → 3 valid related papers 返却
- [x] pytest 99/99、ruff clean、pyright 0 errors

## S7 実装中の決定事項 (ログ)

- **Round 2 の seed は source title** — 本来は created concepts の display (SPEC §3.7) だが、arxiv search は specific concept 名より paper 名の方が広く related を返す。意図外の horizon を広げるので実用上有利
- **Round 3 は lint の sparse output を流用** — 独自の「sparse 判定」を作らない (DRY)
- **Dry-run が default** — ネットワーク呼び出しを伴うので「実行する前に確認」を UX default に。`--auto` で一気通貫
- **`_round2_expand` / `_round3_sparse` は auto=False 時 skip** — Round 1 が何も ingest しないと Round 2 以降の seed が無いため意味がない。dry-run は「Round 1 の候補だけ見たい」に最適化
- **Error は batch 継続、log に append** — 1 paper の arxiv fetch 失敗で残り全 skip は非効率

### iter-S8 (2026-04-20 完了)

- [x] `SKILL.md` 執筆 (Hard rules / Vault layout / Scripts / Procedure / Page format / Known failures / Notes)
- [x] `~/.claude/skills/ai-wiki/` に SKILL.md + scripts/ + _dev/ (REQUIREMENTS/SPEC/IMPROVE) を deploy
- [x] Available skills list に `ai-wiki` が表示されることを確認 (system-reminder 側で認識)
- [x] Fresh-Claude cold check (general-purpose subagent, SKILL.md のみ可読):
  - **全 5 コマンド初回成功** — status / ingest / lint / pillars / research 全て SKILL.md だけで正しく invocation
  - 指摘事項: (a) 各コマンドの出力 JSON schema が未記載、(b) 空 vault の挙動が未明示、(c) `ingest` vs `research` の "dry-run" の違いが暗黙
- [x] 修正 deploy: `## Output contract` セクションを SKILL.md に追加 (全 command の top-level keys 一覧)、空 vault 動作明記、dry-run semantics 明記
- [x] example 内の typo 修正 (`arxiv-2604.14265` → `arxiv-2604.14765`)

## S8 実装中の決定事項 (ログ)

- **SKILL.md は 130 行台** — xlsx skill (~300 行) より短く、obsidian-wiki の wiki-* skill (~100 行) と同等。冗長説明は `_dev/*.md` に分離
- **Deploy は cp による copy 配備** — symlink も可能だが、skill が安定するまでは source tree と独立 copy で管理 (事故時の復旧容易)
- **Fresh-Claude test は "SKILL.md 以外 read 禁止" を subagent prompt で明示** — これで SKILL.md の自己充足性が厳密に検証される

## 🎯 ai-wiki v1 完了

全 ステージ完了 (S5 は DROPPED):

| Stage | 状態 | Deliverable |
|---|---|---|
| S1 Vault I/O + Ingest | ✅ | vault.py, ingest.py stage1, arxiv fetch |
| S2 Drill/Coverage/Ignore | ✅ | slug-keyed drill, wikilink coverage |
| S3 Extract + Resolve | ✅ | stdlib-only extraction, string-match resolve |
| S4 Schema/Lint/Pillars | ✅ | orphan/dead/sparse lint, top-N pillars, index auto-regen |
| S5 Hot-cache + Query | ❌ DROPPED | obsidian-wiki 流に agent 直読みで代替 |
| S6 ai-digest 統合 | ✅ | `/wiki-ingest --from-digest` で Core/Adjacent 自動取込 |
| S7 Research autonomous | ✅ | 3-round arxiv 探索 (dry-run / --auto) |
| S8 Fresh-Claude + deploy | ✅ | SKILL.md + ~/.claude/skills/ai-wiki/ + cold check |

**テスト総数: 99 tests / 全 pass / ruff clean / pyright 0 errors / Fresh-Claude cold check pass**

**積み残し (v1 機能完備、必要になったら着手):**
- **S3.5 sudachipy**: 日本語複合名詞抽出 (現状 katakana のみ)
- **Embedding merge tier**: cosine > 0.85 自動 merge (resolve.py 拡張)
- **`/wiki-drill` の分野別 filter**: urban-wiki 等 domain 切替時の filter パラメタ
- **Hook-based regression gating**: xlsx の hook_check.sh 流のポストエディット検証 (PREREQS.md の recommend)

詳細な不採用 / 保留案は [ALTERNATIVES.md](../docs/ALTERNATIVES.md) 参照。

---

## 🚧 v2 paradigm shift 開始 (2026-04-20)

### iter-v2-0 (2026-04-20) — docs 整理 phase 1

**動機**: v1 deploy 後の実データテスト (`~/ai-digest/2026-04-19.md` から 19 sources / 46 concepts ingest) で、以下の限界が顕在化:

1. **concepts がフラット**: `concepts/*.md` が並んでいるだけで関連性が見えない (user 指摘)
2. **body 空**: 出典 link だけなので drill 時の答え合わせが貧弱 (user 指摘)
3. **階層なし**: 原設計の本旨「上位概念で出題 → subtree 全体を free recall」が未達、drill が leaf-level cued recall に縮退

**方向性の転換 (REQUIREMENTS §11)**:

- Tree → **Graph** (`parent::` / `related::` / `contrasts::` / `prereq::` の multi-edge)
- User authoring → **LLM enrich が frontmatter + 1-3 文 body を自動生成**
- Tree は graph の projection として扱う
- Drill mode 拡張: tree / contrast / prereq / related の 4 種

**Phase 分割**:
- **Phase 1 (本 iter)**: docs 整理 — REQUIREMENTS に §11 追加、ALTERNATIVES.md 新設、SPEC に v2 placeholder、IMPROVE に本記録
- **Phase 2**: SPEC.md §10 を実質化 (v2 データモデル / enrich prompt / projection アルゴリズム / drill mode 拡張)
- **Phase 3**: 実装 + 実データ E2E + v1 regression (99 tests pass 維持)

**Phase 1 で決まっていないこと (Phase 2 で決める)**:
- `parent::` の cardinality 上限 (1? 2? 無制限?)
- enrich prompt の細部 (何を LLM に書かせるか)
- projection algorithm (parent:: に ambiguity がある時どうするか)
- drill mode 切替 UX (flag? subcommand? default?)
- v1 で生成済み concepts への migration 手順

**Hygiene check (self-improve loop)**:
- ✅ 設計判断は meta でなく substantive
- ✅ 依存関係明確 (Phase 1 → Phase 2 → Phase 3)
- ✅ 不採用案は ALTERNATIVES.md に台帳化済
- 次の decision point: Phase 2 開始時に edge schema と cardinality を決める
