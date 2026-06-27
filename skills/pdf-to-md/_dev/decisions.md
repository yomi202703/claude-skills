# pdf-to-md decisions / 摩擦ログ

実使用で踏んだ摩擦を事実として残す。設計の経緯は REDESIGN_2026-06.md。

## 2026-06-25 実運用 gripe(原典マニュアル6本=A〜F・born-digital を一括変換)

文脈: あかつき証券のコンプラ原典PDF 6本(本体88p / 株式説明18p / 投信外債35p / モニタリング28p / 高齢取引12p / 高齢GL6p)を一括変換。本体のみゲート PASS(0.9991)、他5本は 0.917〜0.976 で FAIL。

### G1(最重要・契約とゲートの自己矛盾): 剥がせと言ったボイラープレートをゲートが欠落計上 → 偽FAIL
- 転写契約は「Strip running headers/footers/page numbers」を要求する。サブエージェントは正しく各ページの running footer(例「あかつき証券株式会社 … PAGE 14」「関係者限」、高齢GLは「05028‐高齢顧客への勧誘販売…ガイドライン -n-」)を除去した。
- ところがゲートは出力 md を text-layer 原文(footer を含む)と char-multiset 比較する。assemble の recurring-line strip は「ページ番号が増分で毎行ユニーク」ゆえ footer 行を反復と認識できず除去しない(REDESIGN の「増分ページ番号は assemble が触らない=サブエージェント任せ」設計の裏返し)。結果、契約どおり剥がした footer 文字が丸ごと「欠落」に計上される。
- 実測(char-multiset 差分を自分で取って証明): 高齢GL 欠落168字の100%が footer「…高齢顧客への勧誘販売…ガイドライン」+ページ番号×6ページ。モニタ 欠落478字の主成分は「関係者限」×28・「あかつき証券株式会社 PAGE n」×〜25・章ヘッダ「株式(国内株式、外国株式)」断片。本文・条項・表の実欠落はゼロ。
- 症状: footer/divider が多い slide系ドキュメントほど coverage が 95〜98% に張り付き、本文を完璧に取り込んでも 99.5% に構造上到達不能。高齢GL は2回目に本文を100%取り込んでも 0.9717 から1字も動かず(=丸ごと footer 分)。
- 何が問題か: ゲートが「真の欠落」でなく「正しく剥がした定型」を罰する。利用者(私)は FAIL の真偽を判定するため、ゲートと別に自前で char-multiset 差分スクリプトを書いて欠落文字列を復元する羽目になった。ゲートの存在意義(=安心して ship してよいかの判定)が footer 込みドキュメントで機能しない。
- 直し筋(提案): assemble のゲート側で、(a) text-layer からも「ページ番号を含む準反復 footer 行」(各ページ同位置・編集距離小・数字のみ差分)を検出して分母から除外する、または (b) ゲートの ground を「サブエージェントが剥がす前提の footer/page-number を除いた text-layer」にする。少なくとも FAIL 時に「欠落文字の上位N」を出力して footer 由来か本文由来かを即判定できるようにする(現状は coverage 数値と line_coverage だけで、何が落ちたか分からない)。

### G2(検証の非収束): LLM転写の揺れを当てにならないゲートでしか確かめられない
- 転写はサブエージェント(LLM)依存ゆえ再走で取り込み完全性が揺れる。同一PDFで版サイズが変動(モニタ 1回目 37.8KB→厳格プロンプト2回目 49.2KB・投信外債 90→102KB)。1回目は dense な2D表/フロー図を要約・脱落、2回目に「全セル逐語」を明示して回復。
- だが収束したかの判定は G1 で壊れたゲートしか無い。「真の欠落が残るか」を gate 数値から切り分けられないので、結局ページ画像と text-layer を人手照合する必要がある。再走しても footer 分で頭打ちになるため「これ以上やっても無駄」の判断も自前差分でしか付かない。
- 直し筋(提案): G1 を直せば G2 はかなり解消(本文欠落だけが残差に出る)。加えて「low-coverage ページの欠落文字列を実際に表示」する diagnostic があれば、再走すべきページが一目で分かる。

