Base directory for this skill: /Users/ivymee/.claude/skills/loop

# loop

Project の現状を 1 ページの briefing にまとめる autonomous loop playbook。
Claude Code が `/gemma-worker` (code 監査) + `/problems` (課題抽出) + `/constraints` (escalation) + `/progress` (進捗分類) を順次呼び、自身で drill-down + 矛盾解消し、最後に `loop synthesize` で統合する。

skill 同士は直接呼び合わない。中間成果物 (`<repo>/.loop/*.json`) を
ファイル渡しするだけ。

> **設計思想と仕様詳細**: [DESIGN.md](./DESIGN.md) を参照。
> 4 原理 (skill=oracle 1 種類 / LLM 判断を恐れない / CC は integrator / 一次資料 grounded)、
> 失敗パターン記録、reconciliation rule、既知の制限、将来課題まで網羅。

## When to invoke

- ユーザが `/loop` と打った時
- ユーザが「現状確認」「改善 plan 立てて」「次やる事見つけて」等と頼んだ時
- 自律改善ループの起点として project 全体を構造的に把握したい時

## When NOT to invoke

- 単発の調査・1 ファイル編集 (重い、約 100 LLM call)
- 既に最新の `.loop/briefing.md` がある時 (それを直接読めば良い)
- `.env` / `.loop/` 未セットアップ (まず `loop bootstrap`)

## Steps (順序通り実行)

### (1) code 監査

**`/gemma-worker` を呼ぶ**。呼び方は gemma-worker 側 SKILL.md に従う。
出力は `<PATH>/.loop/code_audit.json` として保存する。

その後、Claude Code が出力の妥当性を精査し、fix を入れる (ユーザに諮りながら)。

### (2) doc 抽出

(1) の fix で clean になった state で open な問題点を per-problem timeline で抽出。

```bash
uv run --project ~/.claude/skills/problems python -m problems run --repo <PATH>
```

→ `.loop/problems.json` + `.loop/problems.md`

### (2.4) 制約 (escalation) 抽出

各 problem が **外部のボール待ち** かを判定。1 gemma call、escalation package (`_<name>版_*.md`, MTG transcripts) を cross-problem で見て分類。

```bash
uv run --project ~/.claude/skills/constraints python -m constraints run --repo <PATH>
```

→ `.loop/constraints.json` (各 problem について `kind: client_response | external_review | null`、escalation_doc, since, owner, evidence_quote, last_sent_days_ago)

### (2.45) 進捗状態分類

各 problem を done / undone / dropped / superseded / pending_escalation に細分類。`/problems` の open/resolved 二値を補完。git log + artifact dir + 完了 language を oracle として 1 gemma call。

```bash
uv run --project ~/.claude/skills/progress python -m progress run --repo <PATH>
```

→ `.loop/progress.json` (各 problem について `status`, evidence_quote, evidence_source, completion_date, reason)

### (2.5) Claude Code drill-down + 制約ベース効果検証

**目的**: gemma / problems は signal を出すだけ。「我々が動ける課題」と「外部回答待ち (制約)」を分離し、**制約下での効果検証 (今期の活動が制約を尊重して進捗したか)** を行う。これが無いと "open N件" を並べるだけの briefing になる。

#### Drill 対象選定 rule (機械的、迷ったらこの順)

1. `code_audit.json` の `kind=global_theme && severity=high` 全件 → 該当 file を Read tool で full read。重複テーマは 1 回だけ。
2. `problems.json` の `latest_state=open` 上位 5件 → 各 problem の `timeline[-1].doc` を full read。`(verify stage)` など pseudo-doc が来た場合は **その手前の real doc** (timeline を遡って `(...)` で始まらない `doc` を採る) を使う。
3. ファイル名から `<名前>版` パターン (例: `_西村版_`) を検出 → 同名の原版と pair で両方 full read し diff を取る。これは **escalation 準備済 signal** の検出に最も有効。
4. 最新の "handoff memo" 候補を full read: top-level `*.md`, 最近 7 日変更の `*.md` 上位 5、内容が "memo/status/TODO/decision/meeting/retro/postmortem" を含む file_summary に該当するもの。これは repo 依存の固有 file 名 (`作業メモ_*.md` 等) に依存しない汎用 heuristic。
5. **archive 配下の README.md は全件 full read** (各 100 行未満で軽い、過去事例の retro が宝)。

