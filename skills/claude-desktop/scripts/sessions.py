#!/usr/bin/env python3
"""List the Claude desktop sidebar sessions and their state — via AX.

Each sidebar entry is an AXButton whose label encodes both state and title, e.g.
  "未読の返答 aiwiki information architecture"   (has an unread reply)
  "アイドル Work report 6/22"                    (idle)

This is the monitoring half of background-delegation automation: hand work off
with ask.py, then poll here for which sessions have flipped to "未読の返答".

  sessions.py            # print all sessions
  sessions.py --unread   # only sessions with an unread reply
  sessions.py --json     # machine-readable
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ax  # noqa: E402

# state prefixes seen on sidebar buttons (extend if the app adds more)
STATES = {
    "未読の返答": "unread",
    "アイドル": "idle",
    "実行中": "running",
    "エラー": "error",
}
# non-session sidebar buttons to ignore
IGNORE = {"Collapse sidebar", "Search", "Chat", "Cowork", "Code",
          "新規セッション", "ルーチン", "カスタマイズ", "最近の項目"}


def list_sessions(app):
    out = []
    seen = set()
    for b in ax.walk(app, lambda el: ax.role(el) == "AXButton"):
        lab = ax.label(b).strip()
        if not lab or lab in IGNORE:
            continue
        if lab.startswith("最近の項目の") or "さらに表示" in lab:
            continue
        state, name = "unknown", lab
        for prefix, code in STATES.items():
            if lab.startswith(prefix):
                state, name = code, lab[len(prefix):].strip()
                break
        if state == "unknown":
            continue  # not a session row
        key = (state, name)
        if key in seen:
            continue
        seen.add(key)
        out.append({"state": state, "title": name})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--unread", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    app = ax.connect()
    rows = list_sessions(app)
    if a.unread:
        rows = [r for r in rows if r["state"] == "unread"]
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for r in rows:
            print(f"{r['state']:8s}  {r['title']}")
        if not rows:
            print("(none)")


if __name__ == "__main__":
    main()
