#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Single shared review server — diagnostic / GT-creation / evaluation modes.

Domain-agnostic template (S1, config-driven). The judgment vocabulary, axes,
and unit are read from contract.json (S2), never hard-coded here. Code is a
template: adapt data.py for your domain; this file should not need changes.

Gates wired structurally:
  S3  GT-creation path (render_review) NEVER calls adapter.judges() — a
      reviewer cannot see any machine output until commit. The firewall is the
      RENDERING, not a login: mode is chosen by route (/diag vs /review), no
      auth by default. Authentication / reviewer attribution is a later concern
      (grill hook), added only when untrusted external blind reviewers arrive.
  S4  commit stores the blind verdict, THEN reveals judges + divergence.
  S8  every GET is read-only; only POST /commit and POST /ingest write.
  S9  one ingestion path (POST /ingest, inbox CSV).
  S10 provenance footer (live vs snapshot) on every page; --package excludes
      the answer DB / inbox / caches.

  python3 server.py                 # http://localhost:8030/
  python3 server.py --snapshot      # freeze a snapshot provenance marker
  python3 server.py --package        # build a distributable zip and exit

Standard library only.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import os
import sys
import urllib.parse
import zipfile
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

from data import DemoAdapter, divergence
from store import GateViolation, Store

HERE = os.path.dirname(os.path.abspath(__file__))
CONTRACT = json.load(open(os.path.join(HERE, "contract.example.json"), encoding="utf-8"))
ADAPTER = DemoAdapter()
DB_PATH = os.environ.get("REVIEW_DB", os.path.join(HERE, "gt.db"))
STORE = Store(DB_PATH)
# Runtime state lives WITH the instance (next to the DB), not in the skill —
# auto-written by the server, gitignored, never hand-edited. A leftover runfile
# means the last process crashed (atexit didn't fire) → doctor can flag it.
RUNFILE = os.path.join(os.path.dirname(os.path.abspath(DB_PATH)), ".review-run.json")
SOURCE = "live"  # flipped to "snapshot" by --snapshot marker (S10)
# No auth by default: mode is chosen by route (/diag vs /review). Reviewer
# attribution defaults to a constant; named/authenticated reviewers are a later
# grill hook (review-server CHOICES: auth strength), wired only when external
# blind reviewers are onboarded — not pre-built.
REVIEWER = "anon"

# UI chrome strings (operator-facing). The judgment VOCABULARY/axes are the
# domain's own words and come from the contract (S2). These are the fixed labels
# of the surface itself — collected in ONE place so a host translates the chrome
# without touching logic, and so gate codes (S3/S4 …) stay in code comments and
# never leak onto a reviewer's screen. Default Japanese for this template.
UI = {
    "title": "レビューサーバー",
    "pick_mode": "下記を選択してください",
    "mode_gt": "GT作成（ブラインド）",
    "mode_dev": "開発者診断",
    "nav_aggregate": "集計",
    "nav_eval": "評価",
    "foot_source": "データ源",
    "foot_contract": "契約",
    "src_live": "ライブ（最新）",
    "src_snapshot": "スナップショット（凍結）",
    "who_dev": "開発者",
    "who_gt": "GT作成",
    "gt_index": "GT作成 — ユニット一覧",
    "gt_reason": "理由",
    "gt_evidence": "根拠（本文の行をクリックで選択）",
    "gt_ev_selected": "選択した根拠",
    "gt_commit": "確定して開示",
    "gt_committed": "を確定しました",
    "gt_stored": "あなたのブラインド判定を保存しました。以下が開示された機械の判定です。",
    "gt_next": "次へ",
    "role_proposer": "提案器(Claude)",
    "role_production": "本番判定器(Gemma)",
    "dev_header": "開発者診断 — すべての判定器が見えます",
    "dev_keyhint": "j / k または ↑↓ で移動",
    "dev_select": "ユニットを選んでください",
    "dev_problems": "食い違いキュー（提案器 ⇔ 本番判定器）",
    "dev_judges": "判定器",
    "dev_divergence": "食い違い → キューへ",
    "dev_diverges": "食い違い",
    "dev_none": "なし",
    "dev_search": "ユニットを絞り込み…",
    "dev_only_div": "食い違いのみ",
    "dev_count": "件",
    "nav_gt_manage": "GT管理",
    "gt_manage_title": "GT管理 — blind を gold に昇格",
    "gt_empty": "まだ確定したGTがありません（GT作成で確定すると blind/silver で貯まります）",
    "gt_promote": "gold化",
    "gt_promoted": "件を gold に昇格しました",
    "col_unit": "ユニット",
    "col_axis": "軸",
    "col_verdict": "判定",
    "col_prov": "由来",
    "col_tier": "成熟度",
    "col_act": "操作",
    "prov_blind": "独立(blind)",
    "prov_anchored": "参照(anchored)",
    "prov_synthetic": "合成",
    "tier_counts": "成熟度別",
    "agg_title": "食い違いキュー",
    "eval_title": "評価（測定であって目標ではありません）",
    "eval_gold": "gold 件数",
    "eval_agree": "判定器の一致",
    "eval_miss": "不一致",
    "eval_stale": "陳腐化した gold（基準バージョン遅れ）",
    "eval_holdout": "holdout アクセス履歴",
    "eval_no_holdout": "holdout アクセスなし",
    "rows": "件",
    "not_found": "見つかりません",
}


