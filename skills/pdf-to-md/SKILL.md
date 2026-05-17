---
name: pdf-to-md
description: Convert a PDF into AI-friendly markdown using MinerU (local VLM, 95%+ accuracy on OmniDocBench, CJK + LaTeX math + figure captions + auto-mermaid). Output goes to ~/preprocessed/<stem>/<backend>/<stem>.md with images alongside. Session-lifecycle server: start once at batch begin, stop at batch end — 2nd+ PDF stays warm in the same session.
---

# pdf-to-md (v2, MinerU-backed)

## Session lifecycle

MinerU's VLM takes ~3 min to load. **Start the server before the batch, stop it at the end.** `convert` auto-detects the server via `/tmp/pdf-to-md-server.json` (`mode: warm` if alive, `mode: cold` ad-hoc fallback otherwise).

## Commands

`python3 ~/.claude/skills/pdf-to-md/scripts/dispatcher.py <cmd>`

| Command | Purpose |
|---|---|
| `start-server` | Launch `mineru-api` with VLM preload, wait until ready |
| `convert <pdf>` | Convert; uses server if alive, else ad-hoc cold |
| `stop-server` | Kill the server |
| `status` | Server liveness |

`convert` flags: `--backend hybrid-auto-engine` (default, ~95% accuracy) / `pipeline` (fast, ~85%) / `vlm-auto-engine`. Others via `--help`.

## Output

`~/preprocessed/<stem>/<backend>/<stem>.md` + sibling `images/`. Math = LaTeX, tables = markdown, figures = image refs + `<details>` captions, flowcharts → mermaid.

Setup notes: `_dev/SETUP.md`.
