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
├── narratives/<slug>.md      # primary content (declarative: what / why)
├── narratives/_index.md      # auto-generated forest index
├── sources/<src>.md          # immutable originals (arxiv or user md)
├── derivations/<slug>.md     # procedural: subgoal-labeled derivation spines (lazy)
├── derivations/_index.md     # auto-generated, grouped by anchor narrative
├── derivations/_targets/<src>.md  # derivation-scan manifests (台帳)
├── notes/<slug>.md           # friction-driven, user-curated (lazy-created)
├── index.md                  # auto-generated stats + dead links
├── log.md                    # append-only operation history
└── manifest.json             # source delta tracking
```

## Active commands

Invoke via `python3 ~/.claude/skills/ai-wiki/scripts/dispatcher.py <cmd> [args]`. JSON to stdout. All accept `--vault PATH` (default `$AI_WIKI_ROOT` or `~/ai-wiki`).

| Command | Purpose |
|---|---|
| `narrative-draft <source.md> --slug <s> [--title <t>] [--no-coverage] [--no-holdout] [--mode peer] [--faithfulness] [--judge-model M] [--dry-run]` | LLM: source md → narrative tree (size-adaptive, coverage QA on by default). Auto-normalizes flattened `#` headings (e.g. MinerU PDF output) and drops back-matter (References/Acknowledgements/…). **Pre-flight (cheap, no-LLM): every run attaches a `preflight` block + warnings flagging duplicated heading titles, off-topic tangent sections (余談/コメント返し/次回予告/中休み…), and `in_scope_ratio`. Tangents are kept, not auto-dropped — `--dry-run` runs ONLY the pre-flight (zero cost) so you can confirm/trim a noisy source before paying for generation.** Coverage QA is scoped to skip questions whose answer is a bare citation / proper-noun (author / 文献 / 発行年) — the working-hypothesis tree deliberately omits those, so asking would impose a structural coverage ceiling. **Coverage judging runs on a *different* model from the opus generator (`--judge-model`, default sonnet)** — dodges self-preference bias / reward hacking when a model grades its own output; generation + gap-fix stay on opus. **Hold-out: after the fix loop converges, coverage is re-measured on a fresh independent QA set (`holdout_coverage_pct`) the fixer never optimized against — the honest out-of-sample number vs the optimized in-sample `coverage_pct`; `--no-holdout` skips it.** **Source archival: after a successful draft, the source `.md` is stored idempotently under `sources/` (`source_ingested` in the result) as the immutable verify-against truth (hard rule #3) — matched by absolute path, so re-running never duplicates it; `--no-ingest-source` opts out.** `--mode peer`: one independent peer tree per major section, no master hub — for multi-section papers whose chapters are separate topics. `--faithfulness`: after commit, judge each tree's atomic claims against its source (precision direction, complements coverage's recall) — reports fact-precision (hallucination signal) + synthesized spine edges to `.narrative-faithfulness/`; diagnostic only, judged by a different model (shares `--judge-model`) to avoid self-preference bias. |
| `narratives` | Validate narratives/, regenerate `_index.md` |
| `lint` | Dead-link report + regenerate `index.md` |
| `card-draft <slug> [--model <m>]` | LLM: symbol-walk the tree → exhaustive atomic Q-A deck `cards/<slug>.tsv` (Anki-importable). Primary deck builder. |
| `card-add --slug <s> --front <q> --back <a>` | Append one extra card by hand (rare — only for synthesis the tree lacks) |
| `cards [<slug>]` | Dump deck(s) as JSON (one deck per narrative, or all) |
| `derivation-scan <source.md> [--anchor <n>]` | Source → **derivation target manifest** (`_targets/<src>.md`). Deterministic skip-marker sweep + LLM enumerates stated results worth deriving. Sets scope **even when the source omits the derivation**: a result is a target whether or not its steps are present; skip markers ("略"/"面倒"/"補足参照"/"left as an exercise") flag the hard, high-value ones the source dodged. Routes each into a tier; commits nothing (curate, then draft). |
| `derivation-draft <source.md> --slug <s> --goal <g> [--anchor <n>] [--judge-model M] [--no-verify]` | Source(+anchor)+goal → **subgoal-labeled spine** (`derivations/<slug>.md`). Generator (opus) drafts `[⇣n]` steps from the **source** (the algebra's source of truth); anchor narrative supplies only the subgoal *structure*. Then a **different** judge model (sonnet) verifies each step against the source — confirmed→verified, unconfirmable→`[~]` + verified=false. Same self-preference-bias avoidance as coverage/faithfulness. |
| `derivations` | Validate derivations/, regenerate `_index.md` |

## Cards & recall drill

Two distinct jobs — keep them separate:

- **Cards = the durable memorization asset.** `card-draft <slug>` walks the tree's bracketed symbols and turns **every** node into one or more atomic Q-A cards (symbol fixes the question type; uncovered nodes are reported, never dropped). Full spec lives in `scripts/prompts/card_draft.md`. Output `cards/<slug>.tsv` is Anki-importable; memory forms in the SRS, not here.
- **The drill (this chat) = a check + a pointer**, conducted by you, not by a script. When the user asks to be drilled/quizzed, **first read `reference/recall-drill.md`**, then run the one-question-at-a-time loop it describes.

## Derivation layer (procedural knowledge)

Narratives + cards train **declarative** knowledge (what / why); they do not train **procedural** knowledge — reproducing a derivation, taking an FOC, computing an estimate. Atomic Q-A cards even *can't*: a derivation is an ordered transform, and atomizing it kills the chain (and the transfer). The derivation layer fills this gap.

- **A derivation = a subgoal-labeled spine.** `derivations/<slug>.md` holds an ordered `[⇣n]` step chain from a GOAL to its result, each step tagged with an abstract subgoal label (subgoal labeling lowers cognitive load and transfers to new problems).
- **Provenance is asymmetric with cards.** Cards are built *from the tree* (the tree has everything they need). Derivations are built *from the **source*** — the tree's 1-3-sentence nodes don't contain the algebra, so building a spine from the tree would hallucinate steps. The narrative is used only as the **anchor** (wikilink) and the subgoal *structure*. Source stays the single source of truth (hard rule #3) and the verification target.
- **The source need not contain the derivation.** `derivation-scan` separates *target setting* (always possible from stated results) from *step acquisition* (tiered). Three tiers, by where the steps come from / confidence:
  - **T1 harvest** — full steps present in the source → safe, verified, high.
  - **cross** — steps live in another source ("see Hansen / 補足参照 / ○章参照") → fetch from there.
  - **gen** — source skipped it ("略"/"面倒"/"演習"); LLM-generates, judge-verifies; unconfirmable steps marked `[~]`, verified=false. These skip-markers are the *signal* for the hardest, most valuable targets.
- **Generation never grades the learner.** The judge verifies the *math*, not the user. The faded drill (procedural mode of `reference/recall-drill.md`) surfaces what the user can't yet reproduce only to adjust scaffolding — never as a verdict (hard rule #2).

### derivation spine format

Enforced by `scripts/derivation.py`. Contract:
- **Frontmatter (required)**: `type` (=derivation), `slug`, `title`, `anchor` (→narrative slug), `source` (→source slug), `tier` (`T1|cross|gen`), `verified` (bool), `created`, `updated`
- **Sections**: `## GOAL` (the target expression) + `## SPINE` (the step chain), both required
- **Step marker `[⇣n]`**: numbered subgoal steps, validated **contiguous 1..N in order** (the chain must not be broken). Line shape: `[⇣n] <subgoal label> → <step content>`
- **`[~]`** trailing a step = unverified (source-skipped, judge-unconfirmed); a `verified=true` spine must carry none.

Run `dispatcher.py derivations` after editing to validate.

## narrative tree format

Enforced by `scripts/narrative.py`. Contract:

- **Frontmatter (required)**: `type`, `slug`, `title`, `status` (`pilot|stable|frozen`), `created`, `updated`
- **Sections**: `## ROOT` required; `## 記法` (legend) recommended
- **Bracketed symbols (fixed set)**: `[?] [??] [★] [◯] [✕] [∥] [⛔] [!] [∴] [⤴] [⤵] [⟳] [↺] [⊂] [⊕] [~]` — any other `[<sym>]` token fails validation. `[~]` = model-inferred link (edge the LLM synthesized that the source doesn't state explicitly; marks provenance, not confidence — surfaced by `--faithfulness`).
- **Inline edge markers**: `→`, `⇒` only
- **Body style**: 1–3 sentences per node, problem-driven edges, direct readability
- **Forest peer**: no cross-tree hierarchy; connect via `[[slug]]` wikilinks

Run `dispatcher.py narratives` after editing to validate.
