# -*- coding: utf-8 -*-
# html-deck 推奨雛形のジェネレータ。templates/template.html はこれの出力。
# 思想: 見た目の作り込み(濃色ヘッダー・罫線・角丸・カード影・メリハリ)は残し、
#       情報設計だけ規律を効かせる ── 判定を動かす生数値だけを列にし、
#       該当セルを閾値超で着色、該当を上・重い順に並べる。
#       verdictラベル列・チップ・死に列・免責注釈は持たない。
# 使い方: rows と2つの閾値を自分の案件に差し替えて実行 → template.html を上書き生成。
#   行の着色と並べ替えはコードが決める(49行を手編集しない、の実演)。
#   軸が2本でないとき(1本/3本以上)は both_hit と列定義を増減する。

THRESH_TURN = 4.0
THRESH_FEE  = 5.0

rows = [
    ("田中 一郎", "新宿支店",  18, 7.8, 9.2),
    ("佐藤 美咲", "梅田支店",  24, 6.1, 7.4),
    ("鈴木 健太", "名古屋支店",31, 5.2, 3.1),
    ("高橋 結衣", "横浜支店",  12, 4.3, 6.0),
    ("渡辺 翔",   "札幌支店",  22, 3.9, 5.6),
    ("伊藤 さくら","福岡支店", 19, 2.1, 2.4),
    ("山本 大樹", "仙台支店",  27, 1.4, 1.1),
    ("中村 楓",   "神戸支店",  15, 3.2, 2.9),
]

def both_hit(t, f): return t >= THRESH_TURN and f >= THRESH_FEE
rows_sorted = sorted(rows, key=lambda r: (0 if both_hit(r[3], r[4]) else 1, -r[3]))

def cell(val, hit, suffix=""):
    return f'<td class="num{" hit" if hit else ""}">{val}{suffix}</td>'

trs = []
for name, branch, accts, turn, fee in rows_sorted:
    flag = ' class="watch"' if both_hit(turn, fee) else ""
    trs.append(
        f"<tr{flag}>"
        f"<td class='name'>{name}</td>"
        f"<td class='branch'>{branch}</td>"
        f"<td class='num'>{accts}</td>"
        f"{cell(turn, turn >= THRESH_TURN)}"
        f"{cell(fee, fee >= THRESH_FEE, '%')}"
        "</tr>"
    )
tbody = "\n".join(trs)
n_hit = sum(1 for r in rows if both_hit(r[3], r[4]))

html = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>取引レビュー — 回転売買の確認対象</title>
<style>
  :root {{ --ink:#1f2a36; --head:#34495e; --hit-bg:#ffd9d6; --hit-ink:#9a0007;
           --line:#d4dae0; --watch:#fff7f6; }}
  body {{ font-family:"Hiragino Kaku Gothic ProN","Yu Gothic",sans-serif;
          color:var(--ink); margin:48px; background:#f4f6f8; }}
  .card {{ background:#fff; border-radius:14px; padding:28px 32px; max-width:760px;
           box-shadow:0 1px 3px rgba(20,30,45,.08),0 8px 24px rgba(20,30,45,.06); }}
  h1 {{ font-size:21px; margin:0 0 4px; letter-spacing:.02em; }}
  .lede {{ color:#5b6b7a; margin:0 0 22px; font-size:13.5px; line-height:1.6; }}
  table {{ border-collapse:separate; border-spacing:0; width:100%; font-size:14px; }}
  thead th {{ background:var(--head); color:#fff; font-weight:600; font-size:12px;
              padding:11px 14px; text-align:right; letter-spacing:.04em; }}
  thead th:first-child {{ border-radius:8px 0 0 0; text-align:left; }}
  thead th:last-child  {{ border-radius:0 8px 0 0; }}
  thead th.l {{ text-align:left; }}
  tbody td {{ padding:11px 14px; text-align:right; border-bottom:1px solid var(--line); }}
  tbody td.name {{ text-align:left; font-weight:600; }}
  tbody td.branch {{ text-align:left; color:#5b6b7a; }}
  tbody td.num {{ font-variant-numeric:tabular-nums; }}
  tbody tr.watch {{ background:var(--watch); }}
  tbody td.hit {{ background:var(--hit-bg); color:var(--hit-ink); font-weight:700;
                  box-shadow:inset 2px 0 0 #e8675f; }}
  tbody tr:last-child td:first-child {{ border-radius:0 0 0 8px; }}
  tbody tr:last-child td:last-child  {{ border-radius:0 0 8px 0; }}
  tbody tr:hover {{ filter:brightness(.985); }}
  .note {{ color:#7b8794; font-size:12px; margin-top:16px; }}
  @media print {{ body {{ background:#fff; margin:0; }}
                  .card {{ box-shadow:none; }} tbody tr:hover {{ filter:none; }} }}
</style></head>
<body>
<div class="card">
<h1>取引レビュー — 回転売買の確認対象</h1>
<p class="lede">回転率と手数料化率の両方が高い担当を上に。色のセルが基準超え、両方が色＝確認対象({n_hit}名)。</p>
<table>
  <thead><tr>
    <th class="l">担当</th><th class="l">部店</th><th>口座数</th>
    <th>年間回転率</th><th>手数料化率</th>
  </tr></thead>
  <tbody>
{tbody}
  </tbody>
</table>
<p class="note">回転率 {THRESH_TURN} 以上・手数料化率 {THRESH_FEE}% 以上で着色。</p>
</div>
</body></html>"""

import os
out = os.path.join(os.path.dirname(__file__), "..", "templates", "template.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print(f"wrote {os.path.normpath(out)} ({len(html)} bytes), 確認対象 {n_hit}名")
