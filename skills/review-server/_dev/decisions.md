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

## 2026-06-27 分離FC引き渡しパッケージの参考例を examples/ に追加(Deferred は閉じない)

発端(オーナー): grill で「judge-loop 起点で開発者面とFC面の両方を作る前提では」と提起。一次資料確認の結果、現状すでに前提でなく CHOICE 化済み(2026-06-24 judge-loop 横断.md: S1 開発者面限定・FC面は別成果物可)で、別スキル起こしは G7 premature として TODO Deferred 済みと判明。オーナー「じゃあ参考例としてサーバーを作ってみて」。

何を足したか: examples/fc-handover/ に分離成果物型(別パッケージ)の動く参考例。template/ が同居型(防火壁=render時・/review が judges を呼ばない)なのに対し、こちらは 防火壁=不在 を実演 ── build_package.py が judges() を一度も呼ばず units の input+evidence だけを抜くので、パッケージに機械の答えも judges() 関数も存在しない(S3 最強形)。fc_server.py はブラインド面のみ(reveal 経路自体が無い)。
跨ぐ不変を実コードで実演: S2=契約は単一ソースから生成(_generated スタンプ・手編集禁止)、S9=/export の CSV 列が dev /ingest と完全一致し同じ Store.append を通って戻る、S6=生むのは provenance=blind のみで gold 化は dev 側。
検証: selftest.py が build→S2生成スタンプ→S3不在(data に機械出力なし・code に judges() なし)→commit→S9往復(吐いた行が dev store に取り込まれ blind→gold 昇格可)まで端から端まで通す。実起動 smoke でブラインド面の機械出力ヒット0・契約由来の軸ラジオ表示・export=inbox CSV も確認。PASS。

なぜ template を増やさないか: これは維持対象の正準テンプレートでなく example。S1(乱立させない)に従い template/ は1つのまま、分離型は「こう分けてよい」の例示として別ディレクトリに隔離。dist/・fc_gt.db は gitignore(生成物)。

閉じないもの: judge-loop TODO Deferred「FC面を別成果物/別スキルとして起こす[トリガ=外部FC実投入&campaign痛反復]」は据え置きのまま。本例は方法論実演であって本番起こしではない。判定の中身・既存 template コードは無改変。

追記(同日・オーナー指摘): commit 後の「保存しました/次へ」中間ページを撤去し、確定→次の未確定ユニットへ 303 直行(保存通知は遷移先上端の細い帯のみ)に変更。根拠=この分離型は防火壁が不在で reveal 経路が無いため、中間ページは情報ゼロ＋1ユニットあたり1クリックの純粋な摩擦。設計点として一般化: 同居型 template/ は commit 後に機械判定を reveal(S4) するので中間ページは有意=撤去しない。「commit 後に出すものがあるか」が両形の分岐。最小面(S3/W2)は「情報を貧しく」だが「無駄に遅く」ではない＝advance-on-submit は IDE 肥大化でなく摩擦除去。redirect 後も機械出力ヒット0を smoke 確認・selftest PASS。

追記4(同日・オーナー指摘): 軸設計の見直し＋例を template から切り離し。①2軸目 evidence_quality(根拠の質)を削除 ── これは元々ドメイン的必然でなく「多軸 config-driven を見せるためのデモ2本目」(template contract のコメント "Adapt or delete per domain")。オーナー「普通にいらない」。②判定軸を binary(要確認/問題なし)→3値 ○/△/× に。表現はケース依存(S2 ＝ 語彙は契約で持つ)。③理由枠を1行 input→textarea に。④確定済みを再訪すると 自分の前回判定(verdict/理由/根拠)を初期表示し改訂可(append-only)。
切り離しの判断: これらは契約(単一ソース)変更。template/contract.example.json を直接いじると template/data.py の judges fixtures(要確認/問題なし/十分/薄い…全件)と template デモ全体へ波及し、維持対象を巻き込む。オーナーが触っているのは fc-handover の例なので、例に自前の単一ソース source/{contract.json,units.json} を持たせ template から decouple。build_package.py は source/ から生成するよう書き換え(S2 の筋＝単一ソース→生成コピー→dist 手編集禁止は保持)。S9 往復(selftest)は dev 側 store.py へ取り込む形のままで、語彙非依存ゆえ ○/△/× でも通る。
検証: selftest PASS(axes=['judgment']・v2)。UI smoke=単軸 v_judgment の ○/△/× radio・reason は textarea・evidence_quality 消滅・再訪で前回○ checked＋理由プリフィル・一覧は「判定: ○ ・理由: …」。template 側は無改変。

追記3(同日・オーナー指摘): 一覧(index)を、確定済みユニットについて レビュアー自身の判定(軸別)＋理由＋✓判定済/未判定 を表示する形に変更(従来は素のリンク＋✓のみで進捗・自分の判定内容が見えなかった)。S3 との切り分けを明記: S3 が禁じるのは commit 前に 機械の出力 を見せること。表示するのは レビュアー自身が確定した自分の判定＝機械出力でないので firewall 違反でない。未判定ユニットには何も出さない(機械の答えはそもそも存在しない)。確定済みもリンクは残し再判定可(append-only=改訂は新行・store.latest_by_unit が最終行採用)。検証: 2件確定後 index に軸別判定＋理由＋2/6完了が出る・機械出力ヒット0・selftest PASS。設計点として一般化: ブラインド面で「自分の過去判定の表示」は firewall に抵触しない(機械出力でない)。進捗・自己一貫性の確認に必要なので出してよい。

