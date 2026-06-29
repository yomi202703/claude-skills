# aftercare — decisions (append-only)

Maintenance material. Why each choice was made; never rewritten.

## 2026-06-30 — skill founded: after-change cleanup orchestrator

Origin: the user often writes "過去の残骸を片付けて" prompts when something was updated. Goal was to design a skill for that, or layer it on /deadcode. Designed in conversation; a ChatGPT second-opinion (chatgpt-web) sharpened the safety model.

### The niche (why it is neither deadcode nor ripple-check)

Three cleanup concepts, by detection model:
- deadcode = reachability: "X exists, nothing references it" → remove X (orphan).
- ripple-check = fresh ripple: "I just changed X, make Y follow" → fix Y (forward consistency, live single-change intent, change-neighborhood).
- aftercare's own track = supersession: "Y still assumes a world that no longer exists" → remove/fix/preserve Y (backward, cold/accumulated, doc+code).

Dangling reference is the inverse of an orphan (deadcode finds X with no referrers; aftercare finds a referrer to a deleted X), and doc/ledger contradiction is invisible to deadcode because both sides may be referenced. So the detection models are genuinely distinct.

User's usage shape (elicited): seed = "scan, don't name a target"; residue = code + doc/decisions; timing = end of session, accumulated, intent cold at the single-change level but warm at the session level. Run as the twin of ripple-check, after it.

### Decision 1 — composition, not merge into deadcode

The user first leaned "make deadcode the superset / merge in." Rejected merging into deadcode's SKILL.md (deadcode-as-parent). Instead aftercare is the parent and invokes deadcode as a sub-pass.

Why: deadcode's value is its narrowness (code-only, reachability, test/AST/runtime gates). Folding doc/ledger editing and supersession semantics into it dilutes its safety contract, and a context-keyed "find dead code" that sometimes also edits docs is unpredictable. Composition keeps deadcode unchanged (cold invocation behaves exactly as before), gives the risky semantic-staleness logic a name that signals its risk, and still reuses reachability. "上位互換" is preserved by composition rather than by cramming. (ChatGPT independently reached the same conclusion via the contract-pollution argument.)

### Decision 2 — ripple-check brought under the same parent

User's proposal. The three are the same trigger ("I changed things, reconcile and clean") in time order, share DNA (tool output is candidate; grep+read decides; confidence gate; safety commit; intent = conversation + diff), and the repo already has the judge-loop thin-orchestrator precedent. aftercare sequences ripple-check (A) → supersession (B) → deadcode (C) → verify (D), with one feedback pass. Sub-skills are composed, not absorbed — each stays independently invokable (mid-session you want only ripple-check).

### Decision 3 — explicit trigger on the parent (reversal)

Earlier design had "no trigger; activation keyed on warm-vs-cold context." Reversed: the parent gets an explicit trigger; deadcode and ripple-check keep their own for standalone use. Why: deletion tools must be predictable; a fuzzy "warmth"-keyed activation is opaque to both the router and the user. Cold-invoking deadcode then provably never touches docs.

### Decision 4 — warm path stays broad, but gated by classification

User chose "温かい時は広く踏み越す" (auto-delete on session-context evidence without full oracle agreement), against ChatGPT's stricter "context proposes candidates, never authorizes deletion." Kept broad — but only candidates that survived the four-way classification are eligible, so preserve/redirect/rewrite are carved out first, and a still-present live consumer is treated as breakage (incomplete migration), not residue. The preserve-guards are the safety net that makes broad warm action defensible.

### Decision 5 — decisions ledger written only for judgment calls

User chose "判断がある時だけ decisions"; rejected appending every run's removals to decisions. Why: routine cleanup logs dilute the ADR ledger's density, which matters because aftercare also reads the latest decisions entry as a truth oracle. Mechanical removals live in the commit message and run report; only actions carrying a real reason are appended, routed to the relevant topic file.

### Adopted from the ChatGPT critique (old ≠ trash)