def _src_label() -> str:
    return UI["src_snapshot"] if SOURCE == "snapshot" else UI["src_live"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _versions() -> dict:
    return dict(CONTRACT["version"])


# --- rendering ---------------------------------------------------------------
# Shared visual design tokens + element styles. stdlib only — no external fonts
# or CDN, so an offline / packaged handover (S10) renders identically. Both the
# page() chrome and the diagnostic SPA pull from this one sheet.
BASE_CSS = """
:root{--bg:#f6f7f9;--surface:#fff;--ink:#1b2026;--muted:#6b7280;--line:#e7e9ee;
--accent:#3b5bdb;--accent-weak:#eef2ff;--flag:#d2392b;--flag-weak:#fdf3f2;--mark:#ffe9a8;--radius:10px}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","Hiragino Kaku Gothic ProN","Noto Sans JP",Meiryo,system-ui,sans-serif}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.bar{display:flex;align-items:center;gap:1.2em;padding:.7em 1.3em;background:var(--ink);color:#fff;font-size:14px}
.bar a{color:#aec3ff}
.bar .brand{font-weight:700;color:#fff;font-size:15px}
.bar .keyhint{margin-left:auto;color:#8a93a3;font-size:12px}
.wrap{max-width:840px;margin:1.7em auto;padding:0 1.3em}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);
padding:1em 1.15em;margin:.85em 0;box-shadow:0 1px 2px rgba(20,30,50,.04)}
h2{font-size:21px;margin:.1em 0 .5em}
h3{font-size:16px;margin:.1em 0 .7em}
h4{font-size:13px;margin:0 0 .5em;color:var(--muted);font-weight:600}
pre{white-space:pre-wrap;font:13.5px/1.75 ui-monospace,SFMono-Regular,Menlo,monospace;
background:#fbfbfd;border:1px solid var(--line);border-radius:8px;padding:.8em .9em;margin:0}
mark{background:var(--mark);padding:0 .15em;border-radius:3px}
button{font:inherit;font-weight:600;color:#fff;background:var(--accent);border:0;border-radius:8px;padding:.6em 1.3em;cursor:pointer}
button:hover{background:#314bc0}
input[type=text],input:not([type]){font:inherit;width:100%;border:1px solid var(--line);border-radius:7px;padding:.5em .65em;background:var(--surface)}
input:focus{outline:2px solid var(--accent-weak);border-color:var(--accent)}
.modes{list-style:none;padding:0;margin:1.1em 0;display:grid;gap:.75em}
.modes a{display:block;background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);
padding:1em 1.15em;font-weight:600;font-size:16px;color:var(--ink);box-shadow:0 1px 2px rgba(20,30,50,.04)}
.modes a:hover{border-color:var(--accent);text-decoration:none;box-shadow:0 3px 12px rgba(59,91,219,.12)}
.radio-row{display:flex;flex-wrap:wrap;gap:.5em;align-items:center}
.radio-row label{border:1px solid var(--line);border-radius:999px;padding:.3em .85em;font-size:14px;cursor:pointer}
.radio-row input{margin-right:.35em}
.j{border:1px solid var(--line);border-radius:8px;padding:.5em .7em;margin:.4em 0;font-size:14px}
.j.diverge{border-color:var(--flag);background:var(--flag-weak)}
.j .role{color:var(--muted);font-weight:600}
.qlist{list-style:none;padding:0;margin:.3em 0}
.qlist li{padding:.4em .2em;border-bottom:1px solid var(--line);font-size:14px}
.foot{color:var(--muted);font-size:12px;padding:.6em 1.3em;border-top:1px solid var(--line);margin-top:1em}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;padding:.5em .6em;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600;font-size:12px}
.pill{display:inline-block;border-radius:999px;padding:.1em .6em;font-size:12px;font-weight:600}
.pill.gold{background:#fef3c7;color:#92600a}
.pill.silver{background:#eef1f5;color:#52617a}
.pill.blind{background:var(--accent-weak);color:var(--accent)}
.counts{display:flex;gap:.5em;flex-wrap:wrap;margin:.2em 0 .6em}
form.inline{display:inline;margin:0}
form.inline button{padding:.3em .8em;font-size:13px;background:#92600a}
form.inline button:hover{background:#7a4f08}
"""


def page(body: str, *, who: str = "") -> bytes:
    bar = (
        f'<div class=bar><a class=brand href="/">{UI["title"]}</a>'
        f'<a href="/review">{UI["mode_gt"]}</a><a href="/diag">{UI["mode_dev"]}</a></div>'
    )
    foot = (
        f'<div class=foot>{UI["foot_source"]}: <b>{_src_label()}</b> · '
        f'{UI["foot_contract"]} {CONTRACT["version"]["contract"]} · {html.escape(who)} · {_now()}</div>'
    )
    doc = (
        "<!doctype html><html lang=ja><head><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width,initial-scale=1">'
        f"<style>{BASE_CSS}</style></head><body>"
        + bar + f'<div class=wrap>{body}</div>' + foot
        + "</body></html>"
    )
    return doc.encode("utf-8")


def highlight(text: str, evidence: list) -> str:
    """Highlight evidence lines (S11: the human confronts the evidence)."""
    keep = {e.get("idx") for e in evidence}
    out = []
    for line in text.splitlines():
        idx = line.split(":", 1)[0].strip()
        esc = html.escape(line)
        try:
            hit = int(idx) in keep
        except ValueError:
            hit = False
        out.append(f"<mark>{esc}</mark>" if hit else esc)
    return "<pre>" + "\n".join(out) + "</pre>"


def highlight_clickable(text: str) -> str:
    """Input lines as click-to-select evidence (GT-creation, S11). The reviewer
    picks evidence by clicking the actual line, not by typing line numbers."""
    out = []
    for line in text.splitlines():
        raw = line.split(":", 1)[0].strip()
        try:
            di = str(int(raw))
        except ValueError:
            di = ""
        out.append(f'<span class=ln data-idx="{di}" onclick="togEv(this)">{html.escape(line)}</span>')
    return "<pre>" + "\n".join(out) + "</pre>"


def render_judges(judges: dict) -> str:
    diverge = " diverge" if divergence(judges) else ""
    out = f'<div class="j{diverge}">'
    for role in ("proposer", "production"):
        j = judges.get(role) or {}
        out += (
            f'<div><span class=role>{UI["role_" + role]}</span>: '
            f'<b>{html.escape(str(j.get("verdict","")))}</b> — {html.escape(str(j.get("reason","")))}</div>'
        )
    if diverge:
        out += f'<div style="color:var(--flag);font-weight:600;margin-top:.3em">{UI["dev_divergence"]}</div>'
    return out + "</div>"


# Diagnostic SPA shell. Three panes (unit list / input+evidence / every judge)
# plus a persistent Problems pane (the divergence queue) and j/k keyboard nav —
# the developer surface's mental model is code review (W2). Vanilla JS over the
# read-only /api endpoints; stdlib only, no build step. The GT-creation surface
# (/review) stays deliberately minimal and never loads judges (S3).
DIAG_HTML = """<!doctype html><html lang=ja><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>レビューサーバー · 開発者診断</title>
<style>
__BASECSS__
body{height:100vh;display:grid;grid-template-rows:auto 1fr auto;overflow:hidden}
main{display:grid;grid-template-columns:248px 1fr 1fr;grid-template-rows:1fr 168px;min-height:0;gap:1px;background:var(--line)}
main>div{background:var(--surface);overflow:auto}
#list{grid-row:1/3}
#listtools{position:sticky;top:0;background:var(--surface);border-bottom:1px solid var(--line);padding:.55em .6em;display:flex;flex-direction:column;gap:.4em;z-index:1}
#listtools input[type=text]{width:100%;font-size:13px;padding:.4em .55em}
#listtools .row{display:flex;align-items:center;justify-content:space-between;font-size:12px;color:var(--muted)}
#listtools label{cursor:pointer}
#list .u{padding:.6em .85em;cursor:pointer;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:.5em;font-size:14px}
#list .u:hover{background:var(--accent-weak)}
#list .u.active{background:var(--accent-weak);box-shadow:inset 3px 0 0 var(--accent);font-weight:600}
.badge{background:var(--flag);color:#fff;border-radius:999px;font-size:11px;padding:.05em .5em;align-self:center;font-weight:600}
#input,#judges{padding:1.1em}
#input h3,#judges h3{margin-top:0}
#problems{grid-column:2/4;padding:.7em 1.1em}
#problabel{display:block;font-size:13px;color:var(--muted);margin-bottom:.4em}
.axis{border:1px solid var(--line);border-radius:10px;padding:.7em .85em;margin:.6em 0}
.axis.diverge{border-color:var(--flag);background:var(--flag-weak)}
.axis h4{display:flex;align-items:center;gap:.5em;margin-bottom:.4em;color:var(--ink);font-size:14px}
.tag{background:var(--flag);color:#fff;font-size:11px;font-weight:600;border-radius:999px;padding:.1em .6em}
.axis .j{border:0;padding:.1em 0;margin:.15em 0;font-size:13px}
.axis .role{display:inline-block;min-width:128px}
.prob{cursor:pointer;padding:.2em 0;color:var(--flag);font-size:13px}
.prob:hover{text-decoration:underline}
.ev{cursor:pointer;color:var(--accent);font-size:12px}
.ev:hover{text-decoration:underline}
.ln.flash{background:var(--accent-weak);outline:2px solid var(--accent);border-radius:3px}
</style></head><body class=diag>
<div class=bar id=hdr></div>
<main>
  <div id=list>
    <div id=listtools>
      <input type=text id=q>
      <div class=row><label><input type=checkbox id=onlydiv> <span id=onlydivlabel></span></label><span id=count></span></div>
    </div>
    <div id=listitems></div>
  </div>
  <div id=input></div>
  <div id=judges></div>
  <div id=problems><span id=problabel></span><div id=problist></div></div>
</main>
<div class=foot>__FOOT__</div>
<script>
const L=__LABELS__;
let UNITS=[], cur=null;
document.getElementById('hdr').innerHTML=
  '<a class=brand href="/">'+L.title+'</a><span style="color:#8a93a3">'+L.header+'</span>'+
  '<a href="/review">'+L.nav_gt+'</a><a href="/gt">'+L.nav_gtmanage+'</a><a href="/eval">'+L.nav_eval+'</a>'+
  '<span class=keyhint>'+L.keyhint+'</span>';
document.getElementById('input').innerHTML='<p style="color:var(--muted)">'+L.select+'</p>';
document.getElementById('problabel').textContent=L.problems;
document.getElementById('q').placeholder=L.search;
document.getElementById('onlydivlabel').textContent=L.only_div;
const esc=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
function highlight(text, evidence){
  const keep=new Set((evidence||[]).map(e=>e.idx));
  return '<pre>'+(text||'').split('\\n').map(line=>{
    const idx=parseInt(line.split(':')[0]);
    const e=esc(line);
    const inner=keep.has(idx)?'<mark>'+e+'</mark>':e;
    return '<span class=ln data-idx="'+(isNaN(idx)?'':idx)+'">'+inner+'</span>';
  }).join('\\n')+'</pre>';
}
function jumpTo(idx){
  const el=document.querySelector('#input .ln[data-idx="'+idx+'"]');
  if(!el)return;
  el.scrollIntoView({block:'center'});
  el.classList.add('flash');setTimeout(()=>el.classList.remove('flash'),900);
}
function visibleUnits(){
  const q=(document.getElementById('q').value||'').toLowerCase();
  const od=document.getElementById('onlydiv').checked;
  return UNITS.filter(u=>(!od||u.divergent)&&(!q||u.label.toLowerCase().includes(q)));
}
function renderList(){
  const vis=visibleUnits();
  document.getElementById('listitems').innerHTML=vis.map(u=>
    '<div class="u'+(u.unit_key===cur?' active':'')+'" data-k="'+esc(u.unit_key)+'">'+
    '<span>'+esc(u.label)+'</span>'+(u.divergent?'<span class=badge>&#8800;</span>':'')+'</div>'
  ).join('');
  document.querySelectorAll('#listitems .u').forEach(el=>el.onclick=()=>select(el.dataset.k));
  document.getElementById('count').textContent=vis.length+' / '+UNITS.length+' '+L.count;
  const probs=UNITS.filter(u=>u.divergent);
  document.getElementById('problist').innerHTML=probs.length?
    probs.map(u=>'<div class=prob data-k="'+esc(u.unit_key)+'">'+esc(u.label)+' &#8594; '+L.diverges+'</div>').join('')
    :'<div style="color:#888">'+L.none+'</div>';
  document.querySelectorAll('#problist .prob').forEach(el=>el.onclick=()=>select(el.dataset.k));
}
function renderJudge(roleLabel,j){
  j=j||{};
  const ev=(j.evidence&&j.evidence.length)?' '+j.evidence.map(x=>'<a class=ev onclick="jumpTo('+x+')">[idx '+x+']</a>').join(' '):'';
  return '<div class=j><span class=role>'+roleLabel+'</span><b>'+esc(j.verdict||'\\u2014')+'</b> &#8212; '+
    esc(j.reason||'')+ev+'</div>';
}
async function select(key){
  cur=key;
  history.replaceState(null,'','/diag/'+key);
  renderList();
  const d=await (await fetch('/api/diag/'+encodeURIComponent(key))).json();
  document.getElementById('input').innerHTML='<h3>'+esc(d.unit_key)+'</h3>'+highlight(d.input.text,d.input.evidence);
  document.getElementById('judges').innerHTML='<h3>'+L.judges+'</h3>'+d.axes.map(a=>
    '<div class="axis'+(a.divergence?' diverge':'')+'"><h4>'+esc(a.label)+
    (a.divergence?' <span class=tag>'+L.divergence+'</span>':'')+'</h4>'+
    renderJudge(L.role_proposer,a.judges.proposer)+renderJudge(L.role_production,a.judges.production)+'</div>'
  ).join('');
}
function move(d){
  const vis=visibleUnits();
  if(!vis.length)return;
  let i=vis.findIndex(u=>u.unit_key===cur);
  i=Math.max(0,Math.min(vis.length-1,(i<0?0:i+d)));
  select(vis[i].unit_key);
}
document.addEventListener('keydown',e=>{
  if(e.target.id==='q')return;
  if(e.key==='j'||e.key==='ArrowDown'){e.preventDefault();move(1);}
  if(e.key==='k'||e.key==='ArrowUp'){e.preventDefault();move(-1);}
});
document.getElementById('q').addEventListener('input',renderList);
document.getElementById('onlydiv').addEventListener('change',renderList);
(async()=>{
  const m=await (await fetch('/api/units')).json();
  UNITS=m.units;renderList();
  const p=location.pathname.split('/').filter(Boolean);
  const init=p[1]?decodeURIComponent(p[1]):(UNITS[0]&&UNITS[0].unit_key);
  if(init)select(init);
})();
</script></body></html>"""


# --- handler -----------------------------------------------------------------
class H(BaseHTTPRequestHandler):
    def _send(self, body: bytes, code: int = 200, headers: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj, code: int = 200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def _form(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n).decode("utf-8")
        return {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}

    # GETs are read-only (S8) -------------------------------------------------
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        # unquote each segment so non-ASCII unit keys (e.g. 通話-002) match the
        # adapter; without this the percent-encoded key never resolves.
        parts = [urllib.parse.unquote(p) for p in u.path.split("/") if p]
        if not parts:
            return self._send(self.landing_page())
        # Diagnostic mode is a single-page 3-pane surface (developer ergonomics,
        # W2): the SPA shell at /diag (and /diag/<unit> deep-link) reads these
        # read-only JSON endpoints. Judges ARE exposed here — this is developer
        # mode (S3 firewall binds /review, not /diag).
        if parts[:2] == ["api", "units"]:
            return self._send_json(self.api_units())
        if parts[:2] == ["api", "diag"] and len(parts) == 3:
            return self._send_json(self.api_diag(parts[2]))
        if parts[0] == "diag":
            return self._send(self.diag_app())
        if parts[0] == "review" and len(parts) == 1:
            return self._send(self.units_page())
        if parts[0] == "review" and len(parts) == 2:
            return self._send(self.review_page(parts[1]))   # S3: no judges here
        if parts[0] == "aggregate":
            return self._send(self.aggregate_page())
        if parts[0] == "eval":
            return self._send(self.eval_page())
        if parts[0] == "gt":
            return self._send(self.gt_page())
        return self._send(page(UI["not_found"]), 404)

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        parts = [urllib.parse.unquote(p) for p in u.path.split("/") if p]
        if parts[:1] == ["commit"] and len(parts) == 2:
            return self._send(self.commit(parts[1]))
        if parts[:1] == ["promote"] and len(parts) == 2:
            return self._send(self.promote(parts[1]))
        if parts == ["ingest"]:
            return self._send(self.ingest())
        return self._send(page(UI["not_found"]), 404)

    # pages -------------------------------------------------------------------
    def landing_page(self) -> bytes:
        # No login. Mode = route. The anchoring firewall lives in what each
        # route renders (S3), not in authentication.
        return page(
            f"<h2>{UI['title']}</h2>"
            f"<p>{UI['pick_mode']}</p>"
            '<ul class=modes>'
            f'<li><a href="/review">{UI["mode_gt"]}</a></li>'
            f'<li><a href="/diag">{UI["mode_dev"]}</a></li>'
            "</ul>"
        )

    def units_page(self) -> bytes:
        # GT-creation index only — deliberately minimal (anti-IDE, S3/W2): a
        # plain unit list, no judges, no aggregate nav. The rich 3-pane surface
        # is developer-only (/diag).
        rows = "".join(
            f'<li><a href="/review/{html.escape(u["unit_key"])}">{html.escape(u["label"])}</a></li>'
            for u in ADAPTER.units()
        )
        return page(f"<h3>{UI['gt_index']}</h3><ul>{rows}</ul>", who=UI["who_gt"])

    def review_page(self, unit_key: str) -> bytes:
        # S3 ANCHORING FIREWALL: input + evidence ONLY. Never call ADAPTER.judges().
        inp = ADAPTER.unit_input(unit_key)
        axes = "".join(
            f'<div class=card><h4>{html.escape(a["label"])}</h4><div class=radio-row>'
            + "".join(
                f'<label><input type=radio name="v_{a["key"]}" value="{html.escape(opt)}">{html.escape(opt)}</label>'
                for opt in a["vocabulary"]
            )
            + "</div></div>"
            for a in CONTRACT["axes"]
        )
        script = (
            "<script>const sel=new Set();function togEv(el){const i=el.dataset.idx;if(!i)return;"
            "if(sel.has(i)){sel.delete(i);el.classList.remove('selev')}else{sel.add(i);el.classList.add('selev')}"
            "const a=[...sel].sort((x,y)=>x-y);document.getElementById('evidence').value=a.join(',');"
            "document.getElementById('evdisp').textContent=a.length?a.join(', '):'\\u2014';}</script>"
            "<style>.ln{cursor:pointer;border-radius:3px}.ln:hover{background:#eef2ff}.selev{background:var(--mark)}</style>"
        )
        return page(
            f"<h3>{html.escape(unit_key)}</h3>"
            + f'<div class=card><h4>{UI["gt_evidence"]}</h4>{highlight_clickable(inp["text"])}</div>'
            + f'<form method=post action="/commit/{html.escape(unit_key)}">'
            + axes
            + f'<div class=card><h4>{UI["gt_reason"]}</h4><input type=text name=reason>'
            + f'<h4 style="margin-top:.8em">{UI["gt_ev_selected"]}</h4>'
            + '<input type=hidden id=evidence name=evidence>'
            + '<p id=evdisp style="margin:.2em 0;color:var(--muted)">&#8212;</p></div>'
            + f"<button>{UI['gt_commit']}</button></form>" + script,
            who=UI["who_gt"],
        )

    def commit(self, unit_key: str) -> bytes:
        f = self._form()
        revealed = ""
        for a in CONTRACT["axes"]:
            verdict = f.get(f"v_{a['key']}", "")
            if not verdict:
                continue
            STORE.append(
                unit_key=unit_key, axis_key=a["key"], verdict=verdict,
                reason=f.get("reason", ""),
                evidence=json.dumps([s.strip() for s in f.get("evidence", "").split(",") if s.strip()]),
                reviewer=REVIEWER, provenance="blind", tier="silver",
                versions=_versions(),
            )
            # S4: reveal AFTER the blind verdict is stored.
            revealed += f"<h4>{html.escape(a['label'])}</h4>" + render_judges(
                ADAPTER.judges(unit_key, a["key"])
            )
        return page(
            f"<h3>{html.escape(unit_key)} {UI['gt_committed']}</h3>"
            f'<div class=card><p style="margin:0 0 .6em">{UI["gt_stored"]}</p>{revealed}</div>'
            + f'<p><a href="/review">{UI["gt_next"]} →</a></p>',
            who=UI["who_gt"],
        )

    # Diagnostic SPA (W2: 3-pane + Problems queue + keyboard nav) ------------
    def api_units(self) -> dict:
        # NOTE (scale): this computes divergence for every unit×axis on each load.
        # Fine for the demo; for a large real adapter, cache judges/divergence in
        # data.py (or precompute a divergence column) so this stays cheap. The
        # search + "divergent only" filter below is client-side over this list.
        units = []
        for u in ADAPTER.units():
            divergent = any(
                divergence(ADAPTER.judges(u["unit_key"], a["key"])) for a in CONTRACT["axes"]
            )
            units.append({"unit_key": u["unit_key"], "label": u["label"], "divergent": divergent})
        axes = [{"key": a["key"], "label": a["label"]} for a in CONTRACT["axes"]]
        return {"units": units, "axes": axes}

    def api_diag(self, unit_key: str) -> dict:
        inp = ADAPTER.unit_input(unit_key)
        axes = []
        for a in CONTRACT["axes"]:
            j = ADAPTER.judges(unit_key, a["key"])
            axes.append({"key": a["key"], "label": a["label"], "judges": j, "divergence": divergence(j)})
        return {"unit_key": unit_key, "input": inp, "axes": axes}

    def diag_app(self) -> bytes:
        foot = (
            f"{UI['foot_source']}: {_src_label()} · {UI['foot_contract']} "
            f"{CONTRACT['version']['contract']} · {UI['who_dev']} · {_now()}"
        )
        labels = {
            "select": UI["dev_select"], "problems": UI["dev_problems"],
            "judges": UI["dev_judges"], "divergence": UI["dev_divergence"],
            "diverges": UI["dev_diverges"], "none": UI["dev_none"],
            "header": UI["dev_header"], "keyhint": UI["dev_keyhint"],
            "search": UI["dev_search"], "only_div": UI["dev_only_div"], "count": UI["dev_count"],
            "nav_gt": UI["mode_gt"], "nav_eval": UI["nav_eval"], "title": UI["title"],
            "nav_gtmanage": UI["nav_gt_manage"],
            "role_proposer": UI["role_proposer"], "role_production": UI["role_production"],
        }
        return (
            DIAG_HTML
            .replace("__BASECSS__", BASE_CSS)
            .replace("__FOOT__", html.escape(foot))
            .replace("__LABELS__", json.dumps(labels))
            .encode("utf-8")
        )

    def aggregate_page(self) -> bytes:
        queue = []
        for u in ADAPTER.units():
            for a in CONTRACT["axes"]:
                if divergence(ADAPTER.judges(u["unit_key"], a["key"])):
                    queue.append(f"{u['unit_key']} / {a['label']}")
        items = "".join(f"<li>{html.escape(q)}</li>" for q in queue) or f"<li>{UI['dev_none']}</li>"
        return page(f"<h3>{UI['agg_title']}</h3><div class=card><ul class=qlist>{items}</ul></div>", who=UI["who_dev"])

    def eval_page(self) -> bytes:
        # W6 / S12: regression vs gold + stale gold + holdout access log.
        gold = STORE.latest(tier="gold")
        stale = STORE.stale_gold(CONTRACT["version"]["criterion"])
        agree = miss = 0
        for r in gold:
            prod = ADAPTER.judges(r["unit_key"], r["axis_key"]).get("production") or {}
            if prod.get("verdict") == r["verdict"]:
                agree += 1
            else:
                miss += 1
        log = STORE.holdout_access_log()
        loglines = "".join(
            f"<li>{html.escape(r['at'])} · {html.escape(r['caller'])} · {html.escape(r['reason'])} · {r['n_rows']} {UI['rows']}</li>"
            for r in log
        ) or f"<li>{UI['eval_no_holdout']}</li>"
        return page(
            f"<h3>{UI['eval_title']}</h3>"
            f'<div class=card><p style="margin:.1em 0">{UI["eval_gold"]} <b>{len(gold)}</b> · '
            f'{UI["eval_agree"]} <b>{agree}</b> / {UI["eval_miss"]} <b>{miss}</b></p>'
            f'<p style="margin:.1em 0">{UI["eval_stale"]}: <b>{len(stale)}</b></p></div>'
            f'<h4>{UI["eval_holdout"]}</h4><div class=card><ul class=qlist>{loglines}</ul></div>'
            f'<p><a href="/gt">{UI["nav_gt_manage"]} →</a></p>',
            who=UI["who_dev"],
        )

    def gt_page(self, note: str = "") -> bytes:
        # Close the loop (S6): blind verdicts committed in GT-creation land as
        # silver; this developer surface promotes independent blind ones to gold
        # so eval has something to measure against. anchored ⇏ gold is enforced
        # in store.promote, not here.
        axis_label = {a["key"]: a["label"] for a in CONTRACT["axes"]}
        rows = STORE.latest()
        counts: dict = {}
        for r in rows:
            counts[r["tier"]] = counts.get(r["tier"], 0) + 1
        chips = "".join(
            f'<span class="pill {"gold" if t=="gold" else "silver"}">{html.escape(t)}: {n}</span>'
            for t, n in sorted(counts.items())
        ) or f'<span style="color:var(--muted)">{UI["dev_none"]}</span>'
        body_rows = ""
        for r in rows:
            prov = r["provenance"]
            prov_label = str(UI.get(f"prov_{prov}", prov))
            can_gold = prov == "blind" and r["tier"] not in ("gold", "holdout")
            act = (
                f'<form class=inline method=post action="/promote/{r["id"]}">'
                f'<button>{UI["gt_promote"]}</button></form>'
                if can_gold else ""
            )
            tier_cls = "gold" if r["tier"] == "gold" else "silver"
            body_rows += (
                f"<tr><td>{html.escape(r['unit_key'])}</td>"
                f"<td>{html.escape(axis_label.get(r['axis_key'], r['axis_key']))}</td>"
                f"<td><b>{html.escape(r['verdict'])}</b></td>"
                f'<td><span class="pill blind">{html.escape(prov_label)}</span></td>'
                f'<td><span class="pill {tier_cls}">{html.escape(r["tier"])}</span></td>'
                f"<td>{act}</td></tr>"
            )
        table = (
            f"<table><tr><th>{UI['col_unit']}</th><th>{UI['col_axis']}</th>"
            f"<th>{UI['col_verdict']}</th><th>{UI['col_prov']}</th>"
            f"<th>{UI['col_tier']}</th><th>{UI['col_act']}</th></tr>{body_rows}</table>"
            if body_rows else f"<p style='color:var(--muted)'>{UI['gt_empty']}</p>"
        )
        notice = f'<div class=card style="border-color:var(--accent)">{html.escape(note)}</div>' if note else ""
        return page(
            f"<h3>{UI['gt_manage_title']}</h3>{notice}"
            f"<div class=counts>{chips}</div>"
            f"<div class=card>{table}</div>",
            who=UI["who_dev"],
        )

    def promote(self, entry_id: str) -> bytes:
        try:
            STORE.promote(int(entry_id), "gold", REVIEWER)
            return self.gt_page(note=f"#{entry_id} {UI['gt_promoted']}")
        except (GateViolation, ValueError) as e:
            return self.gt_page(note=str(e))

    def ingest(self) -> bytes:
        # S9: one ingestion path. Merge CSVs dropped in inbox/, dedup by content.
        inbox = os.path.join(HERE, "inbox")
        os.makedirs(inbox, exist_ok=True)
        added = 0
        for fn in sorted(os.listdir(inbox)):
            if not fn.endswith(".csv"):
                continue
            with open(os.path.join(inbox, fn), encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    try:
                        STORE.append(
                            unit_key=row["unit_key"], axis_key=row["axis_key"],
                            verdict=row["verdict"], reason=row.get("reason", ""),
                            evidence=row.get("evidence", "[]"),
                            reviewer=row.get("reviewer", "import"),
                            provenance=row.get("provenance", "blind"),
                            tier=row.get("tier", "silver"), versions=_versions(),
                        )
                        added += 1
                    except Exception:
                        pass  # malformed rows are skipped, not fatal
        return page(f"<p>ingested {added} rows from inbox/</p>", who="developer")

    def log_message(self, format, *args):  # quiet
        pass


# --- CLI ---------------------------------------------------------------------
def make_snapshot():
    meta = {"created_at": _now(), "source": "snapshot", "contract": CONTRACT["version"]}
    json.dump(meta, open(os.path.join(HERE, "snapshot_meta.json"), "w"), indent=2)
    print("snapshot marker written; start with REVIEW_SOURCE=snapshot to serve it")


def make_package():
    out = os.path.join(HERE, f"review_dist_{_now().replace(':','').replace('-','')}.zip")
    exclude = ("gt.db", "inbox", "__pycache__")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(HERE):
            dirs[:] = [d for d in dirs if d not in exclude]
            for f in files:
                if f.startswith("gt.db") or f.endswith((".pyc", ".zip")):
                    continue
                p = os.path.join(root, f)
                z.write(p, os.path.relpath(p, HERE))
    print("packaged:", out, "(excluded answer DB / inbox / caches)")


def bind_probe(host, base, handler, attempts=50):
    """Bind from `base` upward to the first free port (probe-up on collision).
    Binding HTTPServer directly (not a separate test socket) avoids the
    TOCTOU race. Returns (httpd, port). The actual port is reported on screen
    and written to the runfile — it is not assumed to equal `base`."""
    last = None
    for p in range(base, base + attempts):
        try:
            return HTTPServer((host, p), handler), p
        except OSError as e:  # port in use → try the next one
            last = e
    raise SystemExit(f"空きポートが {base}..{base + attempts - 1} に見つかりません: {last}")


def write_runfile(port):
    import atexit
    import signal
    info = {
        "port": port,
        "pid": os.getpid(),
        "cwd": os.getcwd(),
        "db": os.path.abspath(DB_PATH),
        "contract_version": CONTRACT.get("version", {}).get("contract"),
        "source": SOURCE,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(RUNFILE, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    atexit.register(lambda: os.path.exists(RUNFILE) and os.remove(RUNFILE))
    # atexit fires on normal exit and on SIGINT (Ctrl-C → KeyboardInterrupt),
    # but NOT on SIGTERM (`kill`). Without this, a cleanly-stopped server would
    # leave a runfile and look like a crash. Translate SIGTERM into a clean
    # exit so atexit runs and the runfile is removed.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))


def show_status():
    """Answer 'what is running where' by DISCOVERY, not a stored ledger
    (a hand-kept port ledger drifts — the akatsuki F2 trap). Cross-reference
    live listeners (lsof) by cwd, the same identity signal used for :8030."""
    import subprocess
    if os.path.exists(RUNFILE):
        try:
            r = json.load(open(RUNFILE, encoding="utf-8"))
            print(f"このインスタンスの runfile: :{r['port']} pid={r['pid']} cwd={r['cwd']} "
                  f"(contract={r.get('contract_version')}, {r.get('started_at')})")
        except Exception as e:  # noqa: BLE001
            print(f"runfile 破損: {e!r}")
    else:
        print("runfile なし（このインスタンスは未起動、または正常終了済み）")
    print("--- 稼働中の LISTEN ポート（lsof で発見、cwd で識別）---")
    try:
        out = subprocess.run(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"],
                             capture_output=True, text=True, timeout=10).stdout
        rows = [l for l in out.splitlines() if "python" in l.lower() or "Python" in l]
        print("\n".join(rows) if rows else "  （python の LISTEN なし）")
    except FileNotFoundError:
        print("  lsof が無いため発見をスキップ")


def main():
    global SOURCE
    ap = argparse.ArgumentParser()
    # --port is the PREFERRED base; on collision we probe upward (8033→8034…).
    # It lives as this default, not in the contract (contract = judgment
    # vocabulary; port = deployment config).
    ap.add_argument("--port", type=int, default=8030)
    ap.add_argument("--snapshot", action="store_true")
    ap.add_argument("--package", action="store_true")
    ap.add_argument("--status", action="store_true",
                    help="稼働中サーバとこのインスタンスの runfile を表示")
    args = ap.parse_args()
    if args.snapshot:
        return make_snapshot()
    if args.package:
        return make_package()
    if args.status:
        return show_status()
    if os.environ.get("REVIEW_SOURCE") == "snapshot":
        SOURCE = "snapshot"
    httpd, port = bind_probe("127.0.0.1", args.port, H)
    write_runfile(port)
    if port != args.port:
        print(f"注意: 希望ポート :{args.port} は使用中。:{port} で起動します。")
    print(f"review-server on http://localhost:{port}/  (source={SOURCE})")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
