# TASK — コンサル役スキル consultant を起こす

自己完結の契約。会話メモリ無しで cold-start する前提。read list が文脈。

## read list(着手前に順に読む・基盤優先)

1. `judge-loop/_dev/handoff/foundation.md` — 共有前提。L3 コンサル役の性質(priors free/evidence bound・境界認識/steerable・探索と製錬の分離・出口スキーマ)が核心。
2. `judge-loop/SKILL.md` — 親オーケストレータ。L3 がここから routing される。薄いオーケストレータが「中身を持たず routing する」関係性を掴む(コンサルの中身はこのスキル側に来る)。
3. `task-handoff/SKILL.md` — このコンサルは「task-handoff で渡された後にコンサルとして動く」=渡された先で自走するプロンプト。渡し方の契約(read list/do/output/trigger)を理解した上で、渡された側として何を受け取り何を返すかを設計する。
4. `grill-me/SKILL.md`・`deep-strict/SKILL.md`(参照) — 隣接スキルの文体・粒度。especially 探索系の書き方。
5. 兄弟1 `task-autonomy-axis/TASK.md` — 親側が L3 をどう名指すか(routing 先・出口スキーマの呼び名)を一致させるため。

## do

コンサル役を独立スキルとして起こす。境界認識のコンサルが、案件の生データを priors 抜きで読み、サブエージェントを刈らず fan out して探索し、ノイズを製錬して「提案軸 + 動機ケース」に圧縮して返す。

単独で立つスキルとして書く(オーナー指示「こいつ単独でも役に立つ」)。judge-loop の L3 専用部品でなく、誰でも直接呼べる「死角コンサル」=任意の no-GT データに対し「今見ていない・判定していない何か」を提案する汎用スキル。judge-loop は composed-by の側(review-server/gemma-prompt と同じ関係)。description は judge-loop に依存せず単独で成立させ、judge-loop L3 は呼び手の一人として書く。

- 起動条件(when to use): no-GT の文脈で、現仕様の外に「判定すべき何か / 見るべき死角」を探索したいとき。judge-loop L3 からも、ユーザー直呼びからも起動。task-handoff で渡された先で自走する。
- 入力: 案件の生データ(evidence)+ 現在の要件/仕様の境界(知るが、なぜそう判定したかの内部解釈=priors は受け取らない)+ メインからの steerable 指示(仕様からの距離: 隣接〜遠方)。
- 中核手順: 探索(サブエージェント fan out・刈らない・ノイズ歓迎)→ 製錬(内部で smelt・圧縮)→ 出口(提案軸 + 動機ケースのクラスタ)。探索と製錬を明示的に分離して書く。
- スコープゲート: 正解がある系は対象外(冒頭で弾く)。提案のみ・自己コミット禁止(G3/G10)。出した提案は judge-loop の grill-hook/オーナー裁定へ戻る。
- 薄さの境界: judge-loop の責務(フェーズ・ゲート・routing)は持たない。このスキルは L3 の「どう探索し圧縮するか」だけを持つ。

## output path

- `consultant/SKILL.md`(新規スキル。frontmatter `name: consultant` + `description` 必須、リポ既存スキルの形式に倣う)。dir も `consultant/`。親(兄弟1)の routing 名と一致させること。

## shared output schema(PM が返り物を測る構造)

SKILL.md の節構成:

- frontmatter(name: consultant / description: 単独で成立・何のスキルか・いつ起動するか・judge-loop L3 は呼び手の一人)
- role(コンサル=逆向き要件定義・SE でなく何を判定すべきかを提案・no-GT 限定・単独で立ち judge-loop が composed-by)
- 入力(生データ=evidence / 仕様境界=知る / priors=受け取らない / steerable 指示)
- 中核手順: 探索(fan out・刈らない・ノイズ=原石の母岩)→ 製錬(内部圧縮)→ 出口
- 出口スキーマ(提案軸 + 動機ケースのクラスタ。生フラグ羅列も生軸提案も不可)
- ゲート結線(no-GT スコープ・提案のみ・G3/G9/G10・「One systemic finding ≠ N flags」)
- task-handoff で渡された先として動く前提の明記
- 制約: `**` 禁止・`#`/`-` のみ。

## integration trigger(再統合の発火条件 + PM の動き)

- 発火: `consultant/SKILL.md` ドラフトが書き上がる。registry の行を `完了・未回収` に。自動レポートバックしない。
- PM の動き: 妥当性判定——「探索を刈っていないか(G9)」「出口が提案軸+動機ケースの対になっているか」「提案のみで自己コミットしていないか(G3/G10)」「judge-loop の薄さを侵していないか(コンサルの責務だけ持つか)」「親=兄弟1の routing 名と一致するか」。ratify したら `_dev/decisions/横断.md` に理由つき記帳(G6)。兄弟1との融合/再設計の判断もここで。

## foundation version stamp

- `judge-loop@ac4e3fb · SKILL.md blob e0b94af200cc9f149734968ba4763288ee1e939b`
- 親 SKILL.md がドリフトしうる。着手時に再 hash 照合し、違えば foundation との齟齬を decision.md に記してから着手。
