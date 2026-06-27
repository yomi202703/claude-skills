#!/usr/bin/env python3
"""Hand a task to the Claude desktop app and capture the reply — via AX, no CDP.

  ask.py "prompt"                       # new session, send prompt, print reply
  ask.py --folder recall "prompt"       # new session bound to a folder, then send
  ask.py --here "prompt"                # send into the CURRENT session (no new one)
  ask.py --timeout 600 "long job"

Folder selection only works on a fresh (pre-conversation) session, mirroring the
app: --folder is honored only when a new session is created (the default).

Completion + reply come from the app's own accessibility announcements
("…応答を完了しました" / "Claudeが返答しました: …") plus a stability check on the
conversation text, which is sturdier than a pure DOM-stability heuristic.
For long/important output prefer file handoff: ask Claude to WRITE its answer to
a file in the bound folder, then read that file.
"""
import sys, os, time, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ax  # noqa: E402

DONE_MARK = "応答を完了しました"
REPLY_MARK = "Claudeが返答しました"
# live-region / placeholder chrome to drop from the captured reply
CHROME_PREFIXES = ("あなたの入力:", REPLY_MARK, "Claudeが応答", "Claudeが返答")
CHROME_EXACT = {"チャットモード", "コマンドは / を入力", "長押しして録音",
                "チャット", "Cowork", "Code", "送信"}


def new_session(app):
    b = ax.first(app, lambda el: ax.role(el) == "AXButton"
                 and "新規セッション" in ax.title(el))
    if b:
        ax.press(b)
        time.sleep(1.5)
        return True
    return False


def select_folder(app, name):
    """In a fresh session, open the folder popup and pick `name` (or open-folder).

    The folder popup is identified structurally: it is the AXPopUpButton whose
    menu contains a 'フォルダを開く…' item / '最近' header. We try popups and
    Escape out of the wrong ones.
    """
    popups = ax.walk(app, lambda el: ax.role(el) == "AXPopUpButton")
    for p in popups:
        # skip obvious non-folder popups by current label
        lab = ax.label(p)
        if any(k in lab for k in ("オプション", "ナビゲーション", "Filter", "Usage",
                                  "工数", "Opus", "Sonnet", "Haiku", "音声")):
            continue
        ax.press(p)
        time.sleep(0.7)
        items = ax.walk(app, lambda el: ax.role(el) == "AXMenuItem")
        item_titles = [ax.title(i) for i in items]
        is_folder_menu = any("フォルダを開く" in t or t == "ai-wiki" for t in item_titles) \
            or any("フォルダを開く" in t for t in item_titles)
        if not is_folder_menu:
            ax.key_escape()
            time.sleep(0.3)
            continue
        # this is the folder popup
        target = None
        for i in items:
            if ax.title(i) == name:
                target = i
                break
        if target is None:
            ax.key_escape()
            raise SystemExit(
                f"[claude-desktop] folder '{name}' not in the recent list: "
                f"{[t for t in item_titles if t and 'フォルダを開く' not in t]}")
        ax.press(target)
        time.sleep(0.8)
        # a first-time folder shows a "trust this workspace" gate; the user asked
        # for this folder explicitly via --folder, so clear it.
        trust = ax.buttons_with(app, "ワークスペースを信頼", "trust")
        if trust:
            ax.press(trust[0])
            time.sleep(1.0)
        return True
    raise SystemExit("[claude-desktop] could not locate the folder popup")


def find_composer(app):
    return ax.first(app, lambda el: ax.role(el) == "AXTextArea")


def find_send(app):
    b = ax.buttons_with(app, "送信", "send")
    return b[0] if b else None


def enter_prompt(app, prompt):
    ta = find_composer(app)
    if not ta:
        sys.exit("[claude-desktop] composer (AXTextArea) not found")
    ax.setv(ta, "AXFocused", True)
    time.sleep(0.2)
    ax.setv(ta, ax_value_attr(), prompt)
    time.sleep(0.4)
    send = find_send(app)
    if send and ax.get(send, "AXEnabled"):
        return ta, send
    # fallback: focus + paste fires the web input's change handler
    ax.setv(ta, "AXFocused", True)
    time.sleep(0.2)
    ax.key_cmd_a()
    ax.paste(prompt)
    time.sleep(0.5)
    send = find_send(app)
    return ta, send


def ax_value_attr():
    from ApplicationServices import kAXValueAttribute
    return kAXValueAttribute


def send_prompt(app, prompt):
    ta, send = enter_prompt(app, prompt)
    if send and ax.get(send, "AXEnabled"):
        ax.press(send)
    else:
        ax.key_return()


def clean_reply(lines, prompt):
    out = []
    for s in lines:
        if s == prompt:
            continue
        if s in CHROME_EXACT:
            continue
        if any(s.startswith(p) for p in CHROME_PREFIXES):
            continue
        out.append(s)
    # de-dupe consecutive
    ded = []
    for s in out:
        if not ded or ded[-1] != s:
            ded.append(s)
    return "\n".join(ded)


def wait_reply(app, baseline, prompt, timeout):
    start = time.time()
    last, stable = "", 0
    saw_done = False
    while time.time() - start < timeout:
        texts = ax.static_texts(app)
        if any(DONE_MARK in t for t in texts):
            saw_done = True
        # explicit announcement of the reply, if short
        announced = next((t.split(":", 1)[1].strip()
                          for t in texts if t.startswith(REPLY_MARK) and ":" in t), "")
        fresh = [t for t in texts if t not in baseline]
        body = clean_reply(fresh, prompt)
        cur = body or announced
        if cur and cur == last and (saw_done or stable >= 1):
            stable += 1
            if stable >= 3:
                return cur
        else:
            stable = 0 if cur != last else stable
        last = cur
        time.sleep(1.0)
    return last or "(timeout: no stable reply captured)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt")
    ap.add_argument("--folder", help="bind a fresh session to this recent folder")
    ap.add_argument("--here", action="store_true",
                    help="send into the current session instead of a new one")
    ap.add_argument("--timeout", type=int, default=300)
    a = ap.parse_args()

    app = ax.connect()
    if not a.here:
        new_session(app)
        if a.folder:
            select_folder(app, a.folder)
    elif a.folder:
        sys.exit("[claude-desktop] --folder requires a new session (omit --here)")

    baseline = set(ax.static_texts(app))
    send_prompt(app, a.prompt)
    print(wait_reply(app, baseline, a.prompt, a.timeout))


if __name__ == "__main__":
    main()
