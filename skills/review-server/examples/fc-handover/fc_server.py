#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fact-checker handover server — blind GT-creation ONLY (the separate-deliverable form).

Contrast with ../../template/server.py: that one server hosts /diag AND /review and
keeps the firewall at RENDER time (the /review handler simply does not call judges).
This package keeps the firewall by ABSENCE instead — there is no judges() function in
this file, and dist/ contains no machine answers (build_package.py never generated
them). A reviewer cannot reach the machine verdict here because it is not present, in
code or in data. That is the strongest form of S3.

Surfaces (deliberately minimal — anti-IDE, S3/W2):
  GET  /                  unit list
  GET  /review/<unit>     input + evidence + one radio group per axis + reason  (no answers)
  POST /commit/<unit>     append the blind verdict; show "saved → next" (NOTHING to reveal)
  GET  /export            emit the GT as inbox CSV — the ONE path back (S9)

The GT this produces is provenance=blind. On the developer side it is gold-eligible
(store.ALLOWED: blind -> gold); it lands as silver on import and is promoted there
after independent blind re-confirmation. This package never assigns gold itself.

Standard library only. Run: python3 fc_server.py   (build_package.py must have run first)
"""
from __future__ import annotations

import argparse
import csv
import html
import io
import json
import os
import sqlite3
import sys
import urllib.parse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(HERE, "dist")
DB_PATH = os.environ.get("FC_DB", os.path.join(HERE, "fc_gt.db"))

# Reviewer attribution defaults to a constant (no auth — mode is the whole point of
# this package, not a route). Named/authenticated reviewers are a later grill hook,
# wired only when submissions from several untrusted reviewers must be told apart.
REVIEWER = os.environ.get("FC_REVIEWER", "fc-anon")

UI = {
    "title": "ファクトチェック",
    "index": "判定する対象を選んでください",
    "evidence": "本文（根拠の行をクリックで選択）",
    "reason": "理由",
    "ev_selected": "選択した根拠",
    "commit": "確定",
    "done": "すべての対象が完了しました。",
    "not_found": "見つかりません",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _require_built():
    if not os.path.isdir(DIST) or not os.path.exists(os.path.join(DIST, "units.json")):
        raise SystemExit("dist/ が未生成です。先に `python3 build_package.py` を実行してください。")


def load_contract() -> dict:
    return json.load(open(os.path.join(DIST, "contract.generated.json"), encoding="utf-8"))


def load_units() -> list:
    return json.load(open(os.path.join(DIST, "units.json"), encoding="utf-8"))["units"]


# --- append-only local store -------------------------------------------------
# Just enough to capture blind verdicts append-only. The maturity-tier gates
# (anchored-never-gold, promotion) live on the developer side where promotion
# happens; this package only ever emits provenance=blind.
class FCStore:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS fc_gt (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 created_at TEXT NOT NULL, unit_key TEXT NOT NULL,
                 axis_key TEXT NOT NULL, verdict TEXT NOT NULL,
                 reason TEXT NOT NULL, evidence TEXT NOT NULL,
                 reviewer TEXT NOT NULL )"""
        )
        self.db.commit()

    def append(self, unit_key, axis_key, verdict, reason, evidence):
        self.db.execute(
            "INSERT INTO fc_gt (created_at,unit_key,axis_key,verdict,reason,evidence,reviewer)"
            " VALUES (?,?,?,?,?,?,?)",
            (_now(), unit_key, axis_key, verdict, reason, evidence, REVIEWER),
        )
        self.db.commit()

    def all_rows(self):
        return self.db.execute("SELECT * FROM fc_gt ORDER BY id").fetchall()

    def committed_keys(self):
        return {r["unit_key"] for r in self.all_rows()}

    def latest_by_unit(self):
        """{unit_key: {axis_key: row}} — the reviewer's own latest verdict per
        (unit, axis). Append-only: revisions are later rows, so the last row by id
        wins. This is the REVIEWER'S OWN work, not machine output — showing it back
        is progress/consistency review, not an S3 firewall breach (which only
        concerns MACHINE output before commit)."""
        out: dict = {}
        for r in self.all_rows():  # ordered by id
            out.setdefault(r["unit_key"], {})[r["axis_key"]] = r
        return out


