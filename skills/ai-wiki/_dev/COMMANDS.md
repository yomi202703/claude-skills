# Latent commands (not in default SKILL.md surface)

These exist in `scripts/dispatcher.py` but have shown zero or vestigial usage in `~/ai-wiki/log.md` over recent practice (as of 2026-05-14). Kept in code, demoted from the loaded SKILL.md context. Promote back when usage resumes.

## `ingest <arxiv:XXXX.XXXXX | path.md>`
Save source to `sources/`. Two paths:
- **arxiv**: used once (2026-04-20, batch of 19 from ai-digest); none of the 19 became narratives and all were later deleted. Dead path.
- **md_path**: occasionally invoked by Claude as a prelude to `narrative-draft`. Not user-facing; the narrative-draft workflow can take an arbitrary md path directly without ingest.

## `status`
Vault summary JSON (counts of narratives / sources / notes).
```
dispatcher.py status
```

## `pillars [--top-n N]`
Rank `[[slug]]` targets by backlink density across narratives. Originally meant to surface "high-traffic concept hubs" worth deepening.

## `narrative-split <slug> --section <H2>`
Split a bloating narrative into a sibling tree at the named H2 boundary. Use when a narrative grows beyond comfortable single-spine reading.

## `coverage-narrative <slug> --source <md>`
QuestEval-style gap report against a source markdown. Auto-runs inside `narrative-draft`; standalone invocation only needed when re-checking an already-drafted narrative against a revised source.

## `note-from-chat <export.md> --study <slug> [--apply-anchor]`
Claude desktop/web chat export → `notes/<slug>.md` with frontmatter `study:`. Heuristic detects chat-export shape (UI markers, broken LaTeX); use `--no-detect-check` to force on clean markdown. With `--apply-anchor`, LLM proposes which H2 in `narratives/<study>.md` the note belongs under and patches the wikilink in.

Asking pattern: dispatcher requires `--study`; ask the user "this dialogue was for which study?" before invoking.

Why latent: in practice, notes get written directly in conversation rather than imported from external chat exports.

## `note-rewire [--study <slug>] [--apply]`
Scans `notes/` for entries with frontmatter `study: <name>`, asks the LLM to propose anchor H2 sections in the matching narrative, and (with `--apply`) patches the wikilink. Default dry-run.

Use case: a narrative gets built after notes for that study already exist standalone.

## `pipeline [--arxiv arxiv:X ...]`
Convenience wrapper: ingest (optional) → lint → narratives. Returns `stages`, `stages_run`, `stages_ok`, `fatal_error`. Useful for batch automation but unused in interactive practice.

---

# Ad-hoc workflows seen in logs but not in dispatcher

- `exercise_gen` / `exercise_check` — 2026-05-05, one session, output in `~/ai-wiki/exercises/`. Hand-rolled via `llm.py` from conversation, not promoted to a dispatcher command. Treat as experiment, not infrastructure.
