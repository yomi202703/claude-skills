# registry — 発行済み独立タスク

PM(=この directory)が「完了・未回収」を見つけるための一枚シート。1タスク1行。
state: 発行済み（走行中） / 完了・未回収 / 回収済み。
回収時、各タスクの妥当性判定を `../decisions/横断.md` へ理由つき記帳(G6)。

## 共有 foundation

- `foundation.md` — 版 `judge-loop@ac4e3fb · SKILL.md blob e0b94af`。両タスクが共有。

## タスク

### task-autonomy-axis
- 出力: `judge-loop/SKILL.md`(編集)
- 版: judge-loop@ac4e3fb · SKILL.md blob e0b94af
- 出力スキーマ: 自律度軸の節構成(導入/L1/L2/L3/不変条項+ゲート結線)。L3 で `consultant` を routing 名指し(composed-by 関係)。`**` 禁止・薄さ堅持。
- 統合トリガ: ドラフト完成 → 未回収。PM が G3/G10 妥当性判定(審級維持・提案のみ・薄さ・routing 名一致)→ ratify を横断.md へ。
- state: 発行済み（走行中）

### task-consultant-skill
- 出力: `consultant/SKILL.md`(新規・単独で立つスキル / judge-loop は composed-by)
- 版: judge-loop@ac4e3fb · SKILL.md blob e0b94af
- 出力スキーマ: コンサル SKILL.md 構成(role/入力/探索→製錬→出口/出口=提案軸+動機ケース/ゲート結線/task-handoff 先で動く前提)。`**` 禁止。
- 統合トリガ: ドラフト完成 → 未回収。PM が妥当性判定(探索を刈らない・出口の対・提案のみ・薄さ・親との routing 名一致)→ ratify を横断.md へ。融合判断もここ。
- state: 発行済み（走行中）
