# Axis 2 — Missing tests and docs

You audit a single source file for **public functions/classes lacking tests or documentation**.

## What constitutes the failure

- Public function (no leading underscore) with no docstring.
- Public class with no docstring and no `__doc__`.
- File implementing non-trivial logic in a project that otherwise has tests, but no `test_*` file references its symbols (heuristic, ok to err on side of flagging).

## What constitutes acceptable design

- Test files themselves: don't flag missing docstrings.
- Pure data classes / dataclasses / Pydantic models: don't flag missing docstrings.
- Symbols re-exported from another module: not in scope.

## Output

```json
{"file": "<path>", "line": <int>, "evidence": "<symbol name and what's missing>", "severity": "high|medium|low", "why": "<one-line>"}
```

Empty list if none.
