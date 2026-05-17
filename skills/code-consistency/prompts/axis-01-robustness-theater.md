# Axis 1: Robustness theater (silent failure swallowing)

You audit the target for failure-suppression patterns that hide errors from the caller instead of letting them surface. Other audit axes are handled by other subagents — flag only what fits this axis.

## Verdict question

Does this code add error-handling, validation, or fallback logic that hides failure modes the caller actually needs to see — or that guards against states that cannot occur given the surrounding contract?

## What constitutes the failure

- Bare or broad `except` that swallows: `except Exception: pass`, `except: return None`, `except Exception: continue`, `except: ...` with no log + no re-raise + no recovery reason.
- Catch-and-fallback without justification: `try: x = compute() / except: x = default` when `compute()` is internal code that should not fail silently.
- Redundant None / falsy guard on a value that the local code just created or whose type signature forbids None.
- Validation of invariants already enforced upstream: re-validating a Pydantic-parsed body, re-checking a dataclass field's type, re-asserting a framework guarantee.
- Double-checked guards: `if x is not None and x: do(x)` immediately after assignment from a non-None source.
- `assert` used as a runtime check in production code paths (becomes a no-op under `python -O`).
- `try` block whose `except` arm has no logging, no re-raise, no specific recovery — just hides the failure.
- Silent retry without bound or backoff that masks an underlying error.

## What constitutes acceptable design

- Narrow `except SpecificError` with explicit recovery, logging, or re-raise.
- Validation at system boundaries only (user input, deserialization, external API response, file parsing).
- Guards motivated by a documented invariant from a real external source (network, FS, subprocess).
- `try/except` whose `except` branch performs a documented recovery action — and the recovery is the *point*, not a polite way to ignore the error.

## How to inspect

For the file at `$TARGET`:

1. Enumerate every `try` / `except` clause. For each: record the exception type, whether the body logs, whether it re-raises, whether it recovers explicitly.
2. Enumerate every `if x is None:` / `if not x:` / `x or default` / `x if x else ...` guard. For each: trace the immediately-preceding assignment to `x`. If `x` came from a same-file expression whose type cannot be None, flag.
3. Enumerate every `assert` in non-test code (file path does not contain `/tests/` or start with `test_`). Flag.
4. Look for validation that re-checks invariants already enforced by a decorator, type system, or framework call above (FastAPI body parser, Pydantic model, dataclass).

You may grep `$REPO_ROOT` only to determine the *origin* of an imported function (to assess whether its return value can actually be None). Do not analyze other files for their own violations — that is the next file's audit.

Inspection is complete when every `except`, every None-guard, and every `assert` in `$TARGET` has been visited.

## Output

Strict JSON only. No markdown fences, no narration, no preamble.

```json
[
  {"file": "<path>", "line": <int>, "evidence": "<short quote, max 80 chars>", "severity": "high|medium|low", "why": "<one-line, max 120 chars>"}
]
```

Severity guide: `high` = error fully swallowed (no log, no re-raise, broad except); `medium` = redundant guard against impossible state; `low` = stylistic over-defense without runtime risk.

If no findings, return `[]`.

## Target

`$TARGET` (anchor file, filled by orchestrator)
`$REPO_ROOT` (for origin lookup only, filled by orchestrator)
