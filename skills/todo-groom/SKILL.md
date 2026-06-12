---
name: todo-groom
description: Read a project's TODO/STATUS/decisions docs yourself and groom them autonomously — merge duplicates, fix priority order, archive completed items, strip redundancy. Inherits the jibun-de stance (no delegation, no grep-only conclusions, read in full).
---

This task grooms a documentation set by hand, end to end. No delegation, no shortcuts. Do not stop to ask for confirmation. But never drop information.

Inherit jibun-de: do not launch subagents (Agent/Explore/Task). Use grep/find only to locate where something is; once it hits, open the file with Read and read the surrounding text before concluding. Read the docs you judge in full. Confirm facts before writing them.

## 1. Read the governance contract first

Do not assume which file does what. Read the contract before editing:

- Read CLAUDE.md (or the docs convention, e.g. under a 成果物/ directory) to learn each file's role, volatility, and rule. The typical four layers:
  - TODO (future / execution queue) = single source of truth. Remove items when done. Keep no completion history and no rationale here.
  - STATUS (one-screen snapshot) = rewritten each session. Often has a line cap (e.g. <= 60 lines).
  - decisions (append-only ADR ledger) = immutable, append at the end. Records why and what happened.
  - archive / summary_log (history) = frozen. Do not touch.
- If no convention is found, infer roles from filenames and openings, state that it is an inference, then proceed.

## 2. Read everything yourself, in full

- TODO in full. STATUS in full.
- decisions is usually large. Use grep to locate the heading matching a completion claim, then open and read that ADR's body with Read. Do not treat a grep line snippet as proof that something is recorded.
- Do not skip on "probably done". Verify completion by reading the decisions body.

## 3. Diagnose each TODO item in your own words

Classify every item along these axes (more than one may apply):

- Done, recorded in decisions -> archive target (delete from TODO).
- Done, not in decisions -> append an ADR to decisions first, then delete from TODO (lose nothing).
- Done and not-done living together -> remove the done part, split out only the open work as atomic tasks.
- Duplicate / one topic scattered (same rule_id or same target in several places) -> consolidate into the one live entry, delete the rest. Read the bodies to decide which is current.
- Priority violation (an item you yourself marked as blocked on "X must finish first" sitting in P0) -> keep in P0 only what can be started now; demote dependency-blocked items to P1 or lower.
- Redundancy (rationale, numbers, "(decisions <date>)" leaking into TODO) -> move rationale to decisions and live numbers to STATUS; reduce the TODO line to the next action only.
- Stale or unnecessary (the step-back lens) -> for each still-open item, try to state its goal in one sentence and ask whether it is needed now. If the goal cannot be stated, or the item is superseded, or it would be better dropped / deferred / done smaller, do not silently delete it (that is a meaning change, not a structure change). Demote it (e.g. to P2/P3) and flag it as a drop / defer candidate with the reason. Deletion stays reserved for items verifiably done in decisions.
- Owner-ruling matter -> do not delete. Keep the task and attach a recommended answer.

## 4. Apply (autonomous, with irreversibility guards)

Do not stop and wait for a human. Hold these invariants instead:

- Delete only after confirming the record. Remove an item from TODO only when its completion is readable in decisions. If it is not readable, move it to decisions first. A grep hit alone is not enough.
- decisions and archive are append-only. Do not rewrite or reorder past entries.
- STATUS holds the current state only. If it exceeds its line cap, move the oldest "recent activity" entries to archive and keep the cap.
- If you provisionally settle an owner-ruling item while running autonomously, append an ADR to decisions marked as a skill-provisional call, and leave a note on the TODO side that it is provisional. Keep it reversible by a human later.
- Default to changing structure, not meaning. Do not silently add or drop claims, open work, or counts.

## 5. Report what you did

When grooming is done, lay out the path you took:

- Items archived (deleted) and their basis in decisions.
- Duplicates merged, and where they were consolidated.
- Priorities demoted or promoted, and the dependencies behind it.
- Redundancy moved out to decisions / STATUS.
- Stale / unnecessary items flagged as drop or defer candidates, each with the reason.
- Remaining owner-ruling items, each with its recommended answer.

State uncertainty as uncertainty. Do not write the unverified as if verified.

This mode continues until the user clears it or the grooming is complete.