#### 読まない判断 (明示)

- gemma `severity=low` の file_summary は drill しない
- 重複 global_theme は最初の 1 件以外飛ばす
- ソース doc に変更が無い (前回 run からの delta ゼロ) ファイルは drill しない

#### 課題の 3 分類 (必ず実施)

drill 結果を以下に分類。これが briefing の骨格になる:

| 分類 | `blocking_constraint.kind` | 判定基準 | 例 |
|---|---|---|---|
| **C: 制約 (待ち)** | `client_response` / `external_review` | 外部 (顧客 / 第三者 / 別チーム) の回答/作業が来ないと resolve 不可能 | F008/F009 統合判断 → 顧客返答待ち |
| **A: 動ける (actionable)** | `null` | 我々の手元に oracle (test, schema, 原文, post_process script) があり今期内に進捗可能 | phantom unit_id 調査、timing mismatch 設計 |
| **D: 後回し (defer)** | `internal_defer` | 動けるが優先度判断で意図的に止めている (memo/MTG で文書化済) | F006/F010 「優先度を下げてよい」 |

**自動分類の活用**: `.loop/constraints.json` + `.loop/progress.json` を `problem_id` で join。

| 自動判定 | drill 分類 |
|---|---|
| `constraints.kind in {client_response, external_review}` | **C (制約・待ち)** |
| `progress.status in {dropped, superseded}` | **D (defer/廃止)** |
| `progress.status == "pending_escalation"` | **C-pre (escalation 予定)** — まだ送ってない |
| `progress.status == "done"` | 分類対象外 (完了) |
| `progress.status == "undone"` + `constraints.kind == null` | **A (動ける)** |

Claude Code の役割は **矛盾解決と検出漏れ補完**:
- `constraints` が null だが `progress=pending_escalation` → C-pre。「送付準備」が drill の残作業
- `constraints` が blocked だが `progress=done` → 矛盾、一次資料で確認
- どちらも null + open → A actionable で確定 (drill 簡素化)

#### Reconciliation rule (3 skill の judgement が衝突した時)

優先順位 (上が勝つ):

1. **`progress=done` / `dropped` / `superseded`** が `constraints=blocked` より勝つ
   - 理由: 完了済 / 棄却済の課題は外部回答を待っても意味が無い。`/constraints` が古い escalation pkg を見て誤判定している可能性が高い → drill で一次資料確認
2. **`progress=pending_escalation`** と **`constraints=blocked`** が同時 → 両方とも真。「我々が更に送りたい論点」+「既に送った別の論点」が共存しうる
3. **`progress=undone` + `constraints=null`** → 純 actionable で確定。これ以上の drill 不要
4. **`progress=deferred`** + 任意 → 一律後回し扱い、drill では「defer 判断は今も有効か?」だけ確認 (memo 日付チェック)
5. **`problems.latest_state=discrepancy`** + 任意 → 強制 drill。code/doc 矛盾の解消が最優先

衝突が見つかった場合、drill_notes.md に「⚠ skill conflict: progress=X / constraints=Y → 採用: Z (根拠: <quote>)」と明記すること。

C/A/D 分類の根拠は必ず一次資料からの **verbatim 引用** で示す (推測禁止)。

#### 効果検証 (制約下で AI 自律可能)

各分類について以下を verify:

- **C 項目**: escalation doc が作成・送付されているか、`last_sent` から何日経過か、ack の有無、制約解除時に消費できる patch/branch 準備が出来てるか
- **A 項目**: 前回 briefing からの delta (commit、test 結果、metric)。動けるのに進捗 0 ならアラート
- **D 項目**: defer 判断の理由が今も有効か (memo の更新日が古すぎないか)
- **横断**: C 領域 (待ち) への commit が 0 件か (= リソース無駄遣いしてないか)

