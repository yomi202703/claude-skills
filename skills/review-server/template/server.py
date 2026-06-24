#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Single shared review server — diagnostic / GT-creation / evaluation modes.

Domain-agnostic template (S1, config-driven). The judgment vocabulary, axes,
and unit are read from contract.json (S2), never hard-coded here. Code is a
template: adapt data.py for your domain; this file should not need changes.

Gates wired structurally:
  S3  GT-creation path (render_review) NEVER calls adapter.judges() — a
      reviewer cannot see any machine output until commit. The firewall is the
      RENDERING, not a login: mode is chosen by route (/diag vs /review), no
      auth by default. Authentication / reviewer attribution is a later concern
      (grill hook), added only when untrusted external blind reviewers arrive.
  S4  commit stores the blind verdict, THEN reveals judges + divergence.
  S8  every GET is read-only; only POST /commit and POST /ingest write.
  S9  one ingestion path (POST /ingest, inbox CSV).
  S10 provenance footer (live vs snapshot) on every page; --package excludes
      the answer DB / inbox / caches.

  python3 server.py                 # http://localhost:8030/
  python3 server.py --snapshot      # freeze a snapshot provenance marker
  python3 server.py --package        # build a distributable zip and exit

Standard library only.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import os
import urllib.parse
import zipfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

from data import DemoAdapter, divergence
from store import Store

HERE = os.path.dirname(os.path.abspath(__file__))
CONTRACT = json.load(open(os.path.join(HERE, "contract.example.json"), encoding="utf-8"))
ADAPTER = DemoAdapter()
STORE = Store(os.path.join(HERE, "gt.db"))
SOURCE = "live"  # flipped to "snapshot" by --snapshot marker (S10)
# No auth by default: mode is chosen by route (/diag vs /review). Reviewer
# attribution defaults to a constant; named/authenticated reviewers are a later
# grill hook (review-server CHOICES: auth strength), wired only when external
# blind reviewers are onboarded — not pre-built.
REVIEWER = "anon"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _versions() -> dict:
    return dict(CONTRACT["version"])


# --- rendering ---------------------------------------------------------------
def page(body: str, *, who: str = "") -> bytes:
    foot = (
        f'<footer style="margin-top:2em;color:#888;font-size:12px">'
        f'source: <b>{SOURCE}</b> · contract {CONTRACT["version"]["contract"]} '
        f'· {html.escape(who)} · {_now()}</footer>'
    )
    doc = (
        "<!doctype html><meta charset=utf-8>"
        "<style>body{font-family:sans-serif;max-width:820px;margin:2em auto}"
        "mark{background:#ffe08a}.j{border:1px solid #ccc;padding:.5em;margin:.4em 0}"
        "pre{white-space:pre-wrap;background:#f6f6f6;padding:.6em}</style>"
        + body + foot
    )
    return doc.encode("utf-8")


def highlight(text: str, evidence: list) -> str:
    """Highlight evidence lines (S11: the human confronts the evidence)."""
    keep = {e.get("idx") for e in evidence}
    out = []
    for line in text.splitlines():
        idx = line.split(":", 1)[0].strip()
        esc = html.escape(line)
        try:
            hit = int(idx) in keep
        except ValueError:
            hit = False
        out.append(f"<mark>{esc}</mark>" if hit else esc)
    return "<pre>" + "\n".join(out) + "</pre>"


def render_judges(judges: dict) -> str:
    out = ""
    for role in ("proposer", "production"):
        j = judges.get(role) or {}
        out += (
            f'<div class=j><b>{role}</b>: {html.escape(str(j.get("verdict","")))}'
            f' — {html.escape(str(j.get("reason","")))}</div>'
        )
    if divergence(judges):
        out += '<div class=j style="border-color:#c00"><b>DIVERGENCE</b> → queue</div>'
    return out


