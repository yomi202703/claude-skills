#!/usr/bin/env python3
"""xlsx ↔ SQLite fidelity verifier.

Given (xlsx, sqlite), check whether the SQLite plausibly contains the same
non-empty data + drawings as the xlsx. Schema-agnostic: tolerates column
name shifts and row reordering. The signal is volume + drawings count.

Use it both before and after a materializer rewrite to confirm fidelity.

Usage:
    python3 xlsx_verify.py <xlsx> <sqlite>
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import openpyxl


def _xlsx_nonempty_cells_per_sheet(xlsx_path: str) -> dict[str, int]:
    """Count non-empty cells per sheet in xlsx (truth)."""
    wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=False)
    counts: dict[str, int] = {}
    for sheet in wb.worksheets:
        n = 0
        for row in sheet.iter_rows(values_only=True):
            for v in row:
                if v is not None and str(v).strip() != "":
                    n += 1
        counts[sheet.title] = n
    return counts


def _xlsx_drawing_count(xlsx_path: str) -> int:
    """Count drawing anchors across all xl/drawings/drawing*.xml in xlsx."""
    total = 0
    with zipfile.ZipFile(xlsx_path) as z:
        for name in z.namelist():
            if not re.match(r"xl/drawings/drawing\d+\.xml$", name):
                continue
            try:
                root = ET.fromstring(z.read(name))
            except ET.ParseError:
                continue
            # count one-cell + two-cell anchors (xdr:oneCellAnchor / xdr:twoCellAnchor / xdr:absoluteAnchor)
            for tag in ("oneCellAnchor", "twoCellAnchor", "absoluteAnchor"):
                total += sum(1 for _ in root.iter(f"{{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}}{tag}"))
    return total


def _sqlite_table_kinds(db_path: str) -> tuple[dict[str, int], dict[str, int]]:
    """Return ({data_table: nonempty_cell_count}, {drawings_table: row_count})."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    data: dict[str, int] = {}
    drawings: dict[str, int] = {}
    for t in tables:
        if t.endswith("_drawings"):
            cur.execute(f'SELECT COUNT(*) FROM "{t}"')
            drawings[t] = cur.fetchone()[0]
            continue
        cur.execute(f'SELECT * FROM "{t}"')
        rows = cur.fetchall()
        n = 0
        for row in rows:
            for v in row:
                if v is not None and str(v).strip() != "":
                    n += 1
        data[t] = n
    conn.close()
    return data, drawings


def verify(xlsx_path: str, db_path: str) -> dict:
    xlsx_cells = _xlsx_nonempty_cells_per_sheet(xlsx_path)
    xlsx_draw = _xlsx_drawing_count(xlsx_path)
    sql_data, sql_draw = _sqlite_table_kinds(db_path)

    xlsx_total = sum(xlsx_cells.values())
    sql_data_total = sum(sql_data.values())
    sql_draw_total = sum(sql_draw.values())

    return {
        "xlsx": str(xlsx_path),
        "sqlite": str(db_path),
        "cells": {
            "xlsx_per_sheet": xlsx_cells,
            "xlsx_total": xlsx_total,
            "sqlite_per_table": sql_data,
            "sqlite_total": sql_data_total,
            "ratio": round(sql_data_total / xlsx_total, 3) if xlsx_total else None,
        },
        "drawings": {
            "xlsx_anchor_count": xlsx_draw,
            "sqlite_drawings_rows": sql_draw_total,
            "sqlite_per_table": sql_draw,
            "ratio": round(sql_draw_total / xlsx_draw, 3) if xlsx_draw else None,
        },
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("xlsx")
    p.add_argument("sqlite")
    args = p.parse_args()
    if not Path(args.xlsx).exists():
        sys.exit(f"xlsx not found: {args.xlsx}")
    if not Path(args.sqlite).exists():
        sys.exit(f"sqlite not found: {args.sqlite}")
    result = verify(args.xlsx, args.sqlite)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
