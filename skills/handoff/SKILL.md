---
name: handoff
description: Hand a work stream to a separate main session that picks it up cold from files — main-to-main over files, not a lossy subagent summary you relay back. Use at a branch point when offloading work to a parallel session that may restart cold weeks later and must rejoin. Not for a quick delegated sub-task (use a subagent); not for the human-facing retrospective (use throughline).
---

When you offload a work stream to a separate main session, communicate by files it reads cold — not a summary you relay back. Two acts.

## Author foundation.md
Write the branch-point context that exists only in this conversation and has no file to point at: what is assumed, what was decided and why, the shape of the work. The separate main starts with zero conversation memory, so this authored file is the context it would otherwise lose. Point at existing files for everything they already hold — a design doc, the parent's decisions, specific sources — and author only what no file holds. Before adding a line, check whether an existing file already says it; if so, point, do not copy. Copy pre-context into the task dir and add a version-stamp string only when it would otherwise drift under the running stream. Put `do` and `output path` as one line each at the top of the stream's own TODO.md.

## Leave a Deferred join-item in your TODO
One line in your own TODO.md, so the stream is rejoinable. It is a join, not a linear blocker: its unblock trigger is "all of {the streams I branched} done", it points at each stream's dir where completion is recorded, and its fired-action is the owner-level validity judgment — collect the returned work, judge its whole validity (re-design included), route the verdict into decisions. It surfaces on its own because session-start governance reads TODO every session; checking whether the trigger fired is reading each stream dir's STATUS. Add a thin registry index only when fan-out is wide enough that re-reading N stream dirs each session is wasteful.

## Delegated
Use the four-role doc governance (TODO/STATUS/decisions/archive) for the task dir as-is → CLAUDE.md; the task dir is that set at task scope. Run grill-me before authoring when the reconvergence is non-trivial, to fix what the join measures. Keep the human-facing retrospective out of foundation.md — that is throughline's output (view ≠ truth).

## Dispatch (optional)
A stream may be launched eagerly into its own session at branch time (a Tabby tab running `claude` with foundation.md baked as the opening prompt) instead of waiting for a cold open; the files stay the source of truth. Mechanism: `_dev/decisions.md` 2026-06-27.
