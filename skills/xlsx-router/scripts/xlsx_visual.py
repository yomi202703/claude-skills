#!/usr/bin/env python3
"""xlsx の各シートを LibreOffice でレンダリングし、ページ単位 PNG として staging する (Tier B)。

レイアウト依存の帳票 / 商品図解 / フロー図など、セル + 図形 + 画像が組み合わさって初めて
意味が通るシートを対象に、「人が Excel で見る姿そのもの」を画像化する。抽出テキストでは
復元できない文脈 (重なり・矢印の向き・近接関係) を Claude Code の Read ツール経由で
Vision に直接見せるためのフォールバック。

パイプライン:
  1. soffice --headless でシート → PDF (calc_pdf_Export)
  2. PyMuPDF (fitz) で PDF → PNG (ページ毎)
  3. {sheet_slug}/page_NN.png を staging + manifest 化

シート単位 PDF 化 (--split-by-sheet) も可能だが、LibreOffice は cmdline から
「特定シートだけ PDF 化」をサポートしない。そのため workbook 全体を一度 PDF 化し、
生成された PDF 内のページレンジを見てシートとの対応を推定するか、シート以外を
非表示にした一時 xlsx を作ってから変換するか、の二択になる。
現状は「workbook 全体を 1 PDF」+「全ページ展開」。シート境界の正確な対応が必要なら
--per-sheet オプション (逐次変換) を使う。

使い方:
  python3 xlsx_visual.py <file.xlsx> --out-dir DIR
  python3 xlsx_visual.py <file.xlsx> --out-dir DIR --per-sheet --sheets 'A,B'
  python3 xlsx_visual.py <file.xlsx> --out-dir DIR --dpi 200
"""
import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional


SOFFICE_CANDIDATES = [
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/usr/local/bin/soffice",
    "/opt/homebrew/bin/soffice",
    "soffice",
]


def find_soffice() -> str:
    for p in SOFFICE_CANDIDATES:
        if p == "soffice":
            if shutil.which(p):
                return p
        elif Path(p).exists():
            return p
    raise RuntimeError(
        "soffice (LibreOffice) not found. Install LibreOffice or adjust SOFFICE_CANDIDATES."
    )


def xlsx_to_pdf(xlsx_path: Path, out_pdf_dir: Path) -> Path:
    """Convert xlsx → PDF via LibreOffice headless. Returns PDF path."""
    soffice = find_soffice()
    out_pdf_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            soffice, "--headless", "--nologo", "--nofirststartwizard",
            "--convert-to", "pdf:calc_pdf_Export",
            "--outdir", str(out_pdf_dir),
            str(xlsx_path),
        ],
        check=True, capture_output=True,
    )
    pdf = out_pdf_dir / (xlsx_path.stem + ".pdf")
    if not pdf.exists():
        raise RuntimeError(f"soffice did not produce expected PDF: {pdf}")
    return pdf


def pdf_to_pngs(pdf_path: Path, out_dir: Path, dpi: int = 150) -> List[Path]:
    """Render every PDF page to PNG via PyMuPDF. Returns list of PNG paths."""
    import fitz
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    paths: List[Path] = []
    zoom = dpi / 72.0
    mtx = fitz.Matrix(zoom, zoom)
    for i, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=mtx, alpha=False)
        out = out_dir / f"page_{i:02d}.png"
        pix.save(str(out))
        paths.append(out)
    doc.close()
    return paths


