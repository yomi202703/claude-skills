#!/bin/bash
# PostToolUse hook: run ai-wiki skill harness on every edit inside the skill.
# Adapted from xlsx/_dev/hook_check.sh.
# Hook receives tool-call JSON on stdin; we check tool_input.file_path.

INPUT=$(cat)
FILE=$(echo "$INPUT" | /usr/bin/python3 -c 'import sys,json
try:
    d = json.load(sys.stdin)
    print(d.get("tool_input", {}).get("file_path", ""))
except Exception:
    print("")')

# Only act when the edited file is inside ai-wiki's source tree or the deployed skill
case "$FILE" in
  */Projects/ai-wiki/*|*.claude/skills/ai-wiki/*)
    # Skip harness artifacts (golden baselines, history, caches, backups)
    case "$FILE" in
      *"/_dev/history/"*|*"/_dev/tests/test_corpus_regressions/"*|*.bak.*|*"__pycache__"*|*".pytest_cache"*) exit 0 ;;
    esac
    export PATH="$HOME/.local/bin:$PATH"
    # Always run from the source tree (has corpus + regression baselines)
    ROOT="$HOME/Projects/ai-wiki"
    OUT=$(cd "$ROOT" && pytest -q --no-header 2>&1)
    STATUS=$?
    if [ $STATUS -ne 0 ]; then
      echo "[ai-wiki skill harness] REGRESSION DETECTED after editing $FILE" >&2
      echo "$OUT" >&2
      exit 2  # hard error: signals failure to the hook runner
    fi
    ;;
esac

exit 0
