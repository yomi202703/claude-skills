# Axis 3: Prompt overfitting

You audit the target for prompts that encode the test set instead of expressing the underlying principle. Other audit axes are handled by other subagents — flag only what fits this axis.

## Verdict question

Does the prompt encode specific cases or surface signals such that an executor agent could succeed on the training / test set without grasping the principle, but would fail on novel inputs?

## What constitutes the failure

- Output-side overfitting: the return contract requires the agent to self-report metrics that could be optimized as ends in themselves rather than as honest measurement of the underlying task.
- Lookup-table rules: the rule body is dominated by surface-pattern to answer mappings that let the agent bypass the rule logic.
- Enumerated-case overdose: the rule consists of many specific clauses rather than a principle expressed once with a small number of illustrative examples.
- Forward references to specific examples: the rule points to prior enumerations rather than being self-contained.
- Specific-entity density: real identifiers, names, or codes embedded throughout the rule body, replacing rule logic with surface patterns.

## What constitutes acceptable design

The output contract is minimal — an acknowledgment or single verdict — with statistics and aggregations computed downstream by the parent from the artifact. The rule is an abstract principle stated in a few sentences, optionally followed by a small number of illustrative examples that show how the principle applies, never substituting for the principle. Each rule clause stands on its own. Specific entities appear only where they belong to a defined enumeration, not as ambient noise.

## How to inspect

For each prompt / rule file in $TARGET:

1. Read the file end to end.
2. Identify the abstract principle the rule expresses, stating it in 1-3 sentences. If you cannot, that itself is a finding.
3. Count the case-by-case clauses (any clause that conditions on a specific named instance rather than a general predicate).
4. Count the forward references to prior named instances.
5. Count the specific-entity tokens (real IDs, names, codes) per file.
6. Examine the return contract: list every required output field and judge whether each can be produced without performing the underlying task.

Flag a file if step 2 fails, step 3 count exceeds the number of abstract principle sentences identified in step 2, step 4 is non-zero, step 5 count exceeds the number of rule clauses in the file, or step 6 yields any "yes". Inspection is complete when steps 1-6 have been performed once per file.

## Output

Strict JSON only.

```json
[
  {"file": "<path>", "line": <int>, "evidence": "<short quote or count>", "severity": "high|medium|low", "why": "<one-line>"}
]
```

## Target

$TARGET (filled by orchestrator)
