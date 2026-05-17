# drawings — Tier A (deterministic shape + image extraction)

Triggered when the classifier flags a sheet with `has_drawings: true`
(actual shapes / pictures / connectors, not empty `wsDr` shells).

## What the script does

`xlsx_drawings.py` parses `xl/drawings/drawing*.xml` directly via
`zipfile` + `xml.etree` — it does NOT use openpyxl for drawings, because
openpyxl has known gaps with text boxes, grouped shapes, and SmartArt.

For each sheet it emits:
- **shapes** (text boxes with `<a:t>` content + anchor cellref)
- **pictures** (resolved `xl/media/<name>` + anchor cellref)
- **connectors** (when they carry text)

Anchors are converted 0-indexed col/row → Excel-style `G17` / `G17:I20`.

## How `xlsx_materialize` consumes it

When materializing a workbook to SQLite, the script also writes a
`<sheet_slug>_drawings` table per sheet that has extracted content:

| column | meaning |
|---|---|
| kind | `shape` / `pic` / `cxn` |
| anchor_range | e.g. `G17:I20` — where the drawing is anchored on the sheet |
| anchor_from | top-left anchor cell |
| anchor_to | bottom-right anchor cell |
| name | drawing's display name (e.g. `テキスト ボックス 8`) |
| text | shape text content (empty for `pic`) |
| media_path | in-zip path, e.g. `xl/media/image3.png` |
| extracted_path | staged PNG/EMF/JPG path, e.g. `/out_dir/.../image3_a1b2c3.png` |

Staged media lives in `<sqlite_stem>_drawings/<sheet>/media/<image>_<sha1>.ext`.

## How Claude Code should use the output

1. **Treat shape text as authoritative labels.** Product / plan codes
   drawn as floating text boxes on diagrams are usually NOT in any cell
   — the drawings table is the only place they exist. When a user asks
   "what is VL3?" the shape text is the answer.
2. **Join shape text to the main table by anchor.** The `anchor_range`
   tells you which cells a shape covers. Shape labels near (or on) a
   specific row are context for that row.
3. **Read image files directly.** `extracted_path` is a real PNG/EMF
   on disk — open it with the Read tool when the surrounding text can't
   answer the question. No Vision API call is needed; Read supports
   images natively.
4. **Don't flood context.** Read one image at a time, only the ones
   your current question requires. Images cost input tokens.

## Edge cases

- **Grouped shapes** (`<xdr:grpSp>`): the parser walks into groups
  recursively; child shapes/pics inherit the group's anchor.
- **`mc:AlternateContent`**: when present, the parser prefers
  `<mc:Choice>` (newer DrawingML) and falls back to `<mc:Fallback>`.
- **Chart-only drawings**: sheets whose `drawing*.xml` contains only
  `<xdr:graphicFrame>` (chart references) produce zero shapes/pics and
  the sheet is NOT flagged `has_drawings` — charts are out of scope.
- **vmlDrawing**: legacy VML (typically cell-comment shapes) is flagged
  as `has_vml_drawings: true` but NOT parsed. If a workbook relies on
  VML for semantic content, reach for Tier B (`p6_visual.md`).
- **EMF images**: staged as-is. macOS Preview can't display EMF; if the
  content matters, fall back to Tier B and read the rendered page PNG.
