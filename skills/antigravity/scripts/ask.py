#!/usr/bin/env python3
"""Send a prompt to Antigravity's agent and capture the reply, via CDP.

Usage:
    python3 ask.py "your prompt"            # open a NEW conversation, then ask
    python3 ask.py --here "your prompt"     # ask in the CURRENTLY open conversation
    python3 ask.py --timeout 180 "..."      # max seconds to wait for the reply

Prints the captured assistant text to stdout. Side effects are real: this runs
the actual Antigravity agent on the user's account. Requires Antigravity to be
running (launch with: open -a Antigravity).
"""
import sys, time, json, subprocess
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from cdp import find_cdp_port, main_page, WS  # noqa: E402

SEL = 'div[contenteditable="true"][role="combobox"]'

def ensure_running():
    try:
        find_cdp_port(); return True
    except Exception:
        subprocess.run(["open", "-a", "Antigravity"], check=False)
        for _ in range(30):
            time.sleep(1)
            try:
                find_cdp_port(); return True
            except Exception:
                pass
    return False

def main():
    args = sys.argv[1:]
    here = False; timeout = 180
    while args and args[0].startswith("--"):
        if args[0] == "--here": here = True; args.pop(0)
        elif args[0] == "--timeout": args.pop(0); timeout = int(args.pop(0))
        else: break
    if not args:
        print("usage: ask.py [--here] [--timeout N] \"prompt\"", file=sys.stderr); sys.exit(2)
    prompt = args[0]
    sentinel = "AGQ" + str(abs(hash(prompt)) % 10000)
    tagged = f"{prompt}\n[[{sentinel}]]"

    if not ensure_running():
        print("ERROR: Antigravity not reachable via CDP", file=sys.stderr); sys.exit(1)

    _, page = main_page()
    ws = WS(page["webSocketDebuggerUrl"]); ws.cmd("Runtime.enable")

    if not here:
        ws.evaluate("""(()=>{const b=[...document.querySelectorAll('button,[role="button"]')]
          .find(x=>(x.getAttribute('aria-label')||'').trim()==='New Conversation'&&x.offsetParent!==null);
          if(b)b.click();})()""")
        time.sleep(1.5)

    ws.evaluate(f'(()=>{{const e=document.querySelector({json.dumps(SEL)});e&&e.focus();}})()')
    ws.type_text(tagged)
    ws.key("Enter", "Enter", 13)

    # poll: find the scroll container holding our sentinel, read until stable
    cap = """(()=>{
      const ns=[...document.querySelectorAll('*')].filter(n=>n.childElementCount<3&&(n.textContent||'').includes('%s'));
      if(!ns.length) return null;
      let el=ns[ns.length-1];
      for(let i=0;i<14&&el.parentElement;i++){const s=getComputedStyle(el);if(/(auto|scroll)/.test(s.overflowY))break;el=el.parentElement;}
      return el.innerText;
    })()""" % sentinel

    last = ""; stable = 0; deadline = time.time() + timeout
    while time.time() < deadline:
        cur = ws.evaluate(cap) or ""
        if cur != last: last = cur; stable = 0
        else: stable += 1
        if stable >= 4 and len(cur) > len(tagged) + 8:
            break
        time.sleep(2)

    # strip the echoed prompt block, return assistant remainder
    out = last
    idx = out.find(f"[[{sentinel}]]")
    if idx != -1:
        out = out[idx + len(sentinel) + 4:]
    print(out.strip())

if __name__ == "__main__":
    main()
