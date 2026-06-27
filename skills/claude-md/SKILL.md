---
name: claude-md
description: Scaffold and maintain a repo's memory — its CLAUDE.md, its working-doc governance (TODO / STATUS / decisions / archive), and its directory map. A method, not a generator: it guides authoring/reviewing, it does not blast out boilerplate. Covers the global-vs-repo split, what belongs where, and the hygiene that keeps it high-signal. Use when the user wants to create/review/improve a CLAUDE.md, set up a repo's working docs, or scaffold a project's memory; or says "/claude-md". Composed by judge-loop's Scaffold step.
---

Set up and maintain a repo's memory layer. Three responsibilities, all method-not-boilerplate: (1) the CLAUDE.md, (2) the working-doc governance, (3) the directory map. The user owns every result — propose and let them edit, never overwrite without a diff. Output style: no `**` emphasis, `#`/`-` structure only.

## 1. CLAUDE.md — two layers, do not duplicate
- Global `~/.claude/CLAUDE.md`: cross-repo constants (output style, doc governance, prompt rules, do-it-yourself bias). Loads everywhere. Assume it is already loaded.
- Repo `CLAUDE.md`: only what is specific to this repo. Do not repeat global rules; if a repo rule overrides a global one, say so explicitly.
- Belongs in the repo file: build/test/run commands that work here; the directory map (where the real work is, what to ignore); local conventions a newcomer gets wrong (new logic goes in X not Y); non-obvious gotchas (required env, generated files, things that look editable but are not).
- Keep out: anything in the global file; dated progress / "we recently did X" (→ commits or decisions); long rationale (one line of why is fine); restating the README or code.

## 2. Working-doc governance — scaffold the four roles (per global CLAUDE.md; do not redefine them here)
Create them under the repo's chosen docs dir (akatsuki: `成果物/`). Do not duplicate the governance definitions that live in global CLAUDE.md — enact them.
- TODO.md — future queue, single source of what's next. Two states: Active (P0–P2) / Deferred (each names its unblock trigger). One line per item; rationale lives in decisions. Delete when done. Adopt it aggressively from day 1.
- STATUS.md — current snapshot, rewritten each session, short.
- decisions/ — append-only ADR ledger; split by topic once large (one file per module + a cross-cutting bucket + a README index). Never rewrite past entries.
- archive/ — frozen history, reference only.
Completed work moves TODO → decisions (not left checked-off). "Won't do" is recorded in decisions only and removed from TODO.

## 3. Directory map + .gitignore
- Author the repo's directory map into CLAUDE.md so a fresh session knows where the real work happens and what to ignore.
- Own the `.gitignore`: secrets and data never get committed (`.env`, raw data dirs, per-unit outputs, snapshots, answer DBs). Commit a `.env.example` template instead of `.env`.
- When the repo is a judge-loop project, the canonical tree is judge-loop's Scaffold output (sources / per-axis modules / single contract source / tiered GT store / outputs / review_server / eval harness / docs). This skill owns only the memory layer (CLAUDE.md + governance docs); judge-loop owns the judgment-specific tree. Reflect that tree in the map; do not reinvent it.

## How to do it
1. Explore the repo first: build config, entry points, key files, existing CLAUDE.md and docs. Do not write from assumptions.
2. Draft only the repo-specific layer, in the user's voice, concise.
3. For each line ask: does this change what the next session does? If not, cut it.
4. Propose; show the diff for anything existing; let the user edit.

## Hygiene over time
Memory rots by accretion. When reviewing: delete stale commands, fold duplicates, move history into decisions/archive, cut lines that no longer change behavior. Shorter and current beats long and comprehensive.

## Composition
- Invoked by judge-loop's Scaffold step (day 1) to stand up CLAUDE.md + governance docs alongside the judgment tree.
- Governance definitions are owned by global CLAUDE.md; this skill enacts them, never restates them.
