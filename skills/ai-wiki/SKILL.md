---
name: ai-wiki
description: Personal study vault (`~/ai-wiki/`) for learning from educational sources via problem-driven narrative trees. Invoke when the user wants to draft a narrative from a source md (textbook chapter, lecture notes, arxiv paper), run coverage gap analysis against a source, or maintain the vault index.
---

# ai-wiki

## Hard rules

1. User reads narrative trees only. Do not file-ize concept definitions; only create `notes/<slug>.md` when the user explicitly externalizes a frustration point.
2. Never score the learner. Retrieval practice is not graded — you do not pass judgment on the person's ability with marks or tallies. In a drill (see the discovery drill), an answer that fails to cover the source is *not* a verdict on the user; it is only the trigger that fires card capture. Frame everything as "the source says X, your answer didn't reach X yet → here's a card," never as "you got it wrong."
3. Source is the single source of truth. `sources/` pages are never overwritten. Re-ingesting the same arxiv ID is a no-op.
4. Wikilinks are the primary currency. Unresolved `[[slug]]` renders as Obsidian "unresolved" — acceptable and normal.
5. narrative tree = working hypothesis. No citations / confidence tags in tree bodies. User verifies against `sources/` when doubtful.

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
├── maps/<subject>-dag.json   # 教科 DAG (俯瞰地図) の真実源 — 手書き (LLM authoring)
├── maps/<subject>-dag.html   # 上記から subject-dag-render が生成するビュー (file:// 可)
├── index.md                  # auto-generated stats + dead links
├── log.md                    # append-only operation history
└── manifest.json             # source delta tracking
```

## Active commands

Invoke via `python3 ~/.claude/skills/ai-wiki/scripts/dispatcher.py <cmd> [args]`. JSON to stdout. All accept `--vault PATH` (default `$AI_WIKI_ROOT` or `~/ai-wiki`).

| Command | Purpose |
|---|---|
| `narrative-draft <source.md> --slug <s> [--title <t>] [--no-coverage] [--no-holdout] [--mode peer] [--faithfulness] [--judge-model M] [--dry-run]` | LLM: source md → narrative tree (size-adaptive, coverage QA on by default). Auto-normalizes flattened `#` headings and drops back-matter (References/Acknowledgements/…). Pre-flight (no-LLM) attaches a `preflight` block + warnings (duplicated heading titles, off-topic tangents 余談/コメント返し/次回予告/中休み, `in_scope_ratio`); tangents kept, not dropped. `--dry-run`: pre-flight only, zero cost. `--judge-model M` (default sonnet): coverage judging runs on a different model from the opus generator. `--no-holdout`: skip the fresh-QA-set re-measure (`holdout_coverage_pct` vs in-sample `coverage_pct`). `--no-ingest-source`: skip archiving the source under `sources/`. `--mode peer`: one peer tree per major section, no master hub. `--faithfulness`: after commit, judge each tree's atomic claims against its source → `.narrative-faithfulness/` (diagnostic). Design WHY in `_dev/commands-rationale.md`. |
| `narratives` | Validate narratives/, regenerate `_index.md` |
| `lint` | Dead-link report + regenerate `index.md` |
| `card-draft <slug> [--model <m>]` | LLM: symbol-walk the tree → exhaustive atomic Q-A deck `cards/<slug>.tsv` (Anki-importable). Primary deck builder. |
| `card-add --slug <s> --front <q> --back <a>` | Append one extra card by hand (rare — only for synthesis the tree lacks) |
| `cards [<slug>]` | Dump deck(s) as JSON (one deck per narrative, or all) |
| `derivation-scan <source.md> [--anchor <n>]` | Source → derivation target manifest (`_targets/<src>.md`). Deterministic skip-marker sweep + LLM enumerates stated results worth deriving. Targets are set whether or not the steps are present; routes each into a tier (`T1|cross|gen`); commits nothing (curate, then draft). Design WHY in `_dev/commands-rationale.md`. |
| `derivation-draft <source.md> --slug <s> --goal <g> [--anchor <n>] [--judge-model M] [--no-verify]` | Source(+anchor)+goal → subgoal-labeled spine (`derivations/<slug>.md`). Generator (opus) drafts `[⇣n]` steps from the source; anchor supplies the subgoal structure only. A different judge model (sonnet) verifies each step against the source — confirmed→verified, unconfirmable→`[~]` + verified=false. Design WHY in `_dev/commands-rationale.md`. |
| `derivations` | Validate derivations/, regenerate `_index.md` |
| `subject-dag-render <slug>` | 機械: `maps/<slug>.json` (真実源) を検証 → 自己完結 HTML `maps/<slug>.html` を生成。配色は region 宣言順に自動付与。HTML は生成物、手で触らない。 |
| `subject-dag-validate <slug>` | 機械: `maps/<slug>.json` を検証 (id 重複・dangling edge・未知 kind・region 不整合 → error / tree 不在 → warning)。 |

