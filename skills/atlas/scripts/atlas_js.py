#!/usr/bin/env python3
"""Run JavaScript in ChatGPT Atlas's front tab via AppleScript (no CDP).

Atlas ships Chrome's AppleScript dictionary, so `execute ... javascript` works
once the pref `browser.allow_javascript_apple_events` is true (set it with
enable_js.py — the menu item that normally toggles it is removed from Atlas's UI).

  atlas_js.py <file.js>       # run JS from a file
  echo '...' | atlas_js.py -  # run JS from stdin

Prints the JS return value (coerce to a string/number in the JS) to stdout.
"""
import sys, subprocess

APP = "ChatGPT Atlas"


def as_str_literal(s: str) -> str:
    # AppleScript double-quoted literal: escape \ and ", encode newlines/tabs.
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    s = s.replace("\n", "\\n").replace("\r", "").replace("\t", "\\t")
    return '"' + s + '"'


def run_js(js: str, timeout_s: int = 30) -> str:
    """Execute `js` in Atlas's front tab; return stdout. Raises on AppleScript error."""
    lit = as_str_literal(js)
    script = (
        f"with timeout of {timeout_s} seconds\n"
        f"  tell application \"{APP}\" to execute front window's active tab javascript {lit}\n"
        f"end timeout"
    )
    p = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=timeout_s + 5,
    )
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or f"osascript exit {p.returncode}")
    return p.stdout.rstrip("\n")


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "-"
    js = sys.stdin.read() if src == "-" else open(src).read()
    try:
        print(run_js(js))
    except Exception as e:
        sys.stderr.write(str(e) + "\n")
        sys.exit(1)
