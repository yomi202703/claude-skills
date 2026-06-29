# claude-md decisions

## 2026-06-30 won't do: repo-shape と claude-md を1本の rooter 系 skill に統合する案

- 提案: 土台作りで両方必要になりがちなので、`/repo-shape` と `/claude-md` を統合して1つの rooter 系 skill にする。
- 結論: 統合しない。
- 根拠:
  - 動詞とリスクモデルが別物。repo-shape は「ファイルを動かす」破壊的・ゲート付き多段手順（branch→git mv→ripple-check→test→owner diff・可逆）。claude-md は「テキストを書く／レビューする」非破壊の方法論。1本に畳むと軽作業に重い移行ゲートが付くか、移行の安全規律が薄まる。
  - ライフサイクルが別物。claude-md はリポの一生を通じた保守・hygiene（memory rots by accretion）。repo-shape は基本一度きりの構造リシェイプ。恒常使用を一回ものに縛る形になる。
  - 単一所有の設計に反する。repo-shape＝ツリー形状の単一所有 / claude-md＝メモリ層の中身の単一所有、という意図的分割（"Do not duplicate either single source"）と compose 関係（repo-shape が枠を予約、claude-md が中身を埋める）を再び曖昧にする。
  - compose 点が濁る。claude-md は judge-loop の Scaffold step から独立に呼ばれる。統合すると judge-loop が移行 skill 全体を引き込む過剰。
- 採った向き（案A）: 統合せず、土台作業の主入口を repo-shape に寄せ、その中で claude-md を compose する既存関係を明示する。所有は分けたまま。
- 実害の特定: 非対称があった。repo-shape は claude-md を compose すると明記するが、claude-md 側に repo-shape への back-pointer もエスカレーション節も無い。claude-md から入って散らかったツリーに出会っても repo-shape へ寄せる導線が無い。
- 手当て: claude-md SKILL.md のみ修正。(1) 手順1に「探索でツリー自体を動かす必要が見えたら repo-shape を先に走らせ、整えてからマップを書く」エスカレーション節を追加。(2) Composition に repo-shape の back-pointer を追加。repo-shape 本体は無修正（既に正しく compose 済み）。

## 2026-06-30 directory map → orientation map（実証研究を踏まえた再定義）

- きっかけ: 「repo map は常に変わるのに、それを CLAUDE.md に固定して更新し続けるのは一般的なのか」という問い。直感的に保守コストが高くアンチパターンに見える、と。
- 結論: その通り。SKILL.md の責任3を「directory map（構造を書く）」から「orientation map（不変条件を書く）」へ再定義した。揺れる構造の記述は CLAUDE.md の責任から外し、エージェントの探索に委ねる。
- 実証の裏付け:
  - Gloaguen, Mündler, Müller, Raychev, Vechev「Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?」arXiv:2602.11988 (ETH Zurich, 2026-02 / rev 2026-06)。SWE-bench 上で、context file は一般にタスク成功率を上げず推論コストを平均+20%超。LLM自動生成は約-2%、人間記述で約+4%。トレース分析の核心: 「repository overview はモデル提供元が推奨しているのに役立たない」「効くのは非標準の運用知識（発見困難な情報）だけ」。→ 構造概要は効かない部分そのもの。
  - Lulla, Mohsenimofidi, Galster, Zhang, Baltes, Treude「On the Impact of AGENTS.md Files on the Efficiency of AI Coding Agents」arXiv:2601.20404 (2026-01)。AGENTS.md 有りで実行時間 中央値-28.64%、出力トークン-16.58%、完了率同等。効くのは効率面。
  - 位置/長さの劣化: Lost in the Middle (arXiv:2307.03172)、LIFBench (arXiv:2411.07037)。長く・中央/後方の指示ほど無視されやすい。→ tight core + 重要ルールを先頭。
- 切り分けの原理: 「リファクタでファイルが動いても真であり続けるか」で line を選別する。真であり続ける＝不変の方針（domain logic は X に置く / generated は触るな / 初手で迷う固定点）だけが CLAUDE.md に残る。現在のツリー構造は ls/grep で安く分かるので書かない。古い地図は無記載より有害（能動的に誤誘導する）。
- 手当て: SKILL.md のみ修正。(1) 責任1の「belongs/keep out」を構造ダンプ排除に書き換え、line 選別テストを追加。(2) 責任3を Orientation map に改題し中身を invariants 主義へ。(3) judge-loop 節を stable slots 限定に。(4) hygiene にツリー突合と長さ希釈の一文を追加。本体の compose 関係・所有分割は不変。

## 2026-06-30 追補: 「repo-shape に claude-md を内蔵すべき／探索を共有できる」への再判断

- 再提案: repo-shape は既にリポを探索している（CLAUDE.md も読むはず）から、claude-md を内蔵し探索を共有させればいい。探索を必須化しては。
- 探索共有の前提は崩れる: repo-shape の探索（散らかった現状＝移動計画用）と claude-md の探索（動かした後の整ったツリー＝マップ用）は別スナップショット。repo-shape は途中でファイルを動かすので、claude-md は移動後を必ず見直す。embed しても探索は1回にならず、別々の探索が同居するだけ。よって「探索共有→内蔵」は根拠にならない。本体マージは維持して却下。
- 「内蔵」には2義あり、意味B（repo-shape がサブステップで claude-md を呼ぶ＝一本叩けば claude-md も走る）は所有を分けたまま既に compose 済み。欲しい「内蔵感」はこれで満たせる。ただし呼び出しが Composition 節に埋もれフローに見えていなかった＝改善余地。
- 採った手当て: repo-shape SKILL.md の Two entrances を修正。(1) 探索を明示の必須ゲート化（憶測でツリーを出さない／現状ツリー・CLAUDE.md・docs・config を先に読む）。(2) claude-md 呼び出しをフローに昇格（settle 後に claude-md を呼んでメモリ層を書く／owner は別途叩かない）。本体マージはせず、意味Bの compose を可視化しただけ。前回の案A の延長で反転ではない。
