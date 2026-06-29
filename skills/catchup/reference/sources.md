# catchup 火元レジストリ

実行時 WebFetch / WebSearch する発見ソースと取り方。SKILL.md の「発見」「重要度」「coverage 監査」節の詳細版。

## 発見プール（スペクトラム散らし・収束カウントの母集団）

並列 WebFetch。`<item>`/`<entry>` の `title` と `link`、可能なら配信元ドメインを拾う。生存は 2026-06 確認。

| 系統 | 火元 | URL |
|---|---|---|
| 公共（基準線） | NHK 主要 | `https://www3.nhk.or.jp/rss/news/cat0.xml` |
| 公共 補助 | NHK 経済 / 国際 | `https://www3.nhk.or.jp/rss/news/cat5.xml` / `cat6.xml`（社会 cat1 / 政治 cat4 / スポーツ cat7 も） |
| 中道左 | 朝日 headlines | `https://www.asahi.com/rss/asahi/newsheadlines.rdf` |
| 中道左 | 毎日 flash | `https://mainichi.jp/rss/etc/mainichi-flash.rss` |
| 中道右 | 産経 flash（wor アグリ） | `https://assets.wor.jp/rss/rdf/sankei/flash.rdf` |
| 国際中立 | BBC日本語 | `https://feeds.bbci.co.uk/japanese/rss.xml` |
| 補助（収束に数えない） | Yahoo 主要 | `https://news.yahoo.co.jp/rss/topics/top-picks.xml` |

NHK は `www.nhk.or.jp/rss/news/cat0.xml` が 301 で NHK ONE 内部 URL に飛ぶ。安定するのは `www3` ホスト直叩き、`-A "Mozilla/5.0"`。

## 収束カウントの注意

「独立した報道ドメインが何社載せたか」で重要度を採点する。記事の実ドメインで数え、Yahoo 等の配信ホスト経由の重複は元記事1社に畳む。Google News RSS の `<source>` タグは日本だと多くを「Yahoo!ニュース」名義に丸めるため、そのまま数えると Yahoo 偏在で汚れる。`<source>` では数えない。

## Google News 検索（薄い軸埋め・収束確認の拡張）

```
https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja
```

- 演算子: `when:1d`（today モード）/ `when:7d`（既定）。`q` は URL エンコード。
- クエリは固有名詞・具体イベント語で撃つ。素の軸キーワード（「国際 安全保障」「災害 気象」「制度 施行」等）は解説・防災情報・提言など evergreen を拾い、実イベントが埋もれる（2026-06 実測）。固有名詞が分からない軸は、まず NHK 等プールから拾った語で具体化してから撃つ。
- 全プール RSS 全滅時の横断代替にもこれを使う（`when:1d 主要 ニュース` 等）。

## coverage 監査軸（発見の点検リスト・出力には出さない）

政治/制度の期限・経済/物価・国際/安全保障・災害/気象/交通・スポーツ・科学/健康・生活/社会。プールで薄い軸を上の Google News 検索で固有名詞化して埋める。

## 死んだ・使えない火元（再提案しないための記録）

- 47NEWS（共同通信）RSS: `/feed`・`/rss/news.rdf` とも 404（2026-06）。通信社直 RSS は公開終了。
- Reuters 日本語 RSS: 取得不可（2026-06）。
- 読売・日経: 公開 RSS なし。

## 増やす時の判断

- 発見プールに足すのは編集スペクトラムの異なる独立社のみ（同系統の重複は収束を水増しするだけ）。
- 配信ホスト（アグリゲータ）は発見補助に留め、収束カウントには数えない。
- velocity を測れる火元でも catchup では使わない（zeitgeist の領分）。
- エンタメ専門火元は足さない。
