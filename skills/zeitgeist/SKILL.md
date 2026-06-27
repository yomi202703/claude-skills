---
name: zeitgeist
description: 問いをまだ持たない「探索」検索＝最適化のツマミを自分で握る SNS フィード。多火元（API＝鮮度/velocity の土台 ＋ WebSearch＝枠の外の広さ）から今の勢いを生で集め、手で選んだ複数の「目」（解釈の角度。トピック絞りではない）で同じプールを読み直して並べて見せる。
---

## 二層の源 — 役割分担

固定 API で鮮度、WebSearch で広さ。

### 鮮度バックボーン = API群

本物のタイムスタンプで velocity を自前計算できる。実行時に並列 WebFetch。`{YYYY-MM-DD}` は会話 context の「今日」から展開。

- Hacker News:
  ```
  http://hn.algolia.com/api/v1/search_by_date?tags=story&numericFilters=points>80&hitsPerPage=50
  ```
  `points` / `created_at` / `num_comments` / `url` から velocity = points/経過h。

- lobste.rs:
  ```
  https://lobste.rs/hottest.json
  ```

- GitHub:
  ```
  https://api.github.com/search/repositories?q=created:>{YYYY-MM-DD}&sort=stars&order=desc&per_page=25
  ```

- arxiv:
  ```
  http://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:q-bio.NC+OR+cat:econ.GN+OR+cat:stat.ME&sortBy=submittedDate&sortOrder=descending&max_results=20
  ```

- はてなブックマーク hotentry:
  ```
  https://b.hatena.ne.jp/hotentry/it.rss
  https://b.hatena.ne.jp/hotentry.rss
  ```
  RSS 1.0(RDF)。`hatena:bookmarkcount` を score、`dc:date` を created に velocity = bookmark/経過h。

- CN 火元（V2EX 等、velocity 取得可＝per-item タイムスタンプ露出のものは印あり）: 対象・エンドポイントは cn-search の reference/sources.md。取った素材は下記 velocity 節の式で一様に created から再計算して混ぜる。

補助（取れれば）: PyPI / npm の新着・急伸。CN の補助火元（掘金等）は cn-search。

### 広さ = WebSearch（レンズ実行系）

固定 API の外、ロングテールのブログ・非定番ドメインへ手を伸ばす＝目を増やす方向。鮮度の土台にはしない。レンズの角度を WebSearch クエリとして撃つのはここ（後述）。出し惜しみせず積極的に複数本撃ってよい — 広さは WebSearch 量で稼ぐ。

### 広さ補助 = Antigravity（Gemini）

CN・動画系 velocity を Gemini 橋で取る機構（撃ち方・受け方・承認 grant・cache パス）は cn-search が所有。広さの一手としてそれを呼ぶ。

## velocity — stateless

履歴を持たず急上昇を出す核:
```
velocity = score / 経過時間(h)
```
絶対 score トップはもう主流＝枠の中。velocity はまだ飽和前＝枠の外に残りやすい。絶対人気より velocity 優先。2日前のホットは経過で自然に沈むので state ゼロでも毎日 churn する。

極小 age ガード（必須）: age→0 で velocity が発散する。`age < 1.5h` は順位付けに使わず「✨新着・勢い未確定」で別扱い。

## 目（レンズ）= 解釈の角度、トピックではない

「目はたくさん持つ」の核:

1. 火元（API＋WebSearch）で広い勢いプールを1つ作る（生の勢い、レンズなし）。
2. 同じプールを複数の目で読み直す。各目は `reference/lenses.md` の解釈の角度。同じ項目が目によって違って見える。
3. 目ごとにブロックを分け、各目は拾った数件＋「なぜ差すか」一言。件数は揃わなくてよい
4. 各目は自分の角度で WebSearch を積極的に撃ち、火元が拾えなかったものを補ってよい。目は多いほどよい。

レンズは揮発する: 起動引数でその場選択、保存も学習もしない。
- 引数なし … 目なし＝純 velocity プールをそのまま出す。
- `zeitgeist 逆張りの目 二次効果の目` … 指定した目で読み直す。
- `zeitgeist 自分から最遠の目` … わざと外す。
- 「いろんな目で」 … `reference/lenses.md` から対照的な 3〜4 個。

## 出力 — 発見リスト

```
## 今の勢い <YYYY-MM-DD HH:MM>  目: <かけた目／なし>

### 🌐 生の勢い（目なし・velocity 降順）
| 勢い | 項目 | 一言で何が新しい | なぜ今(velocity根拠) |
|------|------|------------------|----------------------|
| 🔥 | <title> | | 6h で +420pt |
| 📈 | <repo> | | 4日で +1.2k★ |
| ✨ | <arxiv> | | 投稿2日・未言及 |

### 👁 <目の名前> で読むと
| 項目 | この目が差す理由（1行） |
（目ごとに繰り返し）

### 取得失敗
<落ちた源があれば一行ずつ。無ければ「なし」>
```

記号: 🔥急（velocity 高）/ 📈伸 / ✨新（勢い未確定）。