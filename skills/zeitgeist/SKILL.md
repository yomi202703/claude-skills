---
name: zeitgeist
description: 問いをまだ持たない「探索」検索＝最適化のツマミを自分で握る SNS フィード。多火元（API＝鮮度/velocity の土台 ＋ WebSearch＝枠の外の広さ）から今の勢いを生で集め、手で選んだ複数の「目」（解釈の角度。トピック絞りではない）で同じプールを読み直して並べて見せる。裏取りはしない（拾ったものだけ deep-strict に渡す前段）。状態を持たず嗜好を学習しない＝メタ化しない＝SNS の単眼の偏りへの対抗。「今なんか話題ある？」「最近おもしろい技術」「勢いのあるもの見せて」「○○の目で世界を見せて」等で呼ぶ。
---

# zeitgeist

claim 駆動の deep-strict とは逆向き。問いを持って深掘りするのではなく、問いがまだ無い段階で「何が今おもしろいか」を拾う。狙いは「最適化された SNS、ただしツマミを自分が握る」もの。SNS は挙動から作った単眼を裏で押し付けて嗜好を偏らせる。zeitgeist は最適化を表に出し毎回手で選ぶ。

位置づけ: discovery（ここ）→ ざっと自分で見る → 興味が出たら deep-strict で壁打ち/裏取り。前段。

## 設計原則（崩すと SNS に堕ちる）

- 裏取りしない。source 数も confidence tier も出さない（deep-strict の仕事）。各項目は「一言で何が新しい」「なぜ今」だけ。
- 状態・嗜好を持たない（メタ化禁止）。挙動履歴・嗜好モデル・閲覧プロファイルを作らない＝SNS の偏りの正体を作らない。唯一の成果物は手書きの `reference/lenses.md` だけ。機械が学ぶ＝禁止、人が道具を並べる＝可。
- 鮮度優先・重複許容。dedup 用の既出セットも持たない（それも state）。毎日かぶってよい。velocity churn と WebSearch の変動で入れ替わる。

## 二層の源 — 役割分担

固定 API で鮮度、WebSearch で広さ。混同しない（変動 ≠ 鮮度。WebSearch は recency で並ばないので鮮度の土台にしない）。

### 鮮度バックボーン = API群（velocity は自前計算）

本物のタイムスタンプで velocity を自前計算できる。HN front page（HN 自身の単眼ランキング）は使わず、素の story 流を取り自前で並べ替える。実行時に並列 WebFetch。`{YYYY-MM-DD}` は会話 context の「今日」から展開。

- Hacker News（素の firehose、front_page は使わない）:
  ```
  http://hn.algolia.com/api/v1/search_by_date?tags=story&numericFilters=points>80&hitsPerPage=50
  ```
  `points` / `created_at` / `num_comments` / `url` から velocity = points/経過h。

- lobste.rs（HN と母集団違い＝枠の外要員）:
  ```
  https://lobste.rs/hottest.json
  ```

- GitHub（最近生まれて急に星＝star velocity が構造的に高い。言語不問）:
  ```
  https://api.github.com/search/repositories?q=created:>{YYYY-MM-DD}&sort=stars&order=desc&per_page=25
  ```
  汚染ガード: star は points より gameable（farm/bot）。`description 空 + 言語 null + 履歴薄` の高 velocity repo は疑い「⚠要確認」を付ける。実走で説明なし 2.4k★ の bot 臭 repo が2位に来た実例あり。

- arxiv（score 無し＝「新規」軸。HN/lobste で言及が立てば格上げ。カテゴリは横断、集合は毎回変えてよい）:
  ```
  http://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:q-bio.NC+OR+cat:econ.GN+OR+cat:stat.ME&sortBy=submittedDate&sortOrder=descending&max_results=20
  ```

- はてなブックマーク hotentry（JP 火元。英語圏だけだと JP 発の勢い＝Sakana 等を構造的に取りこぼす＝coverage 欠落なので塞ぐ）:
  ```
  https://b.hatena.ne.jp/hotentry/it.rss
  https://b.hatena.ne.jp/hotentry.rss
  ```
  RSS 1.0(RDF)。`hatena:bookmarkcount` を score、`dc:date` を created に velocity = bookmark/経過h。

補助（取れれば）: PyPI / npm の新着・急伸。落ちても捏造で埋めず末尾に「{源}: 取得失敗」と一行。

### 広さ = WebSearch（レンズ実行系）

固定 API の外、ロングテールのブログ・非定番ドメインへ手を伸ばす＝目を増やす方向。鮮度の土台にはしない。レンズの角度を WebSearch クエリとして撃つのはここ（後述）。出し惜しみせず積極的に複数本撃ってよい — 広さは WebSearch 量で稼ぐ。

## velocity — stateless

履歴を持たず急上昇を出す核:
```
velocity = score / 経過時間(h)
```
絶対 score トップはもう主流＝枠の中。velocity はまだ飽和前＝枠の外に残りやすい。絶対人気より velocity 優先。2日前のホットは経過で自然に沈むので state ゼロでも毎日 churn する。

