---
name: matlab-editor
description: Drive the MATLAB Editor in the user's live desktop session from Claude — open, create, read, write, and navigate .m files as real editor tabs, with edits reflected in the GUI and reads seeing the live (even unsaved) buffer. Uses MATLAB's official matlab.desktop.editor API over a shared Engine session (not screen-scraping). Editor only — the Command Window scrollback is not driveable on this build. Triggers — "edit this in MATLAB", "open the file in MATLAB", "/matlab-editor".
---

# matlab-editor

Edit .m files in the user's running MATLAB desktop as real editor tabs that update in the GUI. Connect to a shared MATLAB session over the Engine API and call matlab.desktop.editor. Use this when a change should appear in the user's editor; to edit files without the GUI, use the Edit tool on disk instead.

## Invoke

Run through the skill's interpreter:

```
scripts/.venv/bin/python scripts/edit.py <command>
```

```
edit.py list                     # open tabs (path + *modified)
edit.py open   FILE              # open an existing file as a tab
edit.py new    FILE --text ...    # create FILE, open it, save
edit.py read   [FILE]            # print the live buffer (active tab if no FILE)
edit.py write  FILE --stdin      # replace FILE's whole content and save
edit.py append FILE --text ...    # append and save
edit.py goto   FILE LINE         # open FILE, move cursor to LINE
edit.py close  FILE [--nosave]    # close the tab (saves first unless --nosave)
```

--text is an inline string; --stdin reads content from stdin, for multi-line or quoted code. new/write/append open the file if needed, apply, save, and make it the active tab.

## Setup

The Engine attaches only to a shared session. If edit.py exits 3, have the user run once in the MATLAB Command Window: matlab.engine.shareEngine. It lasts that session's lifetime.

## Rules

- read a file before write; write replaces the whole file, so for a targeted change read, modify, then write the full buffer.
- read any untitled or unsaved tab before closing or overwriting it — it may hold the user's unsaved work. Untitled tabs report a Filename like untitled4, not empty.
- The Command Window scrollback cannot be driven on this build; edit files here and the user runs them. Rationale in _dev/decisions.md.
