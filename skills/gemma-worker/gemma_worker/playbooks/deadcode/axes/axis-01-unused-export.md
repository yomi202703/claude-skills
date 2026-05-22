# Axis 1 — Unused top-level export

You audit a single source file for **exported / top-level definitions that have no plausible internal use within this file**. Other axes handle cross-file references, dispatcher patterns, framework hooks, and dead branches.

## What constitutes the failure

- A `def` / `class` / `const` at module top level whose name does not appear anywhere else in the same file.
- A `__all__` list that includes a name not defined or exported elsewhere.
- An `export` statement (TS/JS) for a symbol that is never imported nor referenced in the same file.

## What constitutes acceptable design

- Symbols re-exported for downstream consumers (file has `__all__` and the name is listed): mark severity `low`, not flagged.
- Dunder names (`__init__`, `__repr__`, etc.): never flag.
- Public API of a library file (file path ends with `__init__.py` and symbol is in `__all__`): never flag.

## Output

Strict JSON array. For each unused export:

```json
{"file": "<path>", "line": <int>, "symbol": "<name>", "evidence": "<the def/class line>", "severity": "high|medium|low", "why": "<one-line>"}
```

Empty list if none.
