#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Developer smoke test — boot the server on an ephemeral port against a throw-
away DB and exercise the developer loop end-to-end, so a host who adapted
data.py / contract.json can confirm in one command that they did not break the
contract:

  - landing + diagnostic API respond, units have the expected shape
  - this is the DEVELOPER server: there is NO blind /review route (404) — blind
    GT is created in the factcheck skill and flows back via POST /ingest (S9)
  - the loop closes: ingest blind GT (one path, S9) -> /gt promote -> /eval gold
  - the S6 gate holds in the running server (silver vs gold)

  python3 selftest.py      # exit 0 = pass, 1 = fail

Standard library only. Uses REVIEW_DB to keep your real gt.db untouched.
"""
from __future__ import annotations

import csv
import io
import json
import os
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import HTTPServer

FAILS: list[str] = []


def expect(name: str, cond: bool, detail: str = "") -> None:
    print(("  ok   " if cond else "FAIL  ") + name + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def status(opener, p: str, method: str = "GET", data: bytes | None = None) -> int:
    try:
        req = urllib.request.Request(opener + p, data=data, method=method)
        return urllib.request.urlopen(req).status
    except urllib.error.HTTPError as e:
        return e.code


def main() -> int:
    tmp = tempfile.mkdtemp()
    os.environ["REVIEW_DB"] = os.path.join(tmp, "selftest.db")
    # import AFTER REVIEW_DB is set so the store binds to the throwaway db
    import server  # noqa: PLC0415

    httpd = HTTPServer(("127.0.0.1", 0), server.H)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    base = f"http://localhost:{port}"
    inbox = os.path.join(os.path.dirname(os.path.abspath(server.__file__)), "inbox")
    inbox_file = os.path.join(inbox, "_selftest.csv")

    def get(p: str) -> str:
        return urllib.request.urlopen(base + p).read().decode()

    try:
        # 1. surfaces respond; / lands directly on /diag (no chooser interstitial).
        #    The diag SPA marks its body class=diag (raw in the HTML, unlike the
        #    \u-escaped JSON labels), so this is a stable landing marker.
        expect("/ lands on /diag", "<body class=diag>" in get("/"))
        units = json.loads(get("/api/units"))["units"]
        expect("api/units returns units", bool(units), f"{len(units)} units")

        axis = server.CONTRACT["axes"][0]
        unit = units[0]["unit_key"]
        verdict = axis["vocabulary"][0]

        # 2. no blind surface on the developer server — it is the factcheck skill's
        #    job (firewall by absence). /review and POST /commit must be gone.
        expect("no blind /review route (404)", status(base, "/review/" + urllib.parse.quote(unit)) == 404)
        expect("no POST /commit route (404)", status(base, "/commit/x", "POST", b"v=1") == 404)

        # 3. S9: blind GT flows back through the ONE ingestion path. Simulate the
        #    factcheck export landing in inbox/, then POST /ingest.
        os.makedirs(inbox, exist_ok=True)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["unit_key", "axis_key", "verdict", "reason", "evidence",
                    "reviewer", "provenance", "tier"])
        w.writerow([unit, axis["key"], verdict, "selftest", "[]", "fc", "blind", "silver"])
        with open(inbox_file, "w", encoding="utf-8") as fh:
            fh.write(buf.getvalue())
        expect("POST /ingest accepts the flow-back", status(base, "/ingest", "POST", b"") == 200)
        gt = get("/gt")
        expect("/gt lists the ingested blind entry", verdict in gt and "/promote/" in gt)

        # 4. loop closes: promote the ingested blind -> /eval gold count rises (S6:
        #    blind -> gold is allowed; the gate lives in store.ALLOWED).
        before = get("/eval")
        pid = gt.split("/promote/", 1)[1].split('"', 1)[0]
        urllib.request.urlopen(urllib.request.Request(base + f"/promote/{pid}", data=b"", method="POST"))
        after = get("/eval")
        gold_before = before.split(server.UI["eval_gold"], 1)[0].rsplit('class="big">', 1)[1].split("</div>", 1)[0]
        gold_after = after.split(server.UI["eval_gold"], 1)[0].rsplit('class="big">', 1)[1].split("</div>", 1)[0]
        expect("loop closes: eval gold count rises after promote",
               int(gold_after) > int(gold_before), f"{gold_before} -> {gold_after}")
    finally:
        httpd.shutdown()
        if os.path.exists(inbox_file):
            os.remove(inbox_file)
        if os.path.isdir(inbox) and not os.listdir(inbox):
            os.rmdir(inbox)

    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)} check(s)")
        return 1
    print("PASS: smoke test green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