追記2(同日・オーナー指摘): レビュアー面の「GTをエクスポート（CSV）」リンクを撤去。根拠=判定は commit 時点で内部(fc_gt.db)に自動保存されており、レビュアーの関心事は「判定する→保存される」だけ。export はレビュアーが押すボタンでなく、返却パッケージから GT を回収して開発側へ戻す オペレータ操作。設計点として一般化: レビュアー面に出すのは「レビュアーがやること」だけ。永続化は副作用として自動、回収/戻し(S9)はオペレータの面に分離する。実装=GET /export ルートと export リンクを削除し、export を `fc_server.py --export [PATH]` の CLI(オペレータ)へ移動(列は dev /ingest と完全一致のまま)。selftest は新 module 関数 export_inbox_csv() を直接呼ぶ形に更新(旧 dummy-handler ハック撤去)。検証: index に export 文言0・GET /export=404・CLI export が同一 fc_gt.db を読んで inbox CSV 出力・selftest PASS(S9往復含む)。

## 2026-06-27 例 fc-handover を別スキル factcheck へ昇格（このリポから移設）
追記1〜4(同日)で育てた examples/fc-handover は、オーナー裁定で独立スキル `factcheck` に昇格し `factcheck/template/` へ移設（理由=skill としての鋭さ＋汎用、judge-loop 横断.md 2026-06-27）。review-server は「開発者の単一サーバ＋ S1-S12 所有」に純化し、別成果物（ブラインド引き渡し）の形は factcheck へ compose で委譲（SKILL.md description/S1/S3/CHOICES/Composition を更新）。factcheck は gate を再所有せず S2/S6/S9 を本スキルから借りる（F2 回避）。examples/ ディレクトリは廃止。以後この形の更新は factcheck/_dev に記録。

## 2026-06-27 同居型ブラインド面(/review)を撤去 — S3 改訂（オーナー裁定）
発端(オーナー): 「レビューサーバーは GT作成(ブラインド)いらない。機能から外れたものでしょ、もう」。factcheck を切り出した今、review-server に残る /review(render-time 防火壁)は冗長。
裁定根拠(tidy 以上): render-time ブラインドは弱い。/review は judges を描かないだけで auth 無し＝同じ人が別タブで /diag を開けば答えが見える＝その gold は覗ける汚染疑い。factcheck の不在防火壁は答えが無いので auth 無しで構造的に強い＝上位互換。S3 の「render-time or by-absence」併記はブラインドに関して by-absence 一本へ畳む。
決定: review-server は開発者専用に純化＝diagnostic(/diag)＋GT管理(/gt: ingest+promote)＋evaluation(/eval)。ブラインド/gold 生成は factcheck だけ。dev サーバ上の人間判定は anchored→silver のみ(store.ALLOWED で担保)、gold には factcheck からの blind 流入を /ingest(S9)→/gt 昇格で。
実装(template): server.py から /review・/commit・units_page・review_page・commit・highlight/highlight_clickable/render_judges・ランディングと /diag ナビの /review リンク・死んだ UI 文字列(mode_gt/gt_*等)を削除。landing/bar を開発者ナビ(diag/gt/eval)へ。docstring と S3/S4 コメントを「防火壁は factcheck の不在側」に改訂。selftest を blind 依存から S9(inbox CSV→/ingest)→/gt promote→/eval gold 上昇へ組み替え＋ /review・/commit が 404 を確認。検証: 構文OK・selftest 全green・/review,/commit=404・/diag,/gt,/eval,/ingest 健在・ランディングに /review リンク0。
SKILL.md 改訂: description/Three-modes/CHOICES(ブラインド面 form は choice でなく factcheck 固定)/S3(不在防火壁・render-time 撤退)/S4(reveal-after-commit 廃止→divergence は dev 側、人間 GT は flow-back 後)/W2/W4/W7/Composition(html-deck blind 層・judge-loop 行)を factcheck 委譲に統一。factcheck/SKILL.md と judge-loop SKILL.md(P2/Composition)も render-time 撤退に追従。
判定の中身(contract/judges fixtures)は無改変。これは S3 ゲートの改訂＝オーナー裁定として記録(G6)。

## 2026-06-27 ランディングのチューザー撤去 — / は /diag に直着地
発端(オーナー): 「開発者診断/GT管理/評価の3つに分ける landing、なんで？」。3モード自体はライフサイクル(診断→GT管理→評価)の別レンズで1サーバ(S1)＝妥当。だが「下記を選択してください」のチューザー landing は、本セッションで潰してきた無駄な中間画面と同型(バーに既に3つある)。
決定: landing_page を撤去し、do_GET の `/` を 302 で /diag(主面)へリダイレクト。/gt・/eval はバーから。3モードは残す。死んだ pick_mode UI 文字列と .modes CSS も除去。
据え置き(任意): /gt(管理)と /eval(測定)は GT ストアの別ビューゆえ将来1面2セクションに畳める余地。/diag はユニット単位検査で本質別。今回は触らない。/aggregate(乖離の素リスト)は /diag の Problems と重複し未リンク化したが今回は残置(別掃除)。
検証: selftest 組み替え(「/ が /diag に着地」= raw マーカー `<body class=diag>` で判定。JSON labels は \u エスケープされるため raw を使用)→全green。doctor GO。/ →302 /diag・チューザー文言0。
