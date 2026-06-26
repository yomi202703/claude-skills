# task-handoff — TODO

_未来の実行キュー。Active(今やれる、P0–P2)/ Deferred(ブロック中、各項目に解除トリガを明記)。完了は decisions へ移し、ここからは消す。_

## Active
- P1 SKILL.md に dispatch を薄く一行差す(任意の eager-launch 層として。ファイル契約が正本である旨を保つ)。オーナー確認の上で。decisions 2026-06-27「着地と未反映」。
- P2 別件の未コミット SKILL.md 編集(judge-loop ルーティング節の削除)を commit するか revert するか確定(dispatch 追記と絡めない)。

## Deferred
- fan-out 版 dispatch(buildGrid で兄弟ストリームを split に並べる、recall の3面方式)[トリガ: 1分岐点が >1 兄弟に fan-out し、かつそれらを co-visible に並べたい運用が出たとき]。
- task-handoff 発行 ↔ dispatch の配線(契約発行時に task dir へ TASK.md を置く正本側と dispatch ボタンを結ぶ。さらに task dir 監視で自動 dispatch)[トリガ: dispatch MVP が実 handoff 1件で検証された後]。
