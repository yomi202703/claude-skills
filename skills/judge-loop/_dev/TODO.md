# judge-loop — TODO

_未来 / 実行キュー。Active(いま着手可・P0–P2) と Deferred(ブロック中・各項目が解除トリガを名指す) の2状態のみ。_
_一行一項目。理由は decisions(日付で参照)に置く。完了は decisions へ移し、ここから消す。_

## Active

(なし — このセッションで磨く項目を起こしたらここへ。例: SKILL.md ⇔ docs/方法論 の整合チェック。)

## Deferred

- 別ドメインで全ゲート/フェーズを当てて overfit を検出(n=1 由来の最大リスク) [別ドメインに着手するとき]
- P3 ハーネス + run-ledger の実 template/code を起こす [別ドメインで再現性測定が要るとき]
- アクセス層スキル(MCP・SQL/PDF/RAG 統一口)を起こす [別ドメイン着手で源泉アクセスが要るとき・judge-loop の唯一の prerequisite 穴]
