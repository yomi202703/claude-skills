---
name: ai-wiki
description: Personal study vault (`~/ai-wiki/`) for learning from educational sources via problem-driven narrative trees. Invoke when the user wants to draft a narrative from a source md (textbook chapter, lecture notes, arxiv paper), run coverage gap analysis against a source, or maintain the vault index.
---

# ai-wiki (v5)

## Hard rules

1. **User reads narrative trees only.** Do not file-ize concept definitions; only create `notes/<slug>.md` when the user explicitly externalizes a frustration point.
2. **Never score the learner.** Retrieval practice is not graded — you do not pass judgment on the person's ability with marks or tallies. In a drill (see "Recall drill"), an answer that fails to cover the source is *not* a verdict on the user; it is only the trigger that fires card capture. Frame everything as "the source says X, your answer didn't reach X yet → here's a card," never as "you got it wrong."
3. **Source is the single source of truth.** `sources/` pages are never overwritten. Re-ingesting the same arxiv ID is a no-op.
4. **Wikilinks are the primary currency.** Unresolved `[[slug]]` renders as Obsidian "unresolved" — acceptable and normal.
5. **narrative tree = working hypothesis.** No citations / confidence tags in tree bodies. User verifies against `sources/` when doubtful.

## Vault layout

```
~/ai-wiki/
├── narratives/<slug>.md      # primary content
├── narratives/_index.md      # auto-generated forest index
├── sources/<src>.md          # immutable originals (arxiv or user md)
├── notes/<slug>.md           # friction-driven, user-curated (lazy-created)
├── index.md                  # auto-generated stats + dead links
├── log.md                    # append-only operation history
└── manifest.json             # source delta tracking
```

## Active commands

Invoke via `python3 ~/.claude/skills/ai-wiki/scripts/dispatcher.py <cmd> [args]`. JSON to stdout. All accept `--vault PATH` (default `$AI_WIKI_ROOT` or `~/ai-wiki`).

| Command | Purpose |
|---|---|
| `narrative-draft <source.md> --slug <s> [--title <t>] [--no-coverage] [--mode peer] [--faithfulness] [--judge-model M]` | LLM: source md → narrative tree (size-adaptive, coverage QA on by default). Auto-normalizes flattened `#` headings (e.g. MinerU PDF output) and drops back-matter (References/Acknowledgements/…). `--mode peer`: one independent peer tree per major section, no master hub — for multi-section papers whose chapters are separate topics. `--faithfulness`: after commit, judge each tree's atomic claims against its source (precision direction, complements coverage's recall) — reports fact-precision (hallucination signal) + synthesized spine edges to `.narrative-faithfulness/`; diagnostic only, judged by a different model (`--judge-model`, default sonnet) to avoid self-preference bias. |
| `narratives` | Validate narratives/, regenerate `_index.md` |
| `lint` | Dead-link report + regenerate `index.md` |
| `card-draft <slug> [--model <m>]` | LLM: symbol-walk the tree → exhaustive atomic Q-A deck `cards/<slug>.tsv` (Anki-importable). Primary deck builder. |
| `card-add --slug <s> --front <q> --back <a>` | Append one extra card by hand (rare — only for synthesis the tree lacks) |
| `cards [<slug>]` | Dump deck(s) as JSON (one deck per narrative, or all) |

## Recall drill & cards

Two distinct jobs — keep them separate, it's the whole point:

- **Cards = the durable memorization asset.** Generated *from the tree*, up
  front, exhaustively. `cards/<slug>.tsv`, Anki-importable.
- **The drill (this chat) = a check + a pointer.** It surfaces what the user
  can't yet retrieve and points them back to the relevant card. It is **not**
  where cards are born, and it is **not** the memorization engine.

Why this split: a single retrieval doesn't consolidate a memory — only
*repeated, spaced* retrieval does (Karpicke & Roediger). One chat can't deliver
the 2nd/3rd/Nth pass on a whole course's worth of items, and cramming them once
just manufactures an illusion of knowing. The scheduler (Anki/FSRS) is what
brings each card back right before forgetting and scales to thousands of items.
So memorization lives in the SRS; the chat's value is diagnosis and the cards'
value is coverage.

### Building the deck — `card-draft` (primary)

`card-draft <slug>` walks the narrative's bracketed symbols
(`[?] [★] [✕] [∴] [⟳] …`) and turns **every** node into one or more atomic
Q-A cards. Coverage is guaranteed *by construction*, not by what came up in a
drill or by which questions seemed interesting — every node is attempted and any
uncovered node is reported, never silently dropped. This is the right way to
populate a deck: run it once per narrative and you have the whole tree as cards.

The symbol fixes the *question type*, so you get term cards and causal cards for
free: `★`→"what solution / why", `✕`→"what was rejected & why", `∴`→"what
follows", and crucially `⟳`→"why does problem A lead to problem B" (the causal
spine). Rich nodes (a "束" of several facts) are split into several atomic cards
— one fact per card, because a multi-part answer is heavy to re-retrieve and
gives fuzzy pass/fail. Q-A form, not cloze (cloze over prose invites
pattern-matching on context instead of genuine retrieval).

### The drill loop — strictly one question, then stop

1. Ask **one** question and halt. Never fabricate or pre-fill the user's answer
   — the entire value is them retrieving unaided. Wait for real input.
2. When they answer, compare it against the narrative. Supply what they missed.
   A miss means *that card isn't yet memorized* → tell them to keep drilling it
   in the SRS. **Do not mint a new card for the miss** — the card already exists
   in the deck (that's the redundancy `card-draft` eliminates). Then next question.
3. Sweep nodes in source order so the check itself has no blind spots; mix term
   recall and causal prompts.

`card-add` stays only for the rare genuinely-novel synthesis that the tree
doesn't contain — not for routine miss-carding. It is append-only with no
node bookkeeping; `--ref` is provenance, never a coverage key.

### Hand-off to spaced repetition

`cards/<slug>.tsv` is a 2-column (Front, Back) Anki text file with header
directives (`#notetype:Basic`, `#deck:<slug>`) so it imports with no field-
mapping fiddling and auto-routes into a per-narrative deck. Tell the user to
import it and drill via SRS — and **not** to "study" by reading the cards as a
list (Q and A both visible = passive rereading, not retrieval); the hidden-back
drill in the SRS is where memory forms. The one real failure mode at scale
is **review backlog / burnout**, so advise pacing new cards (~10–20/day) and
keeping reviews from piling up rather than dumping a whole course in at once.

## narrative tree format

Enforced by `scripts/narrative.py`. Contract:

- **Frontmatter (required)**: `type`, `slug`, `title`, `status` (`pilot|stable|frozen`), `created`, `updated`
- **Sections**: `## ROOT` required; `## 記法` (legend) recommended
- **Bracketed symbols (fixed set)**: `[?] [??] [★] [◯] [✕] [∥] [⛔] [!] [∴] [⤴] [⤵] [⟳] [↺] [⊂] [⊕] [~]` — any other `[<sym>]` token fails validation. `[~]` = model-inferred link (edge the LLM synthesized that the source doesn't state explicitly; marks provenance, not confidence — surfaced by `--faithfulness`).
- **Inline edge markers**: `→`, `⇒` only
- **Body style**: 1–3 sentences per node, problem-driven edges, direct readability
- **Forest peer**: no cross-tree hierarchy; connect via `[[slug]]` wikilinks

Run `dispatcher.py narratives` after editing to validate.
