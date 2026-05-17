#!/usr/bin/env python3
"""xlsx 内の drawings (図形・画像・グループ) を抽出し、アンカー情報付きで manifest 化する。

OOXML の xl/drawings/drawing*.xml を zipfile + stdlib で直接パースする。
openpyxl は Picture は拾えるがテキストボックス / グループ図形 / SmartArt の
読み込みに既知の欠損があるため、drawing 系は一切 openpyxl に依存しない。

抽出対象:
  - <xdr:pic>  : 画像 (embed rId → xl/media/* 解決)
  - <xdr:sp>   : シェイプ (txBody 内のテキストを抽出)
  - <xdr:grpSp>: グループ化図形 (再帰展開)
  - <xdr:cxnSp>: コネクタ (テキスト付きなら拾う)

アンカーは twoCellAnchor / oneCellAnchor / absoluteAnchor 全てを扱う。
cell anchor は 0-indexed → Excel 表記 ("G17" 等) に変換して出力する。

使い方:
  python3 xlsx_drawings.py <file.xlsx>                    # stdout に manifest JSON
  python3 xlsx_drawings.py <file.xlsx> --extract-to DIR   # media 実体を DIR/<sheet>/media/ に展開
  python3 xlsx_drawings.py <file.xlsx> --sheet "シート名"  # 1 シートのみ

manifest 形式 (1ファイル分):
  {
    "file": "<path>",
    "sheets": {
      "<sheet_name>": {
        "has_drawings": bool, "has_vml_drawings": bool,
        "shapes": [
          {"kind": "shape"|"pic"|"cxn", "anchor_type": "twoCell"|"oneCell"|"absolute",
           "anchor_from": "G17", "anchor_to": "G17",
           "anchor_range": "G17", "anchor_from_rc": [16, 6], "anchor_to_rc": [16, 6],
           "text": "...",                    # shape / cxn のみ
           "media_path": "xl/media/image1.png",  # pic のみ
           "extracted_path": "/tmp/.../image1.png",  # --extract-to 指定時のみ
           "name": "図 2", "id": "3"},
          ...
        ],
        "counts": {"shape": n, "pic": n, "cxn": n},
      },
      ...
    }
  }
"""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

NS = {
    "r":   "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkg": "http://schemas.openxmlformats.org/package/2006/relationships",
    "s":   "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
    "a":   "http://schemas.openxmlformats.org/drawingml/2006/main",
    "mc":  "http://schemas.openxmlformats.org/markup-compatibility/2006",
}

DRAWING_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing"
VML_REL_TYPE     = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/vmlDrawing"
IMAGE_REL_TYPE   = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"


# ---------- helpers ----------

def col_letter(idx0: int) -> str:
    """0-indexed column → Excel letters. 0→A, 25→Z, 26→AA."""
    n = idx0 + 1
    s = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        s = chr(ord("A") + rem) + s
    return s


def anchor_cellref(col0: Optional[int], row0: Optional[int]) -> Optional[str]:
    if col0 is None or row0 is None:
        return None
    return f"{col_letter(col0)}{row0 + 1}"


def anchor_range(f: Optional[str], t: Optional[str]) -> Optional[str]:
    if f is None:
        return t
    if t is None or f == t:
        return f
    return f"{f}:{t}"


# ---------- package graph ----------

def _parse_xml(data: bytes) -> ET.Element:
    return ET.fromstring(data)


def _read_relationships(z: zipfile.ZipFile, rels_path: str) -> Dict[str, Dict[str, str]]:
    """Return {rId: {Type, Target}} for a .rels file (returns {} if missing)."""
    try:
        data = z.read(rels_path)
    except KeyError:
        return {}
    root = _parse_xml(data)
    out = {}
    for rel in root.findall("{%s}Relationship" % NS["pkg"]):
        out[rel.get("Id")] = {"Type": rel.get("Type"), "Target": rel.get("Target")}
    return out


def _resolve_target(base_path: str, target: str) -> str:
    """Resolve a relationship Target (possibly '../foo' / '/abs/path') against its .rels base.

    base_path is the path that owns the .rels (e.g. xl/worksheets/sheet3.xml);
    rels live at xl/worksheets/_rels/sheet3.xml.rels and their Target is
    relative to base_path's directory.
    """
    if target.startswith("/"):
        return target.lstrip("/")
    base_dir = "/".join(base_path.split("/")[:-1])
    parts = (base_dir + "/" + target).split("/") if base_dir else target.split("/")
    out: List[str] = []
    for p in parts:
        if p in ("", "."):
            continue
        if p == "..":
            if out:
                out.pop()
            continue
        out.append(p)
    return "/".join(out)


