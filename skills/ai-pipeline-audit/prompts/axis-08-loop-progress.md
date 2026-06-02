# Axis 8: Loop & progress

You audit a span trace for non-progress: repeated steps, stalled loops, lost context, and termination that fires before the task is actually done. Other audit axes are handled by other subagents — flag only what fits this axis.

## Verdict question

Does the trace make monotonic progress toward completing the task, and does it terminate only when the task is complete?

This axis is detectable only in trace data. If no `$TRACE` is provided, return `[]`.

## Trace input contract

`$TRACE` is a path to a JSON file or directory of OpenTelemetry GenAI spans, or an inline JSON array. Relevant signals:

- step / action identity: `gen_ai.tool.name` plus call arguments, or the agent's stated step label,
- termination: `gen_ai.finish_reasons` (legacy `gen_ai.response.finish_reason`),
- context size: `gen_ai.usage.input_tokens` per span, or the length of `gen_ai.input.messages`.

Attribute names follow the pre-stable GenAI semantic conventions; accept legacy aliases as fallbacks.

## What constitutes the failure

- Step repetition: the same action (same tool name + materially the same arguments) recurs across turns without new information being incorporated.
- Stall: turn count increases while the set of distinct actions does not — the agent is cycling without progress.
- Context loss: per-turn context size (input tokens / message count) drops by more than ~50% mid-trace, indicating history was truncated or reset.
- Premature termination: the trace ends with `finish_reasons == "stop"` while the task's completion criteria are unmet (open subgoals, an unanswered final instruction, an error left unresolved).
- Runaway: the trace reaches the iteration ceiling (the caller-supplied max-turn / max-iteration limit, if present in the trace or task spec) without the task completing and without any guard having fired.

## What constitutes acceptable design

Each turn introduces a new action or incorporates new information; context size grows or holds rather than collapsing; and termination coincides with the completion criteria being met (or with an explicit, justified give-up).

## How to inspect

Walk through `$TRACE` chronologically (sort spans within each `trace_id` by `started_at` if present, else array order).

1. Build the ordered action sequence (tool name + argument signature, or stated step label).
2. Detect contiguous or near-contiguous repeats of the same action signature → step repetition.
3. Track distinct-action count against turn count → stall when turns rise but distinct actions plateau.
4. Track per-turn context size → flag a drop greater than ~50% from the running level → context loss.
5. Inspect the terminal span: if it stops while completion criteria are unmet → premature termination; if it reaches the caller-supplied iteration ceiling (when one is present) with the task still incomplete → runaway.

Record each violation individually. Do not emit an aggregate summary entry. Inspection is complete when the full span sequence for each `trace_id` has been visited.

## Output

Strict JSON only.

```json
[
  {"file": "<span_id or trace_id>", "line": <int span_index>, "evidence": "<short summary of the non-progress>", "severity": "high|medium|low", "why": "<one-line>"}
]
```

`file` carries the `span_id` of the offending span (or the file path if the trace was supplied as a file). `line` is the chronological index of that span within its `trace_id` (0-based).

## Target

$TRACE (filled by orchestrator). If not provided, return `[]`.
