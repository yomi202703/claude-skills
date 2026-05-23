---
name: pdf-to-md
description: Convert a PDF *or a sequence of page images* (Kindle screenshots, slide photos, scanned pages — png/jpg/webp/heic/tif/bmp) into AI-friendly markdown using MinerU (local VLM, 95%+ accuracy on OmniDocBench, CJK + LaTeX math + markdown tables + figure captions + auto-mermaid). Image input is natural-sorted (`p2 < p10`) and bundled into a PDF first, then converted. Output goes to ~/preprocessed/<stem>/<backend>/<stem>.md with images alongside. Session-lifecycle server: start once at batch begin, stop at batch end — 2nd+ document stays warm in the same session.
---

# pdf-to-md

## Session lifecycle

MinerU's VLM takes ~3 min to load. **Start the server before the batch, stop it at the end.** `convert` auto-detects the server via the state file in the OS temp dir (`/tmp/pdf-to-md-server.json` on macOS/Linux, `%TEMP%\pdf-to-md-server.json` on Windows). `mode: warm` if alive, `mode: cold` ad-hoc fallback otherwise.

**CUDA requirement**: `start-server` and the VLM backends (`hybrid-auto-engine`, `vlm-auto-engine`) require a CUDA GPU. On CPU-only machines (typical Windows laptops, Apple Silicon Macs without CUDA), `start-server` refuses with a hint, and `convert` auto-falls-back to `--backend pipeline` (~85% accuracy, CPU-only, ~1-2 s/page). The fallback note appears in the result JSON as `"fallback": "..."`.

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

`--backend hybrid-auto-engine` (default, ~95% accuracy) / `pipeline` (fast, ~85%) / `vlm-auto-engine`. `--lang japan` default. Others via `--help`.

## Output

`~/preprocessed/<stem>/<backend>/<stem>.md` + sibling `images/`. Math = LaTeX, tables = markdown, figures = image refs + `<details>` captions, flowcharts → mermaid.

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

## Platform notes

- **macOS / Linux**: use `python3` as shown. State file in `/tmp/`.
- **Windows**: same commands work via `python` (PowerShell) or `python3` (Git Bash). State file in `%TEMP%\`. The venv lives at `%USERPROFILE%\mineru-test\.venv\Scripts\`. Without an NVIDIA GPU, only the `pipeline` backend works (auto-selected).

Setup notes: `_dev/SETUP.md`.