極小 age ガード（必須）: age→0 で velocity が発散する。`age < 1.5h` は順位付けに使わず「✨新着・勢い未確定」で別扱い（生データに混ぜて1位を乗っ取らせない）。実走で 0.6h が 253/h を叩き全体を吹き飛ばした実例あり。

## 目（レンズ）= 解釈の角度、トピックではない

「目はたくさん持つ」の核:

1. 火元（API＋WebSearch）で広い勢いプールを1つ作る（生の勢い、レンズなし）。
2. 同じプールを複数の目で読み直す。各目は `reference/lenses.md` の解釈の角度。同じ項目が目によって違って見える。
3. 目ごとにブロックを分け、各目は拾った数件＋「なぜ差すか」一言。件数は揃わなくてよい — その日のプールに刺さる角度ほど多く拾う＝それ自体が信号。
4. 各目は自分の角度で WebSearch を積極的に撃ち、火元が拾えなかったものを補ってよい。目は多いほどよい。

レンズはトピック絞りではない。「生物学のニュースを見せろ」＝ドメイン絞り＝SNS の narrowing 再生産。そうではなく「生物学の目で世界を読む」＝広い火元を進化・生態系・淘汰圧のフレームで解釈する。看板は角度型。

レンズは揮発する: 起動引数でその場選択、保存も学習もしない。
- 引数なし … 目なし＝純 velocity プールをそのまま出す。
- `zeitgeist 逆張りの目 二次効果の目` … 指定した目で読み直す。
- `zeitgeist 自分から最遠の目` … わざと外す。
- 「いろんな目で」 … `reference/lenses.md` から対照的な 3〜4 個（多すぎると信号が薄まる）。

パレットの増減・編集は手で `reference/lenses.md` を書き換える（機械は学習しない）。

## 出力 — 発見リスト（裏取りゼロ）

```
## 今の勢い <YYYY-MM-DD HH:MM>  目: <かけた目／なし>

### 🌐 生の勢い（目なし・velocity 降順）
| 勢い | 項目 | 一言で何が新しい | なぜ今(velocity根拠) | 源 |
|------|------|------------------|----------------------|----|
| 🔥 | <title> | <1行・専門語は噛み砕く> | 6h で +420pt | HN |
| 📈 | <repo> | <1行> | 4日で +1.2k★ | GH |
| ✨ | <arxiv> | <1行> | 投稿2日・未言及 | arxiv |

### 👁 <目の名前> で読むと
| 項目 | この目が差す理由（1行） | 源 |
（目ごとに繰り返し）

### 取得失敗
<落ちた源があれば一行ずつ。無ければ「なし」>
```

記号: 🔥急（velocity 高）/ 📈伸 / ✨新（勢い未確定）。各行に裏取りは付けない。deep-strict に渡して初めて裏取り。

## 失敗時

- 全 API が落ちた: 「鮮度バックボーンが取得できなかった」と明示し、取れた WebSearch だけで出す。捏造しない。
- velocity 計算不能（created_at 欠落）: 絶対 score で並べその旨注記。
- 結果が普段の関心に寄って見える: カテゴリ集合・源配分・かける目を変えて1度だけ振り直す（絞り込みではなく振り直し）。

## 打ち止め

鮮度バックボーン＋（指定あれば）目を適用し発見リストを出した時点で完了。深追い・裏取り・追加検索はしない（deep-strict 側）。

## スナップショット出力（サーバ表示用・任意）

ターミナル出力に加え、走り終わりに同じ内容を `feed.json` に書くと `server.py`（dumb renderer）がブラウザでカード表示する。サーバは fetch も LLM も持たず最後に書かれた `feed.json` を描くだけ（更新＝skill 再走）。鮮度は live ではなく snapshot なので生成時刻を必ず入れる。

`feed.json` 契約（renderer はこの形だけ読む。同梱の `feed.json` が seed 兼スキーマ例）:
```json
{
  "generated_at": "<ISO8601 UTC>",
  "lenses_applied": ["逆張りの目", ...],
  "raw":   [{"rank_symbol":"🔥","title":"...","whats_new":"...","why_now":"6h +420pt ≈83/h","source":"HN","url":"...","flags":["⚠要確認"]}],
  "lenses":[{"name":"逆張りの目","items":[{"title":"...","reason":"...","source":"HN","url":"..."}]}],
  "failures": []
}
```
`flags` `url` は任意。`feed.json` は使い捨ての描画スナップショット（嗜好モデルではない＝メタ化に非該当）。gitignore 済み。

表示: `python3 server.py`（既定 http://localhost:8040/ ）。`--port N` で変更。

## 定期実行との相性

単発完結なので `/loop` で朝1回などに向く。状態を持たない設計なので loop は呼ぶ側の都合、スキルは毎回ゼロから取り直す。`/loop` で回せば毎朝 `feed.json` が上書きされ、ブラウザはリロードで最新 snapshot になる。
