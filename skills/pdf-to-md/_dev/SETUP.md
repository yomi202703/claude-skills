# pdf-to-md setup

## Prerequisite: MinerU venv

### macOS / Linux

```bash
mkdir -p ~/mineru-test && cd ~/mineru-test
uv venv --python 3.12
source .venv/bin/activate
uv pip install -U "mineru[all]"
```

### Windows (PowerShell)

```powershell
New-Item -ItemType Directory "$env:USERPROFILE\mineru-test" -Force | Out-Null
Set-Location "$env:USERPROFILE\mineru-test"
python -m uv venv --python 3.12          # or: uv venv --python 3.12 if uv is on PATH
python -m uv pip install --python .\.venv\Scripts\python.exe -U "mineru[all]"
```

Note: on Windows the venv binaries live in `.venv\Scripts\` (with `.exe` suffix), and the dispatcher branches on `os.name == "nt"` automatically.

The dispatcher hardcodes `~/mineru-test/.venv/{bin,Scripts}/{mineru,mineru-api}[.exe]` — adjust `VENV_BIN` in `scripts/dispatcher.py` if you install elsewhere.

## GPU requirement

The VLM backends (`hybrid-auto-engine` default, `vlm-auto-engine`) require a CUDA GPU via lmdeploy. Without CUDA:

- `start-server` refuses with a hint
- `convert` auto-falls-back to `--backend pipeline` (CPU-only, ~85% accuracy)

This affects most Windows laptops and Apple Silicon Macs. Use a CUDA Linux box or rent cloud GPU if you need ~95% accuracy.

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
