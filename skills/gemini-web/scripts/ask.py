#!/usr/bin/env python3
"""Send a prompt to gemini.google.com and capture the reply, via Chrome CDP.

Usage:
    python3 ask.py "your prompt"          # ask in the current conversation
    python3 ask.py --new "your prompt"     # start a fresh chat first
    python3 ask.py --timeout 240 "..."     # max seconds to wait for the reply

Drives a DEDICATED Chrome instance (own --user-data-dir, debug port) so it never
collides with the user's normal Chrome and the Google login persists. Launches
that instance if it is not already up. Side effects are real: this runs Gemini
on the user's signed-in Google account.

Exit codes: 0 ok | 1 not reachable | 3 not signed in (login once, see SKILL.md).
"""
import sys, os, time, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import PORT, gemini_target, any_page, port_alive, WS  # noqa: E402


def _find_chrome():
    """Resolve the Google Chrome executable for the current OS (Mac/Windows/Linux).
    The Mac path is the original default; Windows/Linux locations are added so the
    skill is portable. Returns the first that exists, else the first candidate."""
    import shutil
    if sys.platform == "darwin":
        cands = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    elif sys.platform == "win32":
        cands = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
    else:
        cands = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]
    for c in cands:
        if (os.sep in c) or (os.altsep and os.altsep in c):
            if os.path.exists(c):
                return c
        else:
            found = shutil.which(c)
            if found:
                return found
    return cands[0]


CHROME = _find_chrome()
PROFILE = os.path.expanduser("~/.gemini-chrome")
APP_URL = "https://gemini.google.com/app"

# Locale-robust send-button finder. Scope to the composer FIRST: a bare
# /送信/ match also hits sidebar conversation menus like "…送信…に関するオプション",
# so we search only inside the input-area container around the editor.
FIND_SEND = r"""
(() => {
  const ed = document.querySelector('.ql-editor');
  const area = ed ? (ed.closest('input-area-v2, [class*="input-area"], form, footer') || document) : document;
  const btns = [...area.querySelectorAll('button')].filter(b => b.offsetParent !== null);
  let b = btns.find(x => /send|送信|送出|enviar|envoyer|senden/i.test(x.getAttribute('aria-label')||''));
  if (!b) b = btns.find(x => { const i = x.querySelector('mat-icon'); return i && i.textContent.trim() === 'send'; });
  return b;
})()
"""

ASSIST = "message-content"
STOP_RE = r"/回答を停止|stop response|stop/i"
LAST_JS = ("(()=>{const n=document.querySelectorAll('%s');"
           "const l=n[n.length-1];return l?l.innerText:'';})()" % ASSIST)


def reconnect(target):
    """Open a fresh WS to the target with Runtime enabled (context may have
    changed after a reload)."""
    ws = WS(target["webSocketDebuggerUrl"])
    ws.cmd("Runtime.enable")
    return ws


def reload_recover(ws, target):
    """A streaming reply can stall client-side (empty bubble, stuck stop button)
    while the server already finished. Reloading re-reads the persisted reply.
    Returns a fresh ws once the editor + history are back."""
    try:
        ws.cmd("Page.enable"); ws.cmd("Page.reload", {"ignoreCache": False})
    except Exception:
        pass
    for _ in range(30):
        time.sleep(2)
        try:
            w = reconnect(target)
            if w.evaluate("!!document.querySelector('.ql-editor')"):
                return w
        except Exception:
            pass
    return reconnect(target)


def poll_reply(ws, target, base, timeout):
    """Poll for the NEW reply, recovering from client-side stream stalls.

    Returns the reply text. Strategy: settle only once generation has finished
    (stop-button gone) and text is stable; while still generating, never settle
    on stable text (it may be a preamble/thinking pause) — reload to re-read the
    server-side reply instead. If generation stalls with no text, reload to
    recover it; on timeout, read the last message directly as a fallback."""
    cap = """(()=>{
      const n=document.querySelectorAll('%s');
      const ready = n.length >= %d + 1;
      const last = ready ? n[n.length-1] : null;
      const gen = [...document.querySelectorAll('button')]
        .some(b=>%s.test(b.getAttribute('aria-label')||''));
      return JSON.stringify({ready, gen, text: last ? last.innerText : ''});
    })()""" % (ASSIST, base, STOP_RE)

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
            if not gen and stable >= 3:   # clean finish
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
        # stall: nothing rendered yet (or no growth) while still "generating"
        if not text and (gen or not ready):
            stalled += 1
        else:
            stalled = 0
        if stalled >= 12 and not reloaded:   # ~24s of empty generation
            ws = reload_recover(ws, target)
            reloaded = True; stalled = 0; stable = 0; last = ""
            continue
        last = text
        time.sleep(2)

    # timed out: try one reload-and-read before giving up
    if not reloaded:
        ws = reload_recover(ws, target)
    txt = ws.evaluate(LAST_JS)
    txt = txt if isinstance(txt, str) else ""
    return (txt or last).strip()


