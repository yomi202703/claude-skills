#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only adapter over the host domain's judgment outputs (S8).

THIS IS THE FILE THE HOST ADAPTS. Reads must be side-effect-free (S8): never
mutate state, never auto-claim, never write back. Return the unit list, each
unit's input text + evidence spans, and the judge outputs (proposer + the
production judge under test).

The DemoAdapter below is an in-memory fixture so the template runs as-is.
Replace it with a real adapter (SQL / file reads) for your domain — keep the
same method signatures so server.py is unchanged.
"""
from __future__ import annotations

from typing import Protocol


class Adapter(Protocol):
    def units(self) -> list[dict]:
        """[{unit_key, label}] — one row per review unit (S7)."""
        ...

    def unit_input(self, unit_key: str) -> dict:
        """{text, evidence:[{idx, span_label}]} — input + evidence to highlight."""
        ...

    def judges(self, unit_key: str, axis_key: str) -> dict:
        """Machine outputs for one unit/axis. NEVER shown to a reviewer before
        commit (S3); revealed only after commit (S4) and in developer mode.
        {proposer:{verdict,reason,evidence}, production:{verdict,reason,evidence}}"""
        ...


class DemoAdapter:
    """Tiny fixture: 2 units, 1 axis, so the server is runnable out of the box."""

    _UNITS = [
        {"unit_key": "item-001", "label": "item-001"},
        {"unit_key": "item-002", "label": "item-002"},
    ]
    _INPUT = {
        "item-001": {
            "text": "0: caller asks about balance\n1: agent states a guaranteed return\n2: caller agrees",
            "evidence": [{"idx": 1, "span_label": "guaranteed return"}],
        },
        "item-002": {
            "text": "0: routine status check\n1: agent confirms settlement date",
            "evidence": [],
        },
    }
    _JUDGES = {
        ("item-001", "concern"): {
            "proposer": {"verdict": "flag", "reason": "asserts a guaranteed return", "evidence": [1]},
            "production": {"verdict": "flag", "reason": "guarantee language", "evidence": [1]},
        },
        ("item-002", "concern"): {
            "proposer": {"verdict": "none", "reason": "routine confirmation", "evidence": []},
            "production": {"verdict": "flag", "reason": "settlement mentioned", "evidence": [1]},
        },
    }

    def units(self) -> list[dict]:
        return list(self._UNITS)

    def unit_input(self, unit_key: str) -> dict:
        return self._INPUT.get(unit_key, {"text": "", "evidence": []})

    def judges(self, unit_key: str, axis_key: str) -> dict:
        return self._JUDGES.get((unit_key, axis_key), {"proposer": {}, "production": {}})


def divergence(judges: dict) -> bool:
    """True when proposer and production judge disagree (drives the queue, S4)."""
    p = (judges.get("proposer") or {}).get("verdict")
    q = (judges.get("production") or {}).get("verdict")
    return p is not None and q is not None and p != q
