#!/usr/bin/env python3
"""Send a prompt to chat.qwen.ai and capture the reply, via Chrome CDP.

Usage:
    python3 ask.py "your prompt"          # ask in the current conversation
    python3 ask.py --new "your prompt"     # start a fresh chat first
    python3 ask.py --timeout 300 "..."     # max seconds to wait for the reply

Shares ONE dedicated Chrome instance with gemini-web / chatgpt-web (port 9333,
profile ~/.gemini-chrome): sibling AI tabs in a single signed-in browser, no API
cost. Side effects are real: runs Qwen on the user's signed-in account.

Exit codes: 0 ok | 1 not reachable | 3 not signed in (log in once, see SKILL.md).
"""
import sys, os, time, json, subprocess
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from cdp import PORT, qwen_target, port_alive, new_tab, WS  # noqa: E402

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE = os.path.expanduser("~/.gemini-chrome")  # shared with gemini-web / chatgpt-web
APP_URL = "https://chat.qwen.ai/"

# chat.qwen.ai selectors (probed against the live DOM).
EDITOR = "textarea.message-input-textarea"
SEND = "button.send-button"      # present+enabled once the textarea has text
STOP = "button.stop-button"      # the send button becomes this while generating
ASSIST_TURN = ".qwen-chat-message-assistant"             # one node per assistant turn
USER_TURN = ".qwen-chat-message-user"                    # one node per user turn
ASSIST_TEXT = ".qwen-chat-message-assistant .response-message-content"  # reply body
LAST_JS = ("(()=>{const n=document.querySelectorAll('%s');"
           "const l=n[n.length-1];return l?l.innerText:'';})()" % ASSIST_TEXT)


def reconnect(target):
    """Fresh WS to the target with Runtime enabled (context changes after reload)."""
    ws = WS(target["webSocketDebuggerUrl"])
    ws.cmd("Runtime.enable")
    return ws


def reload_recover(ws, target):
    """A streaming reply can stall client-side while the server already finished.
    Reload re-reads the persisted reply; return a fresh ws once the editor is back."""
    try:
        ws.cmd("Page.enable"); ws.cmd("Page.reload", {"ignoreCache": False})
    except Exception:
        pass
    for _ in range(30):
        time.sleep(2)
        try:
            w = reconnect(target)
            if w.evaluate(f"!!document.querySelector('{EDITOR}')"):
                return w
        except Exception:
            pass
    return reconnect(target)


def poll_reply(ws, target, base, timeout):
    """Poll for the NEW reply, recovering from client-side stream stalls. Settle
    only once generation has finished (stop-button gone) and text is stable; while
    generation is still active, never settle on stable text (it may be a
    preamble/thinking pause) — reload to re-read the server-side reply instead.
    Also reload if generation stalls empty; on timeout, read the last message
    directly."""
    cap = """(()=>{
      const n=document.querySelectorAll('%s');
      const ready = n.length >= %d + 1;
      const t=document.querySelectorAll('%s');
      const last = ready ? t[t.length-1] : null;
      const gen = !!document.querySelector('%s');
      return JSON.stringify({ready, gen, text: last ? last.innerText : ''});
    })()""" % (ASSIST_TURN, base, ASSIST_TEXT, STOP)

    last = ""; stable = 0; stalled = 0; reloaded = False
    deadline = time.time() + timeout
    while time.time() < deadline:
        raw = ws.evaluate(cap)
        try:
            st = json.loads(raw) if isinstance(raw, str) else {}
        except ValueError:
            st = {}
        text = st.get("text", ""); gen = st.get("gen"); ready = st.get("ready")
        if text and text == last:
            stable += 1
            if not gen and stable >= 3:
                return text.strip()
            # gen still active + long-stable text = a reasoning/preamble pause
            # mid-generation OR a stuck stop-button. Settling here returns the
            # preamble and loses the real answer, so do NOT settle: reload once to
            # clear a stuck button / re-read the server-side reply, then resume.
            if gen and stable >= 20:
                ws = reload_recover(ws, target)
                stable = 0; last = ""
                continue
        else:
            stable = 0
        if not text and (gen or not ready):
            stalled += 1
        else:
            stalled = 0
        if stalled >= 12 and not reloaded:
            ws = reload_recover(ws, target)
            reloaded = True; stalled = 0; stable = 0; last = ""
            continue
        last = text
        time.sleep(2)

    if not reloaded:
        ws = reload_recover(ws, target)
    txt = ws.evaluate(LAST_JS)
    txt = txt if isinstance(txt, str) else ""
    return (txt or last).strip()


