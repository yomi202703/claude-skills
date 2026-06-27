# skill-shape — STATUS

_現状スナップショット。セッションごとに書き直す。短く保つ。_

## 何のスキルか
- スキルを「書く/直す」普遍作法。生成器でなく方法。どの環境でも通る抽象のみ。
- 中身=三 audience 分離(description→ルーター / SKILL.md 本文→実行者 / 補助ファイル→必要時ロード)・runtime vs maintenance ディレクトリ契約・蒸留パス・出荷ゲート。
- 特定の兄弟スキル・governance 名・style 規約は本文から除外(環境固有ゆえ)。Composition は「compose, do not duplicate」の一般原則に抽象化。
- 実体は SKILL.md 一枚(プロンプト専用・scripts なし)。

## いまの状態
- 初版起草(2026-06-27・jibun-de で全30 skill 通読)→ 同日 judge-loop 一家から脱結合して普遍版へ全面書き直し(オーナー裁定「完全に普遍だけ」)。詳細 decisions 2026-06-27。
- 出自: 既存スキル群の最大公約数＋3不満(冗長/README化/ディレクトリ無秩序)を出荷ゲート化。

## 次の一手
- 実スキルで1サイクル回して「三 audience 分離」「出荷ゲート」が実際に冗長/README化を切れるか検証(TODO P0)。
- skill-gripe との往復(build側=本スキル / in-use側=skill-gripe)が回るか観察。
