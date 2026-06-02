---
name: ai-pipeline-audit
description: AI パイプライン（プロンプト駆動でサブエージェントが判定・抽出・分類等を行う系）の事後監査。Prompt-induced bias (sycophancy 含む)・Eval pipeline integrity (reward hacking 含む)・Prompt overfitting・Termination/verification spec・Reasoning-action grounding・Intent-to-Execution integrity・Tool-call grounding・Loop & progress の 8 カテゴリで LLM 特有 failure modes を isolated subagent in parallel で検知する。軸 1–4 は prompt/file を見る設計時監査、軸 5–8 はトレース必須の実行時監査。設計初期/実装区切り/サブエージェント呼出前/レビュー時に呼ぶ。
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

1. Confirm audit targets with user. Determine which layer applies: design-time axes (1–4) need a `$TARGET` file/dir; runtime axes (5–8) need a `$TRACE` (and axis 6 also `$INTENT`). If only one kind of input is supplied, run only that layer's axes. If the user does not respond or supplies an unreadable path, return the request unfulfilled and stop.
2. Enumerate the inputs. For design-time, this is the file queue (recursively if a directory, single entry if a file). For runtime, this is the trace(s).
3. Process the queue one item at a time. For each item:
   a. Spawn the applicable axis subagents in parallel via the Agent tool with `model: opus` — axes 1–4 for a `$TARGET` file, axes 5–8 for a `$TRACE` (axis 6 also receives `$INTENT`). Each subagent's input is the content of the corresponding `~/.claude/skills/ai-pipeline-audit/prompts/axis-NN-*.md` plus the single input path, with the explicit constraint: "Return ONLY the JSON array — no narration, no markdown fences, no preamble." Each subagent receives only its own axis content and one input. A valid return is a JSON array: empty `[]` means the axis is clean for that input; otherwise each element is `{file, line, evidence, severity, why}`. Anything else (prose, fenced text, a non-array) is an invalid return and is handled by step 3c.
   b. Collect the JSON arrays for this item.
   c. If a subagent returns non-JSON, errors, or times out, retry once. On second failure, record `{file, axis: N, status: "error", detail: <short>}` and continue with the other axes for this item.
4. After all items are processed, aggregate every JSON list. Preserve cross-axis duplicates: when the same `file:line` is flagged by multiple axes, keep one entry per axis. Do not merge.
5. Report violations as `file:line | axis# | severity | evidence | why`. If every list is empty: `✓ all <K> axes clean across <N> items` (K = the number of axes actually run for this layer). Report any axis-level errors from step 3c alongside the violations.

The orchestrator does not re-judge subagent findings, does not narrate, does not summarize axes.

## Axes

| # | Axis | Layer | Input | Prompt file |
|---|---|---|---|---|
| 1 | Prompt-induced bias (incl. sycophancy) | design-time (Layer 0) | `$TARGET` file | `prompts/axis-01-prompt-bias.md` |
| 2 | Eval pipeline integrity (incl. reward hacking) | design-time (Layer 0) | `$TARGET` file | `prompts/axis-02-eval-integrity.md` |
| 3 | Prompt overfitting | design-time (Layer 0) | `$TARGET` file | `prompts/axis-03-prompt-overfitting.md` |
| 4 | Termination & verification spec | design-time (Layer 0) | `$TARGET` file | `prompts/axis-04-termination.md` |
| 5 | Reasoning-action grounding | runtime (Layer 2) | `$TRACE` (OTel JSON) | `prompts/axis-05-reasoning-action.md` |
| 6 | Intent-to-Execution integrity | runtime (Layer 2) | `$INTENT` + `$TRACE` | `prompts/axis-06-intent-execution.md` |
| 7 | Tool-call grounding | runtime (Layer 2) | `$TRACE` (OTel JSON) | `prompts/axis-07-tool-grounding.md` |
| 8 | Loop & progress | runtime (Layer 2) | `$TRACE` (OTel JSON) | `prompts/axis-08-loop-progress.md` |

Trace attribute names follow the OpenTelemetry GenAI semantic conventions, which are still pre-stable (Development status); axes 5–8 read the current names and accept legacy aliases as fallback.

Axes are self-contained in their prompt files. The orchestrator does not need to understand them — it only routes targets and collects JSON.

Layer 0 axes can be invoked on every Edit/Write to skill/playbook files (typically via a Claude Code PostToolUse hook). Layer 2 axes are invoked after a worker run completes, against the OpenTelemetry span trace produced by that run.

## Helper scripts

`scripts/meta_judge.py` — reconcile independent judgments of the same finding set and decide which to keep. The `--input` JSON contains aligned arrays; output filters findings whose verdicts converge to `valid` and logs disagreements. Because a panel of correlated judges amplifies bias rather than cancelling it, the script weights diversity: pass a `families` array (one model-family label per judge) and same-family judges are de-weighted with a `low_diversity` warning. A judge whose family matches the evaluatee is dropped for that finding (self-preference guard) when `evaluatee_families` is supplied. Supply a `swapped` verdict array (same findings, inputs reordered) to flag `position_bias` where verdicts flip. Supply a small labelled `calibration` set to report estimated TPR/FPR. Ties remain `uncertain`.

`scripts/verdict_mapper.py` — given a metrics dict, return PROMOTE / HOLD / ROLLBACK. Default thresholds (Task Success ≥ 0.80, Context Preservation ≥ 0.90, P95 Latency < 15s, Safety ≥ 0.95, Evidence Coverage ≥ 0.80, axis 5–8 violations 0) are internal/domain-specific, not a published standard — agentic success rates vary widely by benchmark, so override them per suite via a `thresholds` key in the metrics JSON. For `task_success`, pass a `baseline` to judge by relative improvement instead of an absolute floor. HOLD spans the band down to roughly 70 % of target; below that is ROLLBACK.

Both scripts are pure functions plus a thin CLI; they take no side effects and modify no files. The audit principle "Detect, report, user decides" applies.