CSS = """
*{box-sizing:border-box}
body{margin:0;background:#f6f7f9;color:#1b2026;font:15px/1.6 -apple-system,
"Hiragino Kaku Gothic ProN","Noto Sans JP",system-ui,sans-serif}
.bar{padding:.7em 1.3em;background:#1b2026;color:#fff;font-weight:700}
.wrap{max-width:760px;margin:1.6em auto;padding:0 1.3em}
.card{background:#fff;border:1px solid #e7e9ee;border-radius:10px;padding:1em 1.15em;margin:.8em 0}
h3{font-size:18px;margin:.1em 0 .6em}
h4{font-size:13px;color:#6b7280;margin:0 0 .5em}
pre{white-space:pre-wrap;font:13.5px/1.75 ui-monospace,Menlo,monospace;margin:0}
.ln{cursor:pointer;border-radius:3px;display:block;padding:0 .15em}
.ln:hover{background:#eef2ff}.selev{background:#ffe9a8}
.radio-row{display:flex;flex-wrap:wrap;gap:.5em}
.radio-row input{position:absolute;opacity:0;pointer-events:none}
.radio-row label{border:1px solid #e7e9ee;border-radius:999px;padding:.35em 1.15em;cursor:pointer;
font-size:18px;line-height:1.2;min-width:3.2em;text-align:center;user-select:none}
.radio-row label:hover{border-color:#3b5bdb}
.radio-row label:has(input:checked){background:#3b5bdb;color:#fff;border-color:#3b5bdb}
input[type=text]{width:100%;border:1px solid #e7e9ee;border-radius:7px;padding:.5em .65em;font:inherit}
textarea{width:100%;min-height:4.5em;border:1px solid #e7e9ee;border-radius:7px;padding:.55em .65em;font:inherit;resize:vertical}
textarea:focus,input:focus{outline:2px solid #eef2ff;border-color:#3b5bdb}
button{font:inherit;font-weight:600;color:#fff;background:#3b5bdb;border:0;border-radius:8px;padding:.6em 1.3em;cursor:pointer}
a{color:#3b5bdb}.muted{color:#6b7280}
ul{padding-left:1.1em}
.saved{background:#e9f7ef;border:1px solid #b6e2c6;color:#1d6b3f;border-radius:8px;padding:.45em .8em;margin:.6em 0;font-size:13px}
.units{list-style:none;padding:0;margin:0}
.units li{border-bottom:1px solid #e7e9ee;padding:.7em .2em}
.units li:last-child{border-bottom:0}
.u-head{display:flex;align-items:baseline;gap:.6em}
.u-head .done{color:#1d6b3f;font-weight:600;font-size:12px}
.u-head .todo{color:#9aa3b0;font-size:12px}
.verdicts{margin:.3em 0 0;font-size:13.5px}
.verdicts .ax{color:#6b7280}
.verdicts .v{font-weight:600}
.reason{color:#6b7280;font-size:13px;margin:.15em 0 0}
"""


def _saved_banner(unit_key) -> str:
    if not unit_key:
        return ""
    return f'<div class=saved>{html.escape(unit_key)} を保存しました</div>'


def page(body: str) -> bytes:
    return (
        "<!doctype html><html lang=ja><head><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width,initial-scale=1">'
        f"<style>{CSS}</style></head><body>"
        f'<div class=bar>{UI["title"]}</div><div class=wrap>{body}</div>'
        "</body></html>"
    ).encode("utf-8")


