#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""S10 preflight ("doctor") — validate the RECEIVING side before trusting a
handoff. Structural go/no-go BY NAME, run with the REAL parser (json.load + the
actual data.py adapter + store.py gate), not a hand-written re-check. Catches
the failure mode where an unverified handoff fails with a different symptom
every time: missing file, stale contract, adapter shape drift, broken gate.

  python3 doctor.py        # exit 0 = GO, 1 = NO-GO

Environment + data STRUCTURE only (not behavior/quality). Standard library only.
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
checks: list[tuple[bool, str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    checks.append((bool(cond), name, detail))


# 1. environment
check("Python >= 3.9", sys.version_info[:2] >= (3, 9), sys.version.split()[0])

# 2. required files present
for f in ("server.py", "store.py", "data.py", "contract.example.json"):
    check(f"file present: {f}", os.path.exists(os.path.join(HERE, f)))

# 3. contract parses + shape (the real parser, S2)
contract = None
try:
    contract = json.load(open(os.path.join(HERE, "contract.example.json"), encoding="utf-8"))
    check("contract parses", True)
except Exception as e:  # noqa: BLE001
    check("contract parses", False, repr(e))

if contract:
    v = contract.get("version", {})
    check("contract.version has unit/criterion/contract/judge",
          all(k in v for k in ("unit", "criterion", "contract", "judge")), str(list(v)))
    axes = contract.get("axes", [])
    check("contract.axes non-empty", bool(axes))
    check("each axis has key + label + vocabulary",
          bool(axes) and all(a.get("key") and a.get("label") and a.get("vocabulary") for a in axes))
    check("contract has unit + evidence_pointer",
          bool(contract.get("unit")) and bool(contract.get("evidence_pointer")))

# 4. adapter shape (the real data.py, S8) — sampled, read-only
try:
    data = importlib.import_module("data")
    A = data.DemoAdapter()
    units = A.units()
    check("adapter.units() -> [{unit_key,label}]",
          isinstance(units, list) and all("unit_key" in u and "label" in u for u in units))
    check("divergence() is callable", callable(getattr(data, "divergence", None)))
    if units and contract and contract.get("axes"):
        k = units[0]["unit_key"]
        inp = A.unit_input(k)
        check("adapter.unit_input() -> {text,evidence}", "text" in inp and "evidence" in inp)
        j = A.judges(k, contract["axes"][0]["key"])
        check("adapter.judges() -> {proposer,production}", "proposer" in j and "production" in j)
except Exception as e:  # noqa: BLE001
    check("data.py adapter imports + answers", False, repr(e))

# 5. store gate enforces the leverage rule (S6): anchored may not become gold
try:
    store = importlib.import_module("store")
    with tempfile.TemporaryDirectory() as d:
        S = store.Store(os.path.join(d, "preflight.db"))
        vers = {"unit": "v1", "criterion": "v1", "contract": "v1", "judge": "v1"}
        S.append(unit_key="u", axis_key="a", verdict="x", reason="", evidence="[]",
                 reviewer="doctor", provenance="blind", tier="silver", versions=vers)
        raised = False
        try:
            S.append(unit_key="u", axis_key="a", verdict="x", reason="", evidence="[]",
                     reviewer="doctor", provenance="anchored", tier="gold", versions=vers)
        except store.GateViolation:
            raised = True
        check("store gate: anchored -> gold is blocked", raised)
except Exception as e:  # noqa: BLE001
    check("store.py loads + enforces gate", False, repr(e))

# report
fails = [c for c in checks if not c[0]]
for cond, name, detail in checks:
    mark = " ok " if cond else "FAIL"
    line = f"  [{mark}] {name}"
    if detail and not cond:
        line += f" — {detail}"
    print(line)
print()
if fails:
    print(f"NO-GO: {len(fails)} check(s) failed")
    sys.exit(1)
print("GO: all preflight checks passed")
