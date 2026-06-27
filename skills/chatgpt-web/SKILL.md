---
name: chatgpt-web
description: Drive chatgpt.com from Claude over Chrome's DevTools Protocol — send a prompt, capture the reply — reusing a dedicated, signed-in Chrome profile with no API cost. The CDP-based sibling of the atlas skill (which drives the Atlas browser via AppleScript because Atlas blocks CDP); use this when you want plain Chrome instead. Triggers — "ask ChatGPT via Chrome", "/chatgpt-web".
---

Drives chatgpt.com in a dedicated Chrome instance shared with the gemini-web skill: one signed-in browser, two AI tabs (ChatGPT + Gemini), same debug port (9333) and profile (`~/.gemini-chrome`). Inference runs on the user's signed-in ChatGPT account.

## Fallback

If Chrome starts hitting Cloudflare human-checks, fall back to `atlas` (it reuses the real Atlas app session and resists OpenAI's bot-detection better).

## Use it

```
python3 scripts/ask.py "prompt"            # ask in the current conversation, print reply
python3 scripts/ask.py --new "prompt"       # start a fresh chat first
python3 scripts/ask.py --timeout 400 "..."  # long jobs
```

`ask.py` launches the shared Chrome if down and opens a ChatGPT tab if absent. Prefer file handoff for long/important output: ask ChatGPT to write its answer into a fenced block you then read, rather than trusting the DOM capture.

## One-time setup: sign in

The dedicated profile is fresh per surface, so on first use `ask.py` exits 3 (NOT_SIGNED_IN or BLOCKED). Once done it persists:

1. A Chrome window with a chatgpt.com tab is open (dedicated profile, port 9333). If not, run `python3 scripts/ask.py ping` to spawn it.
2. In that tab, log in to ChatGPT normally. If a Cloudflare "verify you are human" check appears, clear it once by hand there.
3. Re-run `ask.py` — it now works and stays signed in.

## How it works (for debugging)

- `scripts/cdp.py` — dependency-free CDP client. Targets the `chatgpt.com` page on port 9333 (override `AI_CDP_PORT`); `new_tab()` opens tabs via the browser-level `Target.createTarget` (modern Chrome disables GET `/json/new`).
- `scripts/ask.py` — ensures the shared Chrome + a ChatGPT tab, checks sign-in / Cloudflare, inserts the prompt into the ProseMirror `#prompt-textarea` via `execCommand('insertText')`, clicks `[data-testid="send-button"]` (falls back to Enter), then polls `[data-message-author-role="assistant"]` turns until a new reply appears and stabilizes.
- Robustness (shared design with gemini-web):
  - Send verification: confirms a new user turn / active generation appeared and retries insert+send once if not (guards against a silently-dropped long send). Editor-empty is not used as proof, to avoid a double-send.
  - Completion gate: settle only once generation has finished (stop-button gone) and text is stable. While still generating, a stable bubble is a preamble/thinking pause, not the answer — never settle on it; reload to re-read the server-side reply instead (stops returning ChatGPT's preamble before the real reply on reasoning-heavy tasks).
  - Stall recovery: if generation stalls empty (~24s), reloads the tab once (`Page.reload` + WS reconnect) to re-read the server-side reply, then resumes.
  - On timeout, reloads once and reads the last assistant turn directly instead of returning empty.

## Limits

- Shared dedicated Chrome must be reachable on the debug port; `ask.py` launches it. This is a separate instance from everyday Chrome (a normally-running Chrome cannot have a debug port attached after the fact).
- OpenAI's automation detection is stricter than Google's; a CDP-driven session may occasionally face Cloudflare challenges. Solve once by hand, or use `atlas`.
- Completion is a DOM-stability heuristic with stall recovery (see above) — still pass a larger `--timeout` for long jobs, or use file handoff.
- Selectors (`#prompt-textarea`, `data-testid=send-button`/`stop-button`, `data-message-author-role=assistant`) track ChatGPT's web UI; re-probe with cdp.py and update `ask.py` if they drift.
