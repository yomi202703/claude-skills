# review-server template

Domain-agnostic skeleton of the single shared review server. Standard library only. Code is a template — adapt the two marked points, run, distribute.

## Adapt (only these)
- `contract.example.json` → your single contract source (S2): axes, vocabulary, cardinality, review unit, version stamps. Copy to `contract.json` if you want; the server loads `contract.example.json` by default — repoint in `server.py:CONTRACT` if renamed. Axis labels/vocabulary are the domain's own words — write them in the reviewers' language.
- `data.py` → replace `DemoAdapter` with a real read-only adapter over your judgment outputs (S8). Keep the `Adapter` method signatures; `server.py` stays unchanged.

## Language
The judgment vocabulary/axes come from the contract (above). The surface's fixed chrome (mode names, button text, footer) lives in ONE dict — `server.py:UI` — default Japanese. Translate the chrome by editing that dict only; gate codes (S3/S4 …) stay in code comments and never reach a reviewer's screen.

## Do NOT touch (the gates live here)
- `store.py` — append-only, tiers + provenance, `anchored ⇏ gold/holdout`, version stamps required, holdout reads logged (S4/S5/S6/S12).
- `server.py:review_page` — never calls `judges()`; the anchoring firewall (S3). `commit` reveals only after storing the blind verdict (S4).

## Run
- `python3 server.py` → http://localhost:8030/. No login: the landing page picks a mode by route. The anchoring firewall is render-time (S3), not auth.
- `python3 server.py --snapshot` → freeze a snapshot provenance marker; serve with `REVIEW_SOURCE=snapshot`.
- `python3 server.py --package` → distributable zip, excludes the answer DB / inbox / caches (S10).
- Ingestion: drop reviewer CSVs in `inbox/`, POST `/ingest` — the one path (S9).

## Verify
- `python3 doctor.py` → S10 receiver-side preflight: structural go/no-go run with the REAL parser (contract + data.py adapter shape + store gate). Run this before trusting a handoff.
- `python3 selftest.py` → developer smoke test: boots the server on an ephemeral port against a throwaway DB and exercises the whole loop (firewall holds, commit → promote → eval gold rises). Run after adapting `data.py` to confirm you did not break the contract.

## Modes (chosen by route, no login)
- GT-creation (`/review`): input + evidence only → commit → reveal + divergence. Deliberately minimal (anti-IDE — the firewall demands an information-poor view, S3/W2). Evidence is picked by clicking the actual input lines (not typing line numbers). Commits land as provenance=blind, tier=silver.
- Diagnostic (`/diag`): developer 3-pane SPA — unit list (search box + "divergent only" filter + divergence badges) / input+evidence / every judge per axis — plus a persistent Problems pane (the divergence queue) and `j`/`k` keyboard nav. Each judge's `[idx N]` evidence pointer is click-to-jump (scrolls + flashes the input line). Vanilla JS over read-only `/api/units` + `/api/diag/<unit>` (judges ARE exposed here; the firewall binds `/review`, not `/diag`). The DemoAdapter ships 6 units × 2 axes with agreement/divergence mixed.
- GT management (`/gt`): developer surface that promotes independent blind verdicts silver → gold (S6), so eval has gold to measure against. `anchored ⇏ gold` is enforced in `store.promote`. This closes the loop: commit (blind) → `/gt` promote → `/eval` measures gold vs the production judge.
- Evaluation (`/eval`): regression vs gold, stale-gold, holdout access log — measurement, not a target (S12).
- Reviewer attribution defaults to `anon`; auth + named reviewers are a later grill hook, added only when untrusted external blind reviewers arrive.

## Not built (host adds per campaign)
- The anchored/ratify GT surface (fast silver path): `store.py` accepts `provenance="anchored"`; add a surface that shows the proposer reason. It can never produce gold/holdout (enforced).
- Real auth, multi-reviewer aggregation, cross-unit cluster review unit (re-key via `contract.unit`).
