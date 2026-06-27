#!/usr/bin/env python3
"""Send a prompt to chat.z.ai (GLM) and capture the reply, via Chrome CDP.

Usage:
    python3 ask.py "your prompt"          # ask in the current conversation
    python3 ask.py --new "your prompt"     # start a fresh chat first
    python3 ask.py --timeout 300 "..."     # max seconds to wait for the reply

Shares ONE dedicated Chrome instance with gemini-web / chatgpt-web / qwen-web
(port 9333, profile ~/.gemini-chrome): sibling AI tabs in a single signed-in
browser. Side effects are real: runs GLM on the user's signed-in z.ai account.

Exit codes: 0 ok | 1 not reachable | 3 not signed in (log in once, see SKILL.md).
"""
import sys, os, time, json, subprocess
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from cdp import PORT, glm_target, port_alive, new_tab, WS  # noqa: E402

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE = os.path.expanduser("~/.gemini-chrome")  # shared with the sibling AI skills
APP_URL = "https://chat.z.ai/"

# chat.z.ai selectors (probed against the live DOM).
EDITOR = "textarea#chat-input"
SEND = "button.sendMessageButton"   # present (even disabled) when idle; REMOVED while generating
ASSIST_TURN = "div.chat-assistant"  # one node per assistant turn
USER_TURN = "div.chat-user"         # one node per user turn
# reply body is .markdown-prose inside the turn; capacity/error bubbles have none,
# so fall back to the turn's own innerText.
LAST_JS = ("(()=>{const n=document.querySelectorAll('%s');const l=n[n.length-1];"
           "if(!l)return '';const p=l.querySelector('.markdown-prose');"
           "return p?p.innerText:l.innerText;})()" % ASSIST_TURN)


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
    only once generation has finished (the send button is back) and text is stable;
    while generation is still active, never settle on stable text (it may be a
    preamble/thinking pause) — reload to re-read the server-side reply instead.
    Also reload if generation stalls empty; on timeout, read the last message
    directly. Generation signal: the send button is REMOVED from the DOM while
    generating and returns when done."""
    cap = """(()=>{
      const turns=document.querySelectorAll('%s');
      const ready = turns.length >= %d + 1;
      const last = ready ? turns[turns.length-1] : null;
      let text='';
      if(last){const p=last.querySelector('.markdown-prose'); text = p?p.innerText:last.innerText;}
      const gen = !document.querySelector('%s');
      return JSON.stringify({ready, gen, text});
    })()""" % (ASSIST_TURN, base, SEND)

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
    """Ensure the shared debug Chrome is up with a GLM tab; return target."""
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
        t = glm_target()
        if t:
            return t
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

    # settle + detect sign-in. The logged-OUT landing also renders the textarea,
    # so editor presence is NOT proof — a visible Log in / 登录 / Get started CTA
    # means logged out.
    for _ in range(40):
        state = ws.evaluate("""(()=>{
          const login=[...document.querySelectorAll('a,button')].some(e=>e.offsetParent!==null
            && /^(log ?in|sign ?in|sign ?up|登录|登陆|登入|get started)$/i.test((e.textContent||'').trim()));
          return {editor: !!document.querySelector('%s'), login};
        })()""" % EDITOR) or {}
        if state.get("login") and not state.get("editor"):
            print("NOT_SIGNED_IN: log in to z.ai once in the dedicated Chrome window "
                  f"(CDP port {PORT}), then retry. See SKILL.md.", file=sys.stderr)
            sys.exit(3)
        if state.get("editor"):
            break
        time.sleep(1)
    else:
        print("ERROR: GLM editor not found (not signed in or UI changed).", file=sys.stderr)
        sys.exit(1)

    if new:
        ws.evaluate("""(()=>{const b=[...document.querySelectorAll('a,button')]
          .find(x=>/new chat|新对话|新建对话|新聊天/i.test((x.getAttribute('aria-label')||'')+' '+x.textContent));
          if(b)b.click();})()""")
        time.sleep(1.2)

    base = ws.evaluate(f"document.querySelectorAll('{ASSIST_TURN}').length") or 0
    base_user = ws.evaluate(f"document.querySelectorAll('{USER_TURN}').length") or 0

    def insert_and_send():
        # the editor is a real <textarea>: focus, select existing content, then
        # insert via CDP Input.insertText so the framework's onChange fires.
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
        # a new user turn, a grown reply, or active generation (send button gone)
        # proves the send fired. Editor-empty alone is ambiguous, so it is not used.
        st = ws.evaluate(f"""(()=>{{
          const userGrew=document.querySelectorAll('{USER_TURN}').length >= {base_user}+1;
          const grew=document.querySelectorAll('{ASSIST_TURN}').length >= {base}+1;
          const gen=!document.querySelector('{SEND}');
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
