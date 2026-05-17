# Axis 5: Placeholder & residue debt

You audit the target for generation artifacts, half-finished stubs, and evidence-of-AI-authorship markers. Other audit axes are handled by other subagents — flag only what fits this axis.

## Verdict question

Does this code contain artifacts left over from generation — placeholders, narrating comments, conversation-referencing comments, lazy types, debug residue — that should be removed before the code ships?

## What constitutes the failure

### Placeholder values
- Hardcoded placeholder strings: `"YOUR_API_KEY"`, `"REPLACE_ME"`, `"example.com"`, `<your-token>`, `"changeme"`, `"TODO"`, `"FIXME"`, `"xxx"`.
- Stub return values: `return None` / `return {}` / `return []` in a function whose name implies real work and whose docstring or surrounding code suggests a real implementation was intended.
- Empty `pass` body in a non-abstract, non-protocol function.
- `raise NotImplementedError` in a non-abstract path that is reachable from production callers.

### Stub markers
- `# TODO`, `# FIXME`, `# XXX`, `# HACK` left without an owner + tracking link + date.
- `...` (literal ellipsis) used as a function body outside of a `Protocol` / stub file.

### Narration comments (explain WHAT, not WHY)
- Comments that restate the line below: `# Loop through items` above a `for` loop, `# Increment counter` above `counter += 1`, `# Return the result` above `return ...`, `# Initialize the dict` above `d = {}`.
- Docstrings that just restate the function name in English: `"Initialize the account"` on `def init_account`, `"Return the user"` on `def get_user`.

### Conversation / change residue
- Comments referencing past conversations or tasks: `# Added for issue #123`, `# Per user request`, `# Refactored to handle X`, `# Was previously Y`, `# Updated 2026-03-04`.
- Removal residue: `# (deprecated)`, `# (removed)`, `# Previously did X, now Y`, `# Old version below`.
- Renamed-to-hide artifacts: variable / function with `_unused`, `_legacy`, `_old`, `_deprecated`, `_v1` prefix that is still referenced in current code (vs. truly unreferenced, which is axis 2 / dead-code territory).

### Debug residue
- `print(...)` / `pprint(...)` / `console.log(...)` outside of explicit CLI entry points (i.e., outside `if __name__ == "__main__":` and outside Click / Typer command bodies).
- Commented-out code blocks (more than 1 line of `#` followed by what is clearly a former statement).
- `breakpoint()`, `import pdb; pdb.set_trace()`, `import ipdb`.

### Lazy types
- Function signature uses `Any` or `Optional[Any]` where sibling functions in the same file have concrete types.
- Missing return-type annotation on a function where every other function in the same module has one.
- `Dict[str, Any]` as a return type when the dict has a known fixed shape.

## What constitutes acceptable design

- Comments that explain *why*: a non-obvious constraint, a workaround for a specific upstream bug, a subtle invariant, behavior that would surprise a reader.
- `TODO` with assignee + date + tracking ID (`# TODO(ivymee, 2026-05-15, #142): ...`).
- Placeholder in test fixtures clearly marked as such (`fixture_user_id = "test-user-1"` in a `tests/` file).
- `print` / `pprint` inside a CLI entry point or a script intentionally producing CLI output.
- `Any` when the function genuinely accepts arbitrary types (e.g., a serializer over heterogeneous inputs).
- `NotImplementedError` in abstract method overrides or genuinely-unsupported branches.

## How to inspect

For the file at `$TARGET`:

1. **Placeholder strings**: grep `$TARGET` for the literal placeholder patterns above. Flag each occurrence.
2. **Stub markers**: grep `$TARGET` for `TODO`, `FIXME`, `XXX`, `HACK`. For each, check whether it has assignee + date + tracking ID format. If not, flag.
3. **Narration comments**: read each comment line in `$TARGET`. If the comment paraphrases the immediately-following line of code without adding non-obvious context, flag. Apply the same test to docstrings — flag docstrings that only restate the function name.
4. **Conversation residue**: grep for patterns like `# Added`, `# Per user`, `# Refactored`, `# Was`, `# Previously`, `# (deprecated)`, `# (removed)`, `# Old version`. Flag.
5. **Rename artifacts**: grep `$TARGET` for identifier patterns `_unused`, `_legacy`, `_old`, `_deprecated`, `_v1`, `_v2`. Flag identifiers that are still referenced in `$TARGET` or imported elsewhere.
6. **Debug residue**: grep `$TARGET` for `print(`, `pprint(`, `breakpoint(`, `pdb.set_trace`, `ipdb`. For each, check whether the enclosing function is a CLI entry point. If not, flag.
7. **Lazy types**: parse function signatures. Flag `Any` / `Optional[Any]` / missing return annotation where context suggests a concrete type was practical.

Inspection is complete when every comment, every docstring, every function signature, every string literal flagged by the placeholder patterns, and every identifier matching the rename-artifact prefixes in `$TARGET` has been examined.

## Exclusions (do not flag)

- Files under `tests/`, `conftest.py`, fixtures: placeholder values and `print` debugging are common and acceptable.
- Scripts whose name or shebang marks them as CLI tools: `print` is the output mechanism.
- `__init__.py` re-export files: minimal comments are conventional.
- Comments that explain non-obvious WHY (this axis is about WHAT-narration and conversation residue, not WHY-explanations).

## Output

Strict JSON only. No markdown fences, no narration, no preamble.

```json
[
  {"file": "<path>", "line": <int>, "evidence": "<short quote, max 80 chars>", "severity": "high|medium|low", "why": "<one-line, max 120 chars>"}
]
```

Severity guide: `high` = placeholder value or stub that would break in production / debug residue in non-CLI path; `medium` = TODO without owner / conversation-ref comment / rename artifact; `low` = narration comment / lazy type.

If no findings, return `[]`.

## Target

`$TARGET` (anchor file, filled by orchestrator)
`$REPO_ROOT` (for context only, filled by orchestrator)
