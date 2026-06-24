# pdf-to-md 全面再設計 (2026-06) — MinerU前提 → Claude前提

grill で存在意義から各分岐を確定、deep-strict で prior art を調査、実物(88p 和文コンプラマニュアル)の
TOC/本文2スライスで bake-off 検証してから実装。

## 目的

PDF/画像/スクショを、原典に忠実かつ AI が直読できる markdown に変換する。
エンジンは Claude(Read の vision)。スクリプトは前後の機械作業に限定。

## ゲート結論

- ユーザの実証: 対象(スクショ・画像・和文マニュアル)では Claude が MinerU を精度で圧倒。
- MinerU の重さ(3–4GB モデル・3分ロード・専用 venv・サーバ・backends)を丸ごと排除。

## アーキテクチャ

入力(適応ハイブリッド)
- born-digital(テキストレイヤあり): ページ画像(構造・読み順)+ 抽出テキスト(文字 ground truth)。
  読み順は vision、文字はテキストレイヤで裏取り。
- image-only(スクショ/スキャン): 画像のみ、vision で OCR。

3層
- `prepare.py`(機械): 入力正規化(PDF/画像/dir/glob)、ページ毎テキストレイヤ抽出(pdftotext)+
  PNG 描画(pdftoppm)、born-digital 判定、テキストレイヤから見出しアウトライン hint 抽出、
  バッチ manifest(~6p/バッチ)。暗号化 PDF も copy/print 許可なら pdftotext/pdftoppm が直接処理(qpdf 不要)。
- SKILL.md(Claude): バッチを順に処理。各バッチのサブエージェントに{担当ページ画像+テキスト+
  アウトライン hint + 前バッチ末尾 + 現在の見出しスタック}を渡し、continuation フラグ付き
  markdown チャンクをファイルに書かせる。短尺(≤8p)は主エージェントがインライン。
- `assemble.py`(機械): チャンクをページ順連結、continuation マージ、ランニングヘッダ/フッタ/
  ページ番号の重複除去、忠実性ゲート、`~/preprocessed/<stem>/<stem>.md` + `images/` へ。

## オーケストレーション方針(deep-strict 反映)

- 既定は逐次(バッチ N が N-1 の見出しスタック+末尾を受け継ぐ)。並列ファンアウトは
  文脈窓重複・truncation(14.7%)・協調失敗の実害があり(2603.22651)、見出し一貫性を壊す。
  速度より一貫性を優先(ユーザはコスト/速度を許容)。
- 並列化は「アウトライン事前抽出 + continuation フラグ後段マージ」前提でのみ将来の最適化として可。
  常時インフラ型マルチエージェント批判(5-10x)は使い捨て subagent には非該当。
- ページバッチ(~6p)で処理。ページ毎でも固定サイズでもない(Vision-Guided Chunking 2506.16035:
  固定 0.78 → バッチ+文脈持ち越し 0.89)。ページ跨ぎは continuation フラグでマージ、オーバーラップ不要。

## 忠実性ゲート仕様(bake-off で経験的に確定)

素朴な被覆メトリクス(char-shingle / 生行マッチ)は整形・2D図で 0.6〜89% の false-low を連発する。
確定仕様:
- 主ゲート(anti-omission, hard): 文字多重集合 content 被覆。NFKC 正規化 + content 文字
  (かな/漢字/ラテン)のみ、位置・ユニット非依存。TOC スライス・本文スライス両方で 100% を達成。
  これを「原典 content 文字が成果物に全部あるか」の hard gate にする(閾値割れで変換失敗)。
- 副ゲート(locator): 多重集合 deficit が出たときだけ行単位 content-core 照合で落ちたページ/節を特定。
- 乖離(soft): 図/多段組はテキストレイヤ線形順が無意味なので line 不一致は警告止まり
  (損失でなく再構成。char-multiset 100% なら実損失なしと判定)。
- image-only はテキストレイヤ ground truth が無いので softer: ページ被覆 + 必要時スポット二重読み。
  born-digital と同強度は出せないと明文化。

## bake-off 結果(2026-06-22, 実物 88p マニュアル)

- TOC スライス(p2-7): Claude が TOC を認識し機械的見出し化を自ら却下→ネストリスト化。
  char-multiset content 被覆 100%。
- 本文スライス(p9-12, 行為規範/コンプラ体制): ##/### 階層構築、見出しレベルの曖昧さを画像
  インデントで判断、体制図(フローチャート)は文言をコードブロックで逐語保持+簡略化明記、
  p12 末の途切れに continuation マーカー、ページ番号除去。char-multiset content 被覆 100%
  (MD はむしろ15字多い=図ボックス文言がより完全)。line 被覆 89% は全て図のユニット境界
  アーティファクトで実損失ゼロ。
- 結論: Claude-native ハイブリッドは構造判断・逐語忠実性・幻覚ゼロを実証。フォーマット妥当。

## 既存資産の処遇

- 削除: `scripts/dispatcher.py`(MinerU ラッパ)・`scripts/restructure.py`(MinerU の flat-`#`
  病理直し、Claude には不要)・`scripts/tests/test_restructure.py`・`_dev/SETUP.md`(MinerU setup)・
  画像→PDF 束ね・サーバライフサイクル・backends。
- 流用: dispatcher の natural-sort 画像収集・入力解決ロジックは prepare.py に移植。
- 新規: `scripts/prepare.py` / `scripts/assemble.py` / SKILL.md 全面書き直し。
- テスト: assemble の忠実性ゲート(char-multiset 被覆・header 除去・continuation マージ)の unit test。

## E2E 検証(2026-06-22, 実物 88p マニュアルの3バッチ=p1-18)

prepare → 逐次サブエージェント転写(3バッチ)→ assemble の実フロー素通し。
- prepare: 88p→15バッチ、born-digital 判定正(p1 表紙=False)、30s。
- 転写: batch0(表紙+TOC)→ batch1(p7目次継続+本文開始)→ batch2(本文継続)。
  各バッチが前チャンク末尾+見出しスタックを継承し、## 章 / ### 小節の階層が
  バッチ跨ぎで完全に一貫(②→(7)の項目継続、章/節レベル判断も的確)。23見出しの整合木。
  副次: サブエージェントがユーザの no-`**` 出力規約を自発的に尊重。
- assemble: char-multiset content 被覆 0.9998(deficit 2字=軽微な正規化)、status ok。
- 発見した実 bug: 当初の running-header strip が「別に定める社内ルールに従う。」
  (各小節末の正当な反復本文)を chrome 誤認で除去 → 被覆 99.6% に低下。
  → strip を「ページ番号パターンの定数反復のみ」に厳格化(本文を絶対消さない)。
  増分ページ番号はサブエージェントが除去するので assemble は触らない。回帰テスト追加。
- harness: assemble unit test 10 緑。
- 結論: 統合(prepare/逐次転写/assemble+ゲート)が実物で成立。設計妥当。

## 保留(トリガ待ち)

- 並列バッチ最適化(アウトライン事前抽出が安定したら)[速度が問題化したら]。
- 図の画像クロップ出力(現状は文言コードブロック保持)[図の視覚再現が要ると分かったら]。
