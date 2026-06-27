# skill-shape decisions (append-only ADR)

新しい項目は下に足す。過去エントリは書き換えない。

## 2026-06-27 初版起草(jibun-de で全30 skill 通読の上)

- 動機: ユーザーのAI不満3つ＝(1)毎回冗長 (2)SKILL.md を README と誤認 (3)ディレクトリ無秩序。Claude 同梱の skill-creator は boilerplate 生成器で、この3つを直さない。
- 探索: jibun-de モードで30 skill のディレクトリを走査、構造的に情報量の多い10本(judge-loop/consultant/repo-shape/claude-md/grill-me/skill-gripe/recall/pdf-to-md/atlas/deep-strict)と governance docs(TODO/STATUS/decisions 実フォーマット)を全文通読。
- 核心発見: 3不満は別問題でなく一つの欠落の三つの顔＝「各成果物の audience が未定義」。三 audience 分離(description→ルーター / SKILL.md→実行者 / docs→保守者 / _dev→保守 governance)で全て解ける。judge-loop の STATUS が既にこの分離を明示していた。
- 設計判断: claude-md と同型の「生成器でなく方法」型＋judge-loop と同型の薄いオーケストレータ。必要機械の大半は既存スキルに在り再実装でなく compose(grill-me/repo-shape/claude-md/skill-gripe/gemma-prompt)。単独所有は skill 固有差分のみ。
- 命名: 候補 skill-shape / skill-forge / skill-author / meta-skill。ユーザー裁定=skill-shape(repo-shape の対・命名規約と対称性。skill-gripe が回収側、本スキルが制作側)。
- 正準ディレクトリ: 実在パターンの最大公約数＝SKILL.md(必須)＋scripts/reference/templates/docs/_dev(必要時のみ)の6名。空 scaffold 禁止。生成/data は _dev 下＋gitignore。
- 出荷ゲート: 3不満をそのままチェック項目化(executor-voice/no-WHY-bloat/正準ディレクトリ/discriminative description/style/非重複)。owner が diff で ratify。

## 2026-06-27 普遍化へ全面書き直し(judge-loop 一家から脱結合)

- 指摘(オーナー): スキル作成スキルは judge-loop 系列と概念的に独立のはず。初版は core を独立に書いたつもりで、実際はこの repo の兄弟一家(grill-me/repo-shape/claude-md/gemma-prompt/skill-gripe)への配線・四役 governance・`**`禁止 style・「薄いオーケストレータ」自己規定を内在物のように編み込み、過剰適合していた。これは皮肉にも global CLAUDE.md 規則3/judge-loop G9(No overfitting)をスキル自身が犯した形。
- 普遍/環境固有の切り分け: 普遍=三 audience 分離・runtime vs maintenance ディレクトリ契約・蒸留パス・出荷ゲート(Claude Code のスキルという仕組みに内在し誰でも真)。環境固有=兄弟スキルへの具体 route・四役 governance 名・style・世界観。
- オーナー裁定=「完全に普遍だけ」。兄弟スキル名・governance・style 規約を SKILL.md 本文から全除去。Composition は「compose, do not duplicate」の一般原則へ抽象化(具体スキル名を出さない)。description からも兄弟参照(repo-shape/skill-gripe sibling 等)を除去。
- 別案「核は普遍＋Local wiring 分離」(私の推奨)は却下。手持ち route は消えるが汎用純度を優先。
- 据え置き: `_dev/` 四役はこのスキル自身の保守領域ゆえ存続(このリポの規約に従うのは正当=本文の普遍性とは別レイヤ)。
- 副産物: Boundaries 1行目(Composition の焼き直し=非重複ルール違反)を統合で解消。前ターンに自分のゲートが自分の冗長を検出した件もここで着地。

## 2026-06-27 本丸の言語化 + 存在ゲート除去 + 自身を絞る

- オーナーの真意明確化: 本来言いたかったのは「冗長な SKILL.md を作るな」。気に食わない AI 挙動=(a)README 扱い (b)過去の版/履歴を引きずる (c)関係ない衝突/edge case を考え始める。これが冗長の正体。
- 反映: 本文に「Write the body for the executor」核を置き、No README-voice / No history / No defensive hedging / No WHY past a clause を明示禁止。出荷ゲートも同4点で先頭化。
- 存在ゲート除去: 「skill-shape と grill-me を同時に打てばいい」(オーナー)。存在可否は skill-shape に内蔵せず grill-me 併打へ。scope を「存在可否は決めない・grill-me を併打」に変更。
- 自己適合(dogfood): 旧版は three-audience/distillation/ship-gate で同じ核を三重説明=オーナーが嫌う冗長。distillation 節を畳み、全体を ~90→~50 行へ圧縮。

## 2026-06-27 bold-for-emphasis を house style から普遍ゲートへ格上げ + deep-strict 適用

