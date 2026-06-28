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
