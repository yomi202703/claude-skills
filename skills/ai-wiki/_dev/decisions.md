# ai-wiki decisions (append-only ADR ledger)

Why choices were made and what happened. Never rewrite past entries. Maintenance-only; not loaded at runtime. Command-shaping WHY also lives in `commands-rationale.md` (that file is the per-command reference; this file is the dated narrative of cross-cutting calls).

## 2026-06-29 — the skill is correctly-factored labor, not "AI-native"

Context: user asked whether ai-wiki should go "fully AI-native" because they no longer open the vault to read trees, then admitted they also never cross-check trees against `sources/` ("私の怠惰ですわ").

Calls made:

- The end goal stays human. User confirmed they still want to *know* the material (memory + understanding), just via chat rather than by opening Obsidian (branch B of the fork: human-knower, AI-mediated interface). So this is NOT branch C (AI holds the knowledge) — card+SRS, drills, source corpus, coverage gates all stay human-facing and untouched.
- "AI-native" is the wrong label, and naming it that would describe the *worse* design (branch C, which was rejected). What the skill actually is: labor correctly factored. Mechanical/scalable work → AI (generation, coverage, faithfulness, structural soundness, drill questioning). Irreducibly human work → human (forming memory, productive failure, understanding). Artifacts are the interface between the two, optimized for the transaction, not for either side's reading pleasure. The original design got this factoring right; the hard part is the factoring, not the format.
- Do NOT equate "AI-native" with densifying the tree. Principle 4 (prose over symbol-chains) serves generation/re-consumption quality too — LLMs reason more reliably on structured prose than on maximally compressed symbols. The only presentation layer that legitimately sheds its primary consumer under branch B is the *visual/delivery* layer (hard rule #1's "user reads trees", the DAG HTML/SVG render built for external-browser viewing), not the node language.

The one mis-parked task (the real bug): source cross-checking was default-parked on the human (hard rule #5: "user verifies against sources when doubtful"). The user never did it, so it silently never ran. This is a design defect, not laziness — a system must not depend on a discipline humans reliably skip. Fix: move the check to the machine.

- hard rule #5 rewrite: the tree stays a working hypothesis (epistemically honest), but the verification is re-attributed from the human to the machine (coverage = recall, faithfulness = precision, soundness = structure). The "user verifies" clause is dead and removed.
- faithfulness promoted to default-on (`--no-faithfulness` opt-out, mirroring `--no-coverage`/`--no-holdout`). It is no longer a diagnostic afterthought; with no human cross-checker it is the only thing checking claim-level precision.

Residual gap named, and the design to close it:

- faithfulness checks *claims* (precision), coverage checks *content* (recall). Neither validates the *spine topology* — the problem-driven "why B follows from A" edges, which are the LLM's synthesized framing (`[~]`) and the most pedagogically load-bearing, most plausibly-wrong layer. The human, not being a domain expert, could never have caught a wrong framing anyway, so "user verifies" was doubly fictional here.
- Key realization: structural verification is NOT a new parallel subsystem. faithfulness already isolates these as `source_silent` *edges* and the read-guide already says "verify these yourself" — the targets are extracted; only the judgment is missing. So the structural-soundness check is an *extension of faithfulness*: for each `source_silent` edge (the synthesized spine), a second judgment evaluates soundness — is "B follows from A" a valid problem-driven move given the source, or a plausible confabulation? Verdict sound|dubious|unsound, not stated|not-stated (it is by definition not stated). Same diagnostic architecture (post-commit report, different judge model, never auto-edits), default-on with faithfulness.

Status: hard rule #5 rewrite, faithfulness default-on, and structural-soundness extension committed this session.

## 2026-06-29 (refinement) — the DAG SVG is NOT demoted; only tree-reading is

Correcting the call above (append-only, so the earlier note stands as written): the entry above lumped "the DAG HTML/SVG render built for external-browser viewing" in with hard rule #1 as a presentation layer that sheds its consumer under branch B. At implementation time that turned out wrong, and the distinction matters.

- Tree demotion is correct: a tree's content is prose (linear), so the AI re-renders it into chat losslessly. The "user reads tree files" assumption can drop → read surface is the chat-rendered tree (discovery drill). hard rule #1 reworded accordingly; the file-ize discipline is unchanged.
- The DAG is the exception, and it is the opposite case. The DAG exists for one reason — 一見性 / gestalt, the cross-chapter overview a single-parent tree (linear) cannot draw. Gestalt is a *visual modality*; chat (linear text) cannot carry it. An AI narrating the DAG node-by-node in chat is linear again — exactly what the DAG was built to escape. So the SVG is the one human-facing artifact branch B does NOT displace: the only place where opening a browser yields something chat fundamentally can't.
- Net: nothing about the DAG is demoted. The JSON is reclassified as dual-role (AI: discovery-drill question generator + truth source + validate target; human-via-SVG: render source). The SVG stays the human gestalt. Only `subject-dag-render`'s framing as "the way you view the map" is now "the human gestalt export"; validation/JSON remain load-bearing for the AI regardless.

Generalization worth keeping: branch B ("learn via chat") displaces an artifact only when its content is linear (re-renderable as chat). Visual/gestalt artifacts survive intact, because chat is the wrong modality for them. Demote by modality, not by "is it human-facing".

Status: hard rule #1 reworded, DAG dual-role clarified; no code change (the renderer already works, only its status in the docs moved).

## 2026-06-29 — fold the learner-side "wall" prompt's lid detectors into the discovery drill

Context: user brought their own first-person learning contract ("壁としてぶつかる" / "答えを渡さない" / 抽象語・無敵語を許さない / 手続き語も蓋 / 抽象語と突破を見分ける / 一度に一つの壁 / 螺旋の振り返り) and asked whether it could be integrated with `reference/discovery-drill.md`.

Diagnosis: the two are the same mechanism from opposite seats — the drill is operator(AI)-facing machinery, the user's prompt is the learner-facing contract. ~80% is a 1:1 restatement (sealed answer, name-after-function, refute-by-own-words, pull-not-push/third-way, 分からない歓迎, one-edge-at-a-time, hand-off=螺旋). So the integration direction is FOLD the prompt's detectors into the drill, NOT replace the drill with the prompt (replacing loses the DAG question-generator, card capture, sealed-source faithfulness — the three things the single-mountain prompt lacks).

Real new value the prompt has that the drill lacked: a THIRD answer-state. The drill's invariant #2 assumed only on-target vs divergent. An omnibus/invincible word (複雑/バランス/中立/均衡点/どちらも) or a procedure word (流れで/手順通り) is neither — it commits to nothing yet poses as an answer. There is no committed path to refute, so split-and-refute (#2) is the wrong tool; the right move is halt + force one concrete scene (the learner produces the scene → no leak). Plus the lid-vs-breakthrough discrimination: a bared demand/cry may be the abstraction pierced, not a lid — but default to lid (under-help bias) and only ride it forward when unmistakable.

Calls made:
- Added invariant #3 "A non-answer is not a commit — halt it, don't refute it" (two lids: omnibus words, procedure words; force a concrete scene; the breakthrough exception with default-to-lid). Renumbered hints pull-not-push #3→#4; updated cross-refs.
- Added the non-commit branch to drill loop step 2 (halt/force-scene/re-pose, don't refute, rule out breakthrough first).
- SKILL.md drill summary: "Two invariants" → "Core invariants", appended the third-state clause.
- Did NOT import the learner-voice framing (叫び/螺旋/未踏の山) — kept the spec operator-facing and dry; that framing belongs in how the user opens a session, not in the spec.

Status: discovery-drill.md invariants + drill-loop, and SKILL.md summary, committed this session. No code change (drill is chat-time judgment, no dispatcher command).

## 2026-06-29 (style) — skill-shape's body lens applies to reference/ files, not just SKILL.md

Asked whether skill-shape applies to `reference/discovery-drill.md`. Verdict: half of it. The router/frontmatter/description/directory axis is N/A — the file is a supporting `reference/` loaded by name from the parent SKILL.md body, not a routable unit with a description string. But the "write the body for the executor" core applies fully: the file is executor-facing runtime text the drill instance reads token-by-token, so the body ship-gate (no emphasis markers, no history, WHY ≤ one clause) governs it.

Ran that lens and swept emphasis from the file: removed all italics (`*material*` `*procedure*` `*that*` `*set*` `*specific*`) and the ordinary-word emphasis caps (ONLY/ARE/NOT → lowercase). Two of the italics were ones introduced in the invariant-#3 edit earlier today; the rest pre-existing. Rule applied: emphasis by any mechanism is skim-salience for a human, and the executor does not skim — state the rule plainly, keep only caps that name things (DAG/ROOT/MU/MC/SRS retained).

Deliberately NOT done (repo-style decisions, not unilateral): the file-wide manual hard-wrapping (~90 col; whole vault uses it) and the WHY weight of the "What it is and why" / "Grounding" sections (grey — for a judgment task the stance-setting plausibly changes how the executor runs the loop). Flagged, left for author.

Status: emphasis swept from discovery-drill.md; verified zero italics / zero ordinary-word caps. No behavior change — pure presentation.

## 2026-06-29 (ripple) — reconcile the standalone mobile prompt with the canonical drill

ripple-check after the invariant-#3 fold found the one parallel implementation of the drill rules: `reference/standalone-prompt.md` (the paste-ready block for plain Claude chat / mobile, no Claude Code tooling). It enumerates the same invariants in its own compressed Japanese voice, so it does not reference the canonical file by symbol — caught by searching the rule content, not the structure. It had drifted on three counts against the uncommitted delta:
- missing the new third answer-state (non-commit / omnibus-word + procedure-word lid) — the same gap just closed in canonical;
- step-2 still said "当てたら名前を告げて次へ" (old behavior) vs canonical's name-as-retrieval ("それは何と呼ぶ?", don't reveal unprompted);
- 【記録】 captured only misconceptions, not the naming-gap trigger.

Call: fully reconcile (not a half-sync — a duplicate that looks updated but isn't is its own hazard), each port compressed to standalone's register. Kept the breakthrough exception in the port rather than dropping it: omitting it would make standalone STRICTER than canonical (every bared cry forced to a concrete scene), i.e. not the same rule — the ripple goal is 同値に揃える, so the exception ports too, with the default-to-lid bias explicit. Renumbered standalone's 不変ルール (hints 3→4, leak-check 4→5; non-commit inserted as 3) and added the rule-3 path + naming-retrieval line to 進め方.

D1 (canonical invariant renumber) has zero external ripple: standalone uses independent numbering and links nothing; canonical-internal #2/#3/#4 refs verified consistent. No silent confidence-fix was applicable on canonical — only the duplicate needed aligning.

Status: standalone-prompt.md reconciled (4 edits). No code, no tests (instruction files).

## 2026-06-29 — judge-call failure must not masquerade as a coverage/faithfulness score

Context: ingesting an arxiv paper (deterministic-control-plane-llm-coding-agents) via narrative-draft, the run committed a good tree (soundness pass: 19/20 sound) but reported `coverage 0.0% (80/80 missing), did not converge after 3 iterations` and `fact_faithfulness_pct 100.0`. Both numbers were artifacts of a transient judge-model (sonnet) API outage, not real measurements. Evidence in log.md: `op=narrative_faithfulness ... error=yes ... in=0 out=0` and every coverage item carrying `note: "coverage check failed"`.

Diagnosis: two separate spots conflated "the judge call failed" with a real verdict, and they failed in opposite, both-misleading directions.
- coverage (`coverage_qa.py`): on judge error, `check_coverage` returned every QA as `status="missing"`. Downstream `coverage_pct = covered/total` then read 0%. Worse, the remediation loop (`iterate_and_fix`) saw 0% < threshold and spent real money running `_apply_gap_fix` 3× against a tree that was already fine (~$1.18 of the run). A judge outage → false 0% → wasted correction cost.
- faithfulness (`faithfulness.py`): on judge error, `judge_claims` marked every claim `source_silent`. Fact precision is `(fact_total − fact_unsupported)/fact_total`; with 0 unsupported that computes 100% — a perfect score reported precisely because nothing was checked.

Calls made (fix in the scripts, NOT SKILL.md — SKILL.md described the intended behavior correctly; the bug was in code):
- New terminal status `error` (unevaluated) distinct from `missing` (evaluated, not covered). `check_coverage` returns `error` on both API failure and output truncation.
- `_coverage_pct()` excludes `error` items from the denominator; returns `(None, unavailable=True)` when nothing was evaluated OR the error rate exceeds `MAX_ERROR_RATIO=0.5`. With zero errors it equals the legacy `covered/total`. `coverage_pct` is now `float | None` (None ⇒ unmeasured, never a spurious 0%); `CoverageReport` gained `errored` + `unavailable`.
- `iterate_and_fix` breaks the loop immediately when a round is `unavailable` — no gap-fix spend against an unreliable judge.
- `judge_claims` now returns `(claims, cost, judge_ok)`; on failure `run()` sets `faithfulness_pct`/`fact_faithfulness_pct = None` and `judge_failed=True` instead of 100%. Soundness is a separate call and still ran (that is why the same run got a real 19/20 while precision was unmeasured).
- All consumers guarded: gap report + faithfulness report render an explicit "UNMEASURED — judge API failed, N/A, not a tree-quality signal" banner; narrative_draft warnings split the `unavailable` case from genuine non-convergence; every `:.1f` on a now-nullable pct routed through `_fmt_pct`/guards.

Why not SKILL.md: considered adding an operational caveat ("0.0% with note=coverage check failed means judge failure"). Rejected — that documents around a bug in the wrong layer; fixing the code removes the false 0% at the source, so no caveat is needed. SKILL.md unchanged.

Tests: +6 (denominator-excludes-errors, no-error==legacy-ratio, all/majority-errored→unavailable+None, run_coverage end-to-end unavailable, faithfulness judge-failure→N/A-not-100). Full suite 195 passed / 3 skipped.

Deferred (recorded, not done this session): source-slug inheritance — narrative-draft ingested the source as `note-2026-06-29-paper` (from the temp filename) rather than the `--slug`/`--title`. P2; trigger [next time source provenance matters]. Re-running coverage alone still requires a full narrative-draft regeneration (no standalone `coverage-recheck <slug>` entry point); the `error`/`unavailable` plumbing added here is the precondition for such a command if it is ever wanted.

Status: coverage_qa.py / faithfulness.py / narrative_draft.py committed this session with tests. The original arxiv run's committed tree is unaffected (faithfulness/coverage are diagnostic, never mutate the tree); only the QA *reporting* was wrong, and only on judge-outage runs.
