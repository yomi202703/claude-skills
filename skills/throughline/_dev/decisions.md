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

## 2026-06-30 成果物/ fallback を `handoffs/` から外す(task-handoff との不整合修正)
- 発端: オーナー指摘「task-handoff と throughline が不整合」。
- 不整合の実体: `成果物/` fallback が `成果物/handoffs/throughline/…` をハードコードし、task-handoff の領分である `handoffs/`(cold main が実行するタスク契約の置き場)に squat していた。throughline の出力は人が読む派生ビュー(view≠真実)で handoff 契約ではない ── カテゴリ違い。かつ「スロット配置は repo-shape に委ねる」という本 skill 自身の規律(末尾)とも矛盾。
- 修正: fallback を `成果物/views/throughline/…` に変更。`handoffs/` 下には置かない理由(task-handoff の契約 vs ここの派生ビュー)を一行で添えた。task-handoff 側も境界を明文化(task-handoff _dev 2026-06-30 参照)。
- ripple-check(同日): 当初 fallback 行に「スロットは repo-shape が macro 層に定める」と添えたが overclaim ── repo-shape:33 が予約する view スロットは `.lavish/`/`narrative/` で `成果物/views/` ではない。委譲は既に末尾行(repo-shape が定める)にあり重複かつ不正確なので削除。`成果物/views/` は `.lavish/` 不在時の素の fallback パスとして残す(repo-shape スロットを名乗らない)。

## 2026-06-30 gripe: 「2枚出力」と「2ペイン(1ページ分割)」の食い違いで消費面を取り違えた
- 使用中に感じた摩擦(skill-gripe): `.lavish/` を新規導入し横断 home(:8076) に出す作業で、流れ/ロジックを**別ページへ飛ばすランディング(カード2枚)**として shell を作ったら、オーナー即訂正「この2つ、1ページ画面分割で同時に見せる想定では?」。グローバル CLAUDE.md の「standing front of **two panes**」が正で、私の作りは間違いだった。
- 原因 = 本 skill が出力を「**2枚の出力**(別ファイル `session-arc.html` / `logic-<slug>.html`)」とだけ規定し、**その2枚が人にどう提示されるか(消費面)を一切書いていない**。生成の単位(2ファイル独立に焼き直す=正しい)と、消費の単位(1ページに2ペイン分割=CLAUDE.md の意図)が別物なのに、skill は前者しか語らず「2枚」という語が後者を「2つの別ページ」と誤読させた。
- 併発: `.lavish/` を home に拾わせるには `<title>` 付きランディング(`shell.html` 等)が要るが、この**統合面(shell)の存在自体が skill に無記載**。アグリゲータ規約(home-server の `_CANDIDATES=/, /shell.html, /index.html`)と本 skill の橋渡しが空白で、即興で埋めて外した。
- 正しい最終形(今回の着地): 土台は2ファイル独立(throughline が各々上書き=契約維持)、人が見る面は `shell.html` が両者を左右 iframe で嵌める**1ページ分割**(両方/単独トグル+ドラッグ境界)。生成と消費を分離すれば両立する。
- 直すなら(skill 本体・未着手): 出力節に「消費面=`.lavish/shell.html` が2ペインを1ページ分割で同時提示。生成は2ファイル独立・提示は1面」を1行で明記し、`shell.html` を `.lavish/` 規約スロットとして列挙(中身=2 iframe 分割の最小形)。「2枚」という語は生成単位限定と注記。スロット配置の委譲先(repo-shape)と home 規約(titled landing 必須)の接続もそこで触れる。