# --- handler -----------------------------------------------------------------
class H(BaseHTTPRequestHandler):
    def _send(self, body: bytes, code: int = 200, headers: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _form(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n).decode("utf-8")
        return {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}

    # GETs are read-only (S8) -------------------------------------------------
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        parts = [p for p in u.path.split("/") if p]
        if not parts:
            return self._send(self.landing_page())
        if parts[0] == "diag" and len(parts) == 1:
            return self._send(self.units_page("diag"))
        if parts[0] == "review" and len(parts) == 1:
            return self._send(self.units_page("gt"))
        if parts[0] == "review" and len(parts) == 2:
            return self._send(self.review_page(parts[1]))   # S3: no judges here
        if parts[0] == "diag" and len(parts) == 2:
            return self._send(self.diag_page(parts[1]))
        if parts[0] == "aggregate":
            return self._send(self.aggregate_page())
        if parts[0] == "eval":
            return self._send(self.eval_page())
        return self._send(page("not found"), 404)

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        parts = [p for p in u.path.split("/") if p]
        if parts[:1] == ["commit"] and len(parts) == 2:
            return self._send(self.commit(parts[1]))
        if parts == ["ingest"]:
            return self._send(self.ingest())
        return self._send(page("not found"), 404)

    # pages -------------------------------------------------------------------
    def landing_page(self) -> bytes:
        # No login. Mode = route. The anchoring firewall lives in what each
        # route renders (S3), not in authentication.
        return page(
            "<h2>review-server</h2>"
            "<p>pick a mode (no login — firewall is render-time, S3):</p>"
            "<ul>"
            '<li><a href="/review">GT-creation</a> — blind: input + evidence only, '
            "machine output revealed after commit</li>"
            '<li><a href="/diag">diagnostic</a> — developer: sees every judge · '
            '<a href="/aggregate">aggregate</a> · <a href="/eval">eval</a></li>'
            "</ul>"
        )

    def units_page(self, mode: str) -> bytes:
        base = "diag" if mode == "diag" else "review"
        rows = "".join(
            f'<li><a href="/{base}/{html.escape(u["unit_key"])}">{html.escape(u["label"])}</a></li>'
            for u in ADAPTER.units()
        )
        nav = ' · <a href=/aggregate>aggregate</a> · <a href=/eval>eval</a>' if mode == "diag" else ""
        label = "diagnostic" if mode == "diag" else "GT-creation"
        return page(f"<h3>{label}{nav}</h3><ul>{rows}</ul>", who=mode)

    def review_page(self, unit_key: str) -> bytes:
        # S3 ANCHORING FIREWALL: input + evidence ONLY. Never call ADAPTER.judges().
        inp = ADAPTER.unit_input(unit_key)
        axes = "".join(
            f'<div class=j><b>{html.escape(a["label"])}</b>'
            + "".join(
                f'<label><input type=radio name="v_{a["key"]}" value="{html.escape(opt)}"> {html.escape(opt)}</label> '
                for opt in a["vocabulary"]
            )
            + "</div>"
            for a in CONTRACT["axes"]
        )
        return page(
            f"<h3>review {html.escape(unit_key)}</h3>"
            + highlight(inp["text"], inp["evidence"])
            + f'<form method=post action="/commit/{html.escape(unit_key)}">'
            + axes
            + 'reason: <input name=reason style="width:60%"> '
            + 'evidence idx (comma): <input name=evidence><br><br>'
            + "<button>commit (then reveal)</button></form>",
            who="GT-creation",
        )

    def commit(self, unit_key: str) -> bytes:
        f = self._form()
        revealed = ""
        for a in CONTRACT["axes"]:
            verdict = f.get(f"v_{a['key']}", "")
            if not verdict:
                continue
            STORE.append(
                unit_key=unit_key, axis_key=a["key"], verdict=verdict,
                reason=f.get("reason", ""),
                evidence=json.dumps([s.strip() for s in f.get("evidence", "").split(",") if s.strip()]),
                reviewer=REVIEWER, provenance="blind", tier="silver",
                versions=_versions(),
            )
            # S4: reveal AFTER the blind verdict is stored.
            revealed += f"<h4>{html.escape(a['label'])}</h4>" + render_judges(
                ADAPTER.judges(unit_key, a["key"])
            )
        return page(
            f"<h3>committed {html.escape(unit_key)}</h3>"
            "<p>your blind verdict is stored. now revealed:</p>" + revealed
            + '<p><a href="/review">next</a></p>',
            who="GT-creation",
        )

    def diag_page(self, unit_key: str) -> bytes:
        inp = ADAPTER.unit_input(unit_key)
        body = f"<h3>diagnostic {html.escape(unit_key)}</h3>" + highlight(inp["text"], inp["evidence"])
        for a in CONTRACT["axes"]:
            body += f"<h4>{html.escape(a['label'])}</h4>" + render_judges(ADAPTER.judges(unit_key, a["key"]))
        return page(body, who="developer")

    def aggregate_page(self) -> bytes:
        queue = []
        for u in ADAPTER.units():
            for a in CONTRACT["axes"]:
                if divergence(ADAPTER.judges(u["unit_key"], a["key"])):
                    queue.append(f"{u['unit_key']} / {a['key']}")
        items = "".join(f"<li>{html.escape(q)}</li>" for q in queue) or "<li>none</li>"
        return page(f"<h3>divergence queue (S4)</h3><ul>{items}</ul>", who="developer")

    def eval_page(self) -> bytes:
        # W6 / S12: regression vs gold + stale gold + holdout access log.
        gold = STORE.latest(tier="gold")
        stale = STORE.stale_gold(CONTRACT["version"]["criterion"])
        agree = miss = 0
        for r in gold:
            prod = ADAPTER.judges(r["unit_key"], r["axis_key"]).get("production") or {}
            if prod.get("verdict") == r["verdict"]:
                agree += 1
            else:
                miss += 1
        log = STORE.holdout_access_log()
        loglines = "".join(
            f"<li>{html.escape(r['at'])} · {html.escape(r['caller'])} · {html.escape(r['reason'])} · {r['n_rows']} rows</li>"
            for r in log
        ) or "<li>no holdout access</li>"
        return page(
            f"<h3>evaluation (measurement, not a target — S12)</h3>"
            f"<p>gold n={len(gold)} · judge agrees {agree} / misses {miss}</p>"
            f"<p>stale gold (criterion lag): {len(stale)}</p>"
            f"<h4>holdout access log (S12)</h4><ul>{loglines}</ul>",
            who="developer",
        )

    def ingest(self) -> bytes:
        # S9: one ingestion path. Merge CSVs dropped in inbox/, dedup by content.
        inbox = os.path.join(HERE, "inbox")
        os.makedirs(inbox, exist_ok=True)
        added = 0
        for fn in sorted(os.listdir(inbox)):
            if not fn.endswith(".csv"):
                continue
            with open(os.path.join(inbox, fn), encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    try:
                        STORE.append(
                            unit_key=row["unit_key"], axis_key=row["axis_key"],
                            verdict=row["verdict"], reason=row.get("reason", ""),
                            evidence=row.get("evidence", "[]"),
                            reviewer=row.get("reviewer", "import"),
                            provenance=row.get("provenance", "blind"),
                            tier=row.get("tier", "silver"), versions=_versions(),
                        )
                        added += 1
                    except Exception:
                        pass  # malformed rows are skipped, not fatal
        return page(f"<p>ingested {added} rows from inbox/</p>", who="developer")

    def log_message(self, format, *args):  # quiet
        pass


# --- CLI ---------------------------------------------------------------------
def make_snapshot():
    meta = {"created_at": _now(), "source": "snapshot", "contract": CONTRACT["version"]}
    json.dump(meta, open(os.path.join(HERE, "snapshot_meta.json"), "w"), indent=2)
    print("snapshot marker written; start with REVIEW_SOURCE=snapshot to serve it")


def make_package():
    out = os.path.join(HERE, f"review_dist_{_now().replace(':','').replace('-','')}.zip")
    exclude = ("gt.db", "inbox", "__pycache__")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(HERE):
            dirs[:] = [d for d in dirs if d not in exclude]
            for f in files:
                if f.startswith("gt.db") or f.endswith((".pyc", ".zip")):
                    continue
                p = os.path.join(root, f)
                z.write(p, os.path.relpath(p, HERE))
    print("packaged:", out, "(excluded answer DB / inbox / caches)")


def main():
    global SOURCE
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8030)
    ap.add_argument("--snapshot", action="store_true")
    ap.add_argument("--package", action="store_true")
    args = ap.parse_args()
    if args.snapshot:
        return make_snapshot()
    if args.package:
        return make_package()
    if os.environ.get("REVIEW_SOURCE") == "snapshot":
        SOURCE = "snapshot"
    print(f"review-server on http://localhost:{args.port}/  (source={SOURCE})")
    HTTPServer(("127.0.0.1", args.port), H).serve_forever()


if __name__ == "__main__":
    main()
