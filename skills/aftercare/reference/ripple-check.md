# ripple-check pass (forward consistency)

Loaded by aftercare, and by repo-shape for reference-following after a git mv. After a logic change, check that everything depending on the changed premises follows, and simplify what the change made redundant.

## Principles

- R1. The primary source of intent is the conversation; the primary source of the change surface is the diff. Cross-check both. Never fix a premise from one side alone or from a guess.
- R2. Tool output is a candidate. The final call is your own grep plus reading the code. Never conclude from a single grep line.
- R3. Gate every fix on certainty. Fix only where the way to follow is uniquely determined. Anything whose meaning could change, or that splits on intent, is presented, not fixed — this is the one gate that prevents silently changing behavior.
- R4. "Zero inconsistencies found" is not "no inconsistencies exist". Duplicated logic in particular does not surface by following references.
- R5. Record every fix with file:line, the premise it followed, and the rationale, so all fixes stay reversible and auditable.

## Phase 0 — Scope

The caller hands the change surface (aftercare: the derived git scope; repo-shape: the git-mv'd set). Take that as the changed lines. Pull intent from the conversation (goal, decisions, what was declared out of scope, what was reverted). Cross-check both. If intent is compressed or cold and cannot be traced, proceed on the handed change surface alone and say so. If neither a handed surface nor intent exists, ask for scope and stop.

## Phase 1 — Extract changed premises (deltas)

List how the meaning of values changed, from the changed lines. Number them `D1, D2…` as `<what changed how> @ file:line (goal)`.
Angles: return value (range / meaning / type / null / unit) / arguments (count, order, meaning, defaults) / side effects (write target, firing, order) / exceptions (condition, type, swallowing) / invariants / data shape (schema, enum, constants) / branch conditions (thresholds, boundaries).

Also check intent-vs-diff mismatch: in the diff but not the intent = unintended change (suspected accident); in the intent but not the diff = not applied (forgotten). Present both in Phase 4.
If there is no delta (formatting-only, etc.), report and stop.

## Phase 2 — Find dependents (per delta)

Following symbol references is not enough. For each delta, run the following and open every hit to read it:

- Call sites: does every call site handle the new signature and new return value correctly.
- Parallel / duplicated logic (the most easily missed): the same computation, constant, or decision written independently elsewhere. It does not reference the symbol, so search for the value, expression, or boundary itself and read the paired logic. Hunt for "fixed only one side".
- Tests: tests that pin the old behavior (false green / red), and new behavior left uncovered.
- Types / schemas / contracts / docs / comments / naming / persistence / migration / cache / config / constants / flags.

Collect as `<delta ID> → file:line / content`.

## Phase 2b — Redundancy the change left

Pick up what the change made unnecessary or duplicated. Scope to the changed lines and their neighborhood (whole-repo dead-code sweeping is delegated to the deadcode pass, reference/deadcode/deadcode.md).

- Old-path residue: old code or branches the new logic replaced and no longer reaches.
- Dead branches: conditions a delta made always-true/false, collapsed cases.
- No-longer-needed: arguments, variables, helpers, imports, flags that fell out of use.
- New duplication: where the change wrote logic identical to something existing (the flip side of Phase 2's duplication — here you delete one side and converge).
- Over-guarding: duplicate guards or checks made meaningless by a changed invariant.

Collect as `R<n> → file:line / what is redundant / proposal (delete, merge, simplify)`.

## Phase 3 — Classify and fix

- Already following: consistent; nothing to do.
- Certain: the way to follow is unique (follow a signature, update a doc stating the old premise, align a paired duplicate to equivalence — a new-vs-old inconsistency). Fix it.
- Otherwise: present, do not fix (R3).

## Phase 4 — Verify and report

If tests / typecheck exist, run them after fixing. Report every fix per R5, plus the intent-vs-diff mismatches from Phase 1.
