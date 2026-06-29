---
name: aftercare
description: Pre-commit cleanup — the ritual to run when you are about to commit a chunk of work. Enters from git: the staged plus working diff is the seed for every pass. Runs three selectable passes, chosen at start (default all), then verifies — forward-consistency (make everything follow the change), supersession sweep (residue that still points at a world that no longer exists: dangling references, renamed-away names, stale docs/STATUS/TODO, superseded files), and reachability (dead / unreferenced code). Run before a commit to sweep what the work left behind, or pick any one pass on its own. Not for restructuring a repo's tree (that is repo-shape, which uses this skill's consistency pass). Triggers — 残骸を片付けて, 整合性を精査して
---

## What this runs

A thin router for the pre-commit cleanup. Git is the entry: the staged plus working diff (what you are about to commit), with recent commits, is the universal seed — the router derives it once and hands it to each selected pass, so the passes do not re-derive it. All three passes live as reference procedures: reference/ripple-check.md (forward consistency), reference/supersession.md (residue), reference/deadcode/deadcode.md (reachability). Two evidence models for "no longer load-bearing" run here: reachability (nothing references it) and supersession (it points at a world that no longer exists); dangling references are the inverse of orphans, so the two run together but stay distinct.

## Every run

1. Derive the scope from git once: the staged plus working diff plus recent commits. This is the seed handed to every selected pass; the passes do not re-derive it. Live conversation context sharpens candidate-finding but never authorizes a deletion on its own.
2. Offer the three passes as a multi-select (AskUserQuestion, multiSelect), pre-selected all, in canonical order — ripple-check (forward consistency), supersession (residue), deadcode (reachability). If the invocation already named a subset, pre-select that instead.
3. Run only the selected passes in the canonical order of the phases below, handing each the git scope. Verify and report after them, with at most one feedback pass.
4. Enforce the gates throughout. Anything ambiguous is presented, not acted on.
5. Report grouped by outcome category.

## Phases

Run the selected phases in this order; skip any the user deselected.

- Phase A — forward consistency: run the ripple-check pass (reference/ripple-check.md). Make the change's dependents follow the new contract before judging what is residue, since the supersession pass's "is this still load-bearing" check assumes the code is already consistent. Breakage that pass surfaces (changed X, Y still calls the old X) is fixed here. If B runs without A, the load-bearing checks still run but on possibly-inconsistent code.
- Phase B — supersession sweep: run the supersession pass (reference/supersession.md).
- Phase C — reachability mop-up: run the deadcode pass (reference/deadcode/deadcode.md) on the second-order orphans Phase B created by removing residue.
- Phase D — verify and report: run tests / typecheck. Only when both A and C ran and C's deletions introduced a new inconsistency, run the ripple-check pass once more — one feedback pass only, then report whatever remains.

## Gates (always on)

- Safety commit before any deletion.
- Tool output is a candidate list; the final call is your own grep plus reading the file.
- Confidence gate: act only on the unambiguous; everything else is presented, not done.
- Any pass that edits a governance doc follows the four-role rules (the governance mask in reference/supersession.md): decisions append-only, a completed TODO moved not deleted, STATUS rewritten not deleted, archive untouched.

## Decisions ledger

Append to decisions only when an action carried a real judgment with a reason ("removed the X residue, safe because Y"). Mechanical removals live in the commit message and the run report, not the ledger — this keeps the ADR ledger dense enough to stay usable as a truth oracle. Route an entry to its topic file, cross-cutting when unsure.

## Report

Group by outcome: removed, rewritten, redirected, preserved, breakage (incomplete migration), present-only (ambiguous or cold), governance-smell, deferred. Include the safety-commit SHA and the revert command.
