---
name: antigravity
description: Drive the Antigravity app's agent from Claude — send a prompt, run its skills, capture the reply — over the app's always-open CDP debug port. Use to delegate to capabilities Claude lacks, or to get a second, non-correlated opinion.
---

# antigravity

Drives the locally-running Antigravity app, reusing the app's own authenticated session. Inference runs on Antigravity's backend (the user's account — real cost/side effects).

## Use it

Antigravity must be running (`open -a Antigravity`; `ask.py` will try to launch it if absent).

```
python3 scripts/ask.py "prompt"              # new conversation, ask, print reply
python3 scripts/ask.py --here "prompt"        # ask in the current conversation
python3 scripts/ask.py --timeout 300 "..."    # long jobs (e.g. transcription)
```

Default opens a new conversation so it never disrupts the user's running one. To fire a user's gemini skill, name it in the prompt (skills are natural-language triggered), e.g. `"transcribe_audio skill で /path/to/a.m4a を文字起こしして"`.

Prefer file handoff over scraped text: ask the agent to write its result to a path you specify, then read that file — more robust than the captured reply.

## How it works (for debugging)

- `scripts/cdp.py` — dependency-free CDP client; resolves the live port from `~/Library/Application Support/Antigravity/DevToolsActivePort`, opens the WS, exposes `evaluate` / `type_text` / `key`.
- `scripts/ask.py` — clicks "New Conversation", types via `Input.insertText` (works with the Lexical editor), sends Enter, polls the DOM until the reply stabilizes, prints the assistant text.

## Limits

- App must be running; CDP port changes each launch (resolved automatically).
- Completion is detected by DOM-stability heuristic — for long/streaming jobs pass a larger `--timeout`, or use the file-handoff pattern above.
- Selectors (`role=combobox` input, "New Conversation" button) depend on the app UI; if a future version changes them, re-probe the DOM via cdp.py.
- Reply capture is best-effort; the file-handoff pattern is the reliable channel.
