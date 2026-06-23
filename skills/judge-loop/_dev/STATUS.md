# judge-loop — STATUS

_現状スナップショット。セッションごとに書き直す。短く保つ。_

## 何のスキルか
- ドメイン非依存の薄いオーケストレータ。正解(GT)が事前に存在しない判定/採点/抽出ループの開発標準。
- 自分では判定の中身を指示しない。フェーズ検出 → 不変ゲート(G1–G9)強制 → grill-hook 発火 → 各 sub-skill へ routing、だけを足す。
- 実体は SKILL.md 一枚(プロンプト専用・scripts なし)。`docs/` がその一次資料。

## ドキュメント層の役割分担(混ぜない)
- `SKILL.md` … 配布される本体。蒸留済みの薄い標準。
- `docs/方法論_正解のないAI判定開発.md` … ドメインの WHY 台帳(working design)。SKILL.md が蒸留する元。
- `docs/あかつき判定_引き継ぎ資料.md` … 元事例(n=1)の確認済み事実・歴史・教訓。
- `_dev/` … このスキル自体の開発ワークエリア(本フォルダ・四役ガバナンス)。

## いまの状態
- 骨格は一周完了。ゲート G1–G9 と Scaffold→P0.0→P0u→P1→P2→P3→P4→GT-established のフェーズ routing、Cores が揃っている。
- 出自は n=1(あかつき1ドメイン)。最大の未解決リスク = 別ドメインで各ゲート/フェーズを当てた overfit 検出(docs/方法論 §6・留保)。
- 直近の更新(git):
  - 6d1c15e — decisions/archive 全読(jibun-de)の蒸留を framework へ折り込み(N1–N6/S1/S3/S5)。
  - 9d49b54 — run-ledger(第5記録型)+ P4 の G8 entry-gate を追加。
  - bc62dfb — judge-loop + review-server を新設、claude-md を repo-memory scaffold へ拡張。

## このセッション(2026-06-23)
- _dev/ 開発ガバナンス層を新設(四役)。
- SKILL.md ⇔ docs/方法論 整合チェック実施。蒸留は忠実。ドリフト1件(docs §6 に task-handoff composition 欠落)を発見し解消。詳細は decisions/横断.md。
- G7 を書き直し: 二分法(計器=早/他=遅)→「単位依存度で時を決める」gate 型の問い。現 G7 の内部矛盾(取り込みまで遅らせてしまう)を解消。SKILL.md・docs §5 両方反映。grill-me で詰めた結果は decisions/横断.md。

## 次の一手
- TODO.md 参照(磨く項目)。大半は別ドメイン着手まで Deferred。
