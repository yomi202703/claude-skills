#!/usr/bin/env python3
"""Ask ChatGPT in Atlas's front tab and capture the reply — via AppleScript, no CDP.

  ask.py "your prompt"             # ask in the current conversation
  ask.py --new "your prompt"       # start a fresh chat first
  ask.py --timeout 300 "..."       # max seconds to wait for the reply

Prereq: the pref `browser.allow_javascript_apple_events` must be true (see
SKILL.md "Enable JS" — one-time). ask.py launches Atlas and opens chatgpt.com
if needed.
"""
import os, sys, json, time, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from atlas_js import run_js  # noqa: E402

APP = "ChatGPT Atlas"


def js(code, timeout=30):
    return run_js(code, timeout_s=timeout)


def ensure_atlas():
    import subprocess
    if not subprocess.run(["pgrep", "-f", APP], capture_output=True).stdout.strip():
        subprocess.run(["open", "-a", APP], capture_output=True)
        time.sleep(8)


def ensure_chatgpt(new=False):
    try:
        url = run_js("location.href", timeout_s=8)
    except Exception:
        url = ""
    if new or "chatgpt.com" not in url:
        run_js('(function(){location.href="https://chatgpt.com/";return"ok"})()',
               timeout_s=10)
        time.sleep(3)


def send_prompt(prompt: str):
    p = json.dumps(prompt)
    inject = f"""(function(){{
      var ed = document.querySelector('#prompt-textarea');
      if(!ed) return "NO_EDITOR";
      ed.focus();
      document.execCommand('selectAll', false, null);
      document.execCommand('insertText', false, {p});
      return "typed";
    }})()"""
    r = js(inject)
    if r != "typed":
        raise RuntimeError("inject failed: " + r)
    time.sleep(0.4)
    send = """(function(){
      var b=document.querySelector('[data-testid="send-button"]');
      if(!b) return "NO_SEND";
      if(b.disabled) return "DISABLED";
      b.click(); return "sent";
    })()"""
    for _ in range(12):
        r = js(send)
        if r == "sent":
            return
        time.sleep(0.3)
    raise RuntimeError("send failed: " + r)


POLL = """(function(){
  var streaming = !!document.querySelector('[data-testid="stop-button"]');
  var turns = document.querySelectorAll('[data-message-author-role="assistant"]');
  var last = turns.length ? turns[turns.length-1].innerText : "";
  return JSON.stringify({streaming:streaming, n:turns.length, text:last});
})()"""


def wait_reply(max_wait: int, baseline_n: int):
    start, last, stable = time.time(), "", 0
    while time.time() - start < max_wait:
        st = json.loads(js(POLL))
        if st["n"] > baseline_n and not st["streaming"] and st["text"]:
            if st["text"] == last:
                stable += 1
                if stable >= 2:
                    return st["text"]
            else:
                stable = 0
            last = st["text"]
        time.sleep(1.2)
    return last or "(timeout: no stable reply)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt")
    ap.add_argument("--new", action="store_true")
    ap.add_argument("--timeout", type=int, default=180)
    a = ap.parse_args()
    ensure_atlas()
    ensure_chatgpt(new=a.new)
    baseline = json.loads(js(POLL))["n"]
    send_prompt(a.prompt)
    print(wait_reply(a.timeout, baseline))


if __name__ == "__main__":
    main()
