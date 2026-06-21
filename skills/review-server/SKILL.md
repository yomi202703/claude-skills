---
name: review-server
description: A domain-agnostic standard for standing up THE single shared web server that closes the human loop of any no-ground-truth judgment/scoring/extraction system — one server with two login roles (developer diagnostic mode + human GT-creation mode), a single contract source, append-only disposable GT with maturity tiers, an anchoring firewall (no machine output shown until the human commits), a reconfigurable review unit that follows the judgment unit, side-effect-free reads, and one verified distribution command. NOT a finance/akatsuki tool: the judgment vocabulary, axes, unit, and questions are injected from config, never hard-coded. Composed by judge-loop (P0u inspection mode / P2 human loop = rough-GT + GT-creation back-stage / W6 evaluation mode); replaces the sprawl of one-off per-question viewers with one config-driven server. Use when the user needs to build, restructure, or unify the review/inspection/GT-creation server for a no-GT judgment loop, or asks to set up "the review server".
---

Stand up THE single shared review server for a no-ground-truth judgment loop. Domain-agnostic: vocabulary, axes, unit, and questions are injected from config, never hard-coded. Start from `template/` (runnable skeleton, stdlib only, gates enforced in store.py + server.py); adapt only `contract.json` and the `data.py` adapter. For the failure evidence and rationale, read `docs/事例_あかつきserver断片と失敗.md`. Invoked by judge-loop; fire grill-me for every fork.

One server, three modes across the lifecycle: diagnostic (developer), GT-creation (human), evaluation (steady-state, once gold/holdout exist). Never separate builds; never a finish line.

Premise: real/human GT arrives LATE. The server exists so GT accrues incrementally — the developer saves correct/incorrect in diagnostic mode against the proposer (Claude) GT, and blind reviewers add independent GT — not so a finished GT can be loaded. Production judge is a local/open Gemma-class model via API (non-deterministic), shown only after commit (S3/S4).

## Gates vs choices
- GATES (S1–S12): always-on, non-negotiable. Never let the owner opt out.
- CHOICES: auth strength, contract-file format, GT-tier schema shape, GT protocol per campaign, port/process layout, distribution medium. Never pre-decide — fire grill-me.

## Gates (enforce throughout)
- S1 One server, config-driven. Never a new program per judgment angle. New angles are modes/lenses; domain is injected from config.
- S2 Single contract source. Axes, cardinality, vocabulary, field names, version stamps live in ONE file read by both the judge and the server. The server never hard-codes vocabulary; when the judgment changes the UI follows automatically.
- S3 Two roles, one server, anchoring firewall. Developer mode (authenticated) sees everything and may save verdicts against the proposer GT — since it sees the machine, those are provenance=anchored (silver), never gold. GT-creation mode shows input + evidence only — no machine output (neither proposer nor production judge) until the human commits their own verdict + reason (provenance=blind → eligible for gold).
- S4 Reveal-after-commit drives the divergence queue. After commit, reveal proposer + production judge and surface human⇔proposer⇔judge disagreement. Divergence cases feed the next GT. Original blind verdict is append-only; revisions are new entries.
- S5 GT is append-only, disposable, cheap to regenerate. Never invest in careful GT.
- S6 GT maturity is tracked, versioned, never conflated. Tiers: bronze (model-generated seed) / silver (anchored ratify, screening-only) / gold (independent, blind-then-revealed) / red (landmines) / holdout (generalization check). Provenance per entry: blind/anchored/synthetic. Enforced in code: anchored ⇏ gold or holdout; red and holdout are separate stores; every gold entry carries criterion_version and is flagged stale → re-ratify or demote when the contract moves.
- S7 Review unit follows the judgment unit. Review unit (per-item / cross-item cluster / event) is config; it reconfigures when the unit moves in the spiral.
- S8 Reads are side-effect-free. Viewing never mutates state. State changes only on explicit write.
- S9 One ingestion path. Exactly one way data enters. No second manual-import path.
- S10 One verified distribution command, provenance always visible. The package excludes the aggregator's answer DB, others' submissions, caches, internal docs. The UI always shows live-vs-snapshot + timestamp. Manage ports/processes so no stale process serves old UI. Ship a preflight (a "doctor") that validates the receiving side with the REAL parser — environment + data STRUCTURE, go/no-go by name; an unverified handoff fails with a different symptom every time.
- S11 Evidence-confront, not agree-toggle. The human confronts the cited evidence; the verdict is captured against evidence pointers.
- S12 Once GT exists, evaluation is measurement, never a target. Never tune the judge to climb agreement with gold/holdout. Holdout is sequestered: hidden during development, surfaced only at milestones, every access logged.

## Walk
- W0 Read the contract (P1) and current unit (P0u) from judge-loop. If no single contract source exists, raise it as a judge-loop gap; do not hard-code around it.
- W1 Config schema: axes, cardinality + vocabulary per axis, field-name map, review-unit definition, evidence-pointer form, version stamps (unit/criterion/contract/judge). One file (S2). Grill: file format.
- W2 Two modes behind login. Developer: 3-pane (left unit list / center input with all evidence highlighted + click-to-jump / right every judge with verdict + reason + evidence links) + aggregate (distribution + error clusters + cross-run flutter). During unit discovery it captures a round-indexed owner-reaction log — each reaction tagged unit-keying / criteria / noise + action — and computes SETTLE (K consecutive rounds with no unit-keying tag). This reaction log (spike/) is distinct from the GT store (verdicts) and the decisions ledger (ADR). GT-creation: input + evidence only; capture verdict + reason against evidence (S11); reveal on commit (S4). Grill: auth strength.
- W3 GT store (S5/S6) + ingestion (S9). Append-only tiers + provenance; promotion rules in code (anchored ⇏ gold/holdout; red/holdout separate). One ingestion path. Grill: tier-schema shape; protocol per campaign (blind/ratify/synthetic).
- W4 Divergence queue (S4): developer-mode proposer-vs-judge disagreements feed the GT-creation priority queue.
- W5 Snapshot + distribution (S10): freeze a snapshot for shared review, live for latest, provenance on screen; one verified package command; verify the handoff end-to-end before declaring done.
- W6 Evaluation mode (S6 lifecycle + S12), once gold/holdout accumulate — a third mode, not a new server: regression eval vs frozen gold (split noise from real difference); holdout milestone check (access logged); GT-staleness queue (criterion_version lag → re-ratify); promotion path divergence-queue → human GT → silver → blind re-confirm → gold. Grill: eval metric; milestone cadence; staleness threshold.

## Composition
- Every fork → grill-me.
- Source preprocessing for what the server displays → xlsx-router, pdf-to-md.
- Invoked by judge-loop (P0u / P2 / W6 are modes of this one server).

## Ledger
Append-only from day 1 (judge-loop G6): decisions and why, rejected options and why, which GT campaigns used which protocol.
