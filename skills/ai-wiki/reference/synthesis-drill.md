# Synthesis drill (chat-time behavior)

Read this when the user asks to be drilled on a **synthesis**(`syntheses/<slug>.md` の claim-link spine)— A4自由解答で「複数概念を束ねて説明する」力。declarative recall(言えるか)・procedural recall(導出できるか)に続く第3の技能=composition(構成)。flashcards も derivation drill もこれは鍛えない。

この層が要る理由: 事実(claim)が揃っても、それを繋ぐ連結(link)を自分の言葉で再生できなければ自由解答は書けない。学習者の詰まりは多くが link 側にある(例: 個別事実は出せたが「保険は自由と自己責任を媒介する」という連結が出せない)。だから採点の主眼は link。

## 道具の使い分け

- 白紙再生そのものは viewer(`tools/synthesis_viewer.py`)で回すのが本筋。PROMPT だけ表示→提出するまで答えを送らない→提出後に self-grade。チャットだと答えがスクロールで漏れるので、本番練習は viewer を勧める。
- このチャット drill は、viewer の self-grade では気づけない穴(説明深度の錯覚)を第三者として炙り出す診断。とくに「本人は連結したつもりが論理が飛んでいる」箇所を拾う。

## Drill loop — 一問ずつ、prefill 厳禁

1. PROMPT を1つ提示して止まる。CLAIMS/LINKS/MODEL は見せない。学習者が白紙で書き切るのを待つ(prefill すると練習価値が消える)。
2. 学習者の解答を spine と照合し、下の rubric で「主張被覆・連結被覆・誤り」を返す。miss は人への評価ではない(hard rule #2)— fade を一段下げる/次回再ドリルの印にするだけ。「あなたの解答は L3 に届いていない、ここは scaffold を増やそう」と言い、「間違い」と言わない。
3. 外した link を `_attempts.jsonl` 観点で次回の焦点にする。link を外し続けるなら、その link を支える claim から fade を下げて組み直す。

## Fade ladder(散文版。derivation の worked→faded→independent を文章に写す)

- F0: MODEL ANSWER を読む(まず筋を見る)
- F1: CLAIMS だけ渡し、それらを繋ぐ連結文を書かせる(連結だけを練習)
- F2: 束ねるべき node 名(anchor narrative の見出し)だけ渡し、claim から書かせる
- F3: PROMPT のみ→全文を白紙で書く(本番)

成功で fade を上げ、miss で下げる。★link を外したら必ず F1 まで戻してそこだけ繰り返す。

## Judge rubric(照合の中身。executor 規則に従う)

spine(CLAIMS/LINKS/MODEL)と学習者の解答を入力に、次を中立に分類して返す。人ではなく解答を採点する。

- claim 被覆: 各 [Cn] が解答に現れるか(present / missing)。
- link 被覆: 各 [Ln] の論理が解答内で実際に繋がっているか(present / missing / asserted-but-unconnected)。「present」は結論だけでなく前提から結論への接続が文中にあること。★link は最重要、別建てで報告。
- 誤り: source/spine と矛盾する主張(wrong)。
- 出力は構造(C: present/missing 一覧、L: present/missing/unconnected 一覧、wrong 一覧、外した link を支える claim)。スコアや合否、人物評価を出さない。

規律(CLAUDE.md executor 4原則):
1. 中立: 「よく書けている」等の同意誘導や励まし採点をしない。被覆の事実だけ返す。
2. eval 整合: 学習者へ MODEL を見せる前に判定する。判定者の入力に「期待文」を先に渡して甘くしない。
3. 過適合回避: 特定の言い回し一致を要求しない。連結の論理が再生されていれば言葉は問わない。
4. 終了/失敗: spine に ★link が無い/解答が空/source 不明なら、その旨を返して判定を捏造しない。`unverified` とフラグされた link(木に無い合成命題)は、外しても「本人の穴」と「そもそも source 未確認」を区別して伝える。

判定は別モデルで回すのが望ましい(自己選好バイアス回避)。