- 前ターンで `**` 太字を「house style ゆえ普遍ゲート対象外」と判断したが誤り(オーナー「** 太字を多用もくそ」)。理屈: 太字は文書を視覚スキャンする人間読者向けの装飾で、実行者は太字だから違う動きをしない=README 思考が body に漏れた症状。よって No README-voice の一facet として普遍規則化。
- 反映: skill-shape 本文「Write the body」に No bold-for-emphasis を追加、ship gate にも追加。
- 適用(dogfood 1本目): deep-strict に ship gate を実走。findings=履歴/WHY 2か所(L18 実走確認メモ・L236「廃止」+理由3文)+ ** 78個。2か所をテキスト修正、** を全除去(78→0)。deep-strict は _dev/docs 無しゆえ実走メモの逃がし先が body しか無い構造問題も指摘(逃がし先の新設は今回未実施)。

## 2026-06-27 読み手=非スキャンのモデル、に原則を揃える(オーナー指摘)

- オーナー指摘:「SKILL.md は本来人間が見るものではない」。前ターンの私の bold ルール理由付け「a human scanning a document」と、その後の「強調を構造へ昇格して目立たせる」提案は、消したはずの人間スキャン前提を裏口から戻していた。
- 是正: 実行時の読み手はモデル=全トークンを読み飛ばし読みしない。よって body 内で何かを「目立たせる」必要は原理的に無い。
  - 残す=区切る構造(見出し/箇条書き/コードフェンス。機械パースを助ける)。
  - 消す=注意ランク付け(太字・装飾的 必須/重要。飛ばし読みする人間にしか効かない)。
- 反映: essence に「runtime reader はモデル・非スキャン」を明記。bold ルールを「No emphasis markers」に書き換え(理由を人間装飾→非スキャン読み手に強調は無意味へ)。ship gate 同期。
- 撤回: deep-strict の「強調を構造へ昇格」提案。bold 除去のみで確定、昇格はしない。

## 2026-06-27 dogfood 2本目: ai-wiki

- 標的選定: 全 SKILL.md の `**` 密度を locate → ai-wiki が突出(131行に bold 126)。小1個勢は `` `**` `` 言及で誤検出=無実。
- findings: (1)bold 126 (2)L6 `# ai-wiki (v5)` 版番号=履歴 (3)`narrative-draft` 表セルの WHY 肥大(self-preference bias/holdout out-of-sample 等)。vault layout/コマンド表/format contract は区切る構造ゆえ保持。
- 適用: bold 126→0(italic は意味保持で残す)。`(v5)` 除去。オーナー裁定 A=WHY の逃がし先を新設 → `_dev/commands-rationale.md` を作成し現役4コマンドの設計 WHY を移送、表4セルを「何をする＋フラグ」へ痩せ(narrative-draft セル ~2050→1080字、情報損失なし=WHY は rationale に保全)。dispatcher smoke OK。
- 残: 本文 prose 節(Discovery drill / Derivation layer / 教科 DAG)に教育 rationale が残る。表(A スコープ)外なので別判断として保留。

## 2026-06-27 manual hard-wrap も human-editor 装飾として禁止(オーナー指摘)

- オーナー指摘: ai-wiki Discovery drill 節の段落途中ハード改行は不要では。
- 同根: 桁折りは固定幅エディタで生テキストを読む人間のための装飾。モデルは桁で折らず、段落途中 `\n` は文を細切れにするだけ。bold/emphasis と同じ「読み手=モデル」原則違反。
- 反映: skill-shape「Write the body」に No manual hard-wrapping(1段落=1行・空行とリスト項目間は構造ゆえ保持)を追加、ship gate も同期。
- 適用: ai-wiki Discovery drill 節を1行へ reflow(ハード改行のみ ai-wiki ではこの節だけだった)。

## 2026-06-27 dogfood 3本目: judge-loop → emphasis ルールを CAPS 含む全般へ一般化

- 標的 judge-loop は密度=bloat ではない標準(bold 0・ハード改行なし・WHY の多くはゲート適用条件=操作的・akatsuki 参照は induction 接地で版履歴でない)。
- 唯一の一貫発見: bold の代わりに普通語 ALL-CAPS で強調(ANY/NOT/THIN/ONCE/OTHER/EXTERNAL/IN FULL/EXPLICIT/GENERATED 等 ~40)。bold と同じ human-skimming 装飾、glyph 違い。emphasis はメカニズム非依存。
- skill-shape の穴を是正: emphasis ルールが `**` 限定だった → 「by any mechanism(bold/italic/ALL-CAPS on ordinary words/必須ラベル)」へ一般化。残す CAPS=名前/定義語(acronym・doc が定義する用語)と区別。
- 自己 dogfood: skill-shape 本文の emphasis-CAPS(FORWARD/ONLY/NOT/SEGMENTS/RANKS/LOAD/DO)を小文字化。WHY は概念名詞として残置(叫ぶ副詞でなく定義語側)。
- judge-loop 本体の CAPS 掃除は保留: acronym/定義語と普通語強調の判断パスが要り、最重要 skill ゆえ独断一括せず diff 提示で確認する案件として TODO 化。

## 2026-06-27 judge-loop CAPS 掃除を適用(GO 後)

