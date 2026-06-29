---
name: factcheck
description: Stand up the separate, firewalled blind-review handover package handed to external reviewers — capture independent human verdicts on each unit (judge the case by confronting evidence, not agree/disagree with a machine), persist them internally, and flow them back to the developer server on one ingestion path. The blind GT-creation half of a no-ground-truth judgment loop, as its own self-contained deliverable. Owns: firewall by absence (the package ships no machine answers and no judge code, so concealment is structural — not a render-time guard, not a login), contract generated from a single source, reviewer-minimal surface, one verified distribution command plus a doctor preflight. Use to build or restructure the blind reviewer handover package, or when handing units to an external fact-checker. Triggers — "/factcheck".
---

Stand up the blind reviewer handover package. Start from `template/` (runnable, stdlib only): `build_package.py` generates `dist/` from `source/` (no answers), `fc_server.py` serves the blind surface, `--export` is the operator's flow-back. Fire grill-me for every fork.

review-server is developer-only and hosts no blind route; blind GT-creation is here. The firewall is structural — by absence, not a render-time guard.

## Composes review-server — do not re-own its gates
The shared invariants live in review-server (S1–S12); re-owning them here re-creates the akatsuki F2 drift (contract duplication). Borrow, don't copy:
- S2 single contract source — the package's contract is generated from the host's one source (version-stamped, never hand-edited). Change vocabulary in the source only; the radios and the export follow.
- S9 one GT flow-back — `--export` emits exactly the columns the dev server's ingest reads; one path back, no second import.
- S6 append-only tiered GT — the package produces provenance=blind only (gold-eligible on the dev side); it never assigns gold itself. Gold promotion happens dev-side after independent blind re-confirmation.

## Owns the blind-handover discipline
- Firewall by absence. The package contains no machine answers and no `judges()` code; there is no reveal path. Human ⇔ proposer(Claude) ⇔ production(Gemma) comparison reassembles on the dev `/diag` after the GT flows back (S9).
- Independent verdict, not agree-toggle (S11). The reviewer judges the case by confronting the evidence, never "agree/disagree with the machine's verdict" — that is the anchored ratify path (provenance=anchored → silver), a different surface. Showing the reviewer their own prior verdict (progress, revision) is fine; it is their own work, not machine output.
- Reviewer-minimal surface. Show only what the reviewer does: judge + reason + evidence, and their own progress. Verdicts persist internally on commit; there is no export button on the reviewer surface, since collecting the GT back is an operator action. After commit, advance straight to the next unit.
- One verified distribution (S10). `build_package.py` is the operator's packaging step; a doctor preflight validates the receiving side with the real parser before the handoff is done.

## Forks — fire grill-me, never pre-decide
The package's form has settled; defer these until a real campaign forces them:
- vocabulary & cardinality (the example ships one axis, ○/△/×; meaning and wording are per-case, in the source contract);
- auth strength / reviewer attribution (default none; wire login/named reviewers only when several untrusted external reviewers need sequestration or attribution);
- per-campaign GT protocol (blind / ratify / synthetic);
- multi-reviewer aggregation.

## Composition
- Every fork → grill-me.
- Shared GT invariants + the dev `/diag` where divergence reassembles after flow-back → review-server (composed; S2/S6/S9).
- Invoked by judge-loop P2 (the human loop) as the separate-deliverable choice for the GT-creation surface.
- Source preprocessing for what the reviewer reads → xlsx-router, pdf-to-md.
- Rendering craft for the blind surface → html-deck, only its craft/legibility/owner-language layer; the verdict-rendering layer has no machine output to render here.

## Ledger
Append-only `_dev/decisions`: decisions and why, rejected options and why, which campaigns used which protocol.
