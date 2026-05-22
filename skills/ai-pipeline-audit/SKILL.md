---
name: ai-pipeline-audit
description: AI パイプライン（プロンプト駆動でサブエージェントが判定・抽出・分類等を行う系）の事後監査。Prompt-induced bias・Eval pipeline integrity・Prompt overfitting・Termination/verification spec・Reasoning-action mismatch・Intent-to-Execution integrity の 6 カテゴリで LLM 特有 failure modes を isolated subagent in parallel で検知する。軸 1–4 は prompt/file を見る設計時監査、軸 5–6 はトレース必須の実行時監査。設計初期/実装区切り/サブエージェント呼出前/レビュー時に呼ぶ。
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

| # | Axis | Layer | Input | Prompt file |
|---|---|---|---|---|
| 1 | Prompt-induced bias | design-time (Layer 0) | `$TARGET` file | `prompts/axis-01-prompt-bias.md` |
| 2 | Eval pipeline integrity | design-time (Layer 0) | `$TARGET` file | `prompts/axis-02-eval-integrity.md` |
| 3 | Prompt overfitting | design-time (Layer 0) | `$TARGET` file | `prompts/axis-03-prompt-overfitting.md` |
| 4 | Termination & verification spec | design-time (Layer 0) | `$TARGET` file | `prompts/axis-04-termination.md` |
| 5 | Reasoning-action mismatch | runtime (Layer 2) | `$TRACE` (OTel JSON) | `prompts/axis-05-reasoning-action.md` |
| 6 | Intent-to-Execution integrity | runtime (Layer 2) | `$INTENT` + `$TRACE` | `prompts/axis-06-intent-execution.md` |

Axes are self-contained in their prompt files. The orchestrator does not need to understand them — it only routes targets and collects JSON.

Layer 0 axes can be invoked on every Edit/Write to skill/playbook files (typically via a Claude Code PostToolUse hook). Layer 2 axes are invoked after a worker run completes, against the OpenTelemetry span trace produced by that run.

## Helper scripts

`scripts/meta_judge.py` — reconcile cheap / expensive / tie-breaker verdicts for a batch of findings. Use it when you have already obtained two or three independent judgments of the same finding set and need to decide which to keep. The script's `--input` JSON contains aligned arrays; the output filters findings whose verdicts converge to `valid` and logs any disagreement records.

`scripts/verdict_mapper.py` — given a metrics dict, return a PROMOTE / HOLD / ROLLBACK verdict using the published thresholds (Task Success ≥ 0.80, Context Preservation ≥ 0.90, P95 Latency < 15s, Safety ≥ 0.95, Evidence Coverage ≥ 0.80, axis 5/6 violations 0). HOLD spans the band down to roughly 70 % of target; below that is ROLLBACK.

Both scripts are pure functions plus a thin CLI; they take no side effects and modify no files. The audit principle "Detect, report, user decides" applies.