The biggest correction: old is not the same as residue. Added as first-class structure:
- Four-way outcome before any action: delete / rewrite / redirect / preserve.
- preserve-guards: compat alias, migration shim, old API/CLI/env name, negative/regression test, golden file/fixture, changelog, external-consumer-read artifacts.
- breakage / incomplete-migration as a first-class output (Bへ移行のつもりがA/B混在).
- Live-use detection is wider than AST refs (string literals, prompt/markdown mentions, glob/convention loading, shell/CI/manifest paths, cross-repo); failing to prove use ≠ proof of residue.
- Truth-oracle invariant: never remove what an oracle proves currently load-bearing; oracle conflict (code does B, latest decision says A) is a finding to surface, not auto-resolve.

### Won't-do (rejected, do not re-propose)

- Merge supersession into deadcode's SKILL.md (deadcode-as-parent) — Decision 1.
- No-trigger / context-keyed activation — Decision 3.
- Restrict the warm path to ChatGPT's narrow whitelist — Decision 4.
- Append every run's mechanical removals to decisions — Decision 5.

### Decision 6 — single entry via a multi-select of the three passes; no physical consolidation

The user asked whether the three should be folded under aftercare as subcommands ("統合した方がわかりやすい"), then noted skills here are invoked name-only. Conceded that name-only kills the routing-description argument for separation — but it is symmetric: name-only also kills consolidation's main upside (fewer things to pick), since picking is just typing a name already known. Routing becomes a wash either way, so the decision falls to refactor cost + coupling vs cosmetic grouping.

Kept the three as separate skills (composition), and made aftercare the single entry that offers them as a multi-select (AskUserQuestion multiSelect, all pre-selected, canonical order ripple-check → supersession → deadcode). Selected passes run in that order; the Phase D feedback re-run of ripple-check fires only when both ripple-check and deadcode ran.

Why not physically merge: deadcode and ripple-check are mature independently-tested units (deadcode carries frameworks/, setup.sh, runtime-evidence gate, bisect; ripple-check its own contract), deadcode is a shared dependency both ripple-check and aftercare call, and deadcode is run context-free as repo hygiene with no change/session. Merging flattens that for a cosmetic gain. The multi-select delivers the single-entry clarity the user wanted without the flattening.

### Decision 7 — folded deadcode + ripple-check into aftercare; rewired repo-shape (supersedes Decision 6)

The user chose to physically consolidate after all: aftercare is now the single cleanup skill. The standalone deadcode and ripple-check skills were moved (git mv, history preserved) into aftercare/reference/ — `reference/deadcode/` (deadcode.md + frameworks/ + setup.sh) and `reference/ripple-check.md` — and removed as top-level skills. The multi-select now selects internal passes.

Decision 6's "keep separate" was reversed because name-only invocation makes the routing cost of a single fat skill negligible, and the user values one entry point over independent skill identity.

The blocker surfaced during the fold: a dependency chain repo-shape → ripple-check → deadcode. repo-shape composes ripple-check for git-mv reference-following ("do not reimplement it"), and ripple-check delegates whole-repo dead code to deadcode. Folding dangled both. Resolution (user chose fold + rewire): repo-shape now points at the ripple-check pass at aftercare/reference/ripple-check.md (description + safe-move step + Composition note all rewired); the ripple-check pass's delegation now points at reference/deadcode/deadcode.md. Accepted consequence: repo-shape reaches into aftercare/reference for a procedure doc — the cross-skill coupling Decision 1 had wanted to avoid, taken on deliberately for the single-entry payoff.

Follow-on reference fixes: setup.sh self-path (deadcode.md + setup.sh header), WINDOWS.md note (deadcode → aftercare deadcode pass + new setup.sh path), aftercare SKILL.md (Phase A/C/D now name the passes by reference path, not "invoke the skill"), and aftercare's description absorbed the old deadcode/ripple-check triggers so those intents still route here. Left untouched: the `deadcode` Python-tool references in reference/deadcode/frameworks/python.md (a CLI lens, not the skill), and other skills' append-only _dev ledgers (historical).

### Open

- Name `aftercare` is provisional but adopted; rename touches only the directory name + frontmatter name.
- Phase B lenses are inline in SKILL.md; split to reference/ only if they grow language-specific.
- repo-shape now depends on aftercare/reference/ripple-check.md; if aftercare is ever renamed, that path moves too.
