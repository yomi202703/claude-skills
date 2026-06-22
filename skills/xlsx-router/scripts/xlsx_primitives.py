"""Shared xlsx primitives used by xlsx_to_html / materialize / drawings.

All functions here are pure helpers over an openpyxl Worksheet. No I/O,
no CLI, no business logic. Keeping this the single source of truth
prevents drift (historically the same merge-lookup + cell-type code
lived in 3 places and diverged).
"""
import re
from typing import Dict, List, Optional, Tuple


# ---------- cell-level ----------

def cell_type(v) -> str:
    """Compact type code: e=empty, b=bool, n=num, d=date, s=string, o=other."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return "e"
    if isinstance(v, bool):
        return "b"
    if isinstance(v, (int, float)):
        return "n"
    if hasattr(v, "year") and hasattr(v, "month"):
        return "d"
    if isinstance(v, str):
        return "s"
    return "o"


def cell_len(v) -> int:
    """Effective length of a cell's value (0 for empty-like)."""
    if v is None:
        return 0
    if isinstance(v, str):
        return len(v) if v.strip() else 0
    return len(str(v))


# ---------- merges / forward-fill ----------

def build_merge_lookup(ws) -> Dict[Tuple[int, int], object]:
    """Map (row, col) → anchor value for every non-anchor cell inside a merge."""
    lookup: Dict[Tuple[int, int], object] = {}
    for mr in ws.merged_cells.ranges:
        anchor = ws.cell(row=mr.min_row, column=mr.min_col).value
        if anchor is None:
            continue
        for rr in range(mr.min_row, mr.max_row + 1):
            for cc in range(mr.min_col, mr.max_col + 1):
                if (rr, cc) != (mr.min_row, mr.min_col):
                    lookup[(rr, cc)] = anchor
    return lookup


def effective_value(ws, r: int, c: int, lookup: Dict[Tuple[int, int], object]):
    """Cell value with merge-anchor fall-through."""
    v = ws.cell(row=r, column=c).value
    if v is None:
        return lookup.get((r, c))
    return v


def row_values_ff(ws, r: int, lookup: Dict[Tuple[int, int], object]) -> list:
    """Row values with merge-anchor forward-fill applied.

    Per-row helper. For bulk scans use ``iter_rows_ff`` — it is ~100× faster
    on large sheets because openpyxl's ``ws.cell()`` access is dramatically
    slower than ``iter_rows(values_only=True)``.
    """
    return [effective_value(ws, r, c, lookup) for c in range(1, ws.max_column + 1)]


def iter_rows_ff(ws, start: int, end: int, lookup: Dict[Tuple[int, int], object]):
    """Yield rows in [start, end] as lists, with merge-anchor forward-fill.

    Uses ``iter_rows(values_only=True)`` so it is ~100× faster than calling
    ``row_values_ff`` per row on large sheets. Non-anchor cells inside a
    merge come back as None from iter_rows, so we overlay ``lookup``.
    """
    max_col = ws.max_column
    if start > end or max_col is None or max_col < 1:
        return
    for r, raw in enumerate(
        ws.iter_rows(
            min_row=start, max_row=end, max_col=max_col, values_only=True
        ),
        start=start,
    ):
        if len(raw) < max_col:
            row = list(raw) + [None] * (max_col - len(raw))
        else:
            row = list(raw)
        if lookup:
            for c_idx in range(max_col):
                if row[c_idx] is None:
                    v = lookup.get((r, c_idx + 1))
                    if v is not None:
                        row[c_idx] = v
        yield row


def row_effective_width(ws, r: int, lookup: Dict[Tuple[int, int], object]) -> int:
    """Number of non-empty cells in a row, counting forward-filled merge anchors."""
    cnt = 0
    for c in range(1, ws.max_column + 1):
        v = effective_value(ws, r, c, lookup)
        if v is not None and (not isinstance(v, str) or v.strip()):
            cnt += 1
    return cnt


# ---------- headers ----------

def concat_header_labels(
    ws, header_rows: List[int], lookup: Dict[Tuple[int, int], object]
) -> List[Optional[str]]:
    """Concatenate cell strings column-wise across header_rows with ' / ',
    using merge-anchor forward-fill. Dedupes repeated tiers in a single column.
    Returns one label (or None) per column in ws.
    """
    if not header_rows:
        header_rows = [1]
    labels: List[Optional[str]] = []
    for c in range(1, ws.max_column + 1):
        parts: List[str] = []
        for r in header_rows:
            v = effective_value(ws, r, c, lookup)
            if v is not None and str(v).strip():
                sv = str(v).strip()
                if sv not in parts:
                    parts.append(sv)
        labels.append(" / ".join(parts) if parts else None)
    return labels


# ---------- naming ----------

_SLUG_SAFE = re.compile(r"[^a-zA-Z0-9_\u3040-\u30ff\u4e00-\u9fff\-]")


def sanitize_slug(name, max_len: int = 64, fallback: str = "workbook") -> str:
    """ASCII/Japanese-safe slug. Guaranteed non-empty and ≤ max_len."""
    s = _SLUG_SAFE.sub("_", str(name).strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return (s[:max_len] or fallback)[:max_len]


def sqlite_column_name(raw, fallback: str) -> str:
    """SQLite-safe column name from a raw header string (None → fallback)."""
    if raw is None or str(raw).strip() == "":
        return fallback
    s = _SLUG_SAFE.sub("_", str(raw).strip())
    return s or fallback


def uniquify(labels: List[Optional[str]], fallback_prefix: str = "col") -> List[str]:
    """Make labels unique and non-empty. None → <prefix>_N; dupes get _2, _3."""
    out: List[str] = []
    seen: Dict[str, int] = {}
    for i, raw in enumerate(labels, start=1):
        safe = (
            sqlite_column_name(raw, f"{fallback_prefix}_{i}")
            if raw is not None
            else f"{fallback_prefix}_{i}"
        )
        if safe in seen:
            seen[safe] += 1
            out.append(f"{safe}_{seen[safe]}")
        else:
            seen[safe] = 1
            out.append(safe)
    return out
