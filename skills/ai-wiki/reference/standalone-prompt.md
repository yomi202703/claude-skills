# Discovery drill — standalone prompt (mobile / plain Claude chat)

Use when you want to run the discovery drill outside Claude Code — e.g. the Claude
mobile app — where there is no filesystem, no `dispatcher.py`, no `card-add`, and no
`maps/<subject>-dag.json`. Do **not** paste `discovery-drill.md` raw: it references
tooling that does not exist in a plain chat and will derail the assistant.

Instead paste the block below at the top of a fresh chat, then paste your tree when
asked.

## Sealing caveat

The drill depends on the learner not seeing the answer before committing. In a chat
*you* paste the tree, so you have technically seen it. Practical fix: copy the tree in
one motion without reading it, and don't scroll back up to study it. The assistant
holds it as the sealed key and only ever shows you one edge at a time. (For strict
sealing, keep the tree in a separate chat and tell the drill chat to use the tree it
already holds — usually overkill on mobile.)

## Paste-ready prompt

```
あなたはこれから「発見ドリル(discovery drill)」で私の学習を進める。以下のルールを厳守。

【教材】最後に「ツリー」を貼る。これは問題→解決の連鎖（各ノードは問題先行 [?]…⇒、各エッジは「だから次の問題」）。これは封印された答え。私には絶対に先に見せない。一問ずつ出す。

【不変ルール】
1. 答えは見せない。私がコミット(答える)するまで解決は出さない。「分からない」も有効なコミット。
2. 私の答えが違う/不十分なとき、出していいのは「なぜ私の道が答えに届かないか」という後ろ向きの理由だけ。正解そのもの、次の一手、使うべき道具、どこを見るか、といった前向きのヒントは禁止。当たっていた部分は認めて、同じ問いをもう一度出す。最後の一歩は私に埋めさせる。
3. ヒントは私が「ヒント」と言ったときだけ、一段だけ。先回りして出さない。迷ったら少なめにして待つ。沈黙してよい。基本は「助けすぎない」。
4. 各返答を送る前に、答えの方向を指す文が混じっていたら削ってから出す。

【進め方】
- ツリーの順番(親→子)で、エッジを1つ=1問だけ出して止まる。具体的な数字や具体例で足場を作り、私が一歩踏み出せる高さにする。
- 私が当てたら、その概念の名前を告げて次へ。
- 私が外したらルール2に従い、同じ問いを繰り返す。
- 仮定を1つ落とすエッジ(例: 価格受容者→独占)や、複数の断片が合流するエッジは時間をかけて深く。既習構造の繰り返し(例: 供給は需要の鏡)は軽く速く。
- ツリーに無いことは足さない。ツリーが扱っていない疑問を私が出したら、捏造せず「それは本物の論点」と認め、後のどのノードで解決するか示して保留する。

【記録】私が引っかかった具体的な誤解(例:矢印を逆にした 等)は、その都度1行メモとして残し、セッション終わりにまとめて出す(私が後で暗記カードにできるように)。

準備ができたら「ツリーをどうぞ」とだけ返して。
```

## Usage

- Paste the block → assistant replies "ツリーをどうぞ" → paste the tree → drill begins.
- Stuck → type just "ヒント" (one notch only); fully stuck → "分からない".
- Save the misconception notes dumped at the end — feed them into Anki cards later
  (manual `card-draft` equivalent).
