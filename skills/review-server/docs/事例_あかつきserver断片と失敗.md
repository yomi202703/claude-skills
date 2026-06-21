# 事例 — あかつき server 断片と失敗（review-server の元ネタ）

review-server スキルのゲート S1–S11 は、すべて lab_akatsuki_pipeline で実際に払った授業料の反転。
ここはその一次資料(decisions 台帳・コード)の記録。抽象論は SKILL.md、こちらは具体。
あかつきは「畳むべき sprawl の実例」であって、複写すべきテンプレではない。

## 0. この資料の根拠範囲

実読した一次資料:
- `factcheck/成果物/decisions.md`(全文) — 人手GTサーバーの最も成熟した試みの全経緯。
- `pipeline_13_音声判定統合/成果物/STATUS.md`・`decisions/{認知,横断,規制遵守,主体性心情,callfacts銘柄}.md` の server/viewer 関連エントリ。
- `archive/decisions_pre-split_2026-06-13.md` の review_server/labels.json 廃棄エントリ(5400-5402)。
- 各 server/viewer の docstring とポート定義(grep 実測)。

## 1. server 断片の棚卸し（実在）

開発者側(診断系・pipe13):
- `common/viewer.py` :8012 — 本体3ペイン・5871行。実行＋judge＋閲覧が全部入り。
- `ninchi/eval/cog_xcall_viewer.py` :8031 — 認知の通話横断診断。
- `ninchi/eval/cog_keydiff_viewer.py` :8034 — 2キー(銘柄,aspect)vs(銘柄)の A/B。
- `ninchi/eval/cog_flutter_viewer.py` :8015 — K-run の判定ブレ可視化。
- `ninchi/eval/cog_gt_label_server.py` :8040 — 認知GTラベリング(開発者がGTを作る)。
- `kiseishuuji/checklist_viewer.py` :8020 — 規制チェックリスト閲覧。
- `kiseishuuji/keishiki_check_viewer.py` :8026 — 形式チェック画面。
- `norikae/norikae_dashboard.py` :8020-8022 — 乗換ダッシュボード。
- `common/render_review.py` — 内部レビューHTML生成(静的)。
- 削除済: ab_review_server / prohib_run3x_viewer / run3x_viewer / ab_diff_viewer(experiments 群・本番移植後撤去)。

人間側(GT作成系):
- `factcheck/server.py` :8020 — 人手GT作成。最成熟(追記オンリー・snapshot・配布・反対時独立ラベルまで到達)。
- 削除済: review_server.py — 「使い捨て」で停止・削除。labels.json GT は「厳しすぎる」と2回廃棄。

ポート衝突: 8020 が factcheck/checklist/norikae の3重複・8031 が cog_xcall と旧 prohib で2重複。

## 2. 失敗の抽象（S ゲートとの対応・出典つき）

