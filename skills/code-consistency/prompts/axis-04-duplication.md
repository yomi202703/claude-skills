# Axis 4: Re-implementation / duplication

You audit the target for logic that is re-implemented instead of reused: near-clone functions, hand-rolled stdlib equivalents, and copy-paste blocks. AI sessions don't grep before writing; this axis catches the resulting duplication. Other audit axes are handled by other subagents — flag only what fits this axis.

## Verdict question

Does this code re-implement logic that already exists in (a) the standard library, (b) a project utility module, or (c) another file in this repo?

## What constitutes the failure

- **Stdlib hand-rolls**:
  - Manual flatten loop instead of `itertools.chain.from_iterable`
  - Manual dict-of-list initialization instead of `collections.defaultdict(list)`
  - Manual count instead of `collections.Counter`
  - Manual string concatenation instead of `pathlib.Path` joining
  - Manual file open/read/close instead of `Path.read_text` / `Path.read_bytes`
  - Manual CSV parsing instead of `csv.DictReader`
  - Manual JSON serialization with `str.replace` chains
  - Manual deduplication via O(n²) loop instead of `set()` / `dict.fromkeys()`
  - Manual `try: x = d[k] / except KeyError: x = default` instead of `d.get(k, default)`
  - Manual `if x is not None: list.append(x)` chains instead of comprehension with filter
- **Repo-internal near-clone**: a function in `$TARGET` whose body is structurally similar (same loop pattern, same control flow, same set of called functions) to another function elsewhere in the repo, differing by 1-3 lines or by a single parameterizable value.
- **Copy-paste block**: a 5+ line block in `$TARGET` that appears nearly verbatim in another file (typical AI cross-pipeline pattern).
- **Helper re-implementation**: a utility-flavored function in `$TARGET` (formatter, parser, validator, key normalizer) that duplicates the shape of something in `_shared/` or the repo's equivalent utility module.
- **Repeated idiom**: the same multi-line idiom (e.g., "load TSV → split rows → strip whitespace → drop empty") written inline in multiple sites instead of being a single helper.

## What constitutes acceptable design

- Reuse from stdlib for the canonical idioms above.
- Single source of truth for each utility, imported across the repo.
- A separate implementation when the contract genuinely differs (different return shape, different error semantics, different side effect) — and the difference is obvious from context.

## How to inspect

For the file at `$TARGET`:

1. **Stdlib scan**: read `$TARGET` and look for the hand-roll patterns enumerated above. For each match, flag with the stdlib alternative as `why`.
2. **Repo-internal clone**: for each top-level function in `$TARGET`, extract its rough shape (parameter count, looping construct, set of called function names, return shape). Grep `$REPO_ROOT` for functions with overlapping signatures or function names from a small synonym set (e.g., `load_*`, `parse_*`, `normalize_*`, `format_*`, `build_*`). For likely candidates, read the candidate file and compare bodies. This is a judgment call — flag when the bodies share both the same control-flow shape and the same set of called functions, with only minor parameterization. False positives are acceptable; the user filters.
3. **Block-level duplication**: scan `$TARGET` for blocks of 5+ consecutive non-trivial lines. For each such block, grep `$REPO_ROOT` for a distinctive snippet (e.g., a unique string literal or rare API call) from the block. If the snippet hits another file, read that file and compare blocks.
4. **Shared-module duplication**: if the repo has a shared utility module, list its public surface; check whether helpers in `$TARGET` duplicate anything in that surface.

Inspection is complete when every top-level function in `$TARGET`, every 5+ line non-trivial block, and every helper-flavored definition has been compared against stdlib idioms and against `$REPO_ROOT` candidates.

Skip:
- Boilerplate forced by a framework (e.g., FastAPI route handlers with similar structure; pytest fixtures).
- Schema-style declarations (dataclasses, TypedDict) that look similar but model distinct concepts.
- Test files mirroring fixture setup — duplication in tests is often deliberate.

## Output

Strict JSON only. No markdown fences, no narration, no preamble.

For repo-internal duplication, the `evidence` field should reference both sites: e.g., `"$TARGET:42 vs other_file.py:88 — near-clone of load_tsv"`.

```json
[
  {"file": "<path>", "line": <int>, "evidence": "<short quote w/ cross-ref if applicable, max 120 chars>", "severity": "high|medium|low", "why": "<one-line, max 120 chars>"}
]
```

Severity guide: `high` = full near-clone function / cross-pipeline copy-paste; `medium` = hand-rolled stdlib in non-trivial path; `low` = minor idiom re-implementation.

If no findings, return `[]`.

## Target

`$TARGET` (anchor file, filled by orchestrator)
`$REPO_ROOT` (filled by orchestrator)
