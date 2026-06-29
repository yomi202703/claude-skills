# handoff — TODO

_未来の実行キュー。Active(今やれる、P0–P2)/ Deferred(ブロック中、各項目に解除トリガを明記)。完了は decisions へ移し、ここからは消す。_

## Active
- (なし)

## Deferred
- SKILL.md に dispatch 配線を実装側と結ぶ(契約発行=foundation.md 設置 ↔ dispatch ボタン。さらに task dir 監視で自動 dispatch)[トリガ: dispatch MVP が実 handoff 1件で検証された後]。
- fan-out 版 dispatch(buildGrid で兄弟ストリームを split に並べる、recall の3面方式)[トリガ: 1分岐点が >1 兄弟に fan-out し、かつ co-visible に並べたい運用が出たとき]。
- 薄い registry 索引を足すか判断[トリガ: 1分岐点の fan-out が、毎セッション N 個のストリーム dir を読み直すのが無駄なほど広くなったとき]。