def ensure_chrome():
    """Ensure the shared debug Chrome is up with a Qwen tab; return target."""
    if not port_alive():
        os.makedirs(PROFILE, exist_ok=True)
        subprocess.Popen(
            [CHROME, f"--remote-debugging-port={PORT}", f"--user-data-dir={PROFILE}",
             "--no-first-run", "--no-default-browser-check", APP_URL],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(40):
            time.sleep(1)
            if port_alive():
                break
        else:
            return None
    opened = False
    for _ in range(30):
        t = qwen_target()
        if t:
            return t
        # instance is up (maybe only a sibling AI tab): open a qwen tab once
        if not opened:
            try:
                new_tab(APP_URL)
                opened = True
            except Exception:
                pass
        time.sleep(1)
    return None


def main():
    args = sys.argv[1:]
    new = False; timeout = 300
    while args and args[0].startswith("--"):
        if args[0] == "--new": new = True; args.pop(0)
        elif args[0] == "--timeout": args.pop(0); timeout = int(args.pop(0))
        else: break
    if not args:
        print('usage: ask.py [--new] [--timeout N] "prompt"', file=sys.stderr); sys.exit(2)
    prompt = args[0]

    target = ensure_chrome()
    if not target:
        print(f"ERROR: dedicated Chrome not reachable on CDP port {PORT}", file=sys.stderr)
        sys.exit(1)

    ws = WS(target["webSocketDebuggerUrl"])
    ws.cmd("Runtime.enable")

    # settle + detect sign-in. The logged-OUT landing page also renders the
    # textarea, so editor presence is NOT proof — a visible "Log in / Sign up"
    # (登录) CTA means logged out.
    for _ in range(40):
        state = ws.evaluate("""(()=>{
          const login=[...document.querySelectorAll('a,button')].some(e=>e.offsetParent!==null
            && /^(log ?in|sign ?up|登录|登陆|登入)$/i.test((e.textContent||'').trim()));
          return {editor: !!document.querySelector('%s'), login};
        })()""" % EDITOR) or {}
        if state.get("login"):
            print("NOT_SIGNED_IN: log in to Qwen once in the dedicated Chrome window "
                  f"(CDP port {PORT}), then retry. See SKILL.md.", file=sys.stderr)
            sys.exit(3)
        if state.get("editor"):
            break
        time.sleep(1)
    else:
        print("ERROR: Qwen editor not found (not signed in or UI changed).", file=sys.stderr)
        sys.exit(1)

    if new:
        ws.evaluate("""(()=>{const b=[...document.querySelectorAll('a,button')]
          .find(x=>/new chat|新对话|新建对话|新聊天|新しいチャット/i.test((x.getAttribute('aria-label')||'')+' '+x.textContent));
          if(b)b.click();})()""")
        time.sleep(1.2)

    base = ws.evaluate(f"document.querySelectorAll('{ASSIST_TURN}').length") or 0
    # user-turn baseline: appears immediately on a real send (reliable, unlike the
    # assistant turn which lags streaming) — used to confirm the send fired.
    base_user = ws.evaluate(f"document.querySelectorAll('{USER_TURN}').length") or 0

    def insert_and_send():
        # the editor is a real <textarea>: focus, select existing content, then
        # insert via CDP Input.insertText so React's onChange fires (enables send).
        ws.evaluate(f"""(()=>{{const e=document.querySelector('{EDITOR}');if(!e)return;
          e.focus();e.select&&e.select();}})()""")
        ws.type_text(prompt)
        time.sleep(0.5)
        clicked = ws.evaluate(
            f"(()=>{{const b=document.querySelector('{SEND}');if(!b||b.disabled)return false;b.click();return true;}})()")
        if not clicked:
            ws.evaluate(f"(()=>{{const e=document.querySelector('{EDITOR}');e&&e.focus();}})()")
            ws.key("Enter", "Enter", 13)

    def send_registered():
        # a new user turn, a grown reply, or active generation proves the send
        # fired. Editor-empty alone is ambiguous (a failed insert also empties it),
        # so it is not used — avoiding a double-send.
        st = ws.evaluate(f"""(()=>{{
          const userGrew=document.querySelectorAll('{USER_TURN}').length >= {base_user}+1;
          const grew=document.querySelectorAll('{ASSIST_TURN}').length >= {base}+1;
          const gen=!!document.querySelector('{STOP}');
          return JSON.stringify({{userGrew, grew, gen}});
        }})()""")
        try:
            d = json.loads(st) if isinstance(st, str) else {}
        except ValueError:
            d = {}
        return bool(d.get("userGrew") or d.get("grew") or d.get("gen"))

    insert_and_send()
    time.sleep(2)
    if not send_registered():
        insert_and_send()

    print(poll_reply(ws, target, base, timeout))


if __name__ == "__main__":
    main()
