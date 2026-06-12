---
name: claude-md
description: Teaches how to write a great CLAUDE.md — what belongs in it, the global-vs-repo split, and the hygiene that keeps it high-signal. This is a method, not a generator: it guides authoring or reviewing a CLAUDE.md, it does not emit a boilerplate file. Use when the user wants help creating, reviewing, or improving a CLAUDE.md / project memory file, or says "/claude-md".
---

This skill is a method for writing a good CLAUDE.md. Apply the principles and guide the work. Do not blast out a templated file; the user owns the result.

## What a CLAUDE.md is for

It is the context a fresh session needs to work in this repo without re-deriving it: how to build / test / run, where things live, and the local conventions that are not obvious from the code. It is read every session, so every line costs context. Include only what changes what the next session does. Leave out what the model can discover quickly by itself.

## Two layers — do not duplicate

- Global `~/.claude/CLAUDE.md` holds cross-repo constants (output style, doc governance, prompt-authoring rules, do-it-yourself bias). It loads in every repo.
- The repo `CLAUDE.md` holds only what is specific to this repo. Do not repeat the global rules; assume they are already loaded. If a repo rule conflicts with a global one, state the override explicitly.

## What belongs in the repo file

- Build / test / run commands that actually work here.
- The directory map: where the real work happens, what to ignore.
- Local conventions and constraints a newcomer would get wrong (for example: new logic goes in X, not Y).
- Non-obvious gotchas: required env, generated files, things that look editable but are not.

## What to keep out

- Anything already in the global file.
- Change history, dated progress notes, "we recently did X". That belongs in commits or a decisions ledger, not here.
- Long rationale and design essays. One line of why is fine; a paragraph is drift.
- Restating what the code or README already says clearly.

## How to do it

1. Explore the repo yourself first: read the build config, entry points, a few key files, and the existing CLAUDE.md if any. Do not write from assumptions.
2. Draft only the repo-specific layer, in the user's voice, concise, no `**` emphasis — `#`/`-` structure only.
3. For each line ask: does this change what the next session does? If not, cut it.
4. Propose the draft and let the user edit. Do not overwrite an existing CLAUDE.md without showing the diff.

## Hygiene over time

A CLAUDE.md rots by accretion. When reviewing one: delete stale commands, fold duplicates, move history out, and cut lines that no longer change behavior. Shorter and current beats long and comprehensive.
