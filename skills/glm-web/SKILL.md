---
name: glm-web
description: Drive chat.z.ai from Claude over Chrome's DevTools Protocol — send a prompt, capture the reply — reusing a dedicated, signed-in Chrome profile with no API cost. Use to delegate CODING / engineering work to GLM (Zhipu's GLM-5.x, strongest on code) — a non-correlated opinion on implementation, debugging, and code review. NOT the CN-native-knowledge eye
---

Drives chat.z.ai in a dedicated Chrome instance shared with qwen-web / gemini-web / chatgpt-web (port 9333, profile `~/.gemini-chrome`) — sibling AI tabs in one signed-in browser. GLM's web chat is free, but side effects are real: it runs on the user's signed-in z.ai account and lands in its history.

## Use it

```
python3 scripts/ask.py "prompt"            # ask in the current conversation, print reply
python3 scripts/ask.py --new "prompt"       # start a fresh chat first
python3 scripts/ask.py --timeout 300 "..."  # long jobs
```

`ask.py` launches the shared Chrome if it is not already up, opening a z.ai tab. For long/important output prefer file handoff: ask GLM to write its answer into a fenced block you then read, rather than trusting the DOM-stability capture.

## One-time setup: sign in

The shared Chrome runs its own profile dir (`~/.gemini-chrome`) and debug port (9333) so it never collides with your normal Chrome, and the login persists across runs. If the z.ai tab is logged out, `ask.py` exits 3 (NOT_SIGNED_IN):

1. A Chrome window with a z.ai tab is open (the dedicated profile). If not, run `python3 scripts/ask.py ping` once to launch it.
2. In that tab, click Log in and complete z.ai sign-in (Google / email).
3. Re-run `ask.py` — it now works, and stays signed in for future runs.

The logged-out landing page also renders the input textarea, so "there's an input box" is not proof of sign-in; `ask.py` treats a visible Log in / 登录 / Get started CTA (with no editor) as logged out.

## How it works (for debugging)

- `scripts/cdp.py` — dependency-free CDP client. Resolves the page target whose URL contains `chat.z.ai` on port 9333 (override with `AI_CDP_PORT` / `GEMINI_CDP_PORT`), opens the WS, exposes `evaluate` / `type_text` / `key`, and `new_tab` (via `Target.createTarget`) to add the z.ai tab to the shared instance.
- `scripts/ask.py` — ensures the shared Chrome + a z.ai tab are up, checks sign-in, inserts the prompt into `textarea#chat-input` via CDP `Input.insertText`, clicks `button.sendMessageButton` (falling back to Enter), and polls the last assistant turn until a new reply appears and stabilizes.
- Selectors (probed against the live DOM): editor `textarea#chat-input`; send `button.sendMessageButton`; one assistant turn = `div.chat-assistant`, its reply body `.markdown-prose` (a capacity/error bubble has none, so the turn's own innerText is read as fallback); one user turn = `div.chat-user`. Generation signal: the send button is REMOVED from the DOM while generating and returns when done (so "send button present" = idle/finished).
- Robustness (shared with the sibling skills): send verification (a new user turn / active generation must appear, else retry the insert+send once — editor-empty alone is not treated as proof, avoiding a double-send); completion gate (settle only once the send button is back and text is stable — a stable bubble mid-generation is a preamble, not the answer); stall recovery (reload the tab once to re-read the server-side reply if generation stalls empty); final reload + direct read on timeout.

## Limits

- Shared Chrome must be reachable on the debug port; `ask.py` launches it. Separate instance from your everyday Chrome (a running Chrome cannot get a debug port attached after the fact — hence the own-profile design).
- GLM can answer "Model is currently at capacity" when the default model is busy; `ask.py` returns that text verbatim. Switch model in the z.ai tab and retry.
- Completion is a DOM-stability heuristic with stall recovery. For long/streaming jobs pass a larger `--timeout`, or use file handoff.
- Selectors track chat.z.ai's web UI; if it changes, re-probe the DOM with cdp.py and update `ask.py`.
- Reply capture is best-effort; file handoff is the reliable channel. Scope is text conversation (z.ai's agent/PPT/image surfaces are out of scope — drive them ad hoc via cdp.py if needed).
