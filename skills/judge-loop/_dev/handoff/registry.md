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
- state: 回収済み（2026-06-27 PM が着地・ratify。発行後ドラフトが SKILL.md へ未着地のまま滞留していたのを発見→凍結設計どおり最小差分で着地: 「Autonomy axis」節 L1/L2/L3 + Composition に consultant への L3 routing。着地時 hash は発行時 e0b94af と一致=ドリフト無し。詳細 ../decisions/横断.md 2026-06-27）

### task-consultant-skill
- 出力: `consultant/SKILL.md`(新規・単独で立つスキル / judge-loop は composed-by)
- 版: judge-loop@ac4e3fb · SKILL.md blob e0b94af
- 出力スキーマ: コンサル SKILL.md 構成(role/入力/探索→製錬→出口/出口=提案軸+動機ケース/ゲート結線/task-handoff 先で動く前提)。`**` 禁止。
- 統合トリガ: ドラフト完成 → 未回収。PM が妥当性判定(探索を刈らない・出口の対・提案のみ・薄さ・親との routing 名一致)→ ratify を横断.md へ。融合判断もここ。
- state: 回収済み（2026-06-27 PM が G6 妥当性判定: `consultant/SKILL.md` 実在・frontmatter name=consultant・自立 description で judge-loop L3 を「呼び手の一人」と明記・探索を刈らない/出口=軸+動機ケースの対/提案のみ G3/G10 すべて仕様一致・`**` 無し・親の routing 名と一致。詳細 ../decisions/横断.md 2026-06-27）
