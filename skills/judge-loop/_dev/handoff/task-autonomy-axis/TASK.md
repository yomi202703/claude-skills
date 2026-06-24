# TASK — judge-loop SKILL.md に自律度軸を書く

自己完結の契約。会話メモリ無しで cold-start する前提。read list が文脈。

## read list(着手前に順に読む・基盤優先)

1. `judge-loop/_dev/handoff/foundation.md` — 共有前提。設計の全体。版規約(着手時に SKILL.md を再 hash し blob e0b94af と照合)。
2. `judge-loop/SKILL.md` — 編集対象。現在の軸は1本(フェーズ)+ G1–G10。Phase routing と Composition の節の形をそのまま踏襲する。
3. `judge-loop/_dev/decisions/横断.md` — スキルの形の meta-ADR。なぜ薄いオーケストレータか・なぜこの routing か。書く文体と「持たないものは routing する」方針を掴む。
4. `judge-loop/docs/方法論_正解のないAI判定開発.md`(該当節のみ) — WHY 一次台帳。自律度軸を足すなら方法論側にもドリフトが出ないか確認(双方向整合)。

## do

judge-loop SKILL.md に、フェーズ軸に直交する二次元目=自律度軸 L1→L2→L3 を書き込む。

- 軸を「ハンドルを誰が握るか」=ペーシングと審級の分離として導入。L1/L2/L3 を依存連鎖(L1→L2 アンカー / L2 override→L3 採掘)として定義。
- L2 の不変配線(外部アンカー照合・gemma 脚=脱相関・裁定者バイアス)を書く。
- L3 は Composition でコンサル役スキル(兄弟2、`consultant`)を routing 先として名指す。review-server/gemma-prompt と同じ composed-by 関係(単独でも立つスキルを judge-loop が合成する)。中身は持たない(薄さ堅持)。
- 全段で「人間は審級のまま・L3 は提案のみ」を不変として明記。G3/G9/G10 との整合を本文か近傍ゲートで示す。
- 既存のフェーズ routing・Cores・Composition を壊さない。自律度軸はどのフェーズにも被さる横断概念として置く(フェーズの代替でない)。

## output path

- `judge-loop/SKILL.md`(編集)。新スキル本体は書かない——名指すだけ(本体は兄弟2)。

## shared output schema(PM が返り物を測る構造)

SKILL.md に追加/改訂される節の構成:

- 自律度軸の導入(ペーシング≠審級の分離 / フェーズ軸への直交 / 依存連鎖)
- L1 の定義(現状=人間ペース、律速かつ裁定者)
- L2 の定義(claude×gemma×claude 裁定 / 裁定者バイアス / 外部アンカー照合 / gemma=脱相関)
- L3 の定義(コンサル=逆向き要件定義 / no-GT スコープ / 提案のみ / Composition で `consultant` 名指し)
- 不変条項(人間=審級・L3 自己コミット禁止)と既存ゲート(G3/G9/G10)への結線
- 制約: `**` 禁止・`#`/`-` のみ。薄いオーケストレータ方針堅持(中身を書かない)。

## integration trigger(再統合の発火条件 + PM の動き)

- 発火: SKILL.md ドラフトが書き上がる。自動レポートバックしない——registry の行を `完了・未回収` にし、PM(オーナー)が回収する。
- PM の動き: G3/G10 に照らして全体妥当性判定——「人間は審級のままか」「L3 は提案のみで自己コミットしてないか」「薄さを保ち中身を routing したか」「兄弟2との routing 名(`consultant`)が一致するか」。ratify したら `_dev/decisions/横断.md` に理由つきで記帳(G6)。妥当性判定には再設計(例: 兄弟1と2を融合すべき)も含む。

## foundation version stamp

- `judge-loop@ac4e3fb · SKILL.md blob e0b94af200cc9f149734968ba4763288ee1e939b`
- 着手時に再 hash 照合。違えば差分を読み直し、foundation との齟齬を decision.md に記してから着手。
