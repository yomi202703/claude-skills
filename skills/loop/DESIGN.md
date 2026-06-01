# /loop 設計思想と仕様書

最終更新: 2026-05-25 (Phase 1+2 完成、ack tracking + deferred status 追加後)

---

## 1. 中核の問い

**Q. AI に project 運営を完全に任せられるか?**

A. **半分は可能、半分は構造的に不可能**。境界は「外部 oracle があるか」で決まる:

| 領域 | oracle 例 | AI 自律可否 |
|---|---|---|
| code 品質 | test, lint, type checker | ◯ |
| 仕様準拠 | schema, OpenAPI, contract test | ◯ |
| 完了判定 | git log, artifact 存在, 完了宣言 doc | ◯ |
| escalation 状態 | escalation pkg, 送付日, response doc | ◯ |
| 要件決定 | 顧客回答 (外部) | ✗ (escalation 後、待つしかない) |
| 戦略優先度 | ユーザ判断 (外部) | ✗ |

「AI が全部やる」を成立させる前提は **2 つ**:
1. **oracle がある領域だけ AI に任せる** (oracle 無し領域は人間 escalation で止める)
2. **人間が "書く discipline" を維持する** (handoff memo / MTG transcript / 西村版 等を書き続ける)。AI が "書く役" も兼ねるなら 2 は緩和できるが、本 skill の scope 外

## 2. 設計原理 (4 つ)

### 原理 1: skill = oracle 1 種類

1 skill に複数の oracle を混ぜると分類精度と保守性が壊れる。歴史的失敗:
- 旧 `/problems` が「課題抽出 + 進捗判定 + 制約判定」を全部やっていた
- 結果: 制約検出が「課題抽出が捕捉した timeline summary だけ見る」設計になり、escalation pkg の §5 を見ない → 取りこぼし

修正後:
- `/problems` = 課題抽出のみ (oracle: doc 言及 + code 言及)
- `/constraints` = escalation 追跡のみ (oracle: escalation pkg + response doc)
- `/progress` = 進捗判定のみ (oracle: git log + artifact dir + decision-language doc)
- `/gemma-worker` = code 監査のみ (oracle: code file 内容)

### 原理 2: LLM 判断を恐れない

「LLM 不使用」「deterministic」を必要以上に好まない。日本語の文脈判断 (「ご相談」が future plan か escalation か / 「優先度下げ」が永久か一時か) は keyword では取れない。**verify stage が既に gemma を呼んでるなら、1 field 追加で**コスト ~0。

例外: 数えれば良いだけ (count, hash, diff) は LLM 不要。

### 原理 3: Claude Code は integrator (judge, not worker)

各 skill は **独立した judgment** を返す。CC は:
- 寄せて読む
- 矛盾を解消 (reconciliation rule に従う)
- 検出漏れを drill で補完
- briefing にまとめる

CC が労働 (= 何かを発見) をすると 1M context が無駄。CC は判断に専念し、発見は skill にやらせる。

### 原理 4: 一次資料に grounded

LLM 要約の要約の要約は信用しない。drill step で CC は **必ず原文 file を読む**。skill 出力に `evidence_quote` (verbatim) を必須化、推測は禁止。

---

## 3. アーキ図

```
                          ┌────────────────────┐
                          │   ユーザ requests  │
                          └──────────┬─────────┘
                                     ▼
                          ┌────────────────────┐
                          │  /loop (CC orch)   │
                          └──────────┬─────────┘
       ┌─────────────────┬───────────┴──────────┬─────────────────┐
       ▼                 ▼                      ▼                 ▼
  /gemma-worker      /problems              /constraints      /progress
  (code 監査)        (課題抽出)              (escalation)      (進捗)
       │                 │                      │                 │
       ▼                 ▼                      ▼                 ▼
  .loop/             .loop/                 .loop/             .loop/
  code_audit.json    problems.json          constraints.json   progress.json
                          │                      │                 │
                          └──────────┬───────────┴─────────────────┘
                                     ▼
                          ┌────────────────────┐
                          │  CC drill (2.5)    │
                          │  - 矛盾解消         │
                          │  - 検出漏れ補完     │
                          │  - 効果検証         │
                          └──────────┬─────────┘
                                     ▼
                          ┌────────────────────┐
                          │ .loop/drill_notes  │
                          │      .md           │
                          └──────────┬─────────┘
                                     ▼
                          ┌────────────────────┐
                          │ /loop synthesize   │
                          │ (briefing 生成)     │
                          └──────────┬─────────┘
                                     ▼
                          ┌────────────────────┐
                          │ .loop/briefing.    │
                          │     {md,json}      │
                          └────────────────────┘
```

