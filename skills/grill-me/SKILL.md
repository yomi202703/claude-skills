---
name: grill-me
description: Interview the user one question at a time — starting from whether the work should exist at all, then down every branch of the design — until you reach shared understanding. For each question, give your recommended answer; explore the codebase instead of asking whatever you can find out. Use when the user wants to stress-test or get grilled on a plan or design, or when they are stuck / spinning / asking "do we even need this" / say "step back" or "grill me".
---

Do not write code yet. First investigate the current state yourself: read what is being changed, its callers, and the recent decisions / TODO. Reconstruct from facts why this work started. Do not ask what you can find out by exploring; explore instead.

## Gate first: should this work exist at all?

Before grilling the design, settle the root of the tree. Question one at a time, with your recommended answer for each:

1. What is the goal of this work, in one sentence? If you cannot state it, that is the signal to stop.
2. Is this actually needed right now? Name the concrete alternatives: drop it, defer it, or do something smaller.
3. Is the blocker a symptom or the cause? Where does the stuckness actually come from?

If the honest answer is that the work should be dropped, deferred, or done much smaller, stop here and say so. Do not grill the branches of a plan that should not exist. This early exit is the point of the gate.

## Then grill the design

If the work survives the gate, interview me relentlessly about every aspect of the plan until we reach shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one by one.

Ask the questions one at a time. For each, provide your recommended answer. If a question can be answered by exploring the codebase, explore the codebase instead of asking.