class H(BaseHTTPRequestHandler):
    def _send(self, body: bytes, code=200, ctype="text/html; charset=utf-8", headers=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _form(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n).decode("utf-8")
        return {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}

    def _redirect(self, location: str):
        # 303 See Other after a POST: the browser follows with a GET, so a reload
        # does not re-submit. Used to send the reviewer straight to the next unit.
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    # reads are side-effect-free (S8) ----------------------------------------
    def do_GET(self):
        pr = urllib.parse.urlparse(self.path)
        parts = [urllib.parse.unquote(p) for p in pr.path.split("/") if p]
        saved = urllib.parse.parse_qs(pr.query).get("saved", [None])[0]
        if not parts:
            return self._send(self.index_page(saved))
        if parts[0] == "review" and len(parts) == 2:
            return self._send(self.review_page(parts[1], saved))
        return self._send(page(UI["not_found"]), 404)

    def do_POST(self):
        parts = [urllib.parse.unquote(p) for p in urllib.parse.urlparse(self.path).path.split("/") if p]
        if parts[:1] == ["commit"] and len(parts) == 2:
            return self.commit(parts[1])
        return self._send(page(UI["not_found"]), 404)

    # pages -------------------------------------------------------------------
    def index_page(self, saved=None) -> bytes:
        # Show each unit's progress AND the reviewer's OWN committed verdict +
        # reason, so they can see how far they got and what they decided. This is
        # the reviewer's own work, not machine output — no S3 breach. Undone units
        # show nothing (no answer exists anyway). Done units stay clickable so a
        # verdict can be revised (append-only: a revision is a new row).
        by_unit = STORE.latest_by_unit()
        axis_label = {a["key"]: a["label"] for a in CONTRACT["axes"]}
        rows = ""
        for u in UNITS:
            key = u["unit_key"]
            verdicts = by_unit.get(key)
            link = f'<a href="/review/{html.escape(key)}">{html.escape(u["label"])}</a>'
            if verdicts:
                status = '<span class=done>✓ 判定済</span>'
                # one reason is captured per commit; take it from any axis row
                reason = next((r["reason"] for r in verdicts.values() if r["reason"]), "")
                parts = " ・ ".join(
                    f'<span class=ax>{html.escape(axis_label.get(ax, ax))}:</span> '
                    f'<span class=v>{html.escape(verdicts[ax]["verdict"])}</span>'
                    for ax in axis_label if ax in verdicts
                )
                detail = (f'<div class=verdicts>{parts}</div>'
                          + (f'<div class=reason>理由: {html.escape(reason)}</div>' if reason else ''))
            else:
                status = '<span class=todo>未判定</span>'
                detail = ""
            rows += f'<li><div class=u-head>{link}{status}</div>{detail}</li>'
        done_n = len(by_unit)
        all_done = done_n >= len(UNITS) and len(UNITS) > 0
        note = f'<p class=saved>{UI["done"]}</p>' if all_done else _saved_banner(saved)
        # Verdicts persist internally on commit; collecting them and flowing back
        # to the dev server is an OPERATOR action (`fc_server.py --export`, S9),
        # off the reviewer's surface entirely.
        foot = f'<p class=muted>{done_n}/{len(UNITS)} 完了</p>'
        return page(f"{note}<h3>{UI['index']}</h3>"
                    f'<div class=card><ul class=units>{rows}</ul></div>{foot}')

    def review_page(self, unit_key: str, saved=None) -> bytes:
        u = next((x for x in UNITS if x["unit_key"] == unit_key), None)
        if u is None:
            return page(UI["not_found"])
        # Pre-fill from the reviewer's OWN prior commit when revisiting, so a
        # revision starts from what they last decided (append-only: committing
        # again writes a new row). This is their own work, not machine output, so
        # showing it back does not breach the S3 firewall (which is about MACHINE
        # output before commit). No prior commit → start from the unit's evidence
        # spans as the default highlight.
        prior = STORE.latest_by_unit().get(unit_key, {})
        prior_verdict = {ax: r["verdict"] for ax, r in prior.items()}
        prior_reason = next((r["reason"] for r in prior.values() if r["reason"]), "")
        if prior:
            preselect = []
            for r in prior.values():
                try:
                    preselect = [str(x) for x in json.loads(r["evidence"])] or preselect
                except (ValueError, TypeError):
                    pass
        else:
            preselect = [str(e["idx"]) for e in u.get("evidence", []) if e.get("idx") is not None]
        keep = set(preselect)

        # input lines as click-to-select evidence (S11). No reveal path exists here.
        lines = []
        for line in u["text"].splitlines():
            raw = line.split(":", 1)[0].strip()
            di = str(int(raw)) if raw.isdigit() else ""
            cls = "ln selev" if (di and di in keep) else "ln"
            lines.append(f'<span class="{cls}" data-idx="{di}" onclick="togEv(this)">{html.escape(line)}</span>')
        text_html = "<pre>" + "\n".join(lines) + "</pre>"

        axes = "".join(
            f'<div class=card><h4>{html.escape(a["label"])}</h4><div class=radio-row>'
            + "".join(
                f'<label><input type=radio name="v_{a["key"]}" value="{html.escape(opt)}"'
                f'{" checked" if prior_verdict.get(a["key"]) == opt else ""}>{html.escape(opt)}</label>'
                for opt in a["vocabulary"]
            ) + "</div></div>"
            for a in CONTRACT["axes"]
        )
        script = (
            "<script>const sel=new Set(" + json.dumps(preselect) + ".map(String));"
            "function sync(){const a=[...sel].sort((x,y)=>x-y);"
            "document.getElementById('evidence').value=a.join(',');"
            "document.getElementById('evdisp').textContent=a.length?a.join(', '):'\\u2014';}"
            "function togEv(el){const i=el.dataset.idx;if(!i)return;"
            "if(sel.has(i)){sel.delete(i);el.classList.remove('selev')}"
            "else{sel.add(i);el.classList.add('selev')}sync();}"
            "document.addEventListener('DOMContentLoaded',sync);</script>"
        )
        revisit = ('<p class=muted style="margin:.2em 0 0;font-size:13px">前回の判定を表示しています。'
                   '変更して確定すると上書き（改訂）されます。</p>') if prior else ""
        return page(
            f"{_saved_banner(saved)}<h3>{html.escape(unit_key)}</h3>{revisit}"
            f'<div class=card><h4>{UI["evidence"]}</h4>{text_html}</div>'
            f'<form method=post action="/commit/{html.escape(unit_key)}">{axes}'
            f'<div class=card><h4>{UI["reason"]}</h4>'
            f'<textarea name=reason rows=3>{html.escape(prior_reason)}</textarea>'
            f'<h4 style="margin-top:.8em">{UI["ev_selected"]}</h4>'
            f'<input type=hidden id=evidence name=evidence>'
            f'<p id=evdisp class=muted style="margin:.2em 0">&#8212;</p></div>'
            f'<button>{UI["commit"]}</button></form>{script}'
        )

    def commit(self, unit_key: str):
        f = self._form()
        evidence = json.dumps([s.strip() for s in f.get("evidence", "").split(",") if s.strip()])
        for a in CONTRACT["axes"]:
            verdict = f.get(f"v_{a['key']}", "")
            if not verdict:
                continue
            STORE.append(unit_key, a["key"], verdict, f.get("reason", ""), evidence)
        # No reveal exists in this package (S3 by absence), so a post-commit
        # acknowledgment screen would carry zero information and cost the reviewer
        # an extra click per unit. Go straight to the next uncommitted unit (303),
        # carrying a one-line "saved" banner; when none remain, land on the index.
        # (The same-server template/ keeps an interstitial because it reveals the
        # machine verdict after commit, S4 — that screen is informative there.)
        nxt = next((u for u in UNITS if u["unit_key"] not in STORE.committed_keys()), None)
        saved = urllib.parse.quote(unit_key)
        if nxt:
            return self._redirect(f"/review/{urllib.parse.quote(nxt['unit_key'])}?saved={saved}")
        return self._redirect(f"/?saved={saved}")

    def log_message(self, format, *args):  # quiet
        pass


# S9: ONE path back — the OPERATOR action, not a reviewer button. Emit EXACTLY
# the columns the developer server's POST /ingest reads (inbox CSV). The verdicts
# are already persisted internally on commit; this just hands them back on the one
# ingestion path. provenance=blind (gold-eligible on the dev side); tier=silver on
# import, promoted to gold there after independent blind re-confirmation.
INBOX_COLUMNS = ["unit_key", "axis_key", "verdict", "reason", "evidence", "reviewer", "provenance", "tier"]


def export_inbox_csv() -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(INBOX_COLUMNS)
    for r in STORE.all_rows():
        w.writerow([r["unit_key"], r["axis_key"], r["verdict"], r["reason"],
                    r["evidence"], r["reviewer"], "blind", "silver"])
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8040)
    ap.add_argument("--export", nargs="?", const="-", metavar="PATH",
                    help="オペレータ用: 保存済みGTを inbox CSV で書き出す（省略時は標準出力）")
    args = ap.parse_args()
    if args.export is not None:
        text = export_inbox_csv()
        if args.export == "-":
            sys.stdout.write(text)
        else:
            with open(args.export, "w", encoding="utf-8") as fh:
                fh.write(text)
            print(f"wrote {os.path.abspath(args.export)} ({len(STORE.all_rows())} rows)")
        return
    last = None
    for p in range(args.port, args.port + 50):
        try:
            httpd = HTTPServer(("127.0.0.1", p), H)
            break
        except OSError as e:
            last = e
    else:
        raise SystemExit(f"空きポートなし: {last}")
    if p != args.port:
        print(f"注意: :{args.port} は使用中。:{p} で起動します。")
    print(f"fact-check handover server on http://localhost:{p}/  (firewall by absence)")
    httpd.serve_forever()


_require_built()
CONTRACT = load_contract()
UNITS = load_units()
STORE = FCStore(DB_PATH)

if __name__ == "__main__":
    main()
