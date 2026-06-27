# skill-shape — TODO

_未来 / 実行キュー。Active(いま着手可・P0–P2) と Deferred(ブロック中・各項目が解除トリガを名指す) の2状態のみ。_
_一行一項目。理由は decisions(日付で参照)に置く。完了は decisions へ移し、ここから消す。_

## Active

- [P0] 既存スキル1本(README化/冗長の疑いがあるもの。候補: skill-gripe 本文6行・antigravity)に skill-shape を当て、出荷ゲートが実際に切れるか1サイクル検証 → 結果を decisions へ
- [P1] 出荷ゲートを reference/checklist.md に切り出すか判断(本文インラインのままで足りるか)

## Deferred

- description の良し悪しを機械判定する小 eval(ルーターが正しく route できるか) [複数スキルで誤 route が観測されたとき]
