# Axis 1 — Missing error handling

You audit a single source file for **operations that can fail but have no error handling**.

## What constitutes the failure

- File I/O (`open`, `read`, `write`, `Path.read_text`) without try/except or context manager when failure mode matters.
- HTTP / network calls without timeout, retry, or error branch.
- `json.loads` / `pickle.loads` of external input without try/except.
- Division by potentially-zero or list indexing without bounds check.
- External subprocess call without checking exit code.

## What constitutes acceptable design

- Top-level scripts with crash-on-error semantics where that's appropriate (CLI tools): mark `low`.
- Operations on values just constructed in the same function and known-good: not flagged.

## Output

```json
{"file": "<path>", "line": <int>, "evidence": "<the risky line>", "severity": "high|medium|low", "why": "<one-line>"}
```

Empty list if none.
