Base directory for this skill: /Users/ivymee/.claude/skills/constraints

# constraints

各 problem が **外部のボール待ち** (顧客回答 / 西村レビュー / 他チーム作業中) かを判定する skill。

「課題があるか」(`/problems`) と「進捗があるか」(`/progress`、将来) と独立に、**ボールが誰の手にあるか** だけを専門に扱う。

oracle は **escalation 兆候**:
- `_<人名>版_*.md` 等の escalation package
- `*MTG*` ディレクトリの議事録 (「ご相談」「ご確認いただきたい」「依頼済」「待ち」言及)
- 送付日 / ack の文書化

## When to invoke

- `/loop` から `/problems` の後に呼ばれる (主用途)
- 「今ボール持ってるのは誰?」を整理したい時

## When NOT to invoke

- 課題そのものの抽出 → `/problems`
- 進捗 (done/dropped) 判定 → `/progress` (将来)
- 棄却・後回し (= 我々の意思決定) は **このskill の責務外** (→ `/progress`)

## What it does (1 gemma call)

```
input:
  - .loop/problems.json (各 problem の id/title/timeline)
  - repo 内の escalation package 検出 (filename + content scan)
  - MTG transcript 検出 (top-level *MTG*/ dir 探索)

process:
  - escalation package と MTG 内で言及されている topic を抽出
  - 各 problem に対し: その problem の topic が escalation package で言及されているか
                       → されてれば該当 doc を escalation_doc として記録
                       → されてなければ null
  - 1 gemma call で全 problems 横断判定 (cross-problem context あり)

output: .loop/constraints.json
```

LLM call: 1 回のみ。

## Output

`.loop/constraints.json`:
```json
{
  "constraints": [
    {
      "problem_id": "<8-char>",
      "kind": "client_response|external_review|null",
      "owner": "<name or 'client'|'external'>",
      "since": "YYYY-MM-DD",
      "escalation_doc": "<path>",
      "ack": true | false | null,
      "ack_doc": "<path>" | null,
      "last_sent_days_ago": <int>,
      "evidence_quote": "<verbatim, ≤200 chars>"
    }
  ],
  "escalation_packages_found": [
    {"path": "...", "kind": "version_doc|mtg_transcript|other", "owner": "...", "date": "..."}
  ],
  "response_candidates_found": [
    {"path": "...", "date": "...", "matched_keyword": "...", "excerpt": "..."}
  ],
  "generated_at": "ISO"
}
```

## CLI

```bash
constraints run --repo <PATH>
constraints run --repo <PATH> --no-cache  # ignore .loop/_stages/constraints.json
```

## Design notes

- `internal_defer` (我々が後回し決定) は **進捗状態であり制約ではない** ので扱わない。`/progress` 担当 (将来)
- `discrepancy` (doc と code が矛盾) は `/problems` 担当のまま
- gemma に **全 problems + 全 escalation package を一括** で見せることで、cross-problem の topic 共有を捕捉できる (旧 `/problems` 内 blocking_constraint の取りこぼし問題の解決)
