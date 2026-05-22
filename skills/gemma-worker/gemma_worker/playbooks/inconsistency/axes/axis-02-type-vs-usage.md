# Axis 2 — Type annotation vs. actual usage

You audit a single source file for **declared types that the code itself contradicts**. Other axes handle docstring drift and naming.

## What constitutes the failure

- Parameter annotated `int` but the function indexes a string with it (string indexing accepts int but the call site passes a str literal).
- Return annotated `str | None` but every return path yields `str`.
- Class attribute annotated `list[int]` but code appends a `dict`.
- `Optional[X]` declared but no None branch handled.

## What constitutes acceptable design

- `Any` annotations — out of scope, this axis is about precise contradictions.
- Annotations used as documentation only (no type checker configured): mark `low`.

## Output

```json
{"file": "<path>", "line": <int>, "evidence": "<annotation vs usage>", "severity": "high|medium|low", "why": "<one-line>"}
```

Empty list if none.
