# Axis 3: Drift across files (term, schema, constant inconsistency)

You audit the target for inconsistencies in naming, data shapes, and constants between this file and the rest of the repo. AI sessions independently re-name and re-define things without grepping; this axis catches the resulting drift. Other audit axes are handled by other subagents — flag only what fits this axis.

## Verdict question

Does this file refer to the same domain concept, key, or constant by a different name or shape than other files in the repo do?

## What constitutes the failure

- Same domain entity referred to by inconsistent names across files: `account_id` in one file, `customer_id` in another, `acct_id` in a third — when they denote the same value.
- Magic number / threshold / sentinel value duplicated across files with no shared constant definition. Example: `0.35` appearing as a similarity threshold in multiple sites, with no single `THRESHOLD_X` constant.
- Producer / consumer dict-shape mismatch: function in module A returns `{"name": ..., "id": ...}`, function in module B reads `row["display_name"]` from that same upstream.
- TypedDict / dataclass / pydantic.BaseModel with the same conceptual role but divergent field sets across files (one has `created_at`, another has `timestamp`, etc).
- Enum / string-literal sentinel spelled differently: `"healthy"` in one place, `"ok"` in another, both gating the same downstream branch.
- Constant defined locally in `$TARGET` that already exists in a shared module (`_shared/_config.py`, `_shared/constants.py`, or whichever equivalent the repo uses).
- File path string / table name / column name hardcoded in multiple files instead of referenced from a single source.

## What constitutes acceptable design

- One canonical name per domain concept, used consistently. Aliases only where a transformation occurs.
- All magic numbers above triviality (anything carrying domain semantics: thresholds, limits, weights, scores) defined once in a shared config / constants module.
- Producer schema and consumer schema agree, or there is an explicit adapter function with both shapes spelled out.
- Shared types (TypedDict / dataclass) declared once and imported.

## How to inspect

For the file at `$TARGET`:

1. **Concept map**: enumerate every domain-meaningful identifier in `$TARGET` (column names, dict keys, parameter names that denote entities — not local variables like `i`, `tmp`, `result`). For each, grep `$REPO_ROOT` for *similar* identifiers (Levenshtein-close, or known synonym pairs like `id`/`ID`/`_id`, `name`/`label`/`title`, `user`/`account`/`customer`). Flag when the same concept appears under > 1 name across files.
2. **Magic numbers**: enumerate every numeric literal in `$TARGET` that is not `0`, `1`, `-1`, `2`, or a trivially-obvious index. For each, grep `$REPO_ROOT` for the same literal. If it appears in ≥ 2 files and a shared constants module exists, flag.
3. **Schema diff**: for each dict literal, TypedDict, dataclass, or BaseModel defined in `$TARGET` whose role is "row" or "record" or "response" (semantic role indicated by naming or by being passed between functions), find the consumer sites via grep. If the consumer reads keys that don't exist in the producer, or the producer writes keys the consumer never reads, flag.
4. **Sentinel drift**: for each string literal in `$TARGET` used as an enum-like value (comparison `== "foo"`, key in branching dict), grep `$REPO_ROOT` for related sentinel strings used in the same conceptual switch.
5. **Shared-module bypass**: if `$REPO_ROOT` contains a shared config / constants module, check whether constants in `$TARGET` duplicate values there.

You have read access to all of `$REPO_ROOT` — use it. This axis is fundamentally cross-file.

Inspection is complete when every domain identifier, every non-trivial numeric literal, every shared data shape, every enum-like string sentinel, and every locally-defined constant in `$TARGET` has been cross-referenced against `$REPO_ROOT`.

## Exclusions (do not flag)

- **Single-file local concerns**: if a literal, constant, or identifier appears only in `$TARGET` and nowhere else in `$REPO_ROOT`, it is out of scope for this axis regardless of stylistic merit. Single-file hardcoded paths, single-file magic numbers, and single-file mid-function literals belong to other axes (or to no axis). Drift requires ≥ 2 sites.
- **Idiomatic boilerplate without a canonical home**: patterns like `BASE = Path(__file__).resolve().parent.parent`, `HERE = Path(__file__).parent`, or `sys.path.insert(0, str(...))` that appear identically across many files but where **no shared module defines a canonical version**. These are intentional bootstrap idioms — flagging them creates churn without value. Only flag if a canonical definition already exists in a shared module and `$TARGET` is bypassing it.
- **`__file__`-derived paths**: each file's own location-derived constants are inherently per-file. Treat as boilerplate, not drift.
- **Trivially-shared structural keys**: dict keys like `"id"`, `"name"`, `"value"`, `"data"` that appear across files but denote different things in each context (not the same domain concept).

## Output

Strict JSON only. No markdown fences, no narration, no preamble.

The `evidence` field should reference both the `$TARGET` line and the conflicting site elsewhere: e.g., `"$TARGET:42 'customer_id' vs other_file.py:88 'account_id'"`.

```json
[
  {"file": "<path>", "line": <int>, "evidence": "<short quote w/ cross-ref, max 120 chars>", "severity": "high|medium|low", "why": "<one-line, max 120 chars>"}
]
```

Severity guide: `high` = producer/consumer schema mismatch causing real runtime risk; `medium` = naming inconsistency that obscures cross-file logic; `low` = magic-number duplication or stylistic divergence.

If no findings, return `[]`.

## Target

`$TARGET` (anchor file, filled by orchestrator)
`$REPO_ROOT` (filled by orchestrator)
