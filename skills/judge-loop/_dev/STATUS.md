# judge-loop — STATUS

_現状スナップショット。セッションごとに書き直す。短く保つ。_

## 何のスキルか
- ドメイン非依存の薄いオーケストレータ。正解(GT)が事前に存在しない判定/採点/抽出ループの開発標準。
- 自分では判定の中身を指示しない。フェーズ検出 → 不変ゲート(G1–G10)強制 → grill-hook 発火 → 各 sub-skill へ routing、だけを足す。
- 実体は SKILL.md 一枚(プロンプト専用・scripts なし)。`docs/` がその一次資料。

## ドキュメント層の役割分担(混ぜない)
- `SKILL.md` … 配布される本体。蒸留済みの薄い標準。
- `docs/方法論_正解のないAI判定開発.md` … ドメインの WHY 台帳(working design)。SKILL.md が蒸留する元。
- `docs/あかつき判定_引き継ぎ資料.md` … 元事例(n=1)の確認済み事実・歴史・教訓。
- `_dev/` … このスキル自体の開発ワークエリア(本フォルダ・四役ガバナンス)。

## いまの状態
- 骨格は一周完了。ゲート G1–G10 と Scaffold→P0.0→P0u→P1→P2→P3→P4→GT-established のフェーズ routing、Cores が揃っている。
- 出自は n=1(あかつき1ドメイン)。最大の未解決リスク = 別ドメインで各ゲート/フェーズを当てた overfit 検出(docs/方法論 §6・留保)。
- 直近の更新(git):
  - 6d1c15e — decisions/archive 全読(jibun-de)の蒸留を framework へ折り込み(N1–N6/S1/S3/S5)。
  - 9d49b54 — run-ledger(第5記録型)+ P4 の G8 entry-gate を追加。
  - bc62dfb — judge-loop + review-server を新設、claude-md を repo-memory scaffold へ拡張。

## このセッション(2026-06-23)
- _dev/ 開発ガバナンス層を新設(四役)。
- SKILL.md ⇔ docs/方法論 整合チェック実施。蒸留は忠実。ドリフト1件(docs §6 に task-handoff composition 欠落)を発見し解消。詳細は decisions/横断.md。
- G7 を書き直し: 二分法(計器=早/他=遅)→「単位依存度で時を決める」gate 型の問い。現 G7 の内部矛盾(取り込みまで遅らせてしまう)を解消。SKILL.md・docs §5 両方反映。grill-me で詰めた結果は decisions/横断.md。
- review-server のログインを前倒し設計から外した。役割=ログイン → モード=ルート選択(/diag・/review、既定で認証なし)へ格下げ。アンカリング・ファイアウォール(S3)は RENDER-TIME 構造なので無傷で残る(smoke test 済)。認証は外部 blind レビュアー投入時の後出し grill hook。反映: review-server SKILL.md・template/server.py・README.md。詳細は decisions/横断.md。
- G10 新設: 書いた/直した LLM 実行プロンプトは全文をオーナーに提示し明示の承認を得てから初めてパイプライン投入(非交渉)。Claude は自己承認も黙った投入もしない。全 LLM 実行プロンプト対象・judge-loop(gate)＋gemma-prompt(7か条7項目め)両方で強制。オーナー=審級の前提からの演繹で n=1 リスク無し。反映: judge-loop SKILL.md・gemma-prompt SKILL.md・docs §5/§6。詳細は decisions/横断.md。

## このセッション(2026-06-24)
- S1 スコープ訂正(一次資料で裏取り): 乱立は開発者側9断片・人間GT作成は factcheck 1つ=anti-sprawl の根拠は人間面に無い。S1 を開発診断面に限定し、ファクトチェッカー面は引き渡し可能な別成果物に分離可とした。跨ぐ不変=S2(生成契約)・S9(GT戻し1経路)・S6。最重要失敗 F2 は分離人間サーバの契約ドリフトゆえ「分けるな」でなく「契約を複写するな」。防火壁は不在による隠蔽が最強形(前ターン auth 弱点を上書き)。反映: review-server SKILL.md・docs/事例3章・judge-loop SKILL.md P2/Composition。詳細は decisions/横断.md。

## このセッション(2026-06-24・自律度軸)
- フェーズ軸に直交する二次元目=自律度軸 L1→L2→L3 を設計確定(grill-me)。ペーシング(人間が律速)と審級(人間が裁く)を分離=人間をペーシングから外すが審級からは外さない(G3/G10 不変)。
- L2=claude×gemma×claude 裁定(外部アンカー照合で裁定者バイアス回避・gemma=脱相関)。L3=コンサル役(逆向き要件定義・priors free/evidence bound・境界認識/steerable・探索と製錬を分離=原石はノイズからしか生まれない・出口=提案軸+動機ケース・no-GT 限定・提案のみ)。
- 案A(標準を SKILL.md に書く)採用・案B(動くコンサル即 build)却下。L3 は別スキル `consultant`(単独で立つ/judge-loop は composed-by)へ routing=薄さ堅持。
- task-handoff で2兄弟に fan out 発行: `_dev/handoff/`(foundation + autonomy-axis + consultant-skill + registry)。両者 cold-restart 可・並列走行。詳細・grill-hook 却下は decisions/横断.md。

## このセッション(2026-06-27・handoff 回収)
- handoff 2兄弟を回収・ratify(G6)。consultant=仕様一致で妥当。autonomy-axis=発行後ドラフトが SKILL.md へ未着地のまま滞留していたのを発見→凍結設計どおり最小差分で着地(新節「Autonomy axis」L1/L2/L3 + Composition に L3→consultant 結線)。着地時 hash=発行時 e0b94af 一致でドリフト無し。registry 両 state を回収済みへ。詳細 decisions/横断.md 2026-06-27。

## 次の一手
- handoff ストリームは2本ともクローズ。磨き項目は TODO.md 参照。大半は別ドメイン着手まで Deferred。