def ensure_chrome():
    """Make sure the dedicated debug Chrome is up with a Gemini tab; return target."""
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
    for _ in range(30):
        t = gemini_target()
        if t:
            return t
        p = any_page()
        if p:
            ws = WS(p["webSocketDebuggerUrl"])
            ws.cmd("Page.enable")
            ws.cmd("Page.navigate", {"url": APP_URL})
        time.sleep(1)
    return None


def main():
    args = sys.argv[1:]
    new = False; timeout = 240
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

    # wait for the page to settle and detect sign-in state. NOTE: the logged-OUT
    # landing page also renders a .ql-editor (a teaser), so editor presence alone
    # is NOT proof of sign-in — a visible "Sign in / ログイン" CTA means logged out.
    for _ in range(30):
        state = ws.evaluate("""(()=>{
          const cta=[...document.querySelectorAll('a,button')].some(e=>e.offsetParent!==null
            && /^(ログイン|sign ?in|log ?in)$/i.test((e.textContent||'').trim()));
          return {
            editor: !!document.querySelector('.ql-editor'),
            login: cta || /accounts\\.google\\.|ServiceLogin|signin/i.test(location.href)
          };
        })()""") or {}
        if state.get("login"):
            print(f"NOT_SIGNED_IN: log in to Google once in the dedicated profile "
                  f"window (CDP port {PORT}), then retry. See SKILL.md.", file=sys.stderr)
            sys.exit(3)
        if state.get("editor"):
            break
        time.sleep(1)
    else:
        print("ERROR: Gemini editor not found (page not ready or UI changed).", file=sys.stderr)
        sys.exit(1)

    if new:
        ws.evaluate("""(()=>{const b=[...document.querySelectorAll('button,a,[role=button]')]
          .find(x=>/新しいチャット|new chat|チャットを新規/i.test((x.getAttribute('aria-label')||'')+' '+x.textContent));
          if(b)b.click();})()""")
        time.sleep(1.5)

    # baseline response count so we can identify the NEW reply
    base = ws.evaluate(f"document.querySelectorAll('{ASSIST}').length") or 0
    # user-turn baseline: appears immediately on a real send (reliable, unlike the
    # assistant turn which lags behind streaming) — used to confirm the send fired.
    base_user = ws.evaluate("document.querySelectorAll('user-query').length") or 0

    def insert_and_send():
        # insert into the Quill editor via execCommand (Trusted-Types safe)
        ws.evaluate("""(()=>{const e=document.querySelector('.ql-editor');if(!e)return;
          e.focus();const s=window.getSelection(),r=document.createRange();
          r.selectNodeContents(e);s.removeAllRanges();s.addRange(r);})()""")
        ws.type_text(prompt)
        time.sleep(0.5)
        clicked = ws.evaluate(
            f"(()=>{{const b={FIND_SEND};if(!b||b.disabled)return false;b.click();return true;}})()")
        if not clicked:
            ws.evaluate("(()=>{const e=document.querySelector('.ql-editor');e&&e.focus();})()")
            ws.key("Enter", "Enter", 13)

    def send_registered():
        # confirm the send fired: a new user turn appeared, the reply grew, or
        # generation started. (Editor-empty alone is ambiguous — a failed insert
        # also leaves it empty — so it is NOT treated as proof, avoiding a
        # double-send.)
        st = ws.evaluate(f"""(()=>{{
          const userGrew=document.querySelectorAll('user-query').length >= {base_user}+1;
          const grew=document.querySelectorAll('{ASSIST}').length >= {base}+1;
          const gen=[...document.querySelectorAll('button')]
            .some(b=>{STOP_RE}.test(b.getAttribute('aria-label')||''));
          return JSON.stringify({{userGrew, grew, gen}});
        }})()""")
        try:
            d = json.loads(st) if isinstance(st, str) else {}
        except ValueError:
            d = {}
        return bool(d.get("userGrew") or d.get("grew") or d.get("gen"))

    insert_and_send()
    # verify the send actually fired (the --new + long-prompt path could silently
    # drop it); retry once before falling through to polling.
    time.sleep(2)
    if not send_registered():
        insert_and_send()

    print(poll_reply(ws, target, base, timeout))


if __name__ == "__main__":
    main()