- pair リスト方式(各置換1回検証)で普通語強調 CAPS を35箇所小文字化。acronym/定義語(G1-G10/GT/LLM/P0-P4/L1-L3/SETTLE/GATES/CHOICES/SAFE-DIRECTION/PRODUCE·ROUTE·GRILL 等)は全保持。
- 取りこぼし5+文頭化1を最終 audit(全大文字トークン突き合わせ)で捕捉し second pass。残存は SAFE-DIRECTION のみ(正規表現のハイフン割れ=正当)。
- 行数不変75・bold 0・定義ラベル健在を検証。description 再レンダ確認(any/Not limited/thin orchestrator)。
- 学び: blind sed 不可の判断パスでも、文脈付き pair + 各1回 assert + 事後 audit で安全に一括できる。文頭に来た強調語は小文字化でなく文法上の文頭大文字に戻す例外あり。

## 2026-06-27 dogfood: ツール系5スキル一家の README 雛形を発見

- locate(README節ヘッダ/履歴/ハード改行)で、atlas/chatgpt-web/gemini-web/claude-desktop/antigravity が同一 README 雛形(What this is / How it works (for debugging) / Limits + 全段落ハード改行)を共有と判明。executor 指示でなくツール説明書=README-voice の構造版。
- 代表 claude-desktop を機械修正: 段落 reflow(frontmatter/コードフェンス保護・箇条書き継続行を畳む python・86→51行)、CAPS 強調4(DESKTOP/NOT×2/OWN/TITLE)小文字化。
- 判断保留→オーナー確認: `What this is` 節は description 重複+設計WHY ゆえ削除提案。How it works=修復リファレンスで残置、Limits=操作的で残置。家全体へ同処置を広げるかは確認待ち。
- gemini-web に履歴(`used to silently drop`)も別途あり。

## 2026-06-27 ツール系一家5本に同処置を適用(オーナー裁定: What this is 削除＋4本展開)

- claude-desktop: `## What this is`(description 重複＋設計WHY)を節ごと削除。reflow 86→46行。
- atlas/chatgpt-web/gemini-web/antigravity: reflow 済(63→38/80→45/85→44/48→34)。pairs 方式で intro の transport-WHY を trim(operational=ポート/プロファイル/アカウント課金/セッション再利用は残す)、CAPS 強調を小文字化(名前・acronym・エラー定数 NOT_SIGNED_IN/BLOCKED は保持)。
- gemini-web 履歴(`used to silently drop`)→前向き(`Guards ... against a silently-dropped send`)。
- chatgpt-web `## atlas vs chatgpt-web` 比較節→operational な `## Fallback`(Cloudflare 時 atlas へ)に圧縮。
- 最終 audit: 残 CAPS は全て正当(GET/CLI/RESULT/CURRENT=コード内)、履歴語・What this is・bold ゼロ。各置換 count==1 検証・0エラー。
- 学び: 同一雛形の一家は locate→共通ルール確定→pairs 一括が効く。intro は「全削除」でなく『背景WHY を trim・operational warning(課金/副作用)は残す』が正しい(claude-desktop の What this is は全冗長ゆえ全削除、他は一部 operational ゆえ trim、と現物で割れる)。

## 2026-06-27 全 skill 一周完了(CAPS 強調を標準系一家へ展開)

- 標準系(judge-loop と同一著者文体)が CAPS 強調を共有と判明し一掃: judge-loop(35)・task-handoff(11)・consultant(15)・review-server(21)・claude-md(1)。GATES/CHOICES/S1-S12/W*/P*/G* 等の定義ラベル・acronym は全保持、pairs 各1回検証。
- 軽微: deadcode(bold2+italic3+CAPS)・xlsx-router(CAPS3)・zeitgeist(bold1)・work-report(reflow)・gemma-prompt(frontmatter に name 欠落→追加)。
- クリーンで無処置(=直す対象でないことの確認): windows-share/progress/prism/html-deck/ripple-check/repo-shape/onsen/grill-me/recall。repo-shape は既に締まった文体・html-deck は自分の作法を体現。
- 結論: 約30 skill を一周。装飾(bold/CAPS/italic/桁折り)・履歴・README-voice・WHY肥大を除去、operational と定義語は保持。skill-shape は「見つけたら削る」でなく audience(=モデル) と『執行者の動きを変えるか』で残す/削るを割る道具として機能した。

## 2026-06-27 sweep クローズ + governance 現状化

- 旧 TODO P0(実スキル1本で出荷ゲート検証)は全 skill 実走で完遂 → decisions 済ゆえ TODO から除去。
- 旧 TODO P1(出荷ゲートを reference/checklist.md へ切り出すか)を解決=切り出さない。sweep 全域で本文インラインのチェックリストが機能し、別ファイル化の必要が出なかった(skill-shape 自身を薄く保つ判断とも整合)。won't-do として decisions のみに記録し TODO から除去。
- STATUS を sweep 完了・main push(48c9487)・onsen gitignore まで現状化。Active は空(検証フェーズ終了、運用フェーズへ)。Deferred の description-eval は据置(誤 route 観測がトリガ)。
