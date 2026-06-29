#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the fact-checker handover package — the ONE distribution command (S10).

This is the SEPARATE-DELIVERABLE form of the GT-creation surface (review-server
CHOICES: "mode of the dev server vs separate handover deliverable"). It exists so
an external blind reviewer can be handed a clean, self-contained folder instead of
a route on the developer server.

What this script demonstrates, in code:

  S2  The contract is GENERATED from the single source, never hand-edited. We read
      source/contract.json (this example's single source — it stands in for the
      host's dev-system contract that the judge AND the server read) and write
      contract.generated.json into the package with a provenance stamp. The
      costliest akatsuki failure (F2) was a separate human server that RE-ENCODED
      the contract by hand and drifted; generating it from the source is the
      structural fix. Re-run this whenever the source moves.

  S3  Firewall by ABSENCE — the strongest form. The source carries each unit's input
      + evidence ONLY; there is no judges()/answer anywhere near it, so no machine
      output can enter the package. (In a real host the adapter would ALSO expose
      judges(); the discipline is that this build reads input+evidence only and
      never touches them.) The reviewer cannot be anchored because the answer is not
      present to leak — concealment is structural, not a render-time `if`.

  S10 One verified command. Running this builds dist/ and nothing else.

Standard library only.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "source")
DIST = os.path.join(HERE, "dist")

CONTRACT_SOURCE = os.path.join(SOURCE, "contract.json")
UNITS_SOURCE = os.path.join(SOURCE, "units.json")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_units_input_only():
    """Carry units' input + evidence — and ONLY that. We pass the source units
    through after stripping anything that is not input/evidence, so even if a
    future source file grew an answer field it could not reach the package."""
    src = json.load(open(UNITS_SOURCE, encoding="utf-8"))
    return [
        {"unit_key": u["unit_key"], "label": u.get("label", u["unit_key"]),
         "text": u.get("text", ""), "evidence": u.get("evidence", [])}
        for u in src["units"]
    ]


def generate_contract():
    """Generate the package's contract copy from the single source (S2).

    Carry the judgment vocabulary the reviewer needs (axes + their words + the
    unit/evidence shape) and a provenance stamp recording WHERE it came from and
    at WHICH version. We never re-author the axes by hand."""
    src = json.load(open(CONTRACT_SOURCE, encoding="utf-8"))
    return {
        "_generated": {
            "from": os.path.relpath(CONTRACT_SOURCE, HERE),
            "source_contract_version": src["version"]["contract"],
            "at": _now(),
            "_note": "GENERATED from the single contract source (S2). Do not hand-edit. "
                     "Re-run build_package.py when the source moves.",
        },
        "version": src["version"],
        "unit": src["unit"],
        "evidence_pointer": src["evidence_pointer"],
        # Axes carry only what a blind reviewer needs: the label and the words they
        # pick from. No judge/role internals reach the reviewer surface.
        "axes": [
            {"key": a["key"], "label": a["label"], "cardinality": a["cardinality"],
             "vocabulary": a["vocabulary"]}
            for a in src["axes"]
        ],
    }


def main():
    os.makedirs(DIST, exist_ok=True)
    contract = generate_contract()
    units = load_units_input_only()

    with open(os.path.join(DIST, "contract.generated.json"), "w", encoding="utf-8") as f:
        json.dump(contract, f, ensure_ascii=False, indent=2)
    with open(os.path.join(DIST, "units.json"), "w", encoding="utf-8") as f:
        json.dump({"units": units}, f, ensure_ascii=False, indent=2)

    # Sanity: assert no judge/answer keys leaked into what we are about to ship.
    blob = json.dumps({"contract": contract, "units": units}, ensure_ascii=False)
    for forbidden in ("proposer", "production", "judges", "verdict"):
        if forbidden in blob:
            raise SystemExit(f"FIREWALL BREACH: '{forbidden}' present in package data")

    axes = "/".join(a["label"] for a in contract["axes"])
    vocab = "・".join(contract["axes"][0]["vocabulary"]) if contract["axes"] else ""
    print(f"built package → {DIST}")
    print(f"  contract.generated.json  (from {contract['_generated']['from']} "
          f"@ {contract['_generated']['source_contract_version']}; 軸={axes} 語彙={vocab})")
    print(f"  units.json               ({len(units)} units, input+evidence only, no answers)")
    print("firewall by absence: no judges/answer in the source; none in the package.")


if __name__ == "__main__":
    main()