## 4. 各 skill 仕様

### 4.1 `/gemma-worker`

- 役割: code monolithic scan (per-file synthesis / inconsistency / gap / deadcode 等)
- oracle: code file 内容
- LLM: 多数 (per file, parallel)
- output: `code_audit.json` の `artifacts[]` (kind: file_summary / global_theme / 等)
- 既存 skill、本書改修対象外

### 4.2 `/problems`

- 役割: 課題抽出 + open/resolved/discrepancy 判定
- oracle: doc 内言及 (全 md) + code 内 symbol 出現
- pipeline: extract (A) → consolidate (B) → verify (C, gemma で latest_state 判定) → analyze (D, discrepancy 原因)
- output: `problems.json` の `problems[]` (problem_id / title / timeline / latest_state / code_evidence / discrepancy_analysis)
- **責務外** (重要):
  - escalation 追跡 → `/constraints`
  - 進捗 (deferred/dropped/etc) → `/progress`
  - これらは過去 `/problems` 内に同居していたが、原理 1 違反のため分離した

### 4.3 `/constraints`

- 役割: 各 problem が外部のボール待ちかを判定
- oracle:
  - **escalation package**: `_<人名>版_*.md`, `*MTG*/meeting/wecom/議事録/transcript/minutes/` dir の md (substring match 大文字小文字非依存)
  - **response candidate**: escalation 日以降の md で response 言語 (`決定しました`/`ご回答`/`承認`/`approved` 等) 含む
- LLM: 1 call (全 problems × 全 packages × 全 responses cross-reference)
- output: `constraints.json`
  ```json
  {
    "constraints": [{
      "problem_id", "kind": "client_response|external_review|null",
      "owner", "since", "escalation_doc",
      "ack": true|false|null, "ack_doc",
      "last_sent_days_ago", "evidence_quote"
    }],
    "escalation_packages_found": [...],
    "response_candidates_found": [...]
  }
  ```
- 重要 design 決定:
  - `internal_defer` は本 skill で扱わない (進捗状態であり制約ではない)
  - 「内部 memo に escalation 予定」は `/progress` の `pending_escalation` 担当 (まだ送ってない)

### 4.4 `/progress`

- 役割: 各 problem を 6 状態に細分類
- oracle:
  - git log (直近 50 commit)
  - artifact dir (outputs/dist/build/成果物 etc、非空)
  - **decision-language doc**: 「優先度を下げ」「対象外」「次フェーズ」「要件定義打合せでご相談」「実装完了」等を含む md (±400 char window で excerpt)
  - `/constraints` 出力 (cross-reference)
- LLM: 1 call
- output: `progress.json`
  ```json
  {
    "progress": [{
      "problem_id",
      "status": "done|undone|deferred|dropped|superseded|pending_escalation",
      "evidence_quote", "evidence_source", "completion_date", "reason"
    }],
    "git_log_excerpt": [...],
    "artifact_dirs_found": [...],
    "decision_docs_found": [...]
  }
  ```
- status 区別:
  - `done`: 完了 (artifact あり or 明示宣言)
  - `undone`: 動ける actionable (default)
  - `deferred`: 一時後回し (戻ってくる、「優先度を下げ」)
  - `dropped`: 永久棄却 (「対象外」「やらない」)
  - `superseded`: 別アプローチに置換 (「v1→v2」)
  - `pending_escalation`: 我々が escalation したいが**まだ送ってない** (`/constraints` は送付済を扱う)

### 4.5 `/loop` (orchestrator)

