---
name: deep
description: 最新性・信頼性が結論を左右する web 調査で使う。「最新の〜は？」「ベストプラクティス」「技術選定」「state of the art」「最適化」「比較したい」系。素の WebSearch だと古い情報や SEO 記事に引っ張られて誤判断するリスクがある時に呼ぶ。雑な用語確認・単発の事実確認には使わない。
---

# deep

固定パイプライン: **Phase 1a → 1b → 2 → 3 → 4**。
WebFetch は重い、合計 3 回まで。WebSearch は新規 URL 率 < 30% になるまで自由。

## Phase 1a — 並列メタスイープ（subagent 実行）

Agent ツールで Explore 型 subagent を複数本並列起動。各 subagent への prompt は短文1行:

```
WebSearchして「{クエリ}」。URL / title / 1行 snippet の表だけ返す。
```

クエリ設計（典型 2-3 本、トピック次第で増やす）:
- 時間アンカー: literal YYYY-MM（"X 2026年5月" / "X May 2026"）。`2025-2026` / `last year` / `recent` 禁止
- 軸を変える:
  - 鮮度狙い: "X 2026年5月"
  - 視点違い: "X vs alternatives" / "X benchmark"
  - 否定形/限界: "X failure" / "X limitations" / "X 批判"
- 言語: 日本固有（企業/法規/国内界隈）= 日本語必須 / 学術・OSS・海外発 = 英語優先 / 両方該当 = 各軸を両言語

subagent 戻り値（圧縮表）を本体 context に集約してから Phase 1b へ。

## Phase 1b — アンカー fetch（条件付き、最大 1 件）

バッファに以下があれば 1 件だけ WebFetch、無ければスキップ:
- タイトルに `survey` / `overview` / `awesome-` / `guide` / `comprehensive`
- 公式 doc のインデックス
- 発行日 1 年以上前のサーベイは対象外

## Phase 2 — 未知語解決（必須）

Phase 1 結果を見て自問:
1. 自分が知らない固有名詞・術語はあるか
2. 「文脈から類推して既知扱い」していないか
3. 学習データ cutoff 以降の日付タグを持つソースはあるか

未知語を **網羅列挙** し、各項目が解決するまで WebSearch を追加。本数は内容駆動（未知語ゼロになったら次へ）— 数で打ち止めない。並列実行可。Phase 1 で全て既知の場合のみスキップ。

クエリには Phase 1a と同様に literal YYYY-MM を必ず付ける（"stable な概念だから不要" という判断は禁止 — SEO バイアスで update を逃すリスクの方が大きい）。日付付きで結果が空 or 不十分な場合のみ、同クエリを日付なしで再実行する fallback を許可。

## Phase 3 — 一次ソース fetch

一次ソース = 公式 doc / 公式リポジトリ / arxiv / openreview / 学会原本 / 当事者発信（GitHub 紐付き個人ブログ含む） / 公式リリースノート。

バッファから一次ソース 2-3 件を WebFetch。0 件なら「一次ソース不在の暫定回答」と明記して二次情報で出力。

抽出: ベンチ数値 / バージョン / 日付 / 相対表現（「現在は推奨されない」「以前は X だったが今は Y」）/ 対立点。

## Phase 3.5 — Evidence Sufficiency Check（必須）

Phase 3 で取った証拠を Phase 4 で出力する前に自問:

- **Gap**: 問いの全側面に証拠があるか
- **Corroboration**: 主要主張は 2 つ以上の独立ソースで裏付けられてるか
- **Novelty**: 既知の事実ばかりになってないか
- **Redundancy**: 同じ情報の繰り返しになってないか
- **Relevance**: 証拠が本当に問いに答えているか（distractor じゃないか）

1 つでも NG なら Phase 2 か Phase 3 に戻る（fetch 予算が残っていれば）。予算が尽きていれば「{側面} の証拠不足」を出力に明記して進む。

## Phase 4 — 出力

ユーザーの問いに普通に答える。形式は問わない。ただし:
- 各根拠 URL に日付を付ける
- 一次ソースか二次ソースかを区別できる形で示す
- 古い情報を引いた時は鮮度限界を明示
- 確信を持てない時のみ AskUserQuestion で「A. 確定 / B. 深掘り / C. 再調査」を提示

## 失敗時

不明 / 取得失敗を**捏造で埋めない**。

- WebSearch 0 件: 「検索結果が得られなかった」と明示
- WebFetch エラー 3 回連続: 当該ソースは snippet で代替
- Phase 2 で用語が依然不明: 「未解決」と明記

## 打ち止め

- 一次ソース 2 件以上 fetch 済み
- または WebFetch 3 回到達
- または 新規 URL 率 < 30% かつ Phase 2 完了
