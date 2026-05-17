#!/usr/bin/env python3
"""xlsxをSQLiteに一括変換（Claude Code用 取り込みスクリプト）。

classify_sheet を呼び出して header_rows / data_rows を取得し、
正しいヘッダー行の値を列名として採用、データ行範囲も尊重する。
結合セルの anchor 値はヘッダー・データ行いずれも forward-fill する。

使用例:
  python3 xlsx_materialize.py foo.xlsx
  python3 xlsx_materialize.py foo.xlsx --out data/foo.db
  python3 xlsx_materialize.py foo.xlsx --tables "003申込書,005取扱者報告書"
  python3 xlsx_materialize.py foo.xlsx --skip-merged
"""
import argparse
import sqlite3
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).parent))
import xlsx_primitives as _prim  # noqa: E402
from xlsx_classify import classify_sheet  # noqa: E402
from xlsx_drawings import extract as _extract_drawings  # noqa: E402


def _write_drawings_table(cur, sheet_slug: str, shapes: list) -> int:
    """Create <sheet_slug>_drawings table and insert every shape/pic/cxn row.

    Returns number of rows inserted. Each shape row preserves the anchor
    cellref so downstream can JOIN drawings to the tabular data when needed.
    """
    table = _prim.sqlite_column_name(sheet_slug, "sheet") + "_drawings"
    cur.execute(f'DROP TABLE IF EXISTS "{table}"')
    cur.execute(
        f'CREATE TABLE "{table}" ('
        '"kind" TEXT, "anchor_range" TEXT, "anchor_from" TEXT, "anchor_to" TEXT, '
        '"name" TEXT, "text" TEXT, "media_path" TEXT, "extracted_path" TEXT'
        ')'
    )
    rows = 0
    for s in shapes:
        cur.execute(
            f'INSERT INTO "{table}" VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (
                s.get("kind"),
                s.get("anchor_range"),
                s.get("anchor_from"),
                s.get("anchor_to"),
                s.get("name"),
                s.get("text") or "",
                s.get("media_path"),
                s.get("extracted_path"),
            ),
        )
        rows += 1
    return rows


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("file")
    p.add_argument("--out", help="output SQLite path (default: <file>.sqlite)")
    p.add_argument(
        "--tables", help="comma-separated sheet names to include (default: all)"
    )
    p.add_argument(
        "--skip-merged", action="store_true", help="skip sheets with merged cells"
    )
    args = p.parse_args()

    out_path = args.out or str(Path(args.file).with_suffix(".sqlite"))
    wanted = set(s.strip() for s in args.tables.split(",")) if args.tables else None

    wb = openpyxl.load_workbook(args.file, data_only=True)
    conn = sqlite3.connect(out_path)
    cur = conn.cursor()

    # Drawings: extract once, stage media alongside the SQLite output.
    drawings_dir = Path(out_path).parent / (Path(out_path).stem + "_drawings")
    try:
        drawings_all = _extract_drawings(Path(args.file).resolve(), extract_dir=drawings_dir)
        drawings_by_sheet = drawings_all.get("sheets", {})
    except Exception as e:
        print(f"[warn] drawings extraction failed: {e}", file=sys.stderr)
        drawings_by_sheet = {}

    for sn in wb.sheetnames:
        if wanted and sn not in wanted:
            continue
        ws = wb[sn]
        merged = len(list(ws.merged_cells.ranges))
        if merged > 0 and args.skip_merged:
            print(f"[skip] {sn}: {merged} merged ranges", file=sys.stderr)
            continue
        if merged > 0:
            print(
                f"[warn] {sn}: {merged} merged ranges — forward-filled header and data",
                file=sys.stderr,
            )

        sheet_draw = drawings_by_sheet.get(sn) or {}
        meta = classify_sheet(wb, sn, Path(args.file).name, drawings_info=sheet_draw)
        # Always write the drawings table when meaningful shapes/pics/cxns exist,
        # regardless of content_type — notes sheets with product diagrams still
        # need their annotations captured somewhere queryable.
        shapes = sheet_draw.get("shapes") or []
        sheet_slug = meta.get("sheet_slug") or sn
        if shapes:
            draw_rows = _write_drawings_table(cur, sheet_slug, shapes)
            print(
                f"[ok]   {sn} -> \"{sheet_slug}_drawings\" ({draw_rows} shapes/pics)",
                file=sys.stderr,
            )
        if meta.get("content_type") == "notes":
            print(
                f"[skip] {sn}: content_type=notes — use P3 notes flow "
                f"(xlsx_read + LLM prose generation), not SQLite",
                file=sys.stderr,
            )
            continue
        header_rows = meta.get("header_rows") or [1]
        data_rows_range = meta.get("data_rows") or [max(header_rows) + 1, ws.max_row]
        data_start, data_end = data_rows_range

        merge_lookup = _prim.build_merge_lookup(ws)
        labels = _prim.concat_header_labels(ws, header_rows, merge_lookup)
        unique_cols = _prim.uniquify(labels)

        table = _prim.sqlite_column_name(sn, "sheet")
        cols_def = ", ".join(f'"{c}" TEXT' for c in unique_cols)
        cur.execute(f'DROP TABLE IF EXISTS "{table}"')
        cur.execute(f'CREATE TABLE "{table}" ({cols_def})')

        placeholders = ",".join("?" * len(unique_cols))
        row_count = 0
        for row in _prim.iter_rows_ff(ws, data_start, data_end, merge_lookup):
            if not any(
                v is not None and (not isinstance(v, str) or v.strip()) for v in row
            ):
                continue
            vals = ["" if v is None else str(v) for v in row]
            vals = vals[: len(unique_cols)] + [""] * max(
                0, len(unique_cols) - len(vals)
            )
            cur.execute(f'INSERT INTO "{table}" VALUES ({placeholders})', vals)
            row_count += 1

        print(
            f'[ok]   {sn} -> "{table}" '
            f"(hdr=rows{header_rows}, {row_count} rows, {len(unique_cols)} cols)",
            file=sys.stderr,
        )

    conn.commit()
    conn.close()
    print(out_path)


if __name__ == "__main__":
    main()
