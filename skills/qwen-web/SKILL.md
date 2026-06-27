---
name: qwen-web
description: Drive chat.qwen.ai from Claude over Chrome's DevTools Protocol — send a prompt, capture the reply — reusing a dedicated, signed-in Chrome profile with no API cost. The CN-native sibling of gemini-web / chatgpt-web (same shared Chrome, port 9333). Use to delegate to Qwen (Tongyi Qianwen / 通义千问): a CN-native, non-correlated opinion trained on the Chinese web, and the seed-sowing executor for cn-search (naming edge CN sources Western models miss). Triggers — "ask Qwen", "Qwenに聞いて", "通義/千问に聞いて", "/qwen-web".
---

Drives chat.qwen.ai in a dedicated Chrome instance shared with gemini-web / chatgpt-web (port 9333, profile `~/.gemini-chrome`) — sibling AI tabs in one signed-in browser. Qwen's web chat is free, but side effects are real: it runs on the user's signed-in account and lands in its history.

## Use it

```
python3 scripts/ask.py "prompt"            # ask in the current conversation, print reply
python3 scripts/ask.py --new "prompt"       # start a fresh chat first
python3 scripts/ask.py --timeout 300 "..."  # long jobs
```

`ask.py` launches the shared Chrome if it is not already up, opening a Qwen tab. For long/important output prefer file handoff: ask Qwen to write its answer into a fenced block you then read, rather than trusting the DOM-stability capture.

## One-time setup: sign in

The shared Chrome runs its own profile dir (`~/.gemini-chrome`) and debug port (9333) so it never collides with your normal Chrome, and the login persists across runs. On first use `ask.py` exits 3 (NOT_SIGNED_IN) because the Qwen tab is logged out:

1. A Chrome window with a "Qwen Studio" tab is open (the dedicated profile). If not, run `python3 scripts/ask.py ping` once to launch it.
2. In that tab, click Log in and complete Qwen sign-in (Google / email / phone).
3. Re-run `ask.py` — it now works, and stays signed in for future runs.

The logged-out landing page also renders the input textarea, so "there's an input box" is not proof of sign-in; `ask.py` detects the visible Log in / 登录 CTA and refuses to proceed until you have actually logged in.

## How it works (for debugging)

- `scripts/cdp.py` — dependency-free CDP client. Resolves the page target whose URL contains `chat.qwen.ai` on port 9333 (override with `AI_CDP_PORT` / `GEMINI_CDP_PORT`), opens the WS, exposes `evaluate` / `type_text` / `key`, and `new_tab` (via `Target.createTarget`) to add the Qwen tab to the shared instance.
- `scripts/ask.py` — ensures the shared Chrome + a Qwen tab are up, checks sign-in, inserts the prompt into `textarea.message-input-textarea` via CDP `Input.insertText` (real input events so React enables the send control), clicks `button.send-button` (falling back to Enter), and polls `.response-message-content` until a new reply appears and stabilizes.
- Selectors (probed against the live DOM): editor `textarea.message-input-textarea`; send `button.send-button`; while generating the send control becomes `button.stop-button` (the generation signal); one assistant turn = `.qwen-chat-message-assistant`, its body `.response-message-content`; one user turn = `.qwen-chat-message-user`.
- Robustness (shared with the sibling skills): send verification (a new user turn / active generation must appear, else retry the insert+send once — editor-empty alone is not treated as proof, avoiding a double-send); completion gate (settle only once `button.stop-button` is gone and text is stable — a stable bubble mid-generation is a preamble, not the answer); stall recovery (reload the tab once to re-read the server-side reply if generation stalls empty); final reload + direct read on timeout.

## Limits

- Shared Chrome must be reachable on the debug port; `ask.py` launches it. Separate instance from your everyday Chrome (a running Chrome cannot get a debug port attached after the fact — hence the own-profile design).
- Completion is a DOM-stability heuristic with stall recovery. For long/streaming jobs pass a larger `--timeout`, or use file handoff.
- Selectors track chat.qwen.ai's web UI; if it changes, re-probe the DOM with cdp.py and update `ask.py`.
- Reply capture is best-effort; file handoff is the reliable channel. Scope is text conversation (Qwen's image/video generation widgets are out of scope — drive them ad hoc via cdp.py if needed).
