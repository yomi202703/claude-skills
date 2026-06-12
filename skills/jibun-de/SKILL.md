---
name: jibun-de
description: A mode where you read the target in full in your own context and reason to a conclusion yourself. Forbids delegating to subagents and forbids concluding from deterministic tools (grep etc.) alone. Use when the user says "do it yourself", "no subagents", "don't just grep it", "don't cut corners", "/jibun-de", or the Japanese equivalents (自分でやって, サブエージェント禁止, grepで済ませるな, 手を抜くな).
---

This task is handled to the end in your own context, with no delegation and no shortcuts.

For the rest of this session, hold the following:

## Do not delegate

- Do not launch subagents (Agent / Explore / Task family). Do the searching, reading, and judging yourself.
- Reason: a subagent's return value is a summary, and a summary drops information. Do not judge on top of what was dropped.
- When you want to parallelize, read in sequence yourself instead. Prefer touching the primary source over speed.

## Do not conclude from grep

- Use grep / find and other deterministic tools only to locate where the target is.
- Once they hit, open the file containing that spot with Read and read it before concluding. Do not make a grep line snippet your basis.
- A line-level hit has thrown away the surrounding context. Do not judge "present / absent" or "right / wrong" without reading that context.

## Read in full by default

- Read the file you are judging in full, not partially. If it is too long to read at once, split it and read all of it.
- Do not skip on "it's probably like this". Confirm what can be confirmed before writing it.

## Leave your reasoning in your own words

- Explain what you read as the path you actually traced. Do not transcribe someone else's summary.
- State uncertain points as uncertain. Do not write the unconfirmed as if confirmed.

This mode continues until the user explicitly clears it or the task is complete.
