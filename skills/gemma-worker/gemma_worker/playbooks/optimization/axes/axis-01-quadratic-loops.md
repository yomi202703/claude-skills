# Axis 1 — Quadratic / superlinear loops

You audit a single source file for **nested loops that scale quadratically (or worse) when a linear/log algorithm exists**.

## What constitutes the failure

- Nested `for` loops over the same collection where membership lookup via `set` / `dict` would suffice.
- `if x in list:` inside a loop over the same list (O(n²) membership).
- `list.remove()` / `list.index()` inside a loop on the same list.
- String concatenation in a loop (`s += chunk`) when `"".join(...)` exists.
- Repeated full re-computation that could be memoized.

## What constitutes acceptable design

- Small N known at design time (< 50): mark `low` only.
- Code clearly within a test or one-shot script: mark `low`.

## Output

```json
{"file": "<path>", "line": <int>, "evidence": "<the quadratic pattern>", "severity": "high|medium|low", "why": "<one-line>", "suggestion": "<concrete change>"}
```

Empty list if none.
