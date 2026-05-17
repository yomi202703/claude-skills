---
name: ai-pipeline-audit
description: AI パイプライン（プロンプト駆動でサブエージェントが判定・抽出・分類等を行う系）の事後監査。Prompt-induced bias・Eval pipeline integrity・Prompt overfitting・Termination/verification spec・Reasoning-action mismatch の 5 カテゴリで LLM 特有 failure modes を 5 つの isolated subagent in parallel で検知する（軸間 anchoring 防止）。設計初期/実装区切り/サブエージェント呼出前/レビュー時に呼ぶ。
---

# AI Pipeline Audit (orchestrator)

## Rules

- No change-history comments in source files (applies to audit target and to this skill itself). Diffs belong in git/PR.
- No change-summary prose in document body (same).
- Detect, report, user decides. The skill never modifies on its own.
- Silent on CLEAN: do not emit per-axis results when everything passes.
- False positives are acceptable.
- Idempotent: same input produces the same report.

## Workflow

1. Confirm audit targets with user. If the user does not respond or supplies an unreadable path, return the request unfulfilled and stop.
2. Enumerate the files in the target (recursively if a directory, single entry if a file). This is the file queue.
3. Process the file queue one file at a time. For each file:
   a. Spawn 5 audit subagents in parallel via the Agent tool with `model: opus`. Each subagent's input is the content of the corresponding `~/.claude/skills/ai-pipeline-audit/prompts/axis-NN-*.md` plus the single file path as `$TARGET`, with the explicit constraint: "Return ONLY the JSON array — no narration, no markdown fences, no preamble." Each subagent receives only its own axis content and one file.
   b. Collect the 5 JSON arrays for this file.
   c. If a subagent returns non-JSON, errors, or times out, retry once. On second failure, record `{file, axis: N, status: "error", detail: <short>}` and continue with the other axes for this file.
4. After all files are processed, aggregate every JSON list. Preserve cross-axis duplicates: when the same `file:line` is flagged by multiple axes, keep one entry per axis. Do not merge.
5. Report violations as `file:line | axis# | severity | evidence | why`. If every list is empty: `✓ all 5 axes clean across <N> files`. Report any axis-level errors from step 3c alongside the violations.

The orchestrator does not re-judge subagent findings, does not narrate, does not summarize axes.

## Axes

| # | Axis | Layer | Prompt file |
|---|---|---|---|
| 1 | Prompt-induced bias | prompt | `prompts/axis-01-prompt-bias.md` |
| 2 | Eval pipeline integrity | prompt | `prompts/axis-02-eval-integrity.md` |
| 3 | Prompt overfitting | prompt | `prompts/axis-03-prompt-overfitting.md` |
| 4 | Termination & verification spec | prompt | `prompts/axis-04-termination.md` |
| 5 | Reasoning-action mismatch | trace only | `prompts/axis-05-reasoning-action.md` |

Axes are self-contained in their prompt files. The orchestrator does not need to understand them — it only routes targets and collects JSON.