### G3(誤誘導エラー): prepare.py に複数PDFを渡すと全部弾く
- `prepare.py a.pdf b.pdf c.pdf --out-dir …` が `[error] no PDF or images in: [...]` で6本全拒否。単一PDF(`prepare.py a.pdf`)なら通る。SKILL.md は `<input>` を「a .pdf, a directory of images, a glob, or image paths」と説明しており、複数PDF同時=非対応である旨が読み取れない。エラーも「no PDF or images」で原因(=複数doc非対応)を誤誘導する。
- 回避: 1本ずつループで prepare。
- 直し筋(提案): 複数 .pdf を渡されたら doc ごとに分けて処理する、または「1回1ドキュメント」と明示してエラーメッセージを「multiple PDFs not supported in one call; run one at a time」に変える。

### 解消 2026-06-25(G1/G2/G3 を実装で修正)
- G1: ゲートの ground-truth を「footer 込み text-layer 原文」から「ページ端の反復 chrome を除いた text-layer」に変更。`assemble.py` に `_detect_textlayer_chrome`(各ページの上下端 edge=2 行のうち、桁を除いた key が過半ページで反復する行=running header/footer を検出)+ `_strip_edge_chrome` + `_textlayer_ground_truth` を追加し、`faithfulness` はこの cleaned text-layer に対して計測。位置(ページ端)ゲートで反復本文(「別に定める社内ルールに従う。」等=ページ中央)は除外しない。除外した chrome は `textlayer_chrome_excluded` で透明化。→ 契約どおり footer を剥がした文書がゲートで罰されなくなった(footer 多用 slide も本文完全なら PASS)。
- G2: FAIL 時の `gaps` に `missing_samples`(実際に落ちた本文行テキスト)を追加、かつ chrome を gaps からも除外。→ 数値だけでなく「何が落ちたか(footer か本文か)」が出力で即判定可能。自前 char-multiset 差分スクリプトは不要に。
- G3: `prepare.py` で複数 .pdf / PDF+画像混在を着手前に明示エラーで弾く(「multiple PDFs not supported — run once per PDF」「cannot mix a PDF with other inputs」)。誤誘導の「no PDF or images」は解消。
- doc: SKILL.md にゲートの chrome 除外・FAIL diagnostic・1ドキュメント/run・poppler 前提を明記。
- test: `test_assemble.py` に G1(footer 除外/剥がした文書が PASS/反復本文は保持)・G2(欠落本文の表面化、footer 非計上)の回帰を追加。14 緑。E2E スモーク(footer 多用6p born-digital)で PASS、本文1行欠落で FAIL+欠落行表示を確認。
- 残課題(トリガ待ち): edge=2 の位置ヒューリスティクスは「2〜3行しかない疎ページで本文が端に寄る」極端ケースで誤除外しうる[疎スライド型で偽除外が観測されたら]。偽PASSの唯一の穴=「ページ端にあり桁違いだけで過半ページ反復する本文行(例: 各ページ末の合計行)」は ground-truth 除外され落としても検知不能だが `textlayer_chrome_excluded` に出るので目視で気づける[表中心ドキュメントで実害が出たら]。複数PDF一括処理(doc毎 manifest 連続発行)[一括変換の需要が再燃したら]。
- 追加修正(同日): chrome 候補フィルタを `len(_norm_chrome) >= 2` → `len(core(l)) >= 2` に。純粋なページ番号行(core 0字=coverage無影響)を chrome key 化せず、除外リストのノイズを除去。実PDF(reportlab生成・footer付6p born-digital)で prepare→転写シミュ→assemble の実poppler E2E が PASS(footer は chrome_excluded・coverage 1.0)を確認。

### 付帯(環境・skillの責ではない)
- poppler(pdfinfo/pdftoppm/pdftotext)が PATH 未通で初回 `required tool not found: pdfinfo`。/opt/homebrew/bin を export で解決。SKILL.md に poppler 前提を1行書くと親切。
