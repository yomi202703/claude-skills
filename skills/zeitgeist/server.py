#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""zeitgeist スナップショット renderer — dumb・stateless・stdlib only.

設計（崩すと SNS に堕ちる）:
  - fetch しない / LLM を呼ばない / クリックや閲覧を一切記録しない。
    挙動 state を持った瞬間メタ化＝SNS の偏りに堕ちる。これは「最後に
    zeitgeist を走らせて吐いた feed.json を綺麗に描くだけ」の renderer。
  - 更新は skill 再走（`zeitgeist` → feed.json 上書き）。サーバは再起動不要、
    リロードで最新スナップショットを読む。
  - 鮮度は live ではなく snapshot。生成時刻を必ず画面に出す（古さの自己申告）。

  python3 server.py            # http://localhost:8040/
  python3 server.py --port N
"""
from __future__ import annotations

import argparse
import html
import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
FEED = os.path.join(HERE, "feed.json")

CSS = """
*{box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
 max-width:760px;margin:0 auto;padding:1.5em 1em 4em;color:#1a1a1a;background:#fafafa}
h1{font-size:20px;margin:.2em 0}
.meta{color:#888;font-size:12px;margin-bottom:1.5em}
.stale{color:#c0392b;font-weight:600}
h2{font-size:15px;margin:1.8em 0 .6em;padding-bottom:.3em;border-bottom:2px solid #eee}
.card{background:#fff;border:1px solid #e6e6e6;border-radius:10px;padding:.7em .9em;
 margin:.5em 0;box-shadow:0 1px 2px rgba(0,0,0,.03)}
.card a{color:#1a1a1a;text-decoration:none;font-weight:600;font-size:15px}
.card a:hover{color:#2a6fd6}
.new{font-size:13px;color:#333;margin:.25em 0}
.why{font-size:12px;color:#888}
.src{display:inline-block;font-size:11px;color:#666;background:#f0f0f0;
 border-radius:4px;padding:1px 6px;margin-left:6px}
.flag{font-size:11px;color:#c0392b;margin-left:6px}
.reason{font-size:12px;color:#555;margin-top:.2em}
.empty{color:#aaa;font-size:13px}
footer{margin-top:3em;color:#aaa;font-size:11px;border-top:1px solid #eee;padding-top:1em}
"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _age_str(generated_at: str) -> tuple[str, bool]:
    try:
        g = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        hours = (_now() - g).total_seconds() / 3600
    except Exception:
        return ("生成時刻不明", True)
    if hours < 1:
        return (f"{int(hours*60)}分前", False)
    if hours < 24:
        return (f"{hours:.1f}時間前", hours > 12)
    return (f"{hours/24:.1f}日前", True)  # 1日超は古い扱い


def _card(it: dict) -> str:
    title = html.escape(str(it.get("title", "")))
    url = it.get("url") or ""
    head = f'<a href="{html.escape(url)}" target="_blank" rel="noopener">{title}</a>' if url else f"<b>{title}</b>"
    sym = html.escape(str(it.get("rank_symbol", "")))
    src = f'<span class=src>{html.escape(str(it.get("source","")))}</span>' if it.get("source") else ""
    flags = "".join(f'<span class=flag>{html.escape(str(f))}</span>' for f in it.get("flags", []))
    new = f'<div class=new>{html.escape(str(it["whats_new"]))}</div>' if it.get("whats_new") else ""
    why = f'<div class=why>{html.escape(str(it["why_now"]))}</div>' if it.get("why_now") else ""
    reason = f'<div class=reason>{html.escape(str(it["reason"]))}</div>' if it.get("reason") else ""
    return f'<div class=card>{sym} {head}{src}{flags}{new}{why}{reason}</div>'


def render(feed: dict) -> str:
    age, stale = _age_str(feed.get("generated_at", ""))
    cls = "stale" if stale else ""
    lenses_applied = feed.get("lenses_applied") or []
    lens_label = "・".join(lenses_applied) if lenses_applied else "なし（純 velocity）"
    body = [
        "<h1>zeitgeist</h1>",
        f'<div class=meta>スナップショット: <span class="{cls}">{html.escape(age)}</span>'
        f' （{html.escape(str(feed.get("generated_at","")))}）· 目: {html.escape(lens_label)}'
        f' · 更新は <code>zeitgeist</code> 再走</div>',
    ]

    raw = feed.get("raw") or []
    body.append("<h2>🌐 生の勢い（velocity 降順）</h2>")
    body.append("".join(_card(it) for it in raw) or '<div class=empty>なし</div>')

    for lens in feed.get("lenses") or []:
        body.append(f'<h2>👁 {html.escape(str(lens.get("name","")))} で読むと</h2>')
        items = lens.get("items") or []
        body.append("".join(_card(it) for it in items) or '<div class=empty>該当なし</div>')

    fails = feed.get("failures") or []
    if fails:
        body.append("<h2>取得失敗</h2>")
        body.append("".join(f'<div class=empty>{html.escape(str(f))}</div>' for f in fails))

    body.append(
        "<footer>dumb renderer · fetch/LLM/クリック記録なし · "
        "最後に書かれた feed.json を描くだけ · 鮮度は snapshot（live ではない）</footer>"
    )
    return f"<!doctype html><meta charset=utf-8><title>zeitgeist</title><style>{CSS}</style>" + "".join(body)


def no_feed() -> str:
    return (
        f"<!doctype html><meta charset=utf-8><style>{CSS}</style>"
        "<h1>zeitgeist</h1>"
        "<div class=empty>feed.json がまだ無い。<code>zeitgeist</code> を一度走らせると"
        " スナップショットが書かれてここに出る。</div>"
    )


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        # 全 GET は read-only。state を一切触らない。
        if not os.path.exists(FEED):
            return self._send(no_feed())
        try:
            with open(FEED, encoding="utf-8") as fh:
                feed = json.load(fh)
            return self._send(render(feed))
        except Exception as e:
            return self._send(f"<pre>feed.json 読み込み失敗: {html.escape(str(e))}</pre>", 500)

    def _send(self, doc: str, code: int = 200):
        b = doc.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, format, *args):  # quiet
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8040)
    args = ap.parse_args()
    print(f"zeitgeist renderer on http://localhost:{args.port}/  (reads {FEED})")
    HTTPServer(("127.0.0.1", args.port), H).serve_forever()


if __name__ == "__main__":
    main()
