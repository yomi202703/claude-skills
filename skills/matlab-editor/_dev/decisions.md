# matlab-editor — decisions

Append-only. Why choices were made and what happened.

## 2026-07-01 — Control channel: Engine API, not screen-scraping
MATLAB R2026a (macOS, Apple Silicon) is installed and runs live. Unlike the CDP/AX
skills (chatgpt-web, antigravity, claude-desktop) that scrape apps with no API,
MATLAB ships the official **Engine API for Python** (`matlab.engine`). Chose it:
results come back as real data, not DOM text. Connect to a *shared* session
(`matlab.engine.shareEngine` in the GUI once → `connect_matlab` attaches) so the
live workspace/path are shared. Verified end-to-end (ran the user's probit
estimation `main.m`, pulled `betahat1`/`se` back as numbers, drew a figure, popped
a msgbox — all reflected in the GUI).

Venv pinned to Python 3.12: the Engine API supports CPython 3.9–3.13, and the
system `python3` is 3.14 (too new). Package installed from the app's
`extern/engines/python` so the version matches R2026a exactly.

## 2026-07-01 — No headless-reuse fallback (live-connect only)
Tested: `start_matlab()` spawns a headless MATLAB, but it dies when the spawning
Python process exits — the shared name lingers in the registry as a ghost but
`connect_matlab` to it fails. A python-independent `matlab -desktop -r shareEngine`
process *does* persist and reconnect, but the user opted for live-connect only, so
no daemon/standalone reuse is built. If MATLAB isn't shared, exit 3 with the
one-line `shareEngine` instruction (the "sign-in" analog).

## 2026-07-01 — Command Window scrollback is NOT driveable on this build
Goal was to type into the GUI Command Window "as a human". Both GUI-driving routes
are dead ends on the R2026a JavaScript desktop (jsd, CEF-based):
- CDP: env var `MW_STARTER_JSD_DEBUG_PORT=<port>` (found by strings in
  libmwwebwindow) DOES inject `-remote-debugging-port` into CEF children, but no
  DevTools HTTP server ever binds the port. MATLAB runs CEF in-process
  (`--inprocess`); the flag reaches only `--type=renderer` children, not the
  browser process that would host the endpoint. Only connector ports 31515-31517
  listen. Confirmed with a throwaway `-desktop` launch + lsof.
- AX: `AXManualAccessibility=true` (+ `AXEnhancedUserInterface`) on the app pid
  (3651) does NOT materialize the CEF web a11y tree — only 7 native nodes (window,
  traffic-light buttons, one empty AXGroup, one static text). Web content never
  exposed. So no text field to type into.
- OS-level keystroke injection (Engine `commandwindow` to focus + CGEvent/System
  Events paste+Return): did not land (variable never set); and it's focus-
  dependent — it risks pasting into whatever is focused (e.g. the user's editor
  file). Rejected as unsafe.
ChatGPT (consulted via chatgpt-web) independently confirmed: no known-working CDP
against native jsd; the only browser-automatable MATLAB UI is the separate
`matlab-proxy` (a different instance, not the user's live GUI); native command
window needs OS keystroke injection with focus hacks. All rejected for this skill.

## 2026-07-01 — Scope narrowed to the Editor
Since the Command Window is blocked but the **Editor** has a documented API
(`matlab.desktop.editor`) that runs via the Engine AND reflects in the GUI, the
user chose to make this an editor-only skill (renamed matlab → matlab-editor).
Built `edit.py`: list/open/new/read/write/append/goto/close. Reads see the live
(unsaved) buffer; writes show up as GUI tabs. Content transferred via a temp file
that MATLAB reads with `fileread` (avoids string-escaping). All commands verified
against the live session.

Gotcha found in testing: untitled editor docs report a non-path `Filename` like
`untitled4` (not empty), and one such tab held the *user's* unsaved regression
work — nearly closed as leftover. Lesson baked into the skill: `read` before
closing/overwriting any untitled tab. Checking content before destroying paid off.
