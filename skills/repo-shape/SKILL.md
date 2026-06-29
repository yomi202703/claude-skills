---
name: repo-shape
description: 散らかった既存リポを安全に AI-native 構造へ寄せ直す(主)＋新規リポに base を最初に敷く(従)スキル。単位非依存層の正準スキーマを単一所有し、ツリーを実際に動かす安全移行手順(branch→git mv→ripple-check パス→テスト→オーナー diff・可逆)を持つ。正準名は紙で凍結せず初回の実リポ走行で結晶化する。claude-md(メモリ層の中身)と aftercare の ripple-check パス(参照追従)へ compose、judge-loop §3.5 の base を単一所有。
---

# repo-shape

Fix an existing repo's mess by safely moving what is there one reversible step at a time, not by redesigning the tree on paper. Also lay the universal base into a new repo. Remedial — reshaping a real mess — is the primary case; do not let this drift into a greenfield scaffolder.

## Scope gate (check before anything else)
- git repo + clean working tree required — the safety model is git-mv + branch + revert. Not a git repo: offer `git init` and stop. Dirty tree: have the owner commit or stash first; never reshape on top of uncommitted work.
- Decide and execute the move; do not author the content of the files moved. CLAUDE.md text, the four-role governance docs, and the secret discipline (.gitignore / .env.example) belong to claude-md — compose it, never duplicate it.
- The owner is the審級. Present every proposed tree and every migration as a diff to ratify before it lands. Never self-approve a move.

## Two entrances
Both start by exploring — mandatory, never propose or lay a tree from assumptions. Read the existing tree, the current CLAUDE.md, the docs, and build config first; you cannot classify a mess or place base slots you have not seen. The settled tree always ends in a claude-md call: repo-shape moves the tree, then hands the result to claude-md to author the memory layer. Running repo-shape gets you claude-md — the owner does not invoke it separately.
- Remedial (primary): a repo with accumulated mess. Explore + classify what is there → propose a target tree → owner ratifies → migrate one category at a time → ripple-check pass → test → next category → once all categories land and the tree is settled, invoke claude-md to author CLAUDE.md + governance docs + the orientation map for the post-move tree.
- Preventive: an empty or day-0 repo. Lay the universal layer directly, no migration. Reserve unit-dependent slots empty → invoke claude-md to author the memory layer into the reserved slots.

## The universal layer (what repo-shape single-owns)
Fix only the unit-independent layer — names that do not depend on what the repo eventually judges or produces, so fixing them early causes no rework (G7 applied to directories). Reserve unit-dependent names as empty slots and defer their shape until the unit settles.

Treat these canonical names as the default the first real run confirms or adjusts, not as frozen law (n=1 origin — akatsuki):
- `CLAUDE.md` — repo memory. Content owned by claude-md.
- `.gitignore` / `.env.example` / `.env` — secret discipline owned by claude-md; ensure the slots exist and are placed.
- the gen/source firewall — the discipline repo-shape adds that claude-md is thin on. A trichotomy by "can I rewrite or regenerate this":
  - immutable inputs — given from outside, never written by code (`_data/raw/`). Touch nothing here.
  - regenerable derivations — produced by code, reproducible, disposable, gitignored (`_data/processed/`, build artifacts, re-runnable machine outputs). Safe to delete; never in git.
  - append-only evidence — produced once by a run or a human and not reproducible: run logs, recorded model outputs compared across versions, human reviews / GT. Never overwrite, never gitignore away. A naive source/generated split silently destroys this class.
  Hand-authored mutable artifacts (prompts, rubric, contract) are source — they live in the source layer, versioned, not in the firewall.
- source layer — the repo's actual logic (`src/`, `scripts/`, or module dirs); name varies. Generated artifacts never co-mingle with it.
- `tests/`
- governance dir (`成果物/` or `docs/`) holding `STATUS.md` / `TODO.md` / `decisions/` / `archive/`; structure owned by claude-md.
- the human-facing view layer — `.lavish/` holds the regenerated flow/logic HTML views; `narrative/` holds the repo-local 5th role (durable, frozen, append-only flow). repo-shape reserves and firewall-classifies the slots; throughline owns the view content, claude-md the governance-doc content. `narrative/` is append-only evidence — versioned, never overwrite, never gitignore. `.lavish/` views are regenerable but committed not gitignored, an intentional exception to the regenerable-is-gitignored default because the view is a durable human surface, not disposable output.

Reserve but defer (unit-dependent): `outputs/<unit>/` and any serving/delivery/carve-out dirs — reserve the name, leave the internal shape until the unit settles.

Do not place these (judgment-specific — judge-loop owns them): `contract/` `factlayer/` `gt/` `spike/` `review_server/` `eval/` `access/`. Fix the base; judge-loop adds its judgment delta on top.

## Safe-move procedure
Per category, in order, never skipping:
1. Confirm clean tree, on a dedicated branch (not the default). One category per step.
2. `git mv` the files — preserves history, reversible. Never delete-and-recreate.
3. Run the ripple-check pass over the moved paths: imports, config, scripts, test fixtures, docs, names, persisted paths must all follow. Hand the moved set to the ripple-check pass (aftercare/reference/ripple-check.md); do not reimplement it.
4. Run the repo's own tests / type-check. Green before the next category.
5. Present the diff; land only on ratify. Any step red → revert the branch.

## Crystallize names by running, not on paper
The discipline (firewall, early-fix / defer-settle, safe-move steps) is repo-independent and solid; the specific canonical names are n=1 and provisional. Run the minimal cycle on a real repo (classify → propose → ratify → migrate one category → ripple-check pass → test pass) and let the names settle against a real tree before treating any as canonical. Do not present the name set as fixed before that run.

## Composition
- claude-md — owns memory-layer content (CLAUDE.md, four-role governance, orientation map) and secret discipline. repo-shape owns the tree-shape schema and calls claude-md for that content. Do not duplicate either single source.
- the ripple-check pass (aftercare/reference/ripple-check.md) — owns reference-following after each move; never reimplement it.
- judge-loop — composes repo-shape as its Scaffold base (§3.5) and adds only the judgment-specific delta. repo-shape stands alone for any repo, judgment or not.
- throughline — owns the human-facing view artifacts (`.lavish/` flow/logic, `narrative/` frozen flow). repo-shape reserves their slots and fixes their firewall class; it never authors the views, and throughline defers slot placement back here.
