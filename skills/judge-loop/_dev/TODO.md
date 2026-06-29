# judge-loop — TODO

_未来 / 実行キュー。Active(いま着手可・P0–P2) と Deferred(ブロック中・各項目が解除トリガを名指す) の2状態のみ。_
_一行一項目。理由は decisions(日付で参照)に置く。完了は decisions へ移し、ここから消す。_

## Active

- [P2] /plan を judge-loop に組込む検討: 参考「Plan F3」(YouTube DzbqeO_diOQ / Andy Dev Dan)。phase 境界で plan mode・closed-loop 検証(test+合格基準で次フェーズ拘束)・Questionable Mode≒grill-me・living artifact≒四役 governance。組込可否を評価し方向を decisions へ(ディレクトリ再構成スキルの per-migration テストゲートとも交差)

## Deferred

- repo-shape: 骨格 author 済(`repo-shape/SKILL.md`・2026-06-27・firewall 三分は反映済)。残=①最小版1サイクル検証で正準名を結晶化(この走行が縦割り[task単位カプセル化]vs 横割り[§3.5 共有factlayer]も裁く=外部2モデルが縦を推した検証論点)②judge-loop §3.5 を repo-shape 参照へ痩せさせる手術 [対象リポ zip 到着 → 検証(分類→提案→ratify→1カテゴリ migrate→ripple-check→テスト)通過後に §3.5 手術] → decisions/横断.md 2026-06-26・2026-06-27
- 別ドメインで全ゲート/フェーズを当てて overfit を検出(n=1 由来の最大リスク) [別ドメインに着手するとき]
- P3 ハーネス + run-ledger の実 template/code を起こす [別ドメインで再現性測定が要るとき]
- アクセス層スキル(MCP・SQL/PDF/RAG 統一口)を起こす [別ドメイン着手で源泉アクセスが要るとき・judge-loop の唯一の prerequisite 穴]
- 本物の IDE 統合(レビュー単位を開発者自身のエディタでファイルとして開く)を起こす [単位が settle し人間GT量がその投資を正当化したとき]
