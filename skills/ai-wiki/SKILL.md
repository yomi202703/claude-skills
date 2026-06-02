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
| `narrative-draft <source.md> --slug <s> [--title <t>] [--no-coverage] [--no-holdout] [--mode peer] [--faithfulness] [--judge-model M]` | LLM: source md → narrative tree (size-adaptive, coverage QA on by default). Auto-normalizes flattened `#` headings (e.g. MinerU PDF output) and drops back-matter (References/Acknowledgements/…). **Coverage judging runs on a *different* model from the opus generator (`--judge-model`, default sonnet)** — dodges self-preference bias / reward hacking when a model grades its own output; generation + gap-fix stay on opus. **Hold-out: after the fix loop converges, coverage is re-measured on a fresh independent QA set (`holdout_coverage_pct`) the fixer never optimized against — the honest out-of-sample number vs the optimized in-sample `coverage_pct`; `--no-holdout` skips it.** `--mode peer`: one independent peer tree per major section, no master hub — for multi-section papers whose chapters are separate topics. `--faithfulness`: after commit, judge each tree's atomic claims against its source (precision direction, complements coverage's recall) — reports fact-precision (hallucination signal) + synthesized spine edges to `.narrative-faithfulness/`; diagnostic only, judged by a different model (shares `--judge-model`) to avoid self-preference bias. |
| `narratives` | Validate narratives/, regenerate `_index.md` |
| `lint` | Dead-link report + regenerate `index.md` |
| `card-draft <slug> [--model <m>]` | LLM: symbol-walk the tree → exhaustive atomic Q-A deck `cards/<slug>.tsv` (Anki-importable). Primary deck builder. |
| `card-add --slug <s> --front <q> --back <a>` | Append one extra card by hand (rare — only for synthesis the tree lacks) |
| `cards [<slug>]` | Dump deck(s) as JSON (one deck per narrative, or all) |

## Cards & recall drill

Two distinct jobs — keep them separate:

- **Cards = the durable memorization asset.** `card-draft <slug>` walks the tree's bracketed symbols and turns **every** node into one or more atomic Q-A cards (symbol fixes the question type; uncovered nodes are reported, never dropped). Full spec lives in `scripts/prompts/card_draft.md`. Output `cards/<slug>.tsv` is Anki-importable; memory forms in the SRS, not here.
- **The drill (this chat) = a check + a pointer**, conducted by you, not by a script. When the user asks to be drilled/quizzed, **first read `reference/recall-drill.md`**, then run the one-question-at-a-time loop it describes.

## narrative tree format

Enforced by `scripts/narrative.py`. Contract:

- **Frontmatter (required)**: `type`, `slug`, `title`, `status` (`pilot|stable|frozen`), `created`, `updated`
- **Sections**: `## ROOT` required; `## 記法` (legend) recommended
- **Bracketed symbols (fixed set)**: `[?] [??] [★] [◯] [✕] [∥] [⛔] [!] [∴] [⤴] [⤵] [⟳] [↺] [⊂] [⊕] [~]` — any other `[<sym>]` token fails validation. `[~]` = model-inferred link (edge the LLM synthesized that the source doesn't state explicitly; marks provenance, not confidence — surfaced by `--faithfulness`).
- **Inline edge markers**: `→`, `⇒` only
- **Body style**: 1–3 sentences per node, problem-driven edges, direct readability
- **Forest peer**: no cross-tree hierarchy; connect via `[[slug]]` wikilinks

Run `dispatcher.py narratives` after editing to validate.
