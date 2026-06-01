Base directory for this skill: /Users/ivymee/.claude/skills/progress

# progress

各 problem の **進捗状態** を `/problems` の二値 (open/resolved) よりも細かく分類する skill。

「課題があるか」(`/problems`) と「外部のボール待ちか」(`/constraints`) と独立に、**我々の意思決定としての状態** を扱う。

oracle:
- git log (直近 commit message の「実装」「廃止」「棄却」「fix」言及)
- artifact dir 存在 (outputs/, dist/, build/, etc — 完成物の有無)
- doc 内の完了/棄却 language (「実装完了」「対象外」「優先度下げ」「次フェーズ」「廃止」)

## When to invoke

- `/loop` から `/problems` + `/constraints` の後に呼ばれる (主用途)
- 「これは完了 or 後回し or 棄却 or 未着手?」を問題ごとに知りたい時

## When NOT to invoke

- 課題そのものの抽出 → `/problems`
- 外部 escalation の追跡 → `/constraints`
- 単に「open かどうか」だけが知りたい → `/problems` で十分

## What it does (1 gemma call)

```
input:
  - .loop/problems.json (各 problem の id/title/timeline/latest_state)
  - .loop/constraints.json (optional、blocked 状態の参考)
  - git log (直近 N commit、`git log --oneline -n 50`)
  - artifact dir scan (outputs/, dist/, build/, 35_*/outputs/ 等)

process:
  - 各 problem について、上記から **completion / drop / defer signal** を集める
  - 1 gemma call で全 problems 横断判定 (cross-problem context あり)

output: .loop/progress.json
```

LLM call: 1 回のみ。

## Output

`.loop/progress.json`:
```json
{
  "progress": [
    {
      "problem_id": "<8-char>",
      "status": "done|undone|dropped|superseded|pending_escalation",
      "evidence_quote": "<verbatim ≤200 chars>",
      "evidence_source": "<doc path or commit hash>",
      "completion_date": "YYYY-MM-DD" | null,
      "reason": "<one-line why>"
    }
  ],
  "git_log_excerpt": [...],
  "artifact_dirs_found": [...],
  "generated_at": "ISO"
}
```

`status` 定義:
- **done**: 実装完了・実行成功・廃止後の置き換え完了 (`/problems` の resolved に概ね対応するが、より厳密)
- **undone**: 未着手 or 部分実装、まだやることがある (= 純 actionable)
- **deferred**: 意図的に優先度を下げた、戻ってくる可能性あり (「優先度を下げ」「後回し」「次フェーズ」)
- **dropped**: 明示的に永久棄却 (「対象外」「やらない」「棄却」「廃止」)
- **superseded**: 別のアプローチに置き換えられた (例: v1 → v2)
- **pending_escalation**: 我々は escalation したいが正式送付物がまだ無い (例: 内部 memo に「次回 MTG で論点」)

## CLI

```bash
progress run --repo <PATH>
progress run --repo <PATH> --no-cache
```

## Design notes

- `pending_escalation` は `/constraints` で拾えない隙間を埋める (正式 escalation 前の "送付予定" 状態)
- `dropped` と `undone` の区別は強い signal が要る (memo 内の明示的「やらない」言及など)。曖昧なら undone (= 動ける扱い、保守的)
- `git log` は repo が git 配下のときのみ取得。それ以外は doc 言語のみで判定
