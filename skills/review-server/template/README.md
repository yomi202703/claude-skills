# review-server template

Domain-agnostic skeleton of the single shared review server. Standard library only. Code is a template — adapt the two marked points, run, distribute.

## Adapt (only these)
- `contract.example.json` → your single contract source (S2): axes, vocabulary, cardinality, review unit, version stamps. Copy to `contract.json` if you want; the server loads `contract.example.json` by default — repoint in `server.py:CONTRACT` if renamed.
- `data.py` → replace `DemoAdapter` with a real read-only adapter over your judgment outputs (S8). Keep the `Adapter` method signatures; `server.py` stays unchanged.

## Do NOT touch (the gates live here)
- `store.py` — append-only, tiers + provenance, `anchored ⇏ gold/holdout`, version stamps required, holdout reads logged (S4/S5/S6/S12).
- `server.py:review_page` — never calls `judges()`; the anchoring firewall (S3). `commit` reveals only after storing the blind verdict (S4).

## Run
- `python3 server.py` → http://localhost:8030/ (dev password = env `REVIEW_DEV_PASSWORD`, default `dev`).
- `python3 server.py --snapshot` → freeze a snapshot provenance marker; serve with `REVIEW_SOURCE=snapshot`.
- `python3 server.py --package` → distributable zip, excludes the answer DB / inbox / caches (S10).
- Ingestion: drop reviewer CSVs in `inbox/`, POST `/ingest` (developer) — the one path (S9).

## Modes
- GT-creation (reviewer login): input + evidence only → commit → reveal + divergence.
- Diagnostic (developer login): 3-pane + aggregate divergence queue.
- Evaluation (developer): regression vs gold, stale-gold, holdout access log — measurement, not a target (S12).

## Not built (host adds per campaign)
- The anchored/ratify GT surface (fast silver path): `store.py` accepts `provenance="anchored"`; add a surface that shows the proposer reason. It can never produce gold/holdout (enforced).
- Real auth, multi-reviewer aggregation, cross-unit cluster review unit (re-key via `contract.unit`).
