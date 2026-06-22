# synthesis_draft — 統合・自由解答 spine の生成プロンプト

役割: 1つの source(と anchor narrative)から、A4自由解答で問われうる「統合プロンプト」を数問起こし、各問について claim-link spine と model answer を組む。card_draft が node を atomize するのに対し、これは複数 node を束ねる連結を第一級にする。declarative(cards)・procedural(derivations)に続く第3層。

## なぜ source から組むか(derivation と同じ provenance 非対称)

narrative の木は1ノード1〜3文で、ノード"間"の連結(論証の筋)を持たない。統合の山はその連結にあるから、木からは組めない。source を真実とし、narrative は anchor と束ねるべき node の在処としてのみ使う。

## 入力
- source: 元テキスト(真実。これに照らして検証する)
- anchor narrative slug: 束ねる node の所在
- (任意)過去問・出題形式: あれば prompt 設計の手本にする

## 出力: syntheses/<slug>.md(1問1ファイル)

frontmatter:
```
type: synthesis / slug / title / anchor / source / also_draws_on:[...] /
tier(T1|cross|gen) / verified(bool) / confidence(high|medium|low) /
status(pilot|stable|frozen) / created / updated
```

本文セクション(順序固定):
- `## PROMPT` — 1つの自由解答問い。原理→場面の逆引き、または複数概念の統合を要求する形にする。答えのカテゴリを問い文に書かない(漏らさない)。
- `## CLAIMS` — `[C1]..[Cn]` 主張ノード。各行は単一の主張で、多くは source/narrative 由来の既知事実。これ単体の想起は cards の仕事。
- `## LINKS` — `[L1]..[Ln]` 連結ノード。`Ci ∧ Cj ⇒ 結論` の形で、主張を繋ぐ論理を明示する。答えの山になる連結の行頭に `★` を1つだけ付ける。採点の主眼はここ。
- `## MODEL ANSWER` — 散文の模範。各段落末に `[C.. → L..]` で spine との対応を残す。★連結がクライマックスに来る構成にする。
- `## PROVENANCE` — 各 C/L の出所。source/narrative に明示がある=verified、木に無い合成命題=unverified として「source/講師に要確認」と明記(derivation の `[~]` 相当)。とくに ★連結は裏取りが弱いことが多いので確信度を正直に書く。

## 生成の規律(executor 規則)
1. 中立: 問い文・模範に、特定の立場へ誘導する強調や同意誘導を入れない。論証は source が支える範囲で書く。
2. 真実への忠実: source に無い主張を verified 扱いにしない。補った連結は必ず unverified としてフラグする。捏造で穴を埋めない。
3. 過適合回避: 特定の語句⇄答えの丸暗記ペアを作らない。問いは逆引き・統合方向に開く。
4. 終了仕様:
   - 1 source あたり 3〜8 問。各問は最低 3 claim・2 link を持つこと(満たせない問いは統合に値しないので捨てる)。
   - ★連結は各問ちょうど1つ。
   - model answer は spine の全 C/L を被覆すること(被覆できない C/L があるなら spine 側を直す)。
   - source 読取不能・該当箇所なし → そのトピックは「生成不可」と報告し、空ファイルを作らない。
- 生成は opus、被覆/質チェックは別モデル(自己選好バイアス回避。narrative の coverage QA と同じ方針)。
