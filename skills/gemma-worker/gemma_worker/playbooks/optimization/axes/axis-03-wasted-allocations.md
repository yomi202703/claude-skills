# Axis 3 — Wasted allocations

You audit a single source file for **avoidable allocations and copies**.

## What constitutes the failure

- `list(...)` of an iterator that's only used to iterate once.
- `copy.deepcopy` of immutable structures.
- Building an intermediate list inside a comprehension that's immediately reduced (`sum([x for x in xs])` instead of `sum(x for x in xs)`).
- Concatenating large lists with `+` instead of `extend`.
- Repeated `dict()` calls that just copy.

## What constitutes acceptable design

- Defensive copies where mutation is genuinely a risk: not flagged.
- Conversions required by an API: not flagged.

## Output

```json
{"file": "<path>", "line": <int>, "evidence": "<the wasteful pattern>", "severity": "high|medium|low", "why": "<one-line>", "suggestion": "<concrete change>"}
```

Empty list if none.
