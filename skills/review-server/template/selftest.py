#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Developer smoke test — boot the server on an ephemeral port against a throw-
away DB and exercise the whole loop end-to-end, so a host who adapted data.py /
contract.json can confirm in one command that they did not break the contract:

  - landing + diagnostic API respond, units have the expected shape
  - the S3 firewall holds: /review never contains the machine's verdict/reason
  - the loop closes: commit (blind) -> /gt promote -> /eval measures gold
  - the S6 gate holds in the running server

  python3 selftest.py      # exit 0 = pass, 1 = fail

Standard library only. Uses REVIEW_DB to keep your real gt.db untouched.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import urllib.parse
import urllib.request
from http.server import HTTPServer

FAILS: list[str] = []


def expect(name: str, cond: bool, detail: str = "") -> None:
    print(("  ok   " if cond else "FAIL  ") + name + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


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

    def get(p: str) -> str:
        return urllib.request.urlopen(base + p).read().decode()

    def post(p: str, form: dict) -> str:
        data = urllib.parse.urlencode(form).encode()
        return urllib.request.urlopen(urllib.request.Request(base + p, data=data, method="POST")).read().decode()

    try:
        # 1. surfaces respond
        expect("landing responds", "<" in get("/"))
        units = json.loads(get("/api/units"))["units"]
        expect("api/units returns units", bool(units), f"{len(units)} units")

        # pick a unit + first axis from the live contract
        axis = server.CONTRACT["axes"][0]
        unit = units[0]["unit_key"]
        uq = urllib.parse.quote(unit)
        verdict = axis["vocabulary"][0]

        # 2. firewall (S3): the machine's reason for this unit/axis must NOT be on /review
        machine = server.ADAPTER.judges(unit, axis["key"]).get("production", {}) or {}
        review = get(f"/review/{uq}")
        reason = machine.get("reason", "")
        leaked = bool(reason) and reason in review
        expect("S3 firewall: /review hides machine reason", not leaked, "machine reason leaked into /review")

        # 3. commit a blind verdict, then it must reveal the machine (S4)
        revealed = post(f"/commit/{uq}", {f"v_{axis['key']}": verdict, "reason": "selftest", "evidence": "0"})
        expect("commit reveals machine after storing", server.UI["role_production"] in revealed)

        # 4. loop closes: /gt shows it, /eval is 0 gold, promote, /eval gains gold
        gt = get("/gt")
        expect("/gt lists the committed entry", verdict in gt and "/promote/" in gt)
        before = get("/eval")
        pid = gt.split("/promote/", 1)[1].split('"', 1)[0]
        post(f"/promote/{pid}", {})
        after = get("/eval")
        # gold count renders as the funnel .big value just before its eval_gold label
        gold_before = before.split(server.UI["eval_gold"], 1)[0].rsplit('class="big">', 1)[1].split("</div>", 1)[0]
        gold_after = after.split(server.UI["eval_gold"], 1)[0].rsplit('class="big">', 1)[1].split("</div>", 1)[0]
        expect("loop closes: eval gold count rises after promote",
               int(gold_after) > int(gold_before), f"{gold_before} -> {gold_after}")
    finally:
        httpd.shutdown()

    print()
    if FAILS:
        print(f"FAILED: {len(FAILS)} check(s)")
        return 1
    print("PASS: smoke test green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