def _single_sheet_xlsx(src: Path, sheet_name: str, tmpdir: Path) -> Path:
    """Produce a copy of `src` with only `sheet_name` listed in workbook.xml.

    IMPORTANT: we do NOT use openpyxl here — on save it strips drawings/shapes
    ("DrawingML support is incomplete and limited to charts and images only"),
    which silently loses exactly the annotations this skill exists to capture.

    Instead we operate at the zip level: rewrite `xl/workbook.xml` to keep
    only the target `<sheet>` entry, and copy every other zip part byte-for-byte.
    Orphan relationships / worksheet files for other sheets remain in the
    archive but aren't referenced from workbook.xml, so LibreOffice ignores them.
    """
    import zipfile
    from xml.etree import ElementTree as ET
    ns_s = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    ns_r = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    ET.register_namespace("", ns_s)
    ET.register_namespace("r", ns_r)

    out = tmpdir / (src.stem + "__" + _safe(sheet_name) + ".xlsx")
    tmpdir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(src) as zin:
        wb_xml_bytes = zin.read("xl/workbook.xml")
        root = ET.fromstring(wb_xml_bytes)
        sheets_el = root.find("{%s}sheets" % ns_s)
        if sheets_el is None:
            raise RuntimeError("workbook.xml has no <sheets> element")
        matched = False
        for s in list(sheets_el):
            if s.get("name") == sheet_name:
                # Force visible even if the original marks it hidden, so LO
                # definitely exports a page for it.
                s.attrib.pop("state", None)
                matched = True
            else:
                sheets_el.remove(s)
        if not matched:
            raise RuntimeError(f"sheet '{sheet_name}' not found in {src}")

        # defined names that reference other sheets are now orphaned. LibreOffice
        # tolerates them, but removing the whole <definedNames> block is safer
        # because some printers choke on #REF! references.
        dn = root.find("{%s}definedNames" % ns_s)
        if dn is not None:
            root.remove(dn)
        # calcChain references cells by sheet index — it becomes stale as soon
        # as we drop sheets. Dropping it forces LO to recompute on open.
        new_wb = ET.tostring(root, encoding="UTF-8", xml_declaration=True)

        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
            for name in zin.namelist():
                if name == "xl/workbook.xml":
                    zout.writestr(name, new_wb)
                elif name == "xl/calcChain.xml":
                    # skip — stale after sheet removal
                    continue
                else:
                    zout.writestr(name, zin.read(name))
    return out


def _safe(name: str) -> str:
    import re
    s = re.sub(r"[^a-zA-Z0-9_\u3040-\u30ff\u4e00-\u9fff\-]", "_", name.strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:64] or "sheet"


def render(xlsx_path: Path, out_dir: Path, dpi: int = 150,
           per_sheet: bool = False, sheets: Optional[List[str]] = None) -> dict:
    """Top-level: render xlsx to PNGs. Returns manifest dict."""
    out_dir.mkdir(parents=True, exist_ok=True)
    result: dict = {
        "file": str(xlsx_path),
        "out_dir": str(out_dir),
        "mode": "per_sheet" if per_sheet else "workbook",
        "dpi": dpi,
        "sheets": {},   # sheet_name → [png, ...]
        "workbook_pages": [],  # only when mode == "workbook"
    }

    if per_sheet:
        import openpyxl
        wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
        names = list(wb.sheetnames)
        wb.close()
        if sheets:
            names = [n for n in names if n in set(sheets)]
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            for sn in names:
                per = _single_sheet_xlsx(xlsx_path, sn, td_path)
                pdf = xlsx_to_pdf(per, td_path / "pdf")
                sheet_out = out_dir / _safe(sn)
                pngs = pdf_to_pngs(pdf, sheet_out, dpi=dpi)
                result["sheets"][sn] = [str(p) for p in pngs]
    else:
        pdf = xlsx_to_pdf(xlsx_path, out_dir / "_pdf")
        pngs = pdf_to_pngs(pdf, out_dir / "pages", dpi=dpi)
        result["workbook_pages"] = [str(p) for p in pngs]

    return result


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("file")
    p.add_argument("--out-dir", required=True, help="directory to stage PNGs into")
    p.add_argument("--dpi", type=int, default=150)
    p.add_argument("--per-sheet", action="store_true",
                   help="render one PDF per sheet (slower; accurate sheet→page mapping)")
    p.add_argument("--sheets", help="comma-separated sheet names (requires --per-sheet)")
    args = p.parse_args()

    sheets = [s.strip() for s in args.sheets.split(",")] if args.sheets else None
    manifest = render(
        Path(args.file).resolve(),
        Path(args.out_dir).resolve(),
        dpi=args.dpi,
        per_sheet=args.per_sheet,
        sheets=sheets,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
