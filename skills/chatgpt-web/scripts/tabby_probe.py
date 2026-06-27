import cdp, json, time, sys
PORT=9223
page=[t for t in cdp.http_json("/json/list", PORT) if t.get("type")=="page" and "devtools" not in (t.get("url") or "")][0]
ws=cdp.WS(page["webSocketDebuggerUrl"])
_id=[100]
def raw_send(method,params=None):
    _id[0]+=1
    ws._send_frame(json.dumps({"id":_id[0],"method":method,"params":params or {}}))
def drain(seconds, only_console=True):
    end=time.time()+seconds; out=[]
    ws.sock.settimeout(0.3)
    while time.time()<end:
        try: raw=ws._recv_frame()
        except Exception: continue
        try: m=json.loads(raw)
        except Exception: continue
        if m.get("method")=="Runtime.consoleAPICalled":
            args=m["params"].get("args",[])
            txt=" ".join(str(a.get("value", a.get("description",""))) for a in args)
            out.append((m["params"]["type"], txt))
    ws.sock.settimeout(None); return out
raw_send("Runtime.enable")
raw_send("Page.enable")
time.sleep(0.3)
