---
name: pdf-to-md
description: Convert a PDF, scanned document, or a sequence of page images/screenshots (Kindle captures, slide photos, scanned manuals — png/jpg/webp/heic/tif/bmp) into faithful, AI-readable markdown. Claude itself is the engine: it reads each page (vision) and transcribes to markdown, using the PDF's text layer as verbatim character ground-truth when present (hybrid) and vision-only OCR otherwise. Long documents are split into page batches processed by transcription subagents and stitched; a char-multiset coverage gate verifies no source content was dropped. Use when asked to convert/ingest/OCR/"markdown-ify" a PDF, manual, scanned doc, or screenshot set — especially Japanese business manuals with headings, clauses, tables, and diagrams. Not for authoring new PDFs.
---

# pdf-to-md (Claude-native)

Goal: turn a PDF / images into markdown that is faithful to the source AND directly
readable by an LLM. Claude reads the pages and writes the markdown — no external parser.
Use the page image for reading order / structure / tables / diagrams; use the text layer
(when present) as the exact characters, so legal/clause wording is never paraphrased or
OCR-drifted.

## Workflow

1. Prepare (mechanical: render pages, extract text layer, plan batches):
   ```bash
   python3 ~/.claude/skills/pdf-to-md/scripts/prepare.py <input...> --out-dir ~/preprocessed
   ```
   `<input>` = a single `.pdf`, a directory of images, a glob, or image paths. One document
   per run — to convert several PDFs, call prepare.py once per PDF (each gets its own `<stem>/`).
   Requires poppler on PATH (`pdfinfo`/`pdftoppm`/`pdftotext`; `brew install poppler`). Prints a compact
   manifest; the full manifest (per-page image+text paths, `born_digital` flags, `outline_hint`,
   `batches` of ~6 pages) is at `<out_dir>/<stem>/_work/manifest.json`. Read that JSON.

2. Transcribe each batch **in order** (Claude is the engine):
   - Short doc (≤ 8 pages, one batch): transcribe inline yourself.
   - Longer: for each batch, spawn ONE subagent and pass it the batch's page images + text
     files + the `outline_hint` + the **last ~20 lines of the previous batch's chunk** + the
     **current heading stack** (so headings stay consistent across batches). Each subagent
     writes `<work>/chunks/chunk_<NN>.md` (NN = batch index, zero-padded). Process batches
     sequentially so each inherits the prior heading state — do not fan out blindly.

   Transcription contract (give every subagent these rules verbatim):
   - Read each page image for reading order, layout, headings, lists, tables, diagrams.
   - When a `text` file is given for the page, it is the GROUND TRUTH for characters:
     transcribe verbatim, never paraphrase/summarize/"fix"; on conflict trust the text layer.
   - Judge each page's type (cover / TOC / body / table / figure) and structure accordingly —
     do not mechanically turn every line into a heading. Headings: `#` doc title (first page
     only), `##` section, `###` subsection; body as paragraphs; tables as markdown tables;
     diagrams/flowcharts as a fenced code block preserving the labels verbatim.
   - Strip running headers/footers/page numbers (repeated page boilerplate).
   - Preserve clause/article/item numbering exactly.
   - Continuation: if the batch starts mid-content put `<!-- continues-from-previous -->` at
     the top; if it ends mid-content put `<!-- continues-to-next -->` at the bottom. Join
     content split across pages within the batch into one paragraph/list/table.
   - Never invent content; leave illegible regions out rather than guessing.

3. Assemble + verify (mechanical):
   ```bash
   python3 ~/.claude/skills/pdf-to-md/scripts/assemble.py --manifest <work>/manifest.json
   ```
   Stitches chunks in order, drops continuation markers, strips recurring header/footer lines,
   and runs the faithfulness gate. Writes `<out_dir>/<stem>/<stem>.md`.

## Faithfulness gate (what assemble guarantees)

- Born-digital (text layer present): char-multiset content coverage of the text layer must be
  ≥ 99.5% (NFKC, kana/kanji/latin only, position-insensitive — robust to reformatting and 2D
  figure regrouping). The text-layer ground truth has recurring header/footer/page-number chrome
  removed first (the same boilerplate the transcription contract tells subagents to strip), so a
  correctly-stripped footer is never counted as missing content — footer-heavy / slide docs no
  longer false-FAIL. assemble reports the excluded chrome under `textlayer_chrome_excluded`.
  Below threshold → exit non-zero; the `gaps` list names the low-coverage pages AND shows the
  actual missing text (`missing_samples`), so you can tell a real omission from noise at a glance.
  Re-transcribe the named batches; don't ship a lossy result.
- Image-only (no text layer): no ground-truth anchor — coverage is N/A, assurance is softer.
  For high-stakes image-only docs, spot-re-read a sample of pages and compare.

## Output

`~/preprocessed/<stem>/<stem>.md`. Per-page images and the text layer stay under
`<stem>/_work/` for re-runs and inspection.

## Scripts

- `prepare.py` — input → per-page PNG + text layer + born-digital flags + batch manifest (entry point)
- `assemble.py` — stitch chunks + running-header strip + faithfulness gate
- Transcription itself is done by Claude (you / subagents), not a script.

Encrypted PDFs with copy/print permission are handled directly (no decryption step needed).
macOS Desktop is TCC-protected; copy images to `~/Downloads` first if needed.
