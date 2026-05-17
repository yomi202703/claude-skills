#!/bin/bash
# PostToolUse hook: run xlsx skill harness when any file under ~/.claude/skills/xlsx/ is edited.
# Hook receives tool-call JSON on stdin; we check tool_input.file_path.

INPUT=$(cat)
FILE=$(echo "$INPUT" | /usr/bin/python3 -c 'import sys,json
try:
    d = json.load(sys.stdin)
    print(d.get("tool_input", {}).get("file_path", ""))
except Exception:
    print("")')

# Only act when the edited file is inside the xlsx skill
case "$FILE" in
  *".claude/skills/xlsx/"*)
    # Skip if the edit is itself a harness artifact (history, test baselines, backups)
    case "$FILE" in
      *"/_dev/history/"*|*.bak.*|*"/tests/test_classify_regression/"*) exit 0 ;;
    esac
    export PATH="$HOME/.local/bin:$PATH"
    OUT=$(cd "$HOME/.claude/skills/xlsx/_dev" && pytest tests/ -q --no-header 2>&1)
    STATUS=$?
    if [ $STATUS -ne 0 ]; then
      # Print to stderr so Claude sees the regression
      echo "[xlsx skill harness] REGRESSION DETECTED after editing $FILE" >&2
      echo "$OUT" >&2
      exit 2  # signal a hard error to the harness (blocks if configured so)
    fi
    ;;
esac

exit 0
