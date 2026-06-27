---
name: atlas
description: Drive ChatGPT inside the locally-running ChatGPT Atlas browser from Claude — send a prompt, capture the reply — reusing the app's signed-in session, with no API cost. Does not use CDP (Atlas blocks it); it runs JavaScript in the front tab via AppleScript Apple events. Use to delegate to ChatGPT for free. Triggers — "ask ChatGPT", "/atlas".
---

## Use it

Atlas must be running (`open -a "ChatGPT Atlas"`; `ask.py` launches it and opens chatgpt.com if absent). The one-time "Enable JS" step below must have been done.

```
python3 scripts/ask.py "prompt"            # ask in the current conversation, print reply
python3 scripts/ask.py --new "prompt"       # start a fresh chat first
python3 scripts/ask.py --timeout 300 "..."  # long jobs
```

Prefer file handoff over scraped text for anything long or important: ask ChatGPT to write its answer somewhere you can read — e.g. paste it back in a fenced block you then copy — rather than relying on the DOM-stability capture.

## Enable JS (one-time, required)

JavaScript-from-Apple-Events is gated behind the Chrome pref `browser.allow_javascript_apple_events`. In stock Chrome you'd flip it via View > Developer > "Allow JavaScript from Apple Events", but Atlas removed that menu item, so set the pref directly:

1. Fully quit Atlas (it overwrites Preferences on exit, so it must be closed).
2. In each profile's Preferences JSON under `~/Library/Application Support/com.openai.atlas/browser-data/host/<profile>/Preferences`, set `browser.allow_javascript_apple_events` to `true` (keep a backup first). The signed-in profile is the most recently modified one (not `Default`).
3. Relaunch Atlas. Verify with: `python3 scripts/atlas_js.py <(echo 'document.title')` — it should print `ChatGPT`, not the "JavaScript ... is turned off" error.

The first Apple event also triggers a one-time macOS Automation permission prompt (allow the terminal to control "ChatGPT Atlas").

## How it works (for debugging)

- `scripts/atlas_js.py` — primitive: runs JS in Atlas's front tab via `osascript` (`tell application "ChatGPT Atlas" to execute front window's active tab javascript "..."`), with AppleScript string escaping. Use it to probe the DOM when selectors drift.
- `scripts/ask.py` — launches Atlas / opens chatgpt.com, injects the prompt into the `#prompt-textarea` ProseMirror editor via `execCommand('insertText')`, clicks `[data-testid="send-button"]`, then polls until `[data-testid="stop-button"]` disappears and the last `[data-message-author-role="assistant"]` turn's text stabilizes.

## Limits

- App must be running; the Enable-JS pref must be set (survives restarts, but Atlas could strip it in a future build — re-apply the one-time step if the primitive starts returning the "turned off" error).
- Completion is a DOM-stability heuristic — for long/streaming jobs pass a larger `--timeout`, or use the file-handoff pattern above.
- Selectors (`#prompt-textarea`, `data-testid=send-button`/`stop-button`, `data-message-author-role`) track ChatGPT's web UI; if it changes, re-probe the DOM with `atlas_js.py` and update `ask.py`.
- Reply capture is best-effort; file handoff is the reliable channel.