- S1 ← F1 一問ごとに新サーバー増殖。検証角度(横断/keydiff/flutter/checklist/形式/乗換/禁止)ごとに別プログラム→多くが使い捨て→削除・ポート衝突。
- S2 ← F2 UI が判定契約から遅れ陳腐語を再導入(最重要)。認知2値化後も factcheck が廃止語「懸念あり」を再導入(decisions 2026-06-21・line 102)。aidata が旧フィールド名(shutaisei/torihiki)を読み主体性・心情が全件空表示=人間レビュー不能(2026-06-19・line 14)。
- S9 ← F2 同根の波及: 契約がコード多所に焼かれ1変更が server.py＋aidata.py＋questions.yaml＋README＋screens.md を毎回同期。
- S3 ← F3 アンカリング。AI判定を先見せで賛成9割(Q1a93%/Q2a83%/Q3a94%)・情報は反対35件に偏在(2026-06-19・line 41)。対策「反対時のみ理由＋独立ラベル必須化」に到達。後の裁定: アンカリング ≠ eval汚染。Claude を見せても同じ9割が再生産=commit まで全機械出力を隠す、が結論。
- S4 ← 食い違いキューは factcheck が「口座横断パネルは別タスク」と先送りした当の機能(2026-06-21・line 109)。
- S5 ← F5 GT を careful に作り投資し廃棄で高くついた。labels.json 2回廃棄・review_server 使い捨て(archive 5400-5402)。「高くついたのは GT を作ったことでなく投資したこと」。
- S6 ← labels.json は「厳しすぎる(サインあり過剰・同一記述が軽度/サインあり両方に揺れる)」と裁定され較正基準として不採用(archive 5400)。anchored と independent、red と holdout を混ぜると検証が壊れる。
- S7 ← F4 レビュー単位が AI 主張単位とズレ。認知は本質 cross-call(口座×銘柄×密クラスタ)だが UI は per-call Q3a＋一語Q5 のまま(2026-06-21・line 109)。
- S8 ← F7 read が状態を変えた。通話一覧GETが自動 claim→一括GETで29口座が一斉作業中化(2026-06-19・line 76)。
- S9 ← F6 取り込み二重化。手動 import 画面と inbox 自動取込が重複→手動撤去(2026-06-20・line 93)。
- S10 ← F8 配布・再現が未検証で症状が毎回違う。素 zip が回答DB・他人CSV・__pycache__ を巻き込む(2026-06-21・line 147)。live/snapshot 混同で footer 明示が必要に(line 141)。旧プロセス残留で 404(2026-06-19・line 77)。
- S11 ← 賛否トグルだけでは情報が残らず誤り事例化できなかった→「反対時は理由＋正しい評価を必須」へ(2026-06-19・line 41)。Claude/Gemma は plausible に作話するため reason vs 証拠 の確認を強制。
- S12 ← 予防的ゲート(あかつきでは未実証)。あかつきは安定した gold GT に到達せず(labels.json は2回廃棄=archive 5400)、「GT 確立後に judge をスコアへ寄せる/holdout を繰り返し覗く」失敗は実際には踏んでいない。だが judge-loop G3/G9(judge は reward でない・holdout は最後だけ)が壊れるのは GT ができた瞬間で、その時に足すのでは遅い=GT 存在前に焼くべきゲートとして先置きした。根拠は史実でなく judge-loop 本体のゲート。

## 3. 人間にとっての理想形（抽象・S の総合）

factcheck/server.py の到達点(追記オンリー・snapshot・配布・反対時独立ラベル)を、
ドメイン非依存・契約単一ソース・単位可変・2ロール防火壁・commit後開示 に昇格させた1サーバー。
今ある9断片は、この1サーバーの「レンズ/モード」に畳める。

GT protocol は成熟度ごとに分岐(grill hook):
- gold/holdout(汎化検証の本物): ブランクスレート＋commit後開示。独立性が命。
- silver/triage(量・粗スクリーニング): Claude理由を見せ高速 ratify・anchored タグ・gold/holdout へ昇格禁止。
- bronze: モデル生成のみ・人間なし(使い捨ての種)。
不変条件(ゲート): anchored≠independent・red≠holdout を別管理し混ぜない・汎化主張は independent のみ。

## 4. GT-established レジーム（steady-state・予防設計）

GT 確立は終端でなく、同一サーバーが第3モード(評価)を獲得するだけ。基準は螺旋で動き続け、cadence が落ちるのみ。
- 回帰評価: 現 judge vs 凍結 gold・差はまずノイズか実差か切り分け(P3 K-run 共有)。スコアは測定であって目標でない(S12)。
- holdout マイルストーン検査: 普段触らず節目だけ・アクセスはログ(S12=開発者側の防火壁・S3 の対称)。
- GT 鮮度: gold は criterion_version を持ち基準が動けば stale→再 ratify か降格(S6)。GT は腐る減衰資産。
- 昇格経路: 食い違いキュー→人手GT→silver→(blind 再確認)→gold・anchored⇏gold 据置。
- 指標・cadence・stale 閾値は grill hook(設計時に焼き込まない)。
注: このレジームのゲート S12 はあかつき未実証の予防設計(2章 S12 参照)。

