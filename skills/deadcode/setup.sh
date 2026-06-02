#!/usr/bin/env bash
# deadcode skill — toolchain setup
# Idempotent: re-running skips anything already installed.
# Usage: bash ~/.claude/skills/deadcode/setup.sh [--all | --js | --python | --ast-grep]

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()    { printf "${GREEN}✓${NC} %s\n" "$1"; }
warn()  { printf "${YELLOW}!${NC} %s\n" "$1"; }
err()   { printf "${RED}✗${NC} %s\n" "$1"; }
have()  { command -v "$1" >/dev/null 2>&1; }

WANT="${1:---all}"
do_js=0; do_py=0; do_ast=0; do_common=0
case "$WANT" in
  --all)      do_js=1; do_py=1; do_ast=1; do_common=1 ;;
  --js)       do_js=1; do_common=1 ;;
  --python)   do_py=1; do_common=1 ;;
  --ast-grep) do_ast=1 ;;
  *) err "unknown flag: $WANT"; exit 2 ;;
esac

# ── prerequisites ─────────────────────────────────────────────
need_prereq() {
  local cmd="$1" install_hint="$2"
  if have "$cmd"; then ok "$cmd present"; return 0; fi
  warn "$cmd missing — $install_hint"
  return 1
}

if (( do_js )); then
  need_prereq npm "install Node.js via https://nodejs.org or 'brew install node'" || exit 1
fi
if (( do_py )); then
  need_prereq uv "install uv via 'curl -LsSf https://astral.sh/uv/install.sh | sh'" || exit 1
fi

# ── tool installs ─────────────────────────────────────────────

if (( do_js )); then
  echo "── JS/TS ──"
  if have knip; then
    ok "knip $(knip --version) already installed"
  else
    npm install -g knip
    ok "knip $(knip --version) installed"
  fi
fi

if (( do_py )); then
  echo "── Python ──"
  for pkg in vulture deadcode; do
    if uv tool list 2>/dev/null | grep -q "^$pkg "; then
      ok "$pkg already installed (uv tool)"
    else
      uv tool install "$pkg"
      ok "$pkg installed"
    fi
  done
fi

# ── common deps (ripgrep / jq) ────────────────────────────────
if (( do_common )); then
  echo "── common ──"
  for c in rg jq; do
    if have "$c"; then
      ok "$c present"
    else
      warn "$c missing — running 'brew install $c'"
      brew install "$c"
    fi
  done
fi

# ── ast-grep (optional, used for AST-based deletion in Phase 3c) ───
if (( do_ast )); then
  echo "── ast-grep ──"
  if have ast-grep || have sg; then
    ok "ast-grep present"
  else
    warn "ast-grep missing — running 'brew install ast-grep'"
    brew install ast-grep
  fi
fi

# ── summary ───────────────────────────────────────────────────
echo
echo "── summary ──"
for t in knip vulture deadcode rg jq ast-grep; do
  if have "$t"; then ok "$t"; else warn "$t not on PATH"; fi
done

echo
ok "done"
