#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Self-test + S10 doctor for the fact-checker handover package.

Proves the claims the package is supposed to demonstrate, end to end:

  1. BUILD            build_package.py produces dist/ from the single contract source.
  2. S2 (generation)  the shipped contract carries a _generated stamp pointing at the
                      source + its version — it was generated, not hand-authored.
  3. S3 (absence)     NO machine answer is present anywhere in the shipped package —
                      not in dist/ data, not as a judges() function in fc_server.py.
                      The firewall is structural: there is nothing to leak.
  4. COMMIT           a blind verdict written through the server's store persists.
  5. S9 (one path)    the /export CSV has EXACTLY the columns the developer server's
                      ingest reads, AND those rows import cleanly through the SAME
                      Store.append the dev ingest uses — the GT flows back on one path.

Run: python3 selftest.py   (exit 0 = PASS / GO).  Standard library only.
"""
from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.normpath(os.path.join(HERE, "..", "..", "template"))
DIST = os.path.join(HERE, "dist")

INGEST_COLUMNS = ["unit_key", "axis_key", "verdict", "reason", "evidence", "reviewer", "provenance", "tier"]
FORBIDDEN = ("proposer", "production", "def judges", "\"verdict\":", "'verdict':")


def _fail(msg):
    print(f"NO-GO: {msg}")
    sys.exit(1)


def step_build():
    r = subprocess.run([sys.executable, os.path.join(HERE, "build_package.py")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        _fail(f"build_package.py failed:\n{r.stdout}\n{r.stderr}")
    for f in ("contract.generated.json", "units.json"):
        if not os.path.exists(os.path.join(DIST, f)):
            _fail(f"dist/{f} missing after build")
    print("1. build .......... OK")


def step_generated_stamp():
    c = json.load(open(os.path.join(DIST, "contract.generated.json"), encoding="utf-8"))
    g = c.get("_generated", {})
    src = json.load(open(os.path.join(HERE, "source", "contract.json"), encoding="utf-8"))
    if g.get("source_contract_version") != src["version"]["contract"]:
        _fail("generated contract version does not match the single source (S2 drift)")
    # the generated contract must carry exactly the source's axes/vocabulary
    if [a["key"] for a in c["axes"]] != [a["key"] for a in src["axes"]]:
        _fail("generated axes diverge from the single source (S2)")
    print(f"2. S2 generation .. OK  (from {g.get('from')} @ {g.get('source_contract_version')}; "
          f"axes={[a['key'] for a in c['axes']]})")


def step_firewall_by_absence():
    # (a) no machine answer in the shipped DATA
    for fn in os.listdir(DIST):
        if not fn.endswith(".json"):
            continue
        blob = open(os.path.join(DIST, fn), encoding="utf-8").read()
        for bad in ("proposer", "production", "\"judges\"", "\"verdict\""):
            if bad in blob:
                _fail(f"machine answer leaked into dist/{fn}: found {bad!r}")
    # (b) no judges() function in the server CODE — firewall is structural
    src = open(os.path.join(HERE, "fc_server.py"), encoding="utf-8").read()
    if "def judges" in src or ".judges(" in src:
        _fail("fc_server.py references judges — the firewall must be by ABSENCE")
    print("3. S3 by absence .. OK  (no answer in data, no judges() in code)")


def step_commit_and_export():
    # Drive the store + export directly (no socket needed) against a temp DB.
    tmpdb = os.path.join(tempfile.mkdtemp(), "fc_gt.db")
    os.environ["FC_DB"] = tmpdb
    sys.path.insert(0, HERE)
    import fc_server  # imports with FC_DB pointed at the temp DB

    contract = fc_server.CONTRACT
    units = fc_server.UNITS
    u0 = units[0]["unit_key"]
    a0 = contract["axes"][0]
    fc_server.STORE.append(u0, a0["key"], a0["vocabulary"][0], "selftest reason", json.dumps(["1"]))
    if u0 not in fc_server.STORE.committed_keys():
        _fail("commit did not persist")

    # export is an operator CLI action (off the reviewer surface); its columns
    # must equal the dev ingest contract exactly.
    csv_text = fc_server.export_inbox_csv()
    header = next(csv.reader(io.StringIO(csv_text)))
    if header != INGEST_COLUMNS:
        _fail(f"export columns {header} != ingest columns {INGEST_COLUMNS}")
    print("4. commit + export OK")
    return csv_text


def step_roundtrip(csv_text):
    # S9: the exported rows import through the SAME Store.append the dev server's
    # POST /ingest uses. If this passes, the GT genuinely flows back on one path.
    sys.path.insert(0, TEMPLATE)
    from store import Store

    src = json.load(open(os.path.join(TEMPLATE, "contract.example.json"), encoding="utf-8"))
    versions = dict(src["version"])
    devdb = os.path.join(tempfile.mkdtemp(), "gt.db")
    store = Store(devdb)
    n = 0
    for row in csv.DictReader(io.StringIO(csv_text)):
        store.append(
            unit_key=row["unit_key"], axis_key=row["axis_key"], verdict=row["verdict"],
            reason=row["reason"], evidence=row["evidence"], reviewer=row["reviewer"],
            provenance=row["provenance"], tier=row["tier"], versions=versions,
        )
        n += 1
    if n == 0 or len(store.latest()) != n:
        _fail("round-trip import into the dev store failed")
    # the imported blind rows are gold-eligible there (ALLOWED: blind -> gold)
    promoted = store.promote(store.latest()[0]["id"], "gold", "selftest")
    if not promoted:
        _fail("imported blind GT is not gold-eligible on the dev side")
    print(f"5. S9 round-trip .. OK  ({n} row(s) imported, blind→gold promotable)")


def main():
    step_build()
    step_generated_stamp()
    step_firewall_by_absence()
    csv_text = step_commit_and_export()
    step_roundtrip(csv_text)
    print("\nPASS / GO — handover package is internally consistent and flows back on one path.")


if __name__ == "__main__":
    main()