- 役割: 上記 4 skill を順次呼び、CC drill + synthesize で briefing を作る
- step 順: 1 → 2 → 2.4 → 2.45 → 2.5 (CC drill) → 3 (synthesize)
- output: `briefing.{md,json}` (全 signal 統合、1 ページ + drill_notes verbatim)

## 5. Reconciliation rule (3 skill 衝突時)

`SKILL.md` Step 2.5 にも記載。優先順位:

1. **`progress=done/dropped/superseded`** が `constraints=blocked` より勝つ
   - 完了済/棄却済を外部回答待ちと誤判定する古い escalation pkg を上書き
2. **`progress=pending_escalation`** ∧ **`constraints=blocked`** → 両方真 (追加送付論点 + 既存送付)
3. **`progress=undone`** ∧ **`constraints=null`** → 純 actionable 確定、drill 不要
4. **`progress=deferred`** + 任意 → 後回し扱い、defer 判断の鮮度 (memo 日付) のみ確認
5. **`problems.latest_state=discrepancy`** + 任意 → 強制 drill

衝突時は drill_notes に `⚠ skill conflict: progress=X / constraints=Y → 採用: Z (根拠: <quote>)` を必ず明記。

## 6. 出力構造 (briefing.md 構成)

```
# Project Briefing
**Headline**: <一行>
## 現状ナラティブ  (LLM 生成、evidence ID 引用必須)
## Drill-down findings (CC、verbatim、再要約禁止)
  1. 制約 (待ち)
  2. 動ける (actionable)
  3. 後回し (defer)
  4. 効果検証 (制約下で今期 ✓/✗/⚠)
  5. エスカレ管理 (aging alert)
  6. 提案 (今期動かす)
## 📊 Progress breakdown  (/progress 自動)
## 🚧 Blocking constraints  (/constraints 自動、ack badge 付き)
## Problems  (open/resolved/discrepancy 一覧)
## Code audit findings  (上位 15)
## Evidence table  (O*/D*/R*/A* ID 付き)
```

## 7. 失敗パターン記録 (将来の再発防止)

### F1: 1 skill で全部やろうとした
- 旧 `/problems` が課題抽出+進捗+制約を全部担当。結果: 制約検出が課題抽出の出力 (timeline summary) しか見ず escalation pkg 本文を読まない構造になり、取りこぼし多発
- **教訓**: 原理 1 (skill = oracle 1 種類)

### F2: LLM 不使用を必要以上に好んだ
- 当初 `/constraints` を keyword scan で実装。結果: TDF で 2/24 しか検出できず
- 同じ verify stage が既に gemma を呼んでるのに、追加 LLM call を避けようとした
- **教訓**: 原理 2 (LLM 判断を恐れない)

### F3: 構造化出力を権威と誤認した
- gemma が `severity: high` で同じテーマを 5 回出してたのを 5 件として扱った (実体は 1 件)
- problems の `open` 25件をそのまま並べた (実体は 4-5 件が真の actionable)
- **教訓**: 原理 4 (一次資料に grounded) + dedup を skill 側で

### F4: メタ的「外部 oracle 不在を context 不足と誤診」
- 「AI が現状理解してれば effect verification できる」と思った。実際は同一モデルの self-eval は coherence trap で誤った確信に収束する (Huang et al. ICLR 2024)
- **教訓**: 外部 oracle が必須、context 充実だけでは足りない (`deep-strict` run 参照: `~/.claude/plans/deep-run-effect-verification-loop.md`)

### F5: 内部 memo を escalation と誤認
- TDF 作業メモ:26-29「確定した要件定義の最優先論点 F008/F009...」を「F008/F009 は client_response」と分類した
- 実際は「内部で escalation 予定」止まり、正式 escalation pkg は未送付
- **教訓**: `/progress` の `pending_escalation` と `/constraints` の `client_response` を厳密に区別

### F6: 私 (CC) が "今日のスコープ" を勝手に切った
- 「Phase 2 は次回」と何度か defer したが、ユーザは前進を望んでいた
- **教訓**: defer は user の指示か、構造的不可能の時だけ。conservative bias に注意

## 8. 既知の制限

