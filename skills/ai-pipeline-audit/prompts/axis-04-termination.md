# Axis 4: Termination & verification spec

You audit the target for missing or vague completion / verification specifications. Other audit axes are handled by other subagents — flag only what fits this axis.

## Verdict question

Does the prompt give the executor a concrete, operational definition of "done" and "verified"?

## What constitutes the failure

- Vague verification: an instruction to verify, check, or ensure correctness without a concrete checklist or action boundary, so the executor has no way to operationalize it.
- Concept-level prohibitions: abstract prohibitions the executor cannot operationalize (no way to tell when it has obeyed).
- Missing stop conditions: a subagent invocation prompt that does not fully specify how the executor terminates — what to return on success, what to return on failure, which inputs are in scope, where the output goes, and what to do when a read or tool call fails.
- Negation density: cumulative prohibitive instructions in a single prompt. Each prohibition adds cognitive load without operational guidance.

## What constitutes acceptable design

Verification expressed as a concrete checklist with named steps the executor can mechanically perform. Stop conditions fully specified: success and failure each have a defined return shape, allowed inputs are enumerated, output paths are fixed, read-failure behavior is named. Instructions expressed positively, with prohibition reserved for cases that are immediately paired with an operational alternative.

## How to inspect

For each prompt file in $TARGET:

1. List every verification verb (anything asking the executor to verify, check, ensure, confirm, validate, review).
2. For each verification verb in step 1, locate the nearest concrete checklist within the same section. If none exists, flag the verb.
3. List every prohibition (negative-form instruction).
4. For each prohibition in step 3, check whether a positive operational alternative immediately follows. If not, flag the prohibition.
5. Count the prohibitions per file. Flag the file when prohibitions outnumber positive operational instructions in the same file.
6. For each subagent invocation prompt, check whether each of the following is specified: success-return shape, failure-return shape, allowed-input scope, output path, read-failure behavior. Each missing item is a finding.

Inspection is complete when steps 1-6 have been performed once per file.

## Output

Strict JSON only.

```json
[
  {"file": "<path>", "line": <int>, "evidence": "<short quote>", "severity": "high|medium|low", "why": "<one-line>"}
]
```

## Target

$TARGET (filled by orchestrator)
