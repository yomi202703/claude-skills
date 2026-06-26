# -*- coding: utf-8 -*-
# 適合性判定.html を html-deck の正準サンプルへ匿名化する一回限りの変換。
# - 口座番号: 全テーブル横断で一貫して 9xxxxx の合成IDへ置換(prose内の言及も追従)。
# - 社名 あかつき → サンプル証券 / あかつき → 当社想定先。
# - localhost リンク(http://127.0.0.1:8012/...)は除去し、IDは素のテキストに。
import re

SRC = "/Users/ivymee/Downloads/適合性判定.html"
OUT = "/Users/ivymee/.claude/skills/html-deck/templates/sample_judgment_table.html"

html = open(SRC, encoding="utf-8").read()

# 1) 権威ある口座IDの集合 = class="acc" セル / href の中の6桁。
ids = set()
ids |= set(re.findall(r'class="acc"[^>]*>(?:<a[^>]*>)?(\d{6})', html))
ids |= set(re.findall(r'/a/(\d{6})/meta', html))
old_ids = sorted(ids)
mapping = {old: str(900001 + i) for i, old in enumerate(old_ids)}

# 2) localhost リンクを剥がす: <a ...>ID</a> -> ID
html = re.sub(r'<a\s+href="http://127\.0\.0\.1:8012/[^"]*"[^>]*>(\d{6})</a>', r'\1', html)

# 3) 口座IDを一貫置換(前後が数字でないトークン境界のみ)。
def repl_id(m):
    return mapping.get(m.group(0), m.group(0))
for old in sorted(mapping, key=len, reverse=True):
    html = re.sub(r'(?<!\d)' + old + r'(?!\d)', mapping[old], html)

# 4) 社名の匿名化。
html = html.replace("あかつき証券様", "サンプル証券様")
html = html.replace("あかつき証券", "サンプル証券")
html = html.replace("あかつきの体制", "貴社の体制")
html = html.replace("あかつき", "貴社")

open(OUT, "w", encoding="utf-8").write(html)
print(f"ids mapped: {len(mapping)}  (例: {old_ids[0]}->{mapping[old_ids[0]]})")
print(f"residual 'あかつき': {html.count('あかつき')}  residual '127.0.0.1': {html.count('127.0.0.1')}")
print(f"wrote {OUT} ({len(html)} bytes)")
