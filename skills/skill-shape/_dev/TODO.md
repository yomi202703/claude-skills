# skill-shape — TODO

_未来 / 実行キュー。Active(いま着手可・P0–P2) と Deferred(ブロック中・各項目が解除トリガを名指す) の2状態のみ。_
_一行一項目。理由は decisions(日付で参照)に置く。完了は decisions へ移し、ここから消す。_

## Active

- なし(初期の検証フェーズは全 skill 実走で完了。decisions 2026-06-27 参照)

## Deferred

- description の良し悪しを機械判定する小 eval(ルーターが正しく route できるか) [複数スキルで誤 route が観測されたとき]
