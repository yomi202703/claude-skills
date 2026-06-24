# decision — task-consultant-skill

append-only。このタスクの思考台帳。発行時に founding rationale を seed。

## 2026-06-24 — 発行(founding rationale)

- 発行元: judge-loop 自律度軸の grill-me セッション。L3(自己起案=コンサル)が独立スキルに値すると確定。
- なぜスキルにするか: 「task-handoff で渡した後にコンサルとして動く必要がある」=渡された先で自走するプロンプトが要る(オーナー指示)。judge-loop は薄いので中身を持てない——L3 の中身はここに来る。
- 設計の核心(grill で潰した順): ①「コンテキスト無関係」→ ②priors free / evidence bound(占い回避)→ ③境界認識・steerable(要件を知るからこそ外を探索・距離はメインが振る)→ ④探索と製錬の分離(原石はノイズからしか生まれない=探索を刈るな・製錬は内部・出口だけ固定)。詳細は foundation.md。
- 命名(2026-06-24 オーナー裁定): `consultant`。`prospect`・`konsaru-tan`(コンサルたん)案はいずれも却下、素直な consultant に確定。
- スコープ昇格(2026-06-24 オーナー): 「単独でも役に立つ」→ judge-loop L3 専用部品でなく独立スキルへ。description は judge-loop 非依存で自立させ、judge-loop は composed-by(review-server/gemma-prompt と同位)。誰でも直呼び可。
- 未決/留保: ①探索の fan out 上限/コスト天井をスキルに焼くか、use-time の grill-hook に回すか(刈らない原則と天井の緊張。実装者判断、grill-hook 推奨)。②音声md など具体案件向けの動くコンサル build は別タスク(本タスクは標準プロンプトのみ・build は別ドメイントリガで Deferred)。
