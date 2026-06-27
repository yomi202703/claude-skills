---
name: gemini-web
description: Drive gemini.google.com from Claude over Chrome's DevTools Protocol — send a prompt, capture the reply — reusing a dedicated, signed-in Chrome profile with no API cost. Use to delegate to Gemini (a second, non-correlated opinion; Google-side reasoning; multimodal the local model lacks). Triggers — "ask Gemini", "Geminiに聞いて", "/gemini-web".
---

Drives gemini.google.com in a dedicated Chrome instance. Inference runs on the user's signed-in Google account (real cost / side effects).

## Use it

```
python3 scripts/ask.py "prompt"            # ask in the current conversation, print reply
python3 scripts/ask.py --new "prompt"       # start a fresh chat first
python3 scripts/ask.py --timeout 300 "..."  # long jobs
```

`ask.py` launches the dedicated Chrome if it is not already up. Prefer file handoff for long/important output: ask Gemini to write its answer into a fenced block you then read, rather than trusting the DOM-stability capture.

## One-time setup: sign in

The skill runs Chrome with its own profile dir (`~/.gemini-chrome`) and debug port (9333) so it never collides with your normal Chrome, and the login persists across runs. On first use `ask.py` exits 3 (NOT_SIGNED_IN) because that profile is fresh:

1. A Chrome window titled Gemini is already open (the dedicated profile). If not, run `python3 scripts/ask.py ping` once to launch it.
2. In that window, click ログイン / Sign in and complete Google login normally.
3. Re-run `ask.py` — it now works, and stays signed in for future runs.

The logged-out Gemini landing page also shows a text box, so "there's an input box" is not proof of sign-in; `ask.py` detects the visible Sign-in CTA and refuses to proceed until you have actually logged in.

## How it works (for debugging)

- `scripts/cdp.py` — dependency-free CDP client. Resolves the page target whose URL contains `gemini.google.com` on port 9333 (override with `GEMINI_CDP_PORT`), opens the WS, exposes `evaluate` / `type_text` / `key`.
- `scripts/ask.py` — ensures the dedicated Chrome + a Gemini tab are up, checks sign-in, inserts the prompt into the Quill `.ql-editor` via `execCommand('insertText')` (the page enforces Trusted Types, so `innerHTML` is blocked), clicks the send button (aria-label matched across locales — scoped to the composer so a sidebar "…送信…" menu can't false-match — falling back to a `mat-icon` named `send`, then to Enter), and polls `message-content` nodes until a new reply appears and stabilizes.
- Robustness (learned the hard way on long replies):
  - Send verification: after sending it confirms a new `user-query` turn / active generation appeared, and retries the insert+send once if not. Guards the `--new` + long-prompt path against a silently-dropped send. (It does not treat an empty editor as proof — a failed insert also empties it — to avoid a double-send.)
  - Completion gate: settle only once generation has finished (stop button gone) and text is stable. While still generating, a stable bubble is a preamble/thinking pause, not the answer — never settle on it; reload to re-read the server-side reply instead.
  - Stall recovery: a streaming reply can stall client-side (empty bubble + stuck stop button) while the server already finished. If generation looks stalled empty for ~24s, `ask.py` reloads the tab once (`Page.reload`, then reconnects the WS) to re-read the persisted reply, and continues.
  - On timeout it does a final reload + reads the last `message-content` directly, rather than returning empty.

## Limits

- Dedicated Chrome must be reachable on the debug port; `ask.py` launches it. This is a separate instance from your everyday Chrome (a normally-running Chrome cannot have a debug port attached after the fact — hence the own-profile design).
- Completion is a DOM-stability heuristic with stall recovery (see above). For long/streaming jobs still pass a larger `--timeout`, or use file-handoff. Gemini streams can stall on long replies — recovery is automatic (one reload), but adds a ~30–60s detour when it triggers.
- Selectors (`.ql-editor`, the send-button aria-labels, `message-content`, `user-query`, the "stop response" label) track Gemini's web UI; if it changes, re-probe the DOM with cdp.py and update `ask.py`.
- Reply capture is best-effort; file handoff is the reliable channel.
- Scope is text conversation. Gemini's web music/media generation renders a `generated-music` / `video-player` widget with its own download menu — out of scope here; drive it ad hoc via cdp.py if needed.
