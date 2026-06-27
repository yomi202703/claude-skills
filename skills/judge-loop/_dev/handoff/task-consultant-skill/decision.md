# decision — task-consultant-skill

append-only。このタスクの思考台帳。発行時に founding rationale を seed。

## 2026-06-24 — 発行(founding rationale)

- 発行元: judge-loop 自律度軸の grill-me セッション。L3(自己起案=コンサル)が独立スキルに値すると確定。
- なぜスキルにするか: 「task-handoff で渡した後にコンサルとして動く必要がある」=渡された先で自走するプロンプトが要る(オーナー指示)。judge-loop は薄いので中身を持てない——L3 の中身はここに来る。
- 設計の核心(grill で潰した順): ①「コンテキスト無関係」→ ②priors free / evidence bound(占い回避)→ ③境界認識・steerable(要件を知るからこそ外を探索・距離はメインが振る)→ ④探索と製錬の分離(原石はノイズからしか生まれない=探索を刈るな・製錬は内部・出口だけ固定)。詳細は foundation.md。
- 命名(2026-06-24 オーナー裁定): `consultant`。`prospect`・`konsaru-tan`(コンサルたん)案はいずれも却下、素直な consultant に確定。
- スコープ昇格(2026-06-24 オーナー): 「単独でも役に立つ」→ judge-loop L3 専用部品でなく独立スキルへ。description は judge-loop 非依存で自立させ、judge-loop は composed-by(review-server/gemma-prompt と同位)。誰でも直呼び可。
- 未決/留保: ①探索の fan out 上限/コスト天井をスキルに焼くか、use-time の grill-hook に回すか(刈らない原則と天井の緊張。実装者判断、grill-hook 推奨)。②音声md など具体案件向けの動くコンサル build は別タスク(本タスクは標準プロンプトのみ・build は別ドメイントリガで Deferred)。

## 2026-06-25 — ドラフト着地

- 着手時 hash 照合: `git hash-object judge-loop/SKILL.md` = e0b94af200cc... → foundation の blob e0b94af と一致。ドリフト無し、齟齬記載不要。
- 出力: `consultant/SKILL.md` 新規。出力スキーマ全節を満たす — role(逆向き要件定義/no-GT scope gate)/入力(evidence bound・spec boundary 既知・priors 受け取らない・steerable distance)/中核(探索=刈らない・ノイズ=母岩 → 製錬=内部 smelt → 出口)/出口スキーマ(提案軸+動機ケースの対・生フラグ単独不可・生軸単独不可)/ゲート結線(scope/G3/G9/G10/One systemic finding≠N flags)/task-handoff 先で cold 自走/薄さ境界(judge-loop の責務を持たない)。
- 未決①の裁定: 天井はスキルに焼かず。「刈らない」を本文で不変として書き、コスト天井は use-time(呼び手の steerable distance + grill-hook)へ寄せた。foundation の留保どおり grill-hook 推奨を採用。
- 命名/routing: frontmatter `name: consultant`。兄弟1(autonomy-axis)の routing 名指しと一致。judge-loop は composed-by(description で L3 は「呼び手の一人」と明記、judge-loop 非依存で自立)。
- registry を `完了・未回収` に更新。自動レポートバックせず。PM 回収待ち — 妥当性判定(刈らない/出口の対/提案のみ/薄さ/routing 名一致)→ ratify を `../../decisions/横断.md` へ(G6)。兄弟1との融合判断も PM 側。
