"""subject-dag: 教科 DAG (俯瞰地図) の検証と JSON→HTML 描画。

判断と機械の分離:
- 判断 (LLM): どの教科 tree 群を、どのトポロジー (収斂/拡散/基準+逸脱…) で
  どう再切断するか、ノード/エッジ/配置をどう置くか — これは maps/<slug>-dag.json
  を「人 (LLM) が書く」。SKILL.md の authoring 手順を見よ。
- 機械 (本モジュール): JSON を真実源として検証し、自己完結 HTML を生成する。
  配色は region 宣言順に palette から自動付与。HTML は file:// で開ける
  (fetch しない=データ埋め込み)。これで JSON と HTML の二重持ち drift が消える。

JSON schema (maps/<slug>-dag.json):
  slug, title, subtitle?, kind="subject-dag",
  regions: { <key>: <表示名>, ... }          # 宣言順が配色順
  nodes: [ { id, layer(数), col(数), region(key), title,
             tag?(右上の短ラベル 例"ch3"/"lec5"), desc,
             trees: [ {slug, label?}, ... ] } ]
  edges: [ { from, to, kind, label? } ]       # kind ∈ flow|join|fan|cross|dissolve
  legend?: [ <下部の凡例文>, ... ]
  motifs?/ai_usage?/contrast_with?            # AI 消費・ドキュメント用 (描画には不使用)

stdlib only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EDGE_KINDS = {"flow", "join", "fan", "cross", "dissolve"}


def maps_dir(vault: Path) -> Path:
    return vault / "maps"


def json_path(vault: Path, slug: str) -> Path:
    slug = slug[:-5] if slug.endswith(".json") else slug
    return maps_dir(vault) / f"{slug}.json"


def html_path(vault: Path, slug: str) -> Path:
    slug = slug[:-5] if slug.endswith(".json") else slug
    return maps_dir(vault) / f"{slug}.html"


def load(vault: Path, slug: str) -> dict[str, Any] | None:
    p = json_path(vault, slug)
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def validate(dag: dict[str, Any], vault: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for key in ("slug", "title", "regions", "nodes", "edges"):
        if key not in dag:
            errors.append(f"missing top-level key: {key}")
    nodes = dag.get("nodes", []) or []
    edges = dag.get("edges", []) or []
    regions = dag.get("regions", {}) or {}
    ids: set[str] = set()
    for i, n in enumerate(nodes):
        for f in ("id", "layer", "col", "region", "title", "desc"):
            if f not in n:
                errors.append(f"node[{i}] missing field: {f}")
        nid = n.get("id")
        if nid in ids:
            errors.append(f"duplicate node id: {nid}")
        ids.add(nid)
        if n.get("region") not in regions:
            errors.append(f"node {nid}: region '{n.get('region')}' not in regions")
        for t in n.get("trees", []) or []:
            slug = t.get("slug") if isinstance(t, dict) else t
            if not slug:
                errors.append(f"node {nid}: tree ref without slug")
                continue
            if not (vault / "narratives" / f"{slug}.md").is_file():
                warnings.append(f"node {nid}: tree file not found: narratives/{slug}.md")
    for i, e in enumerate(edges):
        if e.get("from") not in ids:
            errors.append(f"edge[{i}] from '{e.get('from')}' is not a node id")
        if e.get("to") not in ids:
            errors.append(f"edge[{i}] to '{e.get('to')}' is not a node id")
        if e.get("kind") not in EDGE_KINDS:
            errors.append(f"edge[{i}] kind '{e.get('kind')}' not in {sorted(EDGE_KINDS)}")
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "region_count": len(regions),
    }


# ── 配色 palette: region 宣言順に割り当てる ────────────────────────────
PALETTE = [
    ("#eef2ff", "#9aa7e0"), ("#e7f5ee", "#73b794"), ("#fdeee8", "#d99a7a"),
    ("#fbf6e3", "#cdb95e"), ("#fbeaf0", "#d489a6"), ("#f3eefb", "#a98fd0"),
    ("#eaf3fb", "#7bbdd6"), ("#eafbf4", "#6fc7a0"), ("#e9e6e0", "#b3ada3"),
    ("#fdf1e3", "#dca35a"),
]

_ENGINE = r"""
const esc=s=>(s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const RKEYS=Object.keys(DAG.regions);
const RC={};RKEYS.forEach((k,i)=>RC[k]=PALETTE[i%PALETTE.length]);
const NODES=DAG.nodes, EDGES=DAG.edges, NMAP={};NODES.forEach(n=>NMAP[n.id]=n);
const BW=152,BH=46,COLW=170,LAYH=92,MX=100,MY=44;
NODES.forEach(n=>{n.cx=MX+n.col*COLW;n.cy=MY+n.layer*LAYH;});
let maxX=0,maxY=0;NODES.forEach(n=>{maxX=Math.max(maxX,n.cx+BW/2);maxY=Math.max(maxY,n.cy+BH/2);});
const W=maxX+60,H=maxY+58;
function wrap(s,n){const o=[];let l='';for(const ch of s){l+=ch;if([...l].length>=n){o.push(l);l='';}}if(l)o.push(l);return o.slice(0,2);}
const EK={flow:['#b3ada3',1.4,''],join:['#3f9e6b',2,''],fan:['#8a63d2',2,''],cross:['#d98a2b',1.3,'5 3'],dissolve:['#c2bdb4',1.3,'2 4']};
function mk(id,col){return `<marker id="${id}" markerWidth=9 markerHeight=9 refX=6 refY=3 orient=auto><path d="M0,0 L6,3 L0,6" fill=none stroke="${col}" stroke-width=1.4/></marker>`;}
let defs='';for(const k in EK)defs+=mk('m_'+k,EK[k][0]);
let svg=`<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg"><defs>${defs}</defs>`;
for(const e of EDGES){const p=NMAP[e.from],c=NMAP[e.to];if(!p||!c)continue;
  const x1=p.cx,y1=p.cy+BH/2,x2=c.cx,y2=c.cy-BH/2,my=(y1+y2)/2,st=EK[e.kind]||EK.flow;
  svg+=`<path fill=none stroke="${st[0]}" stroke-width="${st[1]}" ${st[2]?`stroke-dasharray="${st[2]}"`:''} marker-end="url(#m_${e.kind})" d="M${x1},${y1} C${x1},${my} ${x2},${my} ${x2},${y2}"/>`;
  if(e.label)svg+=`<text x="${(x1+x2)/2}" y="${my}" text-anchor=middle font-size=9.5 fill="#9a6f1f">${esc(e.label)}</text>`;
}
for(const n of NODES){const rc=RC[n.region]||PALETTE[0],x=n.cx-BW/2,y=n.cy-BH/2;
  svg+=`<g class=box id="box_${n.id}" onclick="sel('${n.id}')"><rect x=${x} y=${y} width=${BW} height=${BH} rx=9 fill="${rc[0]}" stroke="${rc[1]}"/>`;
  if(n.tag)svg+=`<text class=tag x=${x+BW-8} y=${y+13} text-anchor=end>${esc(n.tag)}</text>`;
  const lines=wrap(n.title,13);
  lines.forEach((ln,i)=>{svg+=`<text x=${n.cx} y=${n.cy+(lines.length>1?(i*14-2):4)} text-anchor=middle>${esc(ln)}</text>`;});
  svg+=`</g>`;
}
(DAG.legend||[]).forEach((t,i)=>{svg+=`<text x=12 y=${H-12-((DAG.legend.length-1-i)*14)} font-size=11 fill="#777">${esc(t)}</text>`;});
svg+='</svg>';
document.getElementById('canvas').innerHTML=svg;
function legendHTML(){return RKEYS.map(k=>`<div><span class=sw style="background:${RC[k][0]};border:1px solid ${RC[k][1]}"></span>${esc(DAG.regions[k])}</div>`).join('');}
function refsHTML(n){const r=n.trees||[];if(!r.length)return'';
  return `<div class=refs><div class=rlab>詳細へ ― 既存の章/講 tree</div>`+r.map(t=>{const slug=t.slug||t,label=t.label||slug;
    return `<a class=ref href="obsidian://open?vault=${encodeURIComponent(DAG.vault||'ai-wiki')}&file=${encodeURIComponent('narratives/'+slug)}">${esc(label)} ↗</a>`;}).join('')+`</div>`;}
let cur=null;
function sel(id){const n=NMAP[id];if(!n)return;
  if(cur)document.getElementById('box_'+cur).classList.remove('sel');
  cur=id;document.getElementById('box_'+id).classList.add('sel');
  document.getElementById('panel').innerHTML=`<h2>${esc(n.title)}</h2>${n.tag?`<div class=ch>${esc(n.tag)}</div>`:''}<div class=d>${esc(n.desc)}</div>`+refsHTML(n)+`<div class=tagrow>${legendHTML()}</div>`;}
document.getElementById('legend').innerHTML=legendHTML();
"""

_CSS = r"""
:root{font-family:-apple-system,"Hiragino Kaku Gothic ProN",sans-serif}
*{box-sizing:border-box}
body{margin:0;background:#faf9f7;color:#1c1c1c}
header{padding:11px 18px;border-bottom:1px solid #e3e0da;background:#fffefb}
header h1{font-size:15px;margin:0 0 3px}
header .sub{font-size:12px;color:#888}
.wrap{display:flex;height:calc(100vh - 56px)}
.canvas{flex:1;overflow:auto;padding:10px}
svg{width:100%;height:auto;display:block}
.box{cursor:pointer}.box rect{stroke-width:1.5;transition:.12s}
.box:hover rect{filter:brightness(.96)}.box.sel rect{stroke:#1c1c1c;stroke-width:2.6}
.box text{font-size:11px;fill:#1c1c1c;pointer-events:none}.box .tag{font-size:9px;fill:#9a958c}
.panel{width:300px;border-left:1px solid #e3e0da;background:#fff;padding:16px 18px;overflow:auto}
.panel h2{font-size:14px;margin:0 0 6px}.panel .ch{font-size:12px;color:#9a958c;margin-bottom:8px}
.panel .d{font-size:13px;line-height:1.8}.panel .ph{color:#aaa;font-size:13px;margin-top:30px}
.refs{margin-top:16px}.refs .rlab{font-size:11px;color:#999;margin-bottom:6px}
.ref{display:block;font-size:12.5px;color:#2f6f4f;text-decoration:none;padding:7px 10px;border:1px solid #e3e0da;border-radius:7px;margin:5px 0;background:#fff}
.ref:hover{background:#f1f8f3}
.tagrow{margin-top:14px;font-size:11.5px;color:#888;border-top:1px solid #eee;padding-top:10px;line-height:1.9}
.sw{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}
"""


def render_html(dag: dict[str, Any], vault_name: str = "ai-wiki") -> str:
    dag = dict(dag)
    dag.setdefault("vault", vault_name)
    title = dag.get("title", dag.get("slug", "subject DAG"))
    sub = dag.get("subtitle", dag.get("design", ""))
    palette_js = json.dumps(PALETTE)
    dag_js = json.dumps(dag, ensure_ascii=False)
    return (
        "<!doctype html><html lang=ja><head><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width,initial-scale=1">'
        f"<title>{title}</title><style>{_CSS}</style></head><body>"
        f"<header><h1>{title}</h1><div class=sub>{sub}</div></header>"
        '<div class=wrap><div class=canvas id=canvas></div>'
        '<div class=panel id=panel><div class=ph>ノードを押すと中身が出る</div>'
        '<div class=tagrow id=legend></div></div></div>'
        f"<script>const PALETTE={palette_js};const DAG={dag_js};{_ENGINE}</script>"
        "</body></html>"
    )


def render(vault: Path, slug: str) -> dict[str, Any]:
    dag = load(vault, slug)
    if dag is None:
        return {"ok": False, "error": f"not found: {json_path(vault, slug)}"}
    report = validate(dag, vault)
    if not report["ok"]:
        return {"ok": False, "error": "validation failed", "report": report}
    out = html_path(vault, dag.get("slug", slug))
    out.write_text(render_html(dag, vault.name), encoding="utf-8")
    return {"ok": True, "html": str(out), "report": report}
