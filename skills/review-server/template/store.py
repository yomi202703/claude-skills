#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Append-only GT store with maturity tiers, provenance, and gate enforcement.

Domain-agnostic. Enforces the review-server gates in code so a host cannot
violate them by accident:
  S4  append-only; revisions are new rows (supersedes), never UPDATE/DELETE.
  S5  cheap to regenerate; no schema ties GT to a single unit/criteria version.
  S6  maturity tiers + provenance; anchored never reaches gold/holdout;
      red and holdout are separate; every gold carries criterion_version.
  S12 holdout reads are logged.

Standard library only.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

TIERS = ("bronze", "silver", "gold", "red", "holdout")
PROVENANCE = ("blind", "anchored", "synthetic")

# Which (provenance -> tier) combinations are allowed. The leverage gate:
# anchored verdicts are contaminated by the machine answer, so they can never
# become gold or holdout (generalization ground truth). synthetic is seed-only.
ALLOWED = {
    "synthetic": {"bronze"},
    "anchored": {"silver", "red"},
    "blind": {"gold", "holdout", "silver", "red"},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class GateViolation(ValueError):
    """Raised when a write would break a server gate."""


class Store:
    def __init__(self, path: str):
        # check_same_thread=False: the stdlib HTTPServer serves one request at a
        # time, but not necessarily on the thread that opened the connection
        # (tests, or a future ThreadingHTTPServer). Access stays serialized by
        # the single-threaded server + the GIL, so this is safe here.
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._init()

    def _init(self) -> None:
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS gt_entries (
              id              INTEGER PRIMARY KEY AUTOINCREMENT,
              created_at      TEXT NOT NULL,
              unit_key        TEXT NOT NULL,
              axis_key        TEXT NOT NULL,
              verdict         TEXT NOT NULL,
              reason          TEXT NOT NULL,
              evidence        TEXT NOT NULL,   -- JSON array of pointers
              reviewer        TEXT NOT NULL,
              provenance      TEXT NOT NULL,   -- blind | anchored | synthetic
              tier            TEXT NOT NULL,   -- bronze | silver | gold | red | holdout
              unit_version    TEXT NOT NULL,
              criterion_version TEXT NOT NULL,
              contract_version  TEXT NOT NULL,
              judge_version   TEXT NOT NULL,
              supersedes      INTEGER          -- id of the entry this revises, or NULL
            );
            CREATE TABLE IF NOT EXISTS holdout_access (
              at      TEXT NOT NULL,
              caller  TEXT NOT NULL,
              reason  TEXT NOT NULL,
              n_rows  INTEGER NOT NULL
            );
            """
        )
        self.db.commit()

    # --- writes (append-only) ------------------------------------------------
    def append(
        self,
        *,
        unit_key: str,
        axis_key: str,
        verdict: str,
        reason: str,
        evidence: str,
        reviewer: str,
        provenance: str,
        tier: str,
        versions: dict,
        supersedes: int | None = None,
    ) -> int:
        if provenance not in PROVENANCE:
            raise GateViolation(f"unknown provenance {provenance!r}")
        if tier not in TIERS:
            raise GateViolation(f"unknown tier {tier!r}")
        if tier not in ALLOWED[provenance]:
            # S6: the anchored-never-gold rule lives here, not in the UI.
            raise GateViolation(
                f"provenance={provenance} may not be tier={tier} "
                f"(allowed: {sorted(ALLOWED[provenance])})"
            )
        for k in ("unit", "criterion", "contract", "judge"):
            if k not in versions:
                raise GateViolation(f"missing version stamp: {k}")
        cur = self.db.execute(
            """INSERT INTO gt_entries
               (created_at, unit_key, axis_key, verdict, reason, evidence,
                reviewer, provenance, tier, unit_version, criterion_version,
                contract_version, judge_version, supersedes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                _now(), unit_key, axis_key, verdict, reason, evidence,
                reviewer, provenance, tier, versions["unit"],
                versions["criterion"], versions["contract"],
                versions["judge"], supersedes,
            ),
        )
        self.db.commit()
        rid = cur.lastrowid
        assert rid is not None
        return rid

    def promote(self, entry_id: int, to_tier: str, reviewer: str) -> int:
        """Promote by appending a new row (never UPDATE). Re-checks the gate."""
        row = self.db.execute(
            "SELECT * FROM gt_entries WHERE id=?", (entry_id,)
        ).fetchone()
        if row is None:
            raise GateViolation(f"no entry {entry_id}")
        return self.append(
            unit_key=row["unit_key"], axis_key=row["axis_key"],
            verdict=row["verdict"], reason=row["reason"],
            evidence=row["evidence"], reviewer=reviewer,
            provenance=row["provenance"], tier=to_tier,
            versions={
                "unit": row["unit_version"],
                "criterion": row["criterion_version"],
                "contract": row["contract_version"],
                "judge": row["judge_version"],
            },
            supersedes=entry_id,
        )

    # --- reads ---------------------------------------------------------------
    def latest(self, tier: str | None = None, *, caller: str = "?", reason: str = "") -> list:
        """Latest non-superseded entry per (unit_key, axis_key).

        Reading holdout is logged (S12). Pass caller/reason at holdout reads.
        """
        rows = self.db.execute(
            "SELECT * FROM gt_entries ORDER BY id"
        ).fetchall()
        superseded = {r["supersedes"] for r in rows if r["supersedes"] is not None}
        latest: dict = {}
        for r in rows:
            if r["id"] in superseded:
                continue
            latest[(r["unit_key"], r["axis_key"])] = r
        out = list(latest.values())
        if tier is not None:
            out = [r for r in out if r["tier"] == tier]
        if tier == "holdout":
            self.db.execute(
                "INSERT INTO holdout_access (at, caller, reason, n_rows) VALUES (?,?,?,?)",
                (_now(), caller, reason, len(out)),
            )
            self.db.commit()
        return out

    def stale_gold(self, current_criterion_version: str) -> list:
        """Gold entries whose criterion_version lags the current contract (S6)."""
        return [
            r for r in self.latest(tier="gold")
            if r["criterion_version"] != current_criterion_version
        ]

    def holdout_access_log(self) -> list:
        return self.db.execute(
            "SELECT * FROM holdout_access ORDER BY at"
        ).fetchall()
