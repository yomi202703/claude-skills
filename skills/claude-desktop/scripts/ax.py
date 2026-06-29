#!/usr/bin/env python3
"""macOS Accessibility (AX) primitives for driving the Claude desktop app.

The Claude desktop app is Electron but ships hardened against automation:
- CDP is blocked (the app refuses to launch with --remote-debugging-port/-pipe),
- it has no AppleScript scripting dictionary (so an `execute javascript`
  trick is unavailable).

The one door left open is the macOS Accessibility API. Chromium does NOT build a
web a11y tree until an assistive client asks for it; the correct way to ask from
outside is to set `AXManualAccessibility=true` on the application's AXUIElement
via the real AX API (NOT System Events, which silently no-ops). Once set, the
renderer's full tree — composer AXTextArea, send AXButton, message AXStaticText,
the folder/branch/model pickers, and the sidebar session list with per-session
state — becomes reachable. No asar/fuse changes required.

This module self-bootstraps a private venv with pyobjc on first run.
"""
import os, sys, subprocess, time

# ---------------------------------------------------------------------------
# Bootstrap: ensure pyobjc is importable, else build a private venv & re-exec.
# ---------------------------------------------------------------------------
def _ensure_deps():
    try:
        import ApplicationServices, Quartz, AppKit  # noqa: F401
        return
    except ImportError:
        pass
    here = os.path.dirname(os.path.abspath(__file__))
    venv = os.path.join(here, ".venv")
    vpy = os.path.join(venv, "bin", "python3")
    if not os.path.exists(vpy):
        sys.stderr.write("[claude-desktop] first run: building venv + installing pyobjc...\n")
        subprocess.run([sys.executable, "-m", "venv", venv], check=True)
        subprocess.run([vpy, "-m", "pip", "install", "-q", "--upgrade", "pip"], check=True)
        subprocess.run([vpy, "-m", "pip", "install", "-q",
                        "pyobjc-framework-Cocoa",
                        "pyobjc-framework-ApplicationServices",
                        "pyobjc-framework-Quartz"], check=True)
    os.execv(vpy, [vpy] + sys.argv)

_ensure_deps()

from AppKit import NSWorkspace, NSPasteboard, NSPasteboardTypeString  # noqa: E402
from ApplicationServices import (  # noqa: E402
    AXIsProcessTrusted, AXUIElementCreateApplication,
    AXUIElementSetAttributeValue, AXUIElementCopyAttributeValue,
    AXUIElementIsAttributeSettable, AXUIElementPerformAction,
    kAXChildrenAttribute, kAXRoleAttribute, kAXWindowsAttribute,
    kAXTitleAttribute, kAXDescriptionAttribute, kAXValueAttribute,
    kAXEnabledAttribute, kAXFocusedAttribute, kAXPressAction,
)
from Quartz import (  # noqa: E402
    CGEventCreateKeyboardEvent, CGEventPost, CGEventSetFlags,
    kCGHIDEventTap, kCGEventFlagMaskCommand,
)

APP_NAME = "claude"


# --- process / element access -------------------------------------------------
def app_pid():
    for a in NSWorkspace.sharedWorkspace().runningApplications():
        if (a.localizedName() or "").lower() == APP_NAME:
            return a.processIdentifier()
    return None


def ensure_running():
    pid = app_pid()
    if pid is None:
        subprocess.run(["open", "-a", "Claude"], check=False)
        for _ in range(20):
            time.sleep(0.5)
            pid = app_pid()
            if pid:
                break
    return pid


def connect():
    """Return an app AXUIElement with the Chromium web a11y tree forced on."""
    if not AXIsProcessTrusted():
        sys.stderr.write(
            "[claude-desktop] This process lacks Accessibility permission.\n"
            "Grant it: System Settings > Privacy & Security > Accessibility,\n"
            "add your terminal (Terminal/iTerm/Ghostty/etc.), then retry.\n")
        sys.exit(3)
    pid = ensure_running()
    if pid is None:
        sys.exit("[claude-desktop] Claude app not running and could not be launched")
    app = AXUIElementCreateApplication(pid)
    AXUIElementSetAttributeValue(app, "AXManualAccessibility", True)
    time.sleep(0.8)
    return app


def get(el, attr):
    try:
        err, val = AXUIElementCopyAttributeValue(el, attr, None)
        return val if err == 0 else None
    except Exception:
        return None


def setv(el, attr, v):
    return AXUIElementSetAttributeValue(el, attr, v)


def settable(el, attr):
    try:
        err, val = AXUIElementIsAttributeSettable(el, attr, None)
        return bool(val) if err == 0 else False
    except Exception:
        return False


def press(el):
    return AXUIElementPerformAction(el, kAXPressAction)


def as_list(x):
    try:
        return list(x) if x is not None else []
    except TypeError:
        return []


def role(el):
    return str(get(el, kAXRoleAttribute) or "")


def title(el):
    return str(get(el, kAXTitleAttribute) or "")


def desc(el):
    return str(get(el, kAXDescriptionAttribute) or "")


def value(el):
    v = get(el, kAXValueAttribute)
    return v


def label(el):
    return " ".join(p for p in (title(el), desc(el)) if p).strip()


# --- tree traversal -----------------------------------------------------------
def walk(app, pred, max_depth=45, max_nodes=25000):
    out = []
    n = [0]
    def rec(el, d):
        if d > max_depth or n[0] > max_nodes:
            return
        n[0] += 1
        try:
            if pred(el):
                out.append(el)
        except Exception:
            pass
        for c in as_list(get(el, kAXChildrenAttribute)):
            rec(c, d + 1)
    for w in as_list(get(app, kAXWindowsAttribute)):
        rec(w, 0)
    return out


def first(app, pred):
    r = walk(app, pred)
    return r[0] if r else None


def buttons_with(app, *needles):
    nd = [s.lower() for s in needles]
    return walk(app, lambda el: role(el) == "AXButton"
                and any(s in label(el).lower() for s in nd))


def static_texts(app):
    out = []
    for el in walk(app, lambda el: role(el) == "AXStaticText"):
        v = value(el)
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
    return out


# --- keyboard (for paste fallback & menu escape) ------------------------------
def _key(keycode, cmd=False):
    for down in (True, False):
        e = CGEventCreateKeyboardEvent(None, keycode, down)
        if cmd:
            CGEventSetFlags(e, kCGEventFlagMaskCommand)
        CGEventPost(kCGHIDEventTap, e)
        time.sleep(0.01)


def key_escape():
    _key(53)


def key_return():
    _key(36)


def key_cmd_a():
    _key(0, cmd=True)


def paste(text):
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_(text, NSPasteboardTypeString)
    time.sleep(0.1)
    _key(9, cmd=True)  # Cmd+V