def _sheet_map(z: zipfile.ZipFile) -> List[Tuple[str, str]]:
    """Return [(sheet_name, sheet_xml_path)] in workbook order."""
    try:
        wb_xml = _parse_xml(z.read("xl/workbook.xml"))
    except KeyError:
        return []
    wb_rels = _read_relationships(z, "xl/_rels/workbook.xml.rels")
    sheets = []
    for s in wb_xml.findall("{%s}sheets/{%s}sheet" % (NS["s"], NS["s"])):
        name = s.get("name")
        rid = s.get("{%s}id" % NS["r"])
        if rid is None or name is None:
            continue
        rel = wb_rels.get(rid)
        if not rel:
            continue
        target = _resolve_target("xl/workbook.xml", rel["Target"])
        sheets.append((name, target))
    return sheets


# ---------- drawing parse ----------

def _iter_anchors(root: ET.Element):
    """Yield (anchor_element, anchor_type) for every top-level anchor in wsDr."""
    for tag, t in (("twoCellAnchor", "twoCell"),
                   ("oneCellAnchor", "oneCell"),
                   ("absoluteAnchor", "absolute")):
        for a in root.findall("{%s}%s" % (NS["xdr"], tag)):
            yield a, t


def _anchor_cell(elem: ET.Element, tag: str) -> Tuple[Optional[int], Optional[int]]:
    """Extract (col0, row0) from xdr:from or xdr:to. Returns (None, None) when absent."""
    sub = elem.find("{%s}%s" % (NS["xdr"], tag))
    if sub is None:
        return None, None
    col_el = sub.find("{%s}col" % NS["xdr"])
    row_el = sub.find("{%s}row" % NS["xdr"])
    col = int(col_el.text) if col_el is not None and col_el.text is not None else None
    row = int(row_el.text) if row_el is not None and row_el.text is not None else None
    return col, row


def _unwrap_alternate(elem: ET.Element) -> ET.Element:
    """If the child is an mc:AlternateContent, prefer <mc:Choice> over <mc:Fallback>.

    Returns the effective container to iterate children from.
    """
    alt = elem.find("{%s}AlternateContent" % NS["mc"])
    if alt is None:
        return elem
    choice = alt.find("{%s}Choice" % NS["mc"])
    fallback = alt.find("{%s}Fallback" % NS["mc"])
    return choice if choice is not None else (fallback if fallback is not None else elem)


def _extract_shape_text(elem: ET.Element) -> str:
    """Concatenate all <a:t> text in a shape's txBody, preserving paragraph breaks."""
    tx = elem.find("{%s}txBody" % NS["xdr"])
    if tx is None:
        return ""
    paras = []
    for p in tx.findall("{%s}p" % NS["a"]):
        runs = [t.text or "" for t in p.findall(".//{%s}t" % NS["a"])]
        paras.append("".join(runs))
    return "\n".join(s for s in paras if s.strip())


def _extract_nvpr_meta(elem: ET.Element, inner_tags: List[str]) -> Tuple[Optional[str], Optional[str]]:
    """Return (id, name) from nv*Pr/cNvPr. inner_tags = ['nvSpPr'] or ['nvPicPr'] etc."""
    for tag in inner_tags:
        nv = elem.find("{%s}%s" % (NS["xdr"], tag))
        if nv is None:
            continue
        cnv = nv.find("{%s}cNvPr" % NS["xdr"])
        if cnv is None:
            continue
        return cnv.get("id"), cnv.get("name")
    return None, None


def _walk_objects(container: ET.Element, anchor_info: dict, rels: Dict[str, Dict[str, str]],
                  drawing_path: str) -> List[dict]:
    """Walk immediate object children (pic / sp / cxnSp / grpSp) of an anchor or group,
    recursing into groups. Returns a flat list of shape dicts with anchor_info merged in.
    """
    out: List[dict] = []
    container = _unwrap_alternate(container)
    for child in list(container):
        tag = child.tag.split("}", 1)[-1]
        if tag == "pic":
            blip = child.find(".//{%s}blip" % NS["a"])
            embed_rid = blip.get("{%s}embed" % NS["r"]) if blip is not None else None
            media_path = None
            if embed_rid and embed_rid in rels:
                t = rels[embed_rid]["Target"]
                media_path = _resolve_target(drawing_path, t)
            oid, oname = _extract_nvpr_meta(child, ["nvPicPr"])
            out.append({
                **anchor_info,
                "kind": "pic",
                "id": oid,
                "name": oname,
                "media_path": media_path,
                "text": "",
            })
        elif tag == "sp":
            text = _extract_shape_text(child)
            oid, oname = _extract_nvpr_meta(child, ["nvSpPr"])
            out.append({
                **anchor_info,
                "kind": "shape",
                "id": oid,
                "name": oname,
                "text": text,
            })
        elif tag == "cxnSp":
            text = _extract_shape_text(child)
            oid, oname = _extract_nvpr_meta(child, ["nvCxnSpPr"])
            out.append({
                **anchor_info,
                "kind": "cxn",
                "id": oid,
                "name": oname,
                "text": text,
            })
        elif tag == "grpSp":
            out.extend(_walk_objects(child, anchor_info, rels, drawing_path))
        elif tag == "AlternateContent":
            inner = _unwrap_alternate(child)
            if inner is not child:
                out.extend(_walk_objects(inner, anchor_info, rels, drawing_path))
    return out


