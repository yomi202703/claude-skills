# Axis 3 — Orphan module heuristic

You audit a single source file for evidence that **the whole module appears to be an orphan**. You are reasoning from this file alone; final orphan judgment belongs to the supervisor.

## What constitutes the failure

- File has only definitions, no `__main__` block, and a name suggesting deprecation (`_old`, `_legacy`, `_v1`, `_archived`).
- File defines functions matching a deprecated API style not seen elsewhere in the codebase (sync versions of an async-first project, callback style of a promise-first codebase).
- File has a top-level docstring saying "deprecated", "legacy", "do not use", "scheduled for removal".

## What constitutes acceptable design

- Newly added file (you cannot tell from a single file's content — emit `low` severity if signals are weak).
- Test fixtures and `__init__.py` files: never flag as orphan.

## Output

Emit at most ONE entry per file (orphan is a module-level claim):

```json
{"file": "<path>", "line": 1, "symbol": "(module)", "evidence": "<short cue>", "severity": "high|medium|low", "why": "<one-line>"}
```

Empty list if none.
