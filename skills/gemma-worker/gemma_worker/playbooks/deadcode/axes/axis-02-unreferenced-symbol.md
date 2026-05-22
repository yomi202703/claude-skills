# Axis 2 — Unreferenced helper

You audit a single source file for **helper / private functions and methods that are defined but never called from within this same file**. Other axes handle exports, dispatcher patterns, framework hooks, and dead branches.

## What constitutes the failure

- Function or method with leading underscore (`_helper`) that has zero call sites in the same file.
- Method on a class that is never invoked by other methods in that class and isn't a known framework hook.
- Static class attribute or module-level constant that is assigned but never read in the same file.

## What constitutes acceptable design

- Test helpers in `test_*.py` / `*_test.py`: even if unreferenced, they may be pytest fixtures — mark severity `low` only.
- Methods overriding a base class contract (`__enter__`, `__exit__`, `close`, etc.): never flag.

## Output

```json
{"file": "<path>", "line": <int>, "symbol": "<name>", "evidence": "<the def line>", "severity": "high|medium|low", "why": "<one-line>"}
```

Empty list if none.