### 8.1 LLM 判断のブレ
gemma は同じ入力に対しても判定が揺れる (例: TDF の `dedd1ddb` が run によって blocked / not-blocked に揺れた)。
- 対策: drill step で CC が確認、矛盾は reconciliation rule で処理
- 将来: same-result check (self-consistency 検証) を verify stage に追加可能だが、コスト 2x

### 8.2 cross-problem topic 解決の限界
F008/F009 のような「同テーマだが別 problem」を 1 つの escalation pkg で扱う場合、`/problems` Stage B が cross-doc クラスタリングしないと取りこぼす。`/constraints` の cross-reference prompt で部分的に救えるが、Stage B 改修が根治。

### 8.3 generic repo 未検証
TDF & MS でのみテスト済み。`<人名>版_*.md` 慣習や handoff memo 文化が無い repo での挙動は未確認。SKILL.md 内 drill rule の「最新 handoff memo 候補」heuristic で対応するが、validation 必要。

### 8.4 ack 検出の弱さ
response candidate は filename 内日付に依存。日付なし response doc (例: PR description, Slack export) は拾えない。git commit message も将来 response source に追加可能。

### 8.5 「人間が書く discipline」依存
本 skill は handoff memo / escalation pkg / MTG transcript が **書かれている** ことを前提とする。書く行為を AI に任せるなら別 skill (chat log → memo 自動生成) が必要。

## 9. 将来課題 (priority 順)

1. **generic repo validation** — TDF 以外の 2-3 repo で挙動確認、heuristic 調整
2. **cross-problem topic linker** — `/problems` Stage B に同テーマ cross-doc クラスタリング追加
3. **ack response source 拡張** — git commit message, Slack export, MTG transcript 直接読解
4. **同一 oracle skill の self-consistency 検証** — 同 run 内 2 回呼んで一致率測定
5. **「人間 → AI への write 任せ替え」 skill** — chat log → handoff doc 自動生成
6. **briefing からの auto action proposal** — Drill §6 の提案を /loop が PR/issue に自動起票

## 10. 関連 file 一覧

```
~/.claude/skills/
├── loop/
│   ├── SKILL.md          ← orchestration spec, drill rule, reconciliation
│   ├── DESIGN.md         ← 本書
│   └── loop/
│       ├── cli.py        ← bootstrap + synthesize CLI
│       └── synthesize.py ← briefing 生成 (gemma narrative + drill verbatim)
├── problems/
│   ├── SKILL.md          ← 課題抽出責務、blocking/progress は別 skill 旨明記
│   └── problems/
│       ├── extract.py    ← A: per-doc per-lens occurrence
│       ├── consolidate.py← B: cluster events into problems
│       ├── verify.py     ← C: gemma 判定 (latest_state のみ、blocking 削除済)
│       ├── analyze.py    ← D: discrepancy 原因
│       └── render.py
├── constraints/
│   ├── SKILL.md          ← escalation 専門
│   └── constraints/
│       ├── scan.py       ← escalation pkg + response candidate 検出
│       ├── classify.py   ← 1 gemma call で cross-reference 判定
│       └── cli.py
├── progress/
│   ├── SKILL.md          ← 進捗 6 状態専門
│   └── progress/
│       ├── scan.py       ← git log + artifact dir + decision-language doc
│       ├── classify.py   ← 1 gemma call
│       └── cli.py
└── gemma-worker/         ← code 監査専門 (本書改修対象外)

~/.claude/plans/
├── deep-run-effect-verification-loop.md  ← 設計根拠の文献調査
└── plan-adaptive-seal.md                  ← 過去の plan
```

## 11. 「これ何の skill?」 を 1 行で

| skill | 1 行説明 |
|---|---|
| `/gemma-worker` | code が壊れてないか調べる |
| `/problems` | 問題は何で、どこまで進んだか言う |
| `/constraints` | ボールを持ってるのは誰か言う |
| `/progress` | やった/やってない/止めた/差し戻し で分類する |
| `/loop` | 上記 4 を寄せて 1 ページの状況報告にする |
| CC (Claude Code) | 矛盾を判断し、現場視察し、briefing に書く |
