---
name: pdf-to-md
description: Convert a PDF *or a sequence of page images* (Kindle screenshots, slide photos, scanned pages — png/jpg/webp/heic/tif/bmp) into AI-friendly markdown using MinerU (local VLM, 95%+ accuracy on OmniDocBench, CJK + LaTeX math + markdown tables + figure captions + auto-mermaid). Image input is natural-sorted (`p2 < p10`) and bundled into a PDF first, then converted. Output goes to ~/preprocessed/<stem>/<backend>/<stem>.md with images alongside. Session-lifecycle server: start once at batch begin, stop at batch end — 2nd+ document stays warm in the same session.
---

# pdf-to-md

## Session lifecycle

MinerU's VLM takes ~3 min to load. **Start the server before the batch, stop it at the end.** `convert` auto-detects the server via `/tmp/pdf-to-md-server.json` (`mode: warm` if alive, `mode: cold` ad-hoc fallback otherwise).

## Commands

`python3 ~/.claude/skills/pdf-to-md/scripts/dispatcher.py <cmd>`

| Command | Purpose |
|---|---|
| `start-server` | Launch `mineru-api` with VLM preload, wait until ready |
| `convert <input...>` | Convert; `<input>` is a `.pdf`, a directory of images, a glob, or image paths |
| `stop-server` | Kill the server |
| `status` | Server liveness |

### `convert` input rules

- **One `.pdf` path** → converted directly.
- **Directory / glob / multiple image paths** → natural-sorted, bundled into `~/preprocessed/_pic_bundles/<stem>.pdf` (stem = source dir name, override with `--name`), then converted. Supported: `.png .jpg .jpeg .webp .tif .tiff .bmp .heic`.

Pre-flight for image input: the bundler natural-sorts and the result includes `bundled_from_images: N` — verify N matches the expected page count.

### `convert` flags

`--backend hybrid-auto-engine` (default, ~95% accuracy) / `pipeline` (fast, ~85%) / `vlm-auto-engine`. `--lang japan` default. `--no-restructure` keeps MinerU's raw flat headings (see below). Others via `--help`.

### Heading reconstruction (slide decks)

MinerU tags every slide title as a level-1 `#`, so a presentation PDF comes out with no document-title/section distinction, mis-tagged body lines as headings, and the same slide title repeated across N slides. After a successful convert, a **layout-aware post-pass** (`restructure.py`, no LLM) reads the sibling `<stem>_content_list.json` (`text_level` + `bbox` + `page_idx`) and rebuilds the hierarchy: first slide title → `#` doc title, each page's first heading → `##` section, extra headings on a page → demoted to body, and runs of identical slide titles → one merged section. The original MinerU markdown is preserved as `<stem>.raw.md`; the result's `restructure` field reports `{applied, doc_title, sections_after, demoted_to_body, merged_duplicate_runs}`. It is a **no-op for genuinely hierarchical PDFs** (MinerU already emitting `##`/`###`) and whenever md/JSON headings don't align 1:1 — so it never mangles a well-structured document. Disable with `--no-restructure`.

## Output

`~/preprocessed/<stem>/<backend>/<stem>.md` (+ `<stem>.raw.md` when restructured) + sibling `images/`. Math = LaTeX, tables = markdown, figures = image refs + `<details>` captions, flowcharts → mermaid.

## Examples

```bash
# warm server (once per batch)
python3 ~/.claude/skills/pdf-to-md/scripts/dispatcher.py start-server

# regular PDF
python3 ~/.claude/skills/pdf-to-md/scripts/dispatcher.py convert ~/Downloads/paper.pdf

# folder of Kindle screenshots (auto-bundled)
python3 ~/.claude/skills/pdf-to-md/scripts/dispatcher.py convert ~/Downloads/kindle_book_xxx

# glob (quote it)
python3 ~/.claude/skills/pdf-to-md/scripts/dispatcher.py convert "~/Downloads/slides/*.png" --name lecture3

# stop at end of batch
python3 ~/.claude/skills/pdf-to-md/scripts/dispatcher.py stop-server
```

macOS Desktop is TCC-protected; copy images to `~/Downloads` or similar first.

Setup notes: `_dev/SETUP.md`.
