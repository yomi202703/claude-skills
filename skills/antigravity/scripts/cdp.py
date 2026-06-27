#!/usr/bin/env python3
"""Minimal dependency-free Chrome DevTools Protocol client for Antigravity.

Antigravity (Electron) always opens a remote-debugging port; the active port is
written to DevToolsActivePort under its user-data dir. We attach over the CDP
WebSocket and drive the renderer (the chat UI) with Runtime/Input commands.
"""
import json, os, socket, base64, struct, urllib.request, glob

USER_DATA = os.path.expanduser("~/Library/Application Support/Antigravity")

def find_cdp_port():
    for c in glob.glob(os.path.join(USER_DATA, "DevToolsActivePort")):
        with open(c) as f:
            return int(f.readline().strip())
    raise RuntimeError("DevToolsActivePort not found — is Antigravity running?")

def http_json(port, path):
    return json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}{path}"))

def main_page(port=None):
    """Return (port, page_target) for the visible chat page."""
    port = port or find_cdp_port()
    pages = [t for t in http_json(port, "/json/list") if t.get("type") == "page"]
    if not pages:
        raise RuntimeError("no CDP page target found")
    return port, pages[0]

class WS:
    def __init__(self, url):
        assert url.startswith("ws://")
        hostport, path = url[5:].split("/", 1)
        self.path = "/" + path
        host, port = hostport.split(":")
        self.sock = socket.create_connection((host, int(port)))
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((
            f"GET {self.path} HTTP/1.1\r\nHost: {hostport}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        ).encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.sock.recv(1)
        self._buf = b""
        self._id = 0

    def _send_frame(self, data):
        data = data.encode()
        header = bytearray([0x81])
        ln = len(data); mask = os.urandom(4)
        if ln < 126: header.append(0x80 | ln)
        elif ln < 65536: header.append(0x80 | 126); header += struct.pack(">H", ln)
        else: header.append(0x80 | 127); header += struct.pack(">Q", ln)
        header += mask
        self.sock.sendall(bytes(header) + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _recv_frame(self):
        def rd(n):
            while len(self._buf) < n:
                self._buf += self.sock.recv(4096)
            out, self._buf = self._buf[:n], self._buf[n:]
            return out
        rd(1); b1 = rd(1)[0]
        ln = b1 & 0x7f
        if ln == 126: ln = struct.unpack(">H", rd(2))[0]
        elif ln == 127: ln = struct.unpack(">Q", rd(8))[0]
        return rd(ln).decode("utf-8", "replace")

    def cmd(self, method, params=None):
        self._id += 1
        self._send_frame(json.dumps({"id": self._id, "method": method, "params": params or {}}))
        while True:
            m = json.loads(self._recv_frame())
            if m.get("id") == self._id:
                return m

    def evaluate(self, expr, await_promise=True):
        r = self.cmd("Runtime.evaluate", {
            "expression": expr, "returnByValue": True,
            "awaitPromise": await_promise, "userGesture": True})
        res = r.get("result", {})
        if "exceptionDetails" in res:
            return {"error": str(res["exceptionDetails"])[:300]}
        return res.get("result", {}).get("value")

    def type_text(self, text):
        self.cmd("Input.insertText", {"text": text})

    def key(self, key, code, vk):
        for t in ("keyDown", "keyUp"):
            self.cmd("Input.dispatchKeyEvent",
                     {"type": t, "key": key, "code": code, "windowsVirtualKeyCode": vk})

if __name__ == "__main__":
    p, page = main_page()
    print("CDP port:", p, "| page:", page["url"][:80])
