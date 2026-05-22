# Axis 2 — Redundant I/O

You audit a single source file for **I/O operations that could be batched or avoided**.

## What constitutes the failure

- Reading the same file multiple times where one read + reuse would suffice.
- Per-row database queries inside a loop (N+1 query pattern).
- HTTP request per item where a batch endpoint exists.
- `open(path).read()` inside a loop over fixed paths.
- `subprocess.run(...)` per iteration where a single call could handle multiple inputs.

## What constitutes acceptable design

- I/O that depends on a previous iteration's output and cannot be batched: not flagged.
- Files known to be small and re-reads aid clarity: mark `low`.

## Output

```json
{"file": "<path>", "line": <int>, "evidence": "<the redundant I/O>", "severity": "high|medium|low", "why": "<one-line>", "suggestion": "<concrete change>"}
```

Empty list if none.
