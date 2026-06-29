# throughline _dev

## 2026-06-29 session-dag を全面新規作成して throughline に改名
- 旧 session-dag の問題2つ: (1) "dag"(有向グラフ)= 廃止した SVG 図レンダラを指す名で、もう存在しない描き方を名乗っていた。(2) "session"(時間の窓)も実態とズレ ── これは時間区切りでなく「考えがどう動いたか(筋・転回・誰の一手か)の道のり」。さらに "dag" は本 skill 自身の language ルール(内部語を出さない)に反する用語。
- 全面新規作成(成果物=出力規約は継承)。名 = throughline(いくつもの筋を貫く一本の線=背骨。脱線も転回もその線上の出来事として辿れる。物語・脚本で使う普通の語で内部語でない)。
- 実態を正典化: 出力 = 全幅1列の対話ビュー(話者は色)。SVG 図レンダラ(旧 templates/arc.html)は廃止。方法 = 筋分け / beat(start・concl・wall・resp)/ 詰まり→転回 / 覆し(reversal)/ 意思決定の印 / language ルール(内部語ゼロ・口語一行)。
- 二層を明文化: live(<repo>/.lavish/session-arc.html)+ 保存版(narrative/<date>、append-only)。出力先は lavish ワークスペース → 成果物/ → cwd の順。
- 採用元プロジェクト = agentic-engineering(narrative role の生成器)。経緯 decisions/2026-06-29_throughline-rename.md。旧 skill のバックアップはセッションの scratchpad に退避。

## 2026-06-29 scope 拡張: 2枚 view(流れ+ロジック)
- owner「throughline 作るなら流れもロジックも作る方が自然・"更新"が近い」。
- throughline = 作業を貫く線を2本: 動きの線(流れ・源=会話・templates/flow.html)と、かたちの線(ロジック・源=コード/決定・templates/logic.html)。両方ソースから引き直す=更新。
- 分離案(ロジックを html-deck に)却下 ── 一動作で両方が自然。html-deck の削る規律は logic 生成の方法として内部で流用。
- language ルールは両 view に適用(流れ=その場の人間語 / ロジック=一般エンジニアが分かる語、内部語ゼロ)。
