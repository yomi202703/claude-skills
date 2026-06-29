---
name: task-handoff
description: Issue a self-contained task contract that lets a separate full-fidelity main session pick up an independent work stream with zero context loss — main-to-main handoff over files, not lossy subagent summaries. Use at a branch point when fanning work out to parallel sessions that may restart cold weeks later, or when judge-loop routes from its branch phase.
---

The core belief: mains communicate by files, not summaries. A subagent returns a lossy summary; an independent main reads the same files you read and runs at full fidelity. This is the correct resolution of the global "do it yourself / don't trust summaries" bias when work must fan out.

## Premise (do this before anything else)
- Run grill-me first. Do not branch until grill-me has settled three things at the branch point: the integration target (what this stream will eventually rejoin), the integration trigger (the concrete condition that fires reunification + what the PM does then), and the shared output schema (what the PM will measure the returned work against). Branching before these are fixed produces streams that can't be rejoined — that is the failure this skill exists to prevent.
- Independent ≠ throwaway. A handed-off stream is "independent but eventually integrated." The contract is what carries the eventually.

## Owns three things (and nothing more)
- The branch-point handoff contract: the field set and how to write each field.
- The per-task micro-directory shape (the scaffold one independent task gets).
- The registry of issued independent tasks — one sheet.

## Delegates three things (reuse, never redefine)
- The four-role doc governance (TODO / STATUS / decisions / archive) → global CLAUDE.md. Enact it inside a task dir; do not restate the definitions.
- The project macro layer (whole-project orientation map + memory) → claude-md.
- Judgment-loop phase progression and gates → judge-loop. This skill is a sub-skill routed from a branch phase; it does not own phases.

## Standing principles
- PM is a place, not a session. The PM's reality is a directory (the project macro layer claude-md stands up — 成果物/), not a conversation. Any session that opens it weeks later recovers the whole picture. Do not create a third memory layer.
- The machine contract is not the human view. The task dir's files are written for a cold main to execute from. The human-facing retrospective — how a stream got where it is, and how it now works — is throughline's output (view≠truth); it is not duplicated into the contract.
- Validity ≠ consistency. When work returns, the PM makes an owner-level whole judgment of validity (including re-design — "these two streams should merge"). Version-stamp drift-checking is one input to that judgment, not its first gate, not its essence.
- Reunification is human-driven. An independent stream does not auto-report-back to a parent. It records completion as a status row in the registry; a human opens the PM directory and collects uncollected-done tasks. A stream may run alone for a week. Every task dir must be fully persistent and cold-restartable with zero conversation memory.
- Dispatch is optional and additive. A stream may be eagerly launched into its own full-fidelity session at branch time (e.g. a Tabby tab running `claude` with the task dir's TASK.md baked as the opening prompt — argv, not keystroke injection) instead of waiting for a cold open. This only accelerates the "parallel now" regime; the file contract stays the source of truth and reunification stays human-driven. See `_dev/decisions.md` (2026-06-27) for the mechanism and why it is layered on top, never a replacement.

## The handoff contract (fields)
The contract is the one file an independent session reads to start cold. It carries exactly these fields. This skill's own issuing TASK.md is the live example of each:
- read list — every file to read before starting, foundation first. The contract assumes no conversation memory; the read list is the context.
- do — what to produce, concretely.
- output path — where the deliverable lands (outside the task dir).
- shared output schema — the structure the PM measures returned work against. For a document deliverable, a section-composition list is the minimum viable schema; for a code/data deliverable, specify the interface/contract level. Plus any global constraints (e.g. output style).
- integration trigger — the condition that fires reunification AND what the PM does when it fires (validity judgment → routing → ledger entry).
- foundation version stamp — a string naming the base snapshot the task was branched from (e.g. `design-2026-06-23`). A string suffices when the foundation is frozen at branch time; escalate to a content hash / commit only if the foundation can drift under the running task.

## Micro task-directory shape
One directory per independent task, fully self-contained. Two files are task-handoff's own (foundation.md, TASK.md); the working docs beside them are the global four-role set enacted at task scope — same role names (decisions / STATUS / TODO / archive), same rules, not redefined here.
- foundation.md — the shared base snapshot. The single source of pre-context. Kept separate from TASK.md because one branch point can fan out to several sibling tasks that share one foundation; the foundation is the reusable part, TASK.md the per-task part. (For a lone task they may be merged — separation is a fan-out affordance, not a rule.) Read first; carries the version stamp.
- TASK.md — the self-contained contract (fields above).
- decisions.md — the task's `decisions` ledger. Seeded at issue time with the founding rationale — seeding it is part of this skill's job (dogfooded by hand until skilled); append-only thereafter.
- STATUS.md — optional, the `STATUS` role: where execution stands right now. Omit for a one-shot task; add it once the stream runs long enough that a cold restart needs a "where am I" snapshot before resuming.
- TODO.md — optional, the `TODO` role: omit for a single-deliverable task (TASK.md's `do` is the queue); add it when the task is multi-step and long-running enough that "what's next" needs its own sheet.
- output path — the deliverable itself, which lives elsewhere (not inside the task dir).

## PM registry shape
One sheet, in the macro layer (成果物/), listing issued independent tasks so the human can find uncollected-done ones. One row per task:
- task name · output path · foundation version stamp · shared output schema · integration trigger · state.
- state values: 発行済み（走行中） / 完了・未回収 / 回収済み.
The only two things this skill adds to the macro layer are this registry and the routing of each returned task's validity verdict into decisions. Nothing else.