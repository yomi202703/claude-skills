---
name: ai-wiki
description: Personal study vault (`~/ai-wiki/`) for learning from educational sources via problem-driven narrative trees. Invoke when the user wants to draft a narrative from a source md (textbook chapter, lecture notes, arxiv paper), run coverage gap analysis against a source, or maintain the vault index.
---

# ai-wiki (v5)

## Hard rules

1. **User reads narrative trees only.** Do not file-ize concept definitions; only create `notes/<slug>.md` when the user explicitly externalizes a frustration point.
2. **Never score the user's recall.** Retrieval practice is never adjudicated.
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
| `narrative-draft <source.md> --slug <s> [--title <t>] [--no-coverage]` | LLM: source md → narrative tree (size-adaptive, coverage QA on by default) |
| `narratives` | Validate narratives/, regenerate `_index.md` |
| `lint` | Dead-link report + regenerate `index.md` |

## narrative tree format

Enforced by `scripts/narrative.py`. Contract:

- **Frontmatter (required)**: `type`, `slug`, `title`, `status` (`pilot|stable|frozen`), `created`, `updated`
- **Sections**: `## ROOT` required; `## 記法` (legend) recommended
- **Bracketed symbols (fixed set)**: `[?] [??] [★] [◯] [✕] [∥] [⛔] [!] [∴] [⤴] [⤵] [⟳] [↺] [⊂] [⊕]` — any other `[<sym>]` token fails validation
- **Inline edge markers**: `→`, `⇒` only
- **Body style**: 1–3 sentences per node, problem-driven edges, direct readability
- **Forest peer**: no cross-tree hierarchy; connect via `[[slug]]` wikilinks

Run `dispatcher.py narratives` after editing to validate.
