# xlsx-router 全面再設計 (2026-06)

ルート `DESIGN.md`(iter5 の family-router 案、STATUS: deferred)を supersede する。
grill-me で存在意義から各分岐まで詰めた合意設計。deep-strict 調査を根拠に持つ。

## 目的

原典 xlsx を「忠実 かつ AI ネイティブ」な成果物に変換する。
AI ネイティブさは事前解釈ではなくフォーマット由来とする。

## ゲート結論

- 作業は存在してよいが、出発点は「コードの全面書き換え」ではなく
  「ターゲット成果物の再定義」。stuckness の原因は実装スコープでなく
  「忠実かつ AI ネイティブな変換物」の未定義だった。
- 発端の実害は `xlsx_classify.py` の overfit した header 検出
  (CHANGELOG が "whack-a-mole" と自認)。これは下記設計で「不要化→削除」。

## 成果物(単一既定 + 2例外に収斂)

- 既定: 忠実な構造保存 HTML
  - 結合 → rowspan/colspan(forward-fill で潰さない)
  - 多段ヘッダ → ネスト thead/th
  - 静的セル色・塗り → inline style(色=意味を保存)
  - number_format 準拠の日付化(46163 問題の唯一の確定対処)
  - 図形/シェイプテキスト → アンカー注記
  - 解釈は入れない(選択肢分割・カテゴリ正規化・ヘッダ確定をしない)
- 例外1(巨大): コンテキストに載らない均一・大 db → SQLite
  (LLM が SQL クエリ=大規模では AI ネイティブ)。複雑さとサイズは
  反相関するため難シートはここに来ない。
- 例外2(レイアウト): 条件付き書式由来の色、または意味がセルでなく
  配置・図形に宿るシート → 画像(Claude が PNG 直読)。

## triage(誰が決めるか)

- Claude が毎シート レビュー(コストは許容、決定論の盲点を避ける)。
  shape_probe(決定論の構造ビュー、生値なし)+ 生成 HTML を見て
  「HTML で十分/画像 overlay/凡例/巨大で SQLite」を schema 制約付き判断。
- 決定論の役割は反転: Claude に証拠を渡し、安全網を張る。
  Claude が破れない hard 制約は2つ:
  - 忠実性 = verify ゲート(原典セル全存在、欠落で変換失敗)
  - 物理サイズ = 溢れたら SQLite 強制
- header 検出ヒューリスティック(detect_header_row + weight 群)は廃止。

## 根拠(deep-strict 調査)

- 構造把握では text エンコード ≥ 画像、VLM-Image は行列インデックスが
  壊滅的(TabVerse 2606.09578, primary)。→ Claude に画像で構造を
  読ませない。vision は layout/図形 overlay 限定。
- LLM-as-router は2026主流だが tool 選択幻覚リスク → schema 制約 + fallback。
- 本番標準は hybrid/tiered だが、ユーザがコスト許容を明言したため
  「Claude 常時レビュー + 決定論は証拠と安全網」へ寄せた。

## 意識的に飲むトレードオフ

- 「画像/凡例を上乗せするか」のルーティングは多少非再現。
- 重要不変条件(忠実 HTML が常に存在・データ損失ゼロ)は決定論で固定。
- 生成 HTML 自体は決定論なので golden テストは変換器で存続。

## テスト物語

- 決定論 golden: HTML 変換器の出力
- 忠実性 hard ゲート: verify を全変換に適用
- eval(fresh-Claude answerability): 「AI ネイティブ」の本品質基準
- classify ルーティングの golden 完全一致: 廃止

## 最初の一歩 — ツール bake-off(本実装ゼロ行)

- 最難関3ファイル: 法人契約チェックシート(多段ヘッダ)/
  業務概要・QA のプランコード(spec ブロック)/ transposed_field_major
- 候補3つ: LibreOffice `--convert-to html` / xlsx2html / 手書き openpyxl
- 採点3軸: 忠実性(verify + 結合・静的色保持)/ AI ネイティブ
  (fresh-Claude が HTML だけで回答)/ トークン量
- 経験的に勝者確定 → 変換器の土台に。足りない分(図形注記・日付・
  画像フラグ)だけ足す。必要ツールは install。

## 既存資産の処遇

- 残す: xlsx_drawings(HTML 注記供給)/ xlsx_visual(画像例外)/
  xlsx_verify(hard ゲート昇格)/ xlsx_materialize(巨大→SQLite 例外)/
  xlsx_primitives / shape_probe(Claude の構造ビューとして復活)
- 消す: xlsx_classify の header 検出と routing
- 新規: xlsx_to_html.py(bake-off 勝者のラッパ)
- 書き直し: SKILL.md(HTML 既定の思想)、docs 再編
- 保留(eval が要求したら): 意味的凡例層

## bake-off 結果 (2026-06-22)

最難関3シート(法人契約チェックシート=多段ヘッダ147結合 / 基本情報一覧=多段ヘッダ
/ transposed_field_major の正解データの確認=転置875値)で
LibreOffice html / xlsx2html / 手書き openpyxl を比較。
注: プランコードは 4334 行で SQLite 例外に回るため HTML bake-off から除外し、
HTML 経路の実対象である 基本情報一覧 に差し替えた。

忠実性(正規化後・原典非空セルが HTML に存在する率):
- 手書き openpyxl: 100% / 100% / 100%(全勝)
- xlsx2html:       100% / 100% / 93.5%(転置で57値欠落)
- libreoffice:      98.3% / 100% / 93.9%(転置で53値欠落)

トークン量(cl100k):
- 手書き:      8145 / 5693 / 11414
- xlsx2html:  60946 / 59219 / 169827(4〜15倍)
- libreoffice:57395 / 24309 / 163343

結合保存(rowspan/colspan 出現数)は3ツール同値(167/18/2)。

判定: 手書き openpyxl が忠実性・トークン両軸で決定的勝利。既製ツールは肥大かつ
転置でセル欠落。→ 変換器の土台は手書き openpyxl。`xlsx_to_html.py` を新規実装。

AI ネイティブ性 eval(fresh subagent に手書き HTML のみ、構造 priming なし):
- 多段ヘッダの大分類6カテゴリ + colspan を完全正答
- 転置構造(行=フィールド・列=レコード)を transposed.md ヒント無しで自力解読、
  レコード値の lookup 正答
- 唯一のスリップ: 区分=新契約 が rowspan=50 で全データ行を跨ぐケースで、
  消費側が行数を誤外挿(96 行と誤答、実際約50)。忠実性の問題ではなく消費側推論ミス。
- 結論: HTML は AI ネイティブとして妥当(3.5/4)。spanning-label の rowspan は
  enrichment 層を起動すべき具体シグナル(保留解除の最初の候補)。
