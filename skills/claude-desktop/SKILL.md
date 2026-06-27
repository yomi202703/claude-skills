---
name: claude-desktop
description: Drive the locally-running Claude desktop app (Electron) from Claude — open a new session, optionally bind it to a folder, send a prompt, capture the reply, and list sidebar sessions by state. Uses the macOS Accessibility API (not CDP — the app blocks it; not AppleScript — the app has no scripting dictionary). For delegating/handing off work to the desktop app's own Claude sessions and monitoring them. Triggers — "hand this to the Claude app", "/claude-desktop".
---

## Use it

```
python3 scripts/ask.py "prompt"                 # new session, send, print reply
python3 scripts/ask.py --folder recall "prompt" # new session bound to a folder
python3 scripts/ask.py --here "prompt"          # send into the CURRENT session
python3 scripts/ask.py --timeout 600 "long job"

python3 scripts/sessions.py                     # list all sessions + state
python3 scripts/sessions.py --unread            # only sessions with a new reply
python3 scripts/sessions.py --json
```

First run builds a private venv (`scripts/.venv`) and installs pyobjc — takes a minute, then persists.

Delegation + monitoring loop: `ask.py --folder X "do the thing, write result to RESULT.md"` to hand off, then poll `sessions.py --unread` until the session flips to `unread`, then read `RESULT.md`. Prefer file handoff over the scraped reply for anything long or important.

## One-time setup: Accessibility permission

The controlling process (your terminal — Terminal/iTerm/Ghostty/…) needs Accessibility permission, or `ask.py`/`sessions.py` exit 3:

1. System Settings > Privacy & Security > Accessibility.
2. Add (and enable) your terminal app.
3. Re-run. The grant persists.

## Folder selection (new sessions only)

A session's folder is fixed once it has a conversation, so `--folder` is honored only when a new session is created (the default; ignored with `--here`). The folder must be in the app's "最近" (recent) list — `ask.py` opens the folder popup, picks the matching `AXMenuItem`, and clears the first-time "ワークスペース を信頼する" (trust workspace) gate automatically. Arbitrary paths (the "フォルダを開く…" native picker) and branch/worktree selection are reachable the same way but not yet wired into the CLI.

## How it works (for debugging)

- `scripts/ax.py` — AX primitives + self-bootstrapping venv. `connect()` finds the Claude pid, sets `AXManualAccessibility`, returns the app element; `walk()` traverses the tree (handles pyobjc returning `NSArray`, not `list` — the easy trap); helpers for roles/labels, `press()` (AXPress), `setv()` (set AXValue), and keyboard (`paste`, Escape, Return) for fallbacks.
- `scripts/ask.py` — new session → optional folder → set composer `AXValue` (falls back to focus+`Cmd+V` paste if the send button doesn't arm) → AXPress the 送信 button → wait. Completion/reply use the app's own accessibility announcements ("…応答を完了しました", "Claudeが返答しました: …") plus a text-stability check — sturdier than a pure DOM-stability heuristic.
- `scripts/sessions.py` — sidebar `AXButton` labels encode state+title ("未読の返答 …" = unread, "アイドル …" = idle); parses them.

## Limits

- AX permission required (see setup). `AXManualAccessibility` must take on this build — confirmed working as of writing; if a future build strips external manual-AX, the web tree won't expose and everything here goes dark.
- Reply capture is best-effort: the auto-generated chat title can leak as a first line, and long/streaming replies may truncate in the announcement. Use file handoff for anything that must be exact.
- Selectors are Japanese-UI labels (新規セッション, 送信, 未読の返答, アイドル, ワークスペースを信頼する). If the app UI language differs, update the literals in `ask.py`/`sessions.py` (English fallbacks are included where known).
- `--folder` only works for new sessions and only for folders already in the recent list.
