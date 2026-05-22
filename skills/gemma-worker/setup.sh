#!/usr/bin/env bash
set -eu
# gemma-worker setup: install external tools used by playbook runners.
# Idempotent. Missing optional tools degrade to LLM-only fallback at runtime.

SKILL_ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "[setup] gemma-worker @ $SKILL_ROOT"

have() { command -v "$1" >/dev/null 2>&1; }

if ! have uv; then
  echo "[setup] uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi

echo "[setup] python 3.12 via uv"
uv python install 3.12 >/dev/null

echo "[setup] python dev deps"
( cd "$SKILL_ROOT" && uv sync --extra dev >/dev/null )
( cd "$SKILL_ROOT" && uv pip install -e . >/dev/null )

# Python static-analysis tools (deadcode playbook)
echo "[setup] vulture (python dead code)"
uv tool install vulture 2>/dev/null || uv tool upgrade vulture 2>/dev/null || true

echo "[setup] ruff (lint)"
uv tool install ruff 2>/dev/null || uv tool upgrade ruff 2>/dev/null || true

echo "[setup] pyright (typecheck)"
uv tool install pyright 2>/dev/null || uv tool upgrade pyright 2>/dev/null || true

# JS/TS optional tools
if have npm; then
  echo "[setup] npm-based tools (ts-prune, ast-grep)"
  npm list -g ts-prune >/dev/null 2>&1 || npm install -g ts-prune >/dev/null 2>&1 || true
  npm list -g @ast-grep/cli >/dev/null 2>&1 || npm install -g @ast-grep/cli >/dev/null 2>&1 || true
else
  echo "[setup] npm not found; ts-prune/ast-grep skipped (TS detection falls back to LLM-only)"
fi

# Universal AST-grep via cargo if available
if have cargo; then
  echo "[setup] ast-grep via cargo"
  cargo install ast-grep --locked >/dev/null 2>&1 || true
fi

echo "[setup] done. installed runners:"
for t in vulture ruff pyright ts-prune sg ast-grep; do
  if have "$t"; then
    echo "  ✓ $t"
  else
    echo "  ✗ $t (LLM fallback)"
  fi
done
