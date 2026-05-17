# ai-wiki corpus

代表的な入力サンプル。harness tests がここから読み込んで regression check する。

| ファイル | 用途 |
|---|---|
| `mini-digest.md` | ai-digest parser + `--from-digest` の入力 (Core 2 + Adjacent 1 + 非 arxiv 1) |
| `arxiv-sample.md` | stage 1 ingest 後の source page フォーマット (stage 4 backfill 前の placeholder 含む) |
| `concept-v1-shell.md` | v1 の空 body concept (出典 link のみ) — 現状の ingest 出力 |
| `concept-v2-enriched.md` | v2 の enrich 済 concept (parent/related/contrasts/prereq + 短い body) — 目標形 |
| `map-sample.md` | user 編集済 map tree (box-drawing + wikilinks) |

corpus を追加するときは、必ず `_dev/tests/test_*_regression.py` にその入力に対する golden test を追加する (regression 必須)。
