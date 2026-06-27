---
name: recall
description: recall コーパス(manuals / genten / transcript)を引く。grep hit を素材別の意味境界へ展開して読む索引ゼロ・状態ゼロの read-primitive。「recall で引いて」「マニュアル/原典/文字起こしから探して」「/recall」等で起動。
---

# recall

`/Users/ivymee/Projects/recall` の read-primitive を CLI で叩く(MCP `recall_search` と出力同一)。どの cwd からでも動く。クエリ語はユーザーでなく自分が自然文から選ぶ。

```
uv run --directory /Users/ivymee/Projects/recall \
  python -m recall_spike.search --query "空白区切りの語" --corpus corpus/manuals
```

- `--corpus`: `corpus/manuals` / `corpus/genten` / `corpus/transcript`(案件混在なら `corpus/<案件>/<種別>`)。資料は常に recall 配下に置き相対で渡す=recall root 基準で解決(絶対パス不要)。
- `--precise`: literal マッチで絞る(送り仮名変種を切る)
- `--coverage 広語`: 広語が当てたが query が落とした region を DROPPED 提示=取りこぼし点検
- `--before`/`--after`(既定 1/2): ターン窓幅、`--max-chars`(既定 1200): 表示上限

作法: 段1=広く当てる → FLOODING なら本文の弁別語を拾って `--precise` で絞る → 最終クエリ前に `--coverage` で被覆漏れを点検。
