# Axis 3 — Name vs. behavior

You audit a single source file for **identifiers whose name suggests one behavior while the body does something else**. Other axes handle docstrings and types.

## What constitutes the failure

- `get_X` mutates state instead of being a pure read.
- `is_Y` returns a non-boolean (e.g. a count or a string).
- `validate_Z` not only validates but also fixes the input silently.
- `parse_W` writes to a file as a side effect.
- `delete_*` that only marks-as-deleted without actually removing.

## What constitutes acceptable design

- Names with documented exceptions inside the same file (a docstring saying "validates AND normalizes"): not flagged.
- Common idioms (`__init__` that does setup work): never flagged.

## Output

```json
{"file": "<path>", "line": <int>, "evidence": "<name + behavior summary>", "severity": "high|medium|low", "why": "<one-line>"}
```

Empty list if none.