def parse_drawing(z: zipfile.ZipFile, drawing_path: str) -> List[dict]:
    """Parse a single xl/drawings/drawingN.xml and return a list of shape dicts."""
    try:
        root = _parse_xml(z.read(drawing_path))
    except KeyError:
        return []
    rels_path = drawing_path.rsplit("/", 1)[0] + "/_rels/" + drawing_path.rsplit("/", 1)[1] + ".rels"
    rels = _read_relationships(z, rels_path)
    shapes: List[dict] = []
    for a, atype in _iter_anchors(root):
        f_col, f_row = _anchor_cell(a, "from")
        t_col, t_row = _anchor_cell(a, "to")
        anchor_info = {
            "anchor_type": atype,
            "anchor_from": anchor_cellref(f_col, f_row),
            "anchor_to":   anchor_cellref(t_col, t_row),
            "anchor_range": anchor_range(anchor_cellref(f_col, f_row),
                                         anchor_cellref(t_col, t_row)),
            "anchor_from_rc": [f_row, f_col] if f_row is not None else None,
            "anchor_to_rc":   [t_row, t_col] if t_row is not None else None,
        }
        shapes.extend(_walk_objects(a, anchor_info, rels, drawing_path))
    return shapes


# ---------- sheet-level orchestration ----------

def collect_sheet_drawings(z: zipfile.ZipFile, sheet_name: str, sheet_xml_path: str,
                           extract_dir: Optional[Path]) -> dict:
    """Parse all drawings linked from one worksheet. Optionally stage media files."""
    sheet_rels_path = sheet_xml_path.rsplit("/", 1)[0] + "/_rels/" + sheet_xml_path.rsplit("/", 1)[1] + ".rels"
    sheet_rels = _read_relationships(z, sheet_rels_path)

    drawing_targets = [
        _resolve_target(sheet_xml_path, r["Target"])
        for r in sheet_rels.values() if r["Type"] == DRAWING_REL_TYPE
    ]
    has_vml = any(r["Type"] == VML_REL_TYPE for r in sheet_rels.values())

    all_shapes: List[dict] = []
    for dp in drawing_targets:
        all_shapes.extend(parse_drawing(z, dp))

    if extract_dir is not None:
        sheet_media_dir = extract_dir / _safe_dirname(sheet_name) / "media"
        for sh in all_shapes:
            mp = sh.get("media_path")
            if not mp:
                continue
            try:
                blob = z.read(mp)
            except KeyError:
                continue
            sheet_media_dir.mkdir(parents=True, exist_ok=True)
            fname = mp.rsplit("/", 1)[-1]
            digest = hashlib.sha1(blob).hexdigest()[:8]
            stem, _, ext = fname.rpartition(".")
            out_name = f"{stem}_{digest}.{ext}" if stem else f"{fname}_{digest}"
            out_path = sheet_media_dir / out_name
            out_path.write_bytes(blob)
            sh["extracted_path"] = str(out_path)
            sh["sha1_prefix"] = digest

    counts = {"shape": 0, "pic": 0, "cxn": 0}
    for s in all_shapes:
        counts[s["kind"]] = counts.get(s["kind"], 0) + 1

    return {
        "has_drawings": bool(drawing_targets),
        "has_vml_drawings": has_vml,
        "drawing_xml_paths": drawing_targets,
        "shapes": all_shapes,
        "counts": counts,
    }


def _safe_dirname(name: str) -> str:
    """Filesystem-safe version of a sheet name for staging subdirs."""
    import re
    s = re.sub(r"[^a-zA-Z0-9_\u3040-\u30ff\u4e00-\u9fff\-]", "_", name.strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:64] or "sheet"


# ---------- entry point ----------

def extract(xlsx_path: Path, only_sheet: Optional[str] = None,
            extract_dir: Optional[Path] = None) -> dict:
    with zipfile.ZipFile(xlsx_path) as z:
        sheets = _sheet_map(z)
        out_sheets: Dict[str, dict] = {}
        for name, path in sheets:
            if only_sheet and name != only_sheet:
                continue
            out_sheets[name] = collect_sheet_drawings(z, name, path, extract_dir)
    return {
        "file": str(xlsx_path),
        "extract_dir": str(extract_dir) if extract_dir else None,
        "sheets": out_sheets,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("file")
    p.add_argument("--sheet", help="limit to one sheet")
    p.add_argument("--extract-to", help="directory to stage media files into")
    p.add_argument("--compact", action="store_true",
                   help="omit 'shapes' arrays from output (counts only)")
    args = p.parse_args()

    extract_dir = Path(args.extract_to).resolve() if args.extract_to else None
    if extract_dir:
        extract_dir.mkdir(parents=True, exist_ok=True)

    result = extract(Path(args.file).resolve(), args.sheet, extract_dir)

    if args.compact:
        for s in result["sheets"].values():
            s.pop("shapes", None)

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