#### 出力: `<PATH>/.loop/drill_notes.md` (Write tool で作成、verbatim、再要約禁止)

```markdown
## Drill-down findings

### 1. 制約 (待ち、AI 不変)
- `[O2/O7]` F008/F009 統合判断 → **顧客返答待ち** (西村経由)
  - escalation doc: `40_成果物/分析レポート_..._西村版_20260515.md:§5`
  - last_sent: 2026-05-15 (9 日経過)
  - ack: あり / 回答期日: 未定
  - 解除時 readiness: schemas/v1_統合.yaml の field 削除 1 行 + prompt 修正。patch 草案未着手 (= **要準備**)
- `[O19]` Ground truth 作成 → **西村作業中** (5/16-17 想定)
  - 解除時 readiness: AI 検証 harness を流すだけの状態にしておく。現状 OK

### 2. 動ける (actionable、今期内に進捗可能)
- `[O5]` Phantom unit_id 根本原因調査
  - oracle: `30_抽出テスト用/scripts/post_process.py:145` (検出ロジック)
  - 現状: self-correction で塞いでる、根本原因も判明済 (`archive/20260501_v2_1715/README.md:18`)
  - 次アクション: 次回実走で発生数を観測、5 件超なら counter-example 追加
- `[O16]` Solicitor Chart timing 設計
  - oracle: 設計後の test
  - 現状: 着手なし

### 3. 後回し (意図的 defer)
- `[O9]` F006 定義曖昧 — `作業メモ_20260509:31-33` で「優先度を下げてよい」明記 (5/8 判断、有効)
- `[O10]` F010 境界未確定 — 同上

### 4. 効果検証 (今期、制約下)
- ✓ C 領域 (F008/F009 等) への commit: **0** (= リソース守った)
- ✓ phantom 発生: **0 件** (前回比同等、self-correction 機能)
- ✗ A 領域の進捗: **0** (動けるのに着手なし、要計画)
- ⚠ C 領域 readiness: F008/F009 patch 草案未着手 → 客回答即応不可

### 5. エスカレ管理 (alert)
- 西村版 送付から 9 日 → 次回 MTG agenda に「F008/F009 回答期日確認」を載せる推奨
```

> 重要: drill_notes.md は LLM 再要約されない (synthesize の LLM プロンプトには渡さず、briefing.md に verbatim 挿入される)。evidence ID 引用は人間可読のままで良い。
>
> 「制約下で効果検証する」が本 step の中核目的。「動ける課題が N 件あります」と並べるだけでは不十分。**動けるのに動いてない / 待ちなのに準備してない / リソース無駄遣い** を必ずチェックする。

### (3) 統合

両 signal を 1 ページに synthesize (evidence ID 強制)。

```bash
uv run --project ~/.claude/skills/loop python -m loop synthesize --repo <PATH>
```

→ `.loop/briefing.{md,json}`

完了後、Claude Code は briefing を読んで **改善 plan を考える**。

## Entrypoint (loop の CLI)

```bash
loop bootstrap --repo <PATH>   # 初回: .loop/, .env, .gitignore セットアップ
loop synthesize --repo <PATH>  # Step 3。--output json で stdout JSON
```

`loop run` は無い (Step 1-3 は Claude Code が直接 bash で叩く)。

## Output schema (`.loop/briefing.json`)

```json
{
  "headline": "<one sentence>",
  "narrative": "<markdown, 各文末に [O3] 等 evidence ID>",
  "problems": [...],            // problems.json の copy
  "code_audit_findings": [...], // code_audit.json の artifacts
  "evidence_table": [{"id": "O1", "snippet": "...", "ref": "..."}],
  "signal_counts": {"problems": N, "code": N},
  "drill_notes": "<markdown verbatim from .loop/drill_notes.md, or null>",
  "generated_at": "<ISO8601>"
}
```

evidence ID prefix: `O*` = open / `D*` = discrepancy / `R*` = resolved / `A*` = code audit。