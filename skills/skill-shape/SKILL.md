---
name: skill-shape
description: Author and reshape Claude Code skills — the discipline of writing a SKILL.md as a thin, forward instruction to the instance that will execute it, not a README. Kills the bloat: README-voice, dragged-in history and past versions, defensive hedging about irrelevant conflicts and edge cases, and WHY that belongs in maintenance notes. Ecosystem-independent core: the three-audience split (description→router, body→executor, supporting files→on-demand, maintenance→never loaded), the runtime-vs-maintenance directory contract, and a ship gate. Pair with grill-me when you also need to decide whether the skill should exist. Use when creating, reviewing, tightening, or de-bloating a skill or its SKILL.md. Triggers — "/skill-shape".
---

# skill-shape

A SKILL.md is a forward instruction to the model instance that will execute it — not a README about the skill, not a changelog. Its runtime reader is the model, not a human: it reads every token and does not skim, so the body is not written to be scanned. Bloat is the symptom; writing for the wrong reader is the disease.

## Scope
- Shapes one skill: its body, its description, its directory.
- Does not decide whether the skill should exist. Invoke grill-me alongside for that.
- Present the result as a diff; the author ratifies. Do not silently overwrite.

## Write the body for the executor (the core)
The body is read only by the future instance running the skill. Write to it: imperative, forward, only what it acts on. Cut everything else:
- No README-voice. Not a sentence describing the skill from outside — tell the runner what to do.
- No emphasis markers — by any mechanism. `**` bold, italics, all-caps on ordinary words, and decorative 必須/重要 flags are the same thing: salience for a skimming human. The reader reads every token and does not skim, so nothing needs to "stand out"; emphasis adds no instruction. State the rule once, plainly. Keep caps that name things (acronyms, terms the doc defines) and structure that segments (headings, lists, code fences) — those aid parsing; drop typography that only ranks attention.
- No manual hard-wrapping. One paragraph is one line; mid-paragraph line breaks are column-fitting for a human reading raw text in an editor — noise to the model. Let it soft-wrap. (Blank lines between blocks, and breaks between list items, are structure — keep those.)
- No history. No "previously…", "changed from…", no past versions or superseded behavior. That is maintenance material, never the body.
- No defensive hedging. Do not enumerate irrelevant conflicts, collisions, or edge cases that will not occur. State the real path; let a rare case be handled when it actually appears.
- No WHY past a clause. Reasons live in maintenance material; one clause inline at most.
Test each line: does the executor do something different because of it? If not, cut it.

## Three audiences (decides where a line goes)
- description → the router deciding whether to load the skill, from this string alone. Discriminative: what it is, what it is not, concrete triggers. The highest-leverage text in the skill; write it last.
- body → the executor: thin, imperative, forward (above).
- supporting files (scripts/ reference/ templates/) → loaded on demand: code, lookup knowledge, emitted skeletons. Referenced from the body, never inlined.
- maintenance material → never loaded at runtime: design notes, decisions, tests, history. Where WHY and the past go to live.

## Directory
SKILL.md is the only guaranteed-loaded file. Everything else is optional, added by necessity — no empty scaffolding.
- scripts/ only if code runs; reference/ for read-at-runtime knowledge; templates/ for emitted artifacts.
- Keep maintenance material and generated data out of the runtime path and out of version control.
- To change an existing layout, move files reversibly (branch, preserve history, follow every reference, verify) — never delete-and-recreate.

## Ship gate (before done)
- Forward instruction, not README; no history; no defensive conflict-hedging; no emphasis markers; no manual hard-wrapping; WHY ≤ one clause.
- Description is discriminative — names what the skill is not, plus triggers; a stranger instance could route from it alone.
- Only necessary directories; generated data kept out of version control.
- Frontmatter is exactly name + description; name = the kebab-case directory name.

## Boundaries
- Owns a skill's shape, voice, and structure — not the domain content of the skill being built (its scripts/templates), and not whether that skill's logic is correct.
