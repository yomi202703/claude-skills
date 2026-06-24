# judge-loop — TODO

_未来 / 実行キュー。Active(いま着手可・P0–P2) と Deferred(ブロック中・各項目が解除トリガを名指す) の2状態のみ。_
_一行一項目。理由は decisions(日付で参照)に置く。完了は decisions へ移し、ここから消す。_

## Active

- 自律度軸 L1→L2→L3: 2兄弟タスクを task-handoff で発行済・走行中 → `_dev/handoff/registry.md`(回収=PM が妥当性判定して decisions へ)

## Deferred

- 別ドメインで全ゲート/フェーズを当てて overfit を検出(n=1 由来の最大リスク) [別ドメインに着手するとき]
- P3 ハーネス + run-ledger の実 template/code を起こす [別ドメインで再現性測定が要るとき]
- アクセス層スキル(MCP・SQL/PDF/RAG 統一口)を起こす [別ドメイン着手で源泉アクセスが要るとき・judge-loop の唯一の prerequisite 穴]
- ファクトチェッカー引き渡し面を別成果物/別スキルとして起こす(契約は単一ソースから生成・GT は S9 で戻す) [外部ファクトチェッカーを実投入し campaign の悩みが反復するとき]
- 本物の IDE 統合(レビュー単位を開発者自身のエディタでファイルとして開く)を起こす [単位が settle し人間GT量がその投資を正当化したとき]