## Cards (durable memorization asset)

`card-draft <slug>` walks the tree's bracketed symbols and turns every node into one or more atomic Q-A cards (symbol fixes the question type; uncovered nodes are reported, never dropped). Full spec lives in `scripts/prompts/card_draft.md`. Output `cards/<slug>.tsv` is Anki-importable (2-column Front/Back + `#notetype`/`#deck` headers); memory forms in the SRS, not in chat — tell the user to import and drill via spaced repetition, pacing new cards (~10–20/day), never to "study" by reading Q+A as a list (passive rereading, not retrieval). Chat-time first-learning, and the misconception cards it mints (`card-add`), both run through the discovery drill (above) — there is no separate recall drill.

## Discovery drill — the default way to *learn* a tree (front of the pipeline)

The other drills train material already acquired. Discovery is how it gets acquired in the first place, and is the main axis of tree learning. Reading a finished tree and nodding is low-density — the learner gets the solution without feeling the problem. Instead: hold the tree as a sealed answer key, hand the learner the problem (a DAG edge = a `⟳ だから次の問題`), and make them reconstruct the resolution before revealing it. Two invariants: never reveal before the learner commits ("分からない" counts); on a divergent answer explain only why it diverges, never the correct answer — they close the last gap themselves. The subject map `maps/<subject>-dag.json` is the question generator (edge `kind` fixes the question type; confirm parents first per `ai_usage`). When the user wants to learn / study / "勉強する" a tree or walk a DAG, first read `reference/discovery-drill.md` and run that loop. Grounded in epistemological obstacles, the genetic method, and productive failure; never scores the learner (hard rule #2) — a divergence is the trigger to capture a misconception card and re-aim, never a verdict.

## Derivation layer (procedural knowledge)

Narratives + cards train declarative knowledge (what / why); they do not train procedural knowledge — reproducing a derivation, taking an FOC, computing an estimate. Atomic Q-A cards even *can't*: a derivation is an ordered transform, and atomizing it kills the chain (and the transfer). The derivation layer fills this gap.

- A derivation = a subgoal-labeled spine. `derivations/<slug>.md` holds an ordered `[⇣n]` step chain from a GOAL to its result, each step tagged with an abstract subgoal label (subgoal labeling lowers cognitive load and transfers to new problems).
- Provenance is asymmetric with cards. Cards are built *from the tree* (the tree has everything they need). Derivations are built *from the source* — the tree's 1-3-sentence nodes don't contain the algebra, so building a spine from the tree would hallucinate steps. The narrative is used only as the anchor (wikilink) and the subgoal *structure*. Source stays the single source of truth (hard rule #3) and the verification target.
- The source need not contain the derivation. `derivation-scan` separates *target setting* (always possible from stated results) from *step acquisition* (tiered). Three tiers, by where the steps come from / confidence:
  - T1 harvest — full steps present in the source → safe, verified, high.
  - cross — steps live in another source ("see Hansen / 補足参照 / ○章参照") → fetch from there.
  - gen — source skipped it ("略"/"面倒"/"演習"); LLM-generates, judge-verifies; unconfirmable steps marked `[~]`, verified=false. These skip-markers are the *signal* for the hardest, most valuable targets.
- Generation never grades the learner. The judge verifies the *math*, not the user. The faded derivation drill (`reference/derivation-drill.md`) surfaces what the user can't yet reproduce only to adjust scaffolding — never as a verdict (hard rule #2).

### derivation spine format

Enforced by `scripts/derivation.py`. Contract:
- Frontmatter (required): `type` (=derivation), `slug`, `title`, `anchor` (→narrative slug), `source` (→source slug), `tier` (`T1|cross|gen`), `verified` (bool), `created`, `updated`
- Sections: `## GOAL` (the target expression) + `## SPINE` (the step chain), both required
- Step marker `[⇣n]`: numbered subgoal steps, validated contiguous 1..N in order (the chain must not be broken). Line shape: `[⇣n] <subgoal label> → <step content>`
- `[~]` trailing a step = unverified (source-skipped, judge-unconfirmed); a `verified=true` spine must carry none.

Run `dispatcher.py derivations` after editing to validate.

## 教科 DAG layer (俯瞰地図) — トップダウンの全体像

narrative tree は教科書の章単位で、しかも一本道。章をまたぐ「全体像」と、複数の流れが一つの結果に合流する構造は、木 (単一親) では描けない。教科 DAG はこれを埋める上位層:1 教科の全 tree を、章順でなく問題構造で疎な有向非巡回グラフに再切断した俯瞰地図。

二層で運用する (詳細を二重に書かない):
- 上層 = 教科 DAG (`maps/<subject>-dag.{json,html}`): 非線形・合流ありの全体像。一見性 (gestalt) 担当。疎 (骨格ノード ~12-18 個)。
- 下層 = 既存の章/講 tree (`narratives/`、無改変): 一塊の詳細な流れ。学習担当。各 DAG ノードの `trees` が出所 tree へ降りる配線。
- 詳細は新規に書かない。DAG (仕様) + tree (出所) を AI に渡せば、構造に沿ってノード単位の説明をその場で生成できる (`json` の `ai_usage` 参照)。

機械と判断の分離 (スキルの哲学通り):
- 判断 = LLM が `maps/<slug>-dag.json` を手で書く (下記手順)。トポロジー発見・再切断・配置は判断であり、決定論化しない。
- 機械 = `subject-dag-render` / `subject-dag-validate` (`scripts/subject_dag.py`)。JSON を真実源に検証・描画。HTML は生成物 (手で触らない)。schema は `subject_dag.py` の docstring。

### authoring 手順 (LLM)

1. 全 tree を自分で読む (jibun-de)。見出し + ROOT + 各節の「だから次の問題」+ 本文。出所を grep で済ませない。
2. トポロジーを発見する (押し付けない)。形はフィールドが決める。実例: 計量経済学=収斂 (多数の問題→1 標準)、産業関係論=拡散 (1 核→5 領域、再収斂せず)、産業組織論=基準+逸脱 (需給を合流させ基準→逸脱を枝で)。同じ表現が分野ごとに逆の地形を映すのが価値。一本道に潰さない。
3. 疎な骨格ノードへ再切断。章と 1 対 1 にしない — 散った一問題を merge、一章の別問題を split。各ノード `desc` は参照ゼロの数行、`trees` に出所 tree (複数可) を配線。
4. エッジを問題構造で張る。`kind`: `flow` (論理の本筋) / `join` (合流=複数親、木で描けない核) / `fan` (分岐・拡散) / `cross` (枝間に残る細い共有の糸) / `dissolve` (消滅)。`label` 任意。
5. 決定論的レイアウト。`layer` (縦=論理段) と `col` (横) を手で置く。背骨 + 分岐/合流で、force 配置の毛玉を避ける。同層の水平エッジは避ける。
6. `maps/<slug>-dag.json` を書く → `subject-dag-validate <slug>` で検査 → `subject-dag-render <slug>` で HTML 生成。`open maps/<slug>-dag.html`。

原則: 一見性が最優先。全部載せない (完全性は下層 tree が担保、全節が到達可能であればよい)。教科をまたぐ繋がりは bridge ノードで張れる (例: 労働経済学→計量経済学)。既存 3 教科 (`計量経済学基礎-dag` / `産業関係論-dag` / `産業組織論-dag`) が canonical な作例。

## narrative tree format

Enforced by `scripts/narrative.py`. Contract:

- Frontmatter (required): `type`, `slug`, `title`, `status` (`pilot|stable|frozen`), `created`, `updated`
- Sections: `## ROOT` required; `## 記法` (legend) recommended
- Bracketed symbols (fixed set): `[?] [??] [★] [◯] [✕] [∥] [⛔] [!] [∴] [⤴] [⤵] [⟳] [↺] [⊂] [⊕] [~]` — any other `[<sym>]` token fails validation. `[~]` = model-inferred link (edge the LLM synthesized that the source doesn't state explicitly; marks provenance, not confidence — surfaced by `--faithfulness`).
- Inline edge markers: `→`, `⇒` only
- Body style: 1–3 sentences per node, problem-driven edges, direct readability
- Forest peer: no cross-tree hierarchy; connect via `[[slug]]` wikilinks

Run `dispatcher.py narratives` after editing to validate.
