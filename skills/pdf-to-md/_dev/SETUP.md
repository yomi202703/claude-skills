# pdf-to-md setup

## Prerequisite: MinerU venv

```bash
mkdir -p ~/mineru-test && cd ~/mineru-test
uv venv --python 3.12
source .venv/bin/activate
uv pip install -U "mineru[all]"
```

The dispatcher hardcodes `~/mineru-test/.venv/bin/{mineru,mineru-api}` — adjust `VENV_BIN` in `scripts/dispatcher.py` if you install elsewhere.

## First-run downloads

First `convert` (or first `start-server`) pulls ~3-4 GB of models into `~/.cache/huggingface/`:
- MinerU2.5-Pro VLM (1.2B params, fp16)
- Surya OCR layout/detection models
- Layout/MFR/OCR-det auxiliary models

After that, models are reused from cache.

## Backends

- `hybrid-auto-engine` (default): VLM + classical fallback, ~95% OmniDocBench accuracy. Best for CJK + math.
- `pipeline`: classical only, no VLM, ~85% accuracy. CPU-only, very fast (~1-2 s/page).
- `vlm-auto-engine`: pure VLM, slowest.

## State files

- `/tmp/pdf-to-md-server.json` — pid/host/port of running server
- `/tmp/pdf-to-md-server.log` — mineru-api stdout/stderr

If a previous session crashed leaving a stale json, `start-server` detects the dead pid and replaces it.
