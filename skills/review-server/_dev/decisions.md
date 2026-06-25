# review-server _dev — decisions

Append-only ADR ledger for the review-server skill and its `template/`. Why a choice was made and what happened. Never rewrite past entries.

## 2026-06-25 — "質素" is two causes, not one
Owner found the template bare. Split (grill-me gate): `/review` is INTENTIONALLY minimal (S3 firewall / W2 anti-IDE) — not a defect, do not "fix"; `/diag` was plain because W2's 3-pane was unbuilt — a real gap. Decided: build the dev 3-pane, keep GT-creation minimal.

## 2026-06-25 — /diag = stdlib 3-pane SPA
Single-page 3-pane (unit list / input+evidence / every judge) + Problems pane + j/k nav, vanilla JS over read-only `/api/units`,`/api/diag`. No build/CDN → preserves the S10 handover gate. Deferred (need K-run / A·B data W2 also defers): native diff, flutter, editor integration. Judges exposed on `/diag` only; `/review` never loads them.

## 2026-06-25 — full JP chrome in one UI dict
Owner: English chrome unreadable. All operator-facing text → Japanese, collected in `server.py:UI`; gate codes (S3/S4…) kept in comments, off-screen. Demo contract+data also JP. Rationale: vocabulary/axes come from the contract (S2); chrome is separate and must translate in one place.

## 2026-06-25 — design pass, substrate kept
Owner: "ダサい", questioned the build approach. Decided: real CSS via one shared token sheet (`BASE_CSS`), no external fonts/CDN. Told owner: ugliness was styling, NOT substrate — stdlib-HTTP+hand-HTML is the deliberate inversion of the akatsuki distribution failures (S10); changing it collides with the one-command-handoff gate. Owner chose fix-the-look, keep-stdlib. Approved.

## 2026-06-25 — bug: non-ASCII unit_key not decoded
Japanese keys (通話-002) came through percent-encoded → empty input/judges. Fixed: `unquote` path segments server-side; `decodeURIComponent` the SPA deep-link. Masked by the ASCII demo; a real domain hits it immediately → fix in template, not per-host.

## 2026-06-25 — loop closure via /gt
`commit` hard-coded silver and nothing produced gold, so `/eval` was always gold=0 — the blind→gold→eval loop couldn't run. Added `/gt`: promote blind silver → gold (POST `/promote/<id>`); `anchored ⇏ gold` stays in `store.promote`. Verified commit→promote→eval gold=1. Still not built: anchored/ratify fast-silver surface; blind re-confirm before gold; multi-reviewer aggregation.

## 2026-06-25 — scale: client-side search + divergent-only filter
Real domains have hundreds of units; the list had no search/filter and `api_units` computes divergence per unit×axis each load. Added client-side search + "食い違いのみ" + count; documented the cost and pushed judge/divergence caching to the host's `data.py` (correctness-sensitive, not pre-baked).

## 2026-06-25 — evidence is click, not typed
GT-creation made reviewers TYPE line numbers; W2's click-to-jump was unbuilt. Now: GT-creation lines are click-to-select; diagnostic `[idx N]` is click-to-jump (S11 — confront the actual line).

## 2026-06-25 — S10 doctor + smoke test; store made thread-safe
Added `doctor.py` (S10 receiver preflight: structural go/no-go via the real parser) and `selftest.py` (boots the server, checks firewall + commit→promote→eval); `REVIEW_DB` env override. selftest found `sqlite3.connect` defaulting to `check_same_thread=True` (dies off the opening thread) → fixed `check_same_thread=False` (single-threaded server + GIL serialize). doctor GO, selftest PASS.

## 2026-06-25 — ENVIRONMENT: a real review server runs on :8030
Port 8030 is held by a SEPARATE real server (not the template): `~/Projects/lab_akatsuki_pipeline/pipeline_13_音声判定統合/gourisei_review_server/server.py` (landing references review/judge/contract — the S1-split shape). PID changes across restarts (69370→50405); identify by cwd. Ran the template on 8033 instead; left 8030 untouched.
Open question (owner judgment, not started): grow the template, or bring the 8030 server onto the standard (S2/S3/S6/S9)? The akatsuki F2 lesson — a separate human server re-encoded the contract and drifted — is exactly this case. Next step if pursued: read that server + its contract handling, map the gap to the gates.
