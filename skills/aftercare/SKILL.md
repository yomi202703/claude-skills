---
name: aftercare
description: After-change cleanup — the single skill for tidying what changes leave behind. Runs three selectable passes, chosen at start (default all), then verifies — forward-consistency (make everything follow a change), supersession sweep (residue that still points at a world that no longer exists: dangling references, renamed-away names, stale docs/STATUS/TODO, superseded files), and reachability (dead / unreferenced code). Use at end of a session to sweep the whole session's residue, or for any one pass on its own. Not for restructuring a repo's tree (that is repo-shape, which uses this skill's consistency pass).
---

## What this runs

A thin orchestrator over a working session's residue. It runs three passes — forward consistency and reachability live as reference procedures (reference/ripple-check.md and reference/deadcode/deadcode.md), supersession is its own track below — without reimplementing them inline. Two evidence models for "no longer load-bearing" run here: reachability (nothing references it) and supersession (it points at a world that no longer exists). Dangling references are the inverse of orphans, so the two are run together but kept distinct.

## Every run

1. Seed from observable state: the session's `git diff` plus recent commits is the durable backbone (survives context compression). Live conversation context sharpens candidate-finding but never authorizes a deletion on its own.
2. Offer the three passes as a multi-select (AskUserQuestion, multiSelect), pre-selected all, in canonical order — ripple-check (forward consistency), supersession (residue), deadcode (reachability). If the invocation already named a subset, pre-select that instead.
3. Run only the selected passes, in the canonical order of the phases below. Verify and report after them, with at most one feedback pass.
4. Enforce the gates throughout. Anything ambiguous is presented, not acted on.
5. Report grouped by outcome category.

## Phases

Run the selected phases in this order; skip any the user deselected.

- Phase A — forward consistency: run the ripple-check pass (reference/ripple-check.md). Make the change's dependents follow the new contract before judging what is residue, since the supersession track's "is this still load-bearing" check assumes the code is already consistent. Breakage that pass surfaces (changed X, Y still calls the old X) is fixed here. If B runs without A, the load-bearing checks still run but on possibly-inconsistent code.
- Phase B — supersession sweep: this skill's own track, below.
- Phase C — reachability mop-up: run the deadcode pass (reference/deadcode/deadcode.md) on the second-order orphans Phase B created by removing residue.
- Phase D — verify and report: run tests / typecheck. Only when both A and C ran and C's deletions introduced a new inconsistency, run the ripple-check pass once more — one feedback pass only, then report whatever remains.

## Phase B — supersession track

Find what still assumes a superseded world, classify how to treat it, then act only where the current truth is unambiguous.

Lenses (collect candidates):

- Dangling reference: a registration, link, import, or path pointing at something that was deleted.
- Git deletion or rename still grepped live: history removed or renamed X, and grep still finds the old form.
- Version-duplicate or deprecation marker: `foo_old`, `v2`, commented-out blocks, 旧 / deprecated / `TODO(remove)`.
- Ledger-staleness signature: STATUS older than the latest decision; a completed item still in TODO Active; a decision reversed by a later one whose artifact still exists.

Governance mask (apply before deciding which side is the old one; the repo's four-role docs):

- `archive/` is out of scope — frozen-old by design.
- A decisions entry is never a deletion target — the ledger is append-only; the residue is the artifact an old decision produced (old code or file), not the entry text.
- A stale STATUS is rewritten to current, never deleted.
- A completed-but-Active TODO item moves to decisions; a Deferred item with no unblock trigger is surfaced as a governance smell.

Four-way classification (every candidate gets one before any action):

- delete — no current use and no preserved value.
- rewrite — a current-snapshot doc (STATUS, README) describing an old world: update it to current.
- redirect — a live reference to a renamed or moved target: re-point it to the new side.
- preserve — old but load-bearing: a compat alias, migration shim, old API / CLI / env name, negative or regression test, golden file or fixture, changelog, or anything an external consumer reads. Never auto-delete these.

Truth-oracle gate (decide which side is current; runs parallel to deadcode's reachability proof):

- Name the concrete new side that superseded the candidate. If none can be named, it is not supersession residue — leave it, or hand a pure orphan to Phase C.
- Confirm the new side is current via executed / entrypoint-reachable code (strongest for behavior), the latest decisions entry, or the session diff and context.
- Warm path: when the session's own diff or context shows the candidate was just superseded, act without waiting for full oracle agreement — but only on a candidate that already survived the four-way classification, so preserve / redirect / rewrite are carved out first. A live consumer still present means incomplete removal (breakage), not residue: surface it, do not clean it.
- Cold path (old accumulated residue, no session signal): act only when the new side is named, a strong oracle confirms it current, no oracle contradicts, and the governance mask passed. Otherwise present, do not act.
- Invariant: never remove anything an oracle proves is currently load-bearing, however old it looks. An oracle conflict (code does B, the latest decision says A) is itself a finding — surface it, do not auto-resolve.

Live use is wider than AST references: string literals, prompt and markdown mentions, glob or convention-based loading, shell / CI / manifest paths, and cross-repo use all count. Failing to prove use is not proof of residue.

## Gates (always on)

- Safety commit before any deletion.
- Tool output is a candidate list; the final call is your own grep plus reading the file.
- Confidence gate: act only on the unambiguous; everything else is presented, not done.
- The four-way classification precedes every action, and preserve-guards are never auto-deleted.
- The governance mask holds on every doc or ledger touch.

## Decisions ledger

Append to decisions only when an action carried a real judgment with a reason ("removed the X residue, safe because Y"). Mechanical removals live in the commit message and the run report, not the ledger — this keeps the ADR ledger dense enough to stay usable as a truth oracle. Route an entry to its topic file, cross-cutting when unsure.

## Report

Group by outcome: removed, rewritten, redirected, preserved, breakage (incomplete migration), present-only (ambiguous or cold), governance-smell, deferred. Include the safety-commit SHA and the revert command.