## 2026-06-30 流れ view を全面廃止 → logic 専用 skill に。logic にプロンプト全文を逐語で載せる
- オーナー使用後のフィードバック(`/throughline` 引数): 「意思決定の流れ、俺全然みたいわ。むしろロジックの方しか見ない。そして絶対にロジックの中にプロンプト全文も欲しい」。直前の gripe(2ペイン同時提示)が前提だったが、その2ペインの片方=流れ自体が読まれていなかった。
- 2つの fork をオーナーに確認(AskUserQuestion): (1) 流れの扱い → 「完全に削除」を選択(opt-in 残し/対等強化 ではなく)。(2) 逐語の範囲 → 「プロンプトファイルだけ逐語」を選択(ルール/spec/設定まで一般化はしない)。
- なぜ流れ削除: owner が唯一の消費者で「全然見ない」と明言。doc governance(使われない物は残さない)。how-we-got-here の証跡は decisions が既に持つ ── 流れ view はその二重持ちでしかなかった。これで前 gripe が直そうとしていた「2ペイン同時提示の shell」自体が不要(消費面が1枚になった)。
- なぜプロンプト逐語: プロンプト駆動の仕組みでは、その正確な文言こそが機構。logic の「内部語ゼロ・一般エンジニア語で平易化」規律はプロンプトに適用すると機構を壊す(言い換え=別物)。owner が見たいのは動かしている当の指示そのもの。範囲をプロンプト本文に限定したのは、ルール/spec まで逐語化すると logic が証拠の貼り場と化し「今こう動く」の散文説明が痩せるから ── 散文(平易・内部語ゼロ)と逐語ブロック(無改変・内部語可)の二層を分けて両立させる。
- 着地(本体に反映済み): `templates/flow.html` 削除。SKILL.md を logic 単一 view に再構成(2枚表/流れ節/BEATS 規約/narrative 凍結/shell 2ペインを撤去、名前の由来を「仕組みを端から端まで貫く一本の線」に再定義、frontmatter description 差し替え)。`templates/logic.html` に「プロンプト全文(逐語)」節と暗色 `<pre>` ブロック(.pr)を追加、header sub の流れ参照を削除、language ルールに逐語ブロックの内部語ゼロ例外を明記。global CLAUDE.md の Human-facing view layer 節を two-pane → logic 単一に書換(流れ廃止・逐語例外を明記)。
- 触らなかった: global CLAUDE.md の4-role doc governance の narrative(5th role)。これは人が書く凍結ナラティブの doc role であって throughline の生成物ではない ── throughline が narrative を吐かなくなっただけで role 概念は残す。session start orientation の `.lavish` 古さチェック(/throughline 誘導)も logic 単一でそのまま有効。

