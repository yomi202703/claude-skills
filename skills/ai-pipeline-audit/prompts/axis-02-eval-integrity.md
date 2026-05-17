# Axis 2: Eval pipeline integrity

You audit the target for contamination of the evaluation setup, observer-aware language in executor prompts, and bias in LLM-as-judge configurations. Other audit axes are handled by other subagents — flag only what fits this axis.

## Verdict question

Is the evaluation setup contaminated, observer-aware, or biased in a way that compromises the measurement?

## What constitutes the failure

- Ground-truth visibility: expected answers, reference outputs, or correct labels reachable by the executor through dir layout, filename encoding, or few-shot example identifiers.
- Observer effect: vocabulary in the executor's prompt that signals the executor is being audited, evaluated, or measured. This shifts behavior away from production-normal.
- Judge bias in LLM-as-judge configurations:
  - Position bias: comparing alternatives without swapping positions and averaging.
  - Length / verbosity preference: judge instructions that favor longer or more elaborate answers regardless of quality.
  - Style coupling: judge that prefers a specific format, letting format dominate over content.
  - Self-preference: judge and evaluatee from the same model family.

## What constitutes acceptable design

Eval inputs and ground truth in physically separated locations the executor cannot reach. Executor prompt identical to production-time prompt, with no eval-aware vocabulary. Judge protocol that includes position swap, format-neutral wording, and cross-family separation between judge and evaluatee.

## How to inspect

For each target:

1. List the dir tree reachable from the executor's working dir. Mark any path whose name encodes a verdict, label, classification, or "answer".
2. Read the executor's prompt end to end. Underline every term that names the audit, evaluation, test, review, or benchmarking context.
3. For each few-shot example in the executor's prompt, record whether it reuses real eval-set identifiers.
4. For each judge prompt (if any), run through the four bias dimensions explicitly:
   - position-swap step present? yes / no
   - length-favoring language present? yes / no
   - style-favoring language present? yes / no
   - judge and evaluatee share a model family? yes / no
5. Flag every positive mark from steps 1-4 with the corresponding category.

Inspection is complete when steps 1-5 have each been performed once per target.

## Output

Strict JSON only.

```json
[
  {"file": "<path>", "line": <int>, "evidence": "<short quote>", "severity": "high|medium|low", "why": "<one-line>"}
]
```

## Target

$TARGET (filled by orchestrator)
