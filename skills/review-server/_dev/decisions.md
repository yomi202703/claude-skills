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

## 2026-06-26 — port management: discovery + auto-written runfile, NOT a hand-kept ledger
Owner asked how to manage ports when several servers run (even within one project) and proposed a gitignored record folder in the skill. Rejected the hand-kept ledger: a parallel record drifts (the akatsuki F2 trap) and PIDs/ports change across restarts. Decided three layers, all auto/derived, none hand-edited:
- runfile `.review-run.json` written by the server at bind, next to the DB (instance side, NOT the skill — the skill is the reusable template; host runtime state there re-introduces template↔instance coupling). gitignored. Holds port/pid/cwd/db/contract_version/source/started_at.
- collision handling = probe-upward (grill answer): `bind_probe` binds from `--port` base upward to first free port (HTTPServer directly, no test-socket TOCTOU); actual port reported on screen + runfile, never assumed == base.
- "what's running where" = discovery, not storage: `--status` cross-references live LISTEN sockets (lsof) by cwd — the same identity signal used for the :8030 incident. Zero stored cross-project ledger.
base_port lives as the `--port` default (grill answer), NOT in contract.json — port is deployment config, contract is judgment vocabulary (keeps S2 clean).
runfile lifecycle = "leftover means crash": removed via atexit on normal exit + Ctrl-C; added SIGTERM→sys.exit(0) handler so `kill` also cleans up (atexit doesn't fire on SIGTERM). doctor.py warns on a leftover runfile (advisory, not a structural NO-GO). Verified: two servers collide 8500→8501 with distinct runfiles; runfile present while running, removed on SIGTERM; doctor GO, selftest PASS.

## 2026-06-27 — W7 rubric-frontier lens を文書追加(新ゲートにはしない・実装は据え置き)
発端: judge-loop 側で「要件 plan=凍結tree / その後のずれ=生成 frontier ビュー」を確定(judge-loop decisions/横断.md 2026-06-27、外部2AI chatgpt-web/gemini-web 非相関相談で「条件付き採用」一致)。レンダ先を review-server と名指したので、こちらの文書にも追加。
何を足したか: W7 = rubric-frontier レンズ(owner-audit ビュー)。基準の変遷を単一ソース(decisions + P4 atomic criteria ledger)から生成し、現行 active 基準=frontier と supersede 済み履歴を分け、各改訂に breaker ケース1件を添える。合流/分岐/失効を許す(因果でなく改訂履歴)。所有者の言葉のみ(内部 id/schema は別層)。Composition の judge-loop 行にも一句。
なぜ新ゲート(S13)にしないか: ゲートは あかつき失敗事例からの帰納で席を得る不変条件(docs/事例)。これは judge-loop からの演繹で失敗証拠がまだ無い。ゆえに S1(新角度はモード/レンズ・新プログラム化しない)に従う「生成レンズ」として、既存ゲートの下に置く — S2(単一ソースから生成・手編集禁止)・S8(読み取り副作用なし)・S3(進化中 rubric を blind /review に出すとレビュアーを anchor するので developer/owner 面限定)。
据え置き: template への実装はしない(ホストが基準変遷を監査したくなった時に W7 を建てる)。本エントリは文書追加の記録。判定の中身・既存 template コードは無改変。

## 2026-06-27 html-deck を判定/スコア面の描画規律として合成(layered, S3 gate)

何を足したか: Composition に html-deck を追加。判定/スコア面(diag 乖離キュー・evaluation・W7)の描画規律として呼ぶ。
層分け(S3 ゲート): diag/evaluation は html-deck 全適用(乖離キュー=判定表、evaluation=スコア表)。W7 は「相手の言葉/内部表現排除」＋craft。ブラインド /review は craft/可読性/相手の言葉 層のみ ── 判定描画層(verdict着色・機械結果のfunnel)を commit 前に当てると S3 を破るので firewall。reveal 後の乖離表示は全適用。
相互強化: html-deck「内部表現を出すな」は S2(サーバは語彙を contract から読む・ハードコードしない)が構造的に実装。S2 が原則5を仕組みに変える。
非衝突: tier pill(gold/silver/blind)は裏に数値の無い provenance メタゆえ html-deck が禁じる verdict チップではない。
実装(ダサさ改善・実コード変更): server.py BASE_CSS に funnel と数値整列(tabular-nums・td.num 右揃え)を追加。eval_page の一致/不一致/陳腐化を プレーンテキスト段落 → html-deck funnel(生数値を大きく、例外=不一致/陳腐化だけ着色、agree は中立)に。UI ラベルは contract 由来のまま(S2 不変)、描画のみ変更。selftest の gold 件数 scrape を新 markup(funnel .big)に追従。selftest 全green(S3 firewall テスト含む)。
据え置き: diag 乖離・/gt 表の生数値着色/右揃えフックの本格適用、/review の craft パスは未了(TODO 候補)。