## 2026-07-01 背景トグル(畳んだ <details>)を logic に追加。流れ廃止と矛盾しない境界を引く
- オーナー要望: 「そういう決定をした背景とかを、トグルで開けるようにもっと具体化できたらいいね」。
- 一見、前日に畳んだ流れ(経緯)view を戻す要求に見えるが、別物として切り分けた ── 流れ view = 時系列の物語(筋・beat・誰の一手)を上から読む独立ページ。背景トグル = 目の前の「今の決まり」に錨を打ち、その「なぜこの形か」だけを畳んで添える(既定は閉)。前者は読まれず畳んだ、後者は表の面をクリーンに保ったまま一クリック下に why を置く漸進開示。SKILL.md に「今の選択への『なぜ?』であって時系列の物語ではない ── 畳んだ流れ view を裏口から戻さない」と境界を明記し、裏口復活を塞いだ。
- 実装: JS 不要の素の `<details>/<summary>`(自己完結を保つ・file:// で開閉)。template に details.why の CSS(破線区切り・▸/▾ 背景ラベル・marker 非表示)と例カードを追加。SKILL.md 作り方に任意 step として追加(背景の無い決まりには付けない・中身は経緯記録から平易語=内部語ゼロ側)。logic.html 上端コメントの「埋めるもの」にも項追加。
- demo(logic-throughline.html 再生成): 設計原則5枚それぞれに背景トグル。中身は decisions から平易語で起こした(例:「線は一本に絞った」← 流れを全然見ないの一手 / 「言葉は二層」← プロンプト全文要求 / 「一枚・自己完結」← 2ページ+束ねる土台の混乱)。

## 2026-07-01 出力先を `.lavish/` 必須化(無ければ作って導入)。成果物/cwd fallback を撤去
- オーナー要望: 「lavish 必須にできないのかな? なくても導入させるようにしたい」。
- 旧 fallback 階段(`.lavish/` → `成果物/views/` → 作業ディレクトリ直下)は出力が散らばり「どこに出たか」が毎回ブレた。`.lavish/` を唯一の家に固定し、無ければ作る(bootstrap)に変更。`成果物/`・cwd 直下の逃がし先を撤去。場所は repo ルート、repo-shape がスロットを定めればそれに従う(委譲は維持)。
- 波及: SKILL.md 出力先節を書換。global CLAUDE.md の「A repo may keep a `.lavish/`」は据置 ── throughline が必須化で常に導入するので、結果として repo は常に1つ持つことになり矛盾しない(may は repo 一般の記述)。
- demo に反映: データの流れ ③出力 に「常に同じ定位置・無ければ作って導入」chip、設計原則に「出力の家は決め打ち」カード+背景トグルを追加。新ソースハッシュ 9bd1b2b6c033。

## 2026-07-01 自己 view を「お手本」に格上げ。骨組みテンプレは差し替え強制のコピー元として残す
- オーナー気付き: 「これってテンプレートにできますよね」。焼いた logic-throughline.html が全機能の埋め済み実物なので、抽象プレースホルダ骨組みより手本価値が高い。
- fork をオーナーに確認(AskUserQuestion): (A)骨組みを実例に置換 (B)骨組み残し+自己viewをお手本リンク (C)現状維持 → (B)を選択。理由: 骨組み(空欄)は差し替えを強制し残留を防ぐ・自己view(満タン)は密度/声/トグル・逐語の見え方を示す、と役割分離。(A)は templates と live view が重複し両方更新になる欠点があった。
- 実装: templates/logic.html は骨組みのまま。SKILL.md 作り方の冒頭に「お手本 = `.lavish/logic-throughline.html`(throughline 自身の埋め済み view)、骨組みはコピー元」と役割分離を明記。お手本を丸ごとコピーしない注意(中身が throughline 固有で残留)も添えた ── overfitting/コピペ残留の予防。
- 鮮度: SKILL.md 変更でハッシュ b0af602d36a6 に更新、お手本=自己 view を焼き直し(逐語ブロックにお手本の記述が入る・自己参照で整合)。生成は scratchpad/gen_logic.py(SKILL.md を読んで html.escape し逐語埋込)で再現可能。

## 2026-07-01 skill-shape パス: SKILL.md を executor 向けに削ぐ(意味は不変)
- /skill-shape 適用。物差し = 前進命令のみ・履歴禁止・強調禁止・手折り返し禁止・WHY≤1節・description 識別的。
- 削り: (1)履歴撤去 ── 「名前の由来」段+「かつては流れ+ロジック…旧称 session-dag」の経緯パラを削除(maintenance 材)。(2)README 声の冒頭導入段落を削除し `# throughline` 直下を「出力」節開始に。(3)WHY/装飾を1節以下へ ──「(正確な文言こそが機構)」「従来通り」「(必須化)」「(repo の常設フロント)」「畳んだ流れ view を裏口から戻さない」(履歴参照)を除去、重複整理。(4)description に「経緯を時系列で辿る物語でも決定台帳の焼き直しでもなく」の NOT 識別子と背景トグル言及を追加。
- 不変: logic 1枚・逐語プロンプト・背景トグル・.lavish 必須・骨組み+お手本 の全機能を保持。振る舞いは変えず表現だけ削いだ。
- ディレクトリ/frontmatter は適合で不変。_dev・.lavish の版管理は本リポの doc governance(意図的 commit)が skill-shape の「版管理外」より上位で勝つと判断し維持。オーナー ratify 済み。お手本 view を焼き直しハッシュ 3699abc314cd に整合。

## 2026-07-01 aftercare ripple-check: repo-shape を新契約に追従(narrative を throughline の産物から切離)
- throughline 再設計(logic 単一・flow/narrative 廃止)の前方整合を repo-shape へ波及。repo-shape:34/55 が旧契約「`.lavish/` = flow/logic」「throughline が `narrative/` frozen flow を所有」と記述していた。
- 修正: `.lavish/` = logic view のみ、narrative は throughline の出力でなく repo-local 5th doc role(claude-md/人が持つ)へ帰属、と明記。narrative/ スロット予約自体は repo-shape に残す(doc role として有効)。判断 = throughline は flow も narrative も吐かなくなったので所有主張を外す(削除でなく帰属替え)。
- present-only(未着手): global CLAUDE.md:38 の narrative「frozen flow」+ 由来 throughline-* は歴史的由来+doc role 定義で新契約と矛盾せず据置。handoff SKILL の「throughline = 人向け retrospective」表現は logic(現在形)へ僅かにズレるが、handoff は別セッションの未 commit 編集中につき触れず提示のみ。
