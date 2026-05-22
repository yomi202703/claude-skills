#!/usr/bin/env bash
set -eu

SKILL_ROOT="/Users/ivymee/.claude/skills/gemma-worker"
LOG="/tmp/gemma-worker-audit.log"

payload="$(cat || true)"
if [ -z "$payload" ]; then
  exit 0
fi

file=""
if command -v jq >/dev/null 2>&1; then
  file="$(printf '%s' "$payload" | jq -r '.tool_input.file_path // .tool_input.path // empty' 2>/dev/null || true)"
fi

case "$file" in
  */gemma-worker/*|*/ai-pipeline-audit/*)
    ;;
  *)
    exit 0
    ;;
esac

case "$file" in
  *.py|*.md|*.toml|*.sh)
    ;;
  *)
    exit 0
    ;;
esac

{
  printf '[gemma-worker-hook] %s\n' "$(date '+%F %T')"
  printf 'target: %s\n' "$file"
} > "$LOG"

if ! command -v uv >/dev/null 2>&1; then
  printf 'uv not on PATH; skipping audit\n' >> "$LOG"
  exit 0
fi

uv run --project "$SKILL_ROOT" \
  python -m gemma_worker.gate.audit_gate \
  --file "$file" --axes 1,2,3,4 --output json \
  >> "$LOG" 2>&1 || true

exit 0
