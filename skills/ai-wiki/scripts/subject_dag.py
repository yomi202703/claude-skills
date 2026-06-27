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
  tree_globs?: [ "<glob>", ... ]              # このマップが担当する tree 名前空間
                                              # (例 ["sangyo-soshiki-*"])。宣言すると
                                              # 一致する narratives で未参照のものを
                                              # 「未配線 tree」warning で報告 (配置は判断)。
  regions: { <key>: <表示名>, ... }          # 宣言順が配色順
  nodes: [ { id, layer(数), col(数), region(key), title,
             tag?(右上の短ラベル 例"ch3"/"lec5"), desc,
             trees: [ {slug, label?}, ... ] } ]
  edges: [ { from, to, kind, label? } ]       # kind ∈ flow|join|fan|cross|dissolve
  legend?: [ <下部の凡例文>, ... ]
  motifs?/ai_usage?/contrast_with?            # AI 消費・ドキュメント用 (描画には不使用)

render() は HTML を書き出すと同時に maps/_index.md (一覧表) を全 json から
再生成する。HTML は JS 不要の静的 SVG (Obsidian の HTML viewer でも描画可)。

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
    wired: set[str] = set()  # tree slugs referenced by some node
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
            wired.add(slug)
            if not (vault / "narratives" / f"{slug}.md").is_file():
                warnings.append(f"node {nid}: tree file not found: narratives/{slug}.md")
    for i, e in enumerate(edges):
        if e.get("from") not in ids:
            errors.append(f"edge[{i}] from '{e.get('from')}' is not a node id")
        if e.get("to") not in ids:
            errors.append(f"edge[{i}] to '{e.get('to')}' is not a node id")
        if e.get("kind") not in EDGE_KINDS:
            errors.append(f"edge[{i}] kind '{e.get('kind')}' not in {sorted(EDGE_KINDS)}")
    # 未配線 tree 検出: tree_globs で宣言した名前空間の narrative のうち、
    # どのノードからも参照されていないもの = 後から足された/載せ忘れの tree。
    # 機械はこれを warning で知らせるだけ。どこに載せるかは authoring (判断)。
    unwired = _unwired_trees(dag, vault, wired)
    for slug in unwired:
        warnings.append(f"未配線 tree (要 authoring 判断): narratives/{slug}.md")
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "region_count": len(regions),
        "unwired_trees": unwired,
    }


def _unwired_trees(dag: dict[str, Any], vault: Path, wired: set[str]) -> list[str]:
    """tree_globs (任意) が宣言する名前空間内で、どのノードも参照しない tree slug。"""
    import fnmatch

    globs = dag.get("tree_globs") or []
    if not globs:
        return []
    ndir = vault / "narratives"
    if not ndir.is_dir():
        return []
    out: list[str] = []
    for p in sorted(ndir.glob("*.md")):
        slug = p.stem
        if slug.startswith("_"):
            continue
        if any(fnmatch.fnmatch(slug, g) for g in globs) and slug not in wired:
            out.append(slug)
    return out


# ── 配色 palette: region 宣言順に割り当てる ────────────────────────────
PALETTE = [
    ("#eef2ff", "#9aa7e0"), ("#e7f5ee", "#73b794"), ("#fdeee8", "#d99a7a"),
    ("#fbf6e3", "#cdb95e"), ("#fbeaf0", "#d489a6"), ("#f3eefb", "#a98fd0"),
    ("#eaf3fb", "#7bbdd6"), ("#eafbf4", "#6fc7a0"), ("#e9e6e0", "#b3ada3"),
    ("#fdf1e3", "#dca35a"),
]

# ── 静的レンダラ (JS 不要) ───────────────────────────────────────────
# Obsidian の HTML viewer は <script> を実行しない (inline も外部も)。
# よって地図は Python 側で静的 SVG に事前描画し、HTML に直接埋め込む。
# 双方向性は JS でなくネイティブ機能で出す:
#   - ノード説明 = SVG <title> (ホバーで OS ネイティブのツールチップ)
#   - クリック → 右パネルの該当詳細へ (アンカー #d_<id> + CSS :target でハイライト)
#   - tree 遷移 = obsidian:// アンカー
# これでブラウザでも Obsidian (HTML Reader) でも同一に見える。

import urllib.parse as _ul

_LAYOUT = dict(BW=152, BH=46, COLW=170, LAYH=92, MX=100, MY=44)
_EK = {
    "flow": ("#b3ada3", 1.4, ""),
    "join": ("#3f9e6b", 2, ""),
    "fan": ("#8a63d2", 2, ""),
    "cross": ("#d98a2b", 1.3, "5 3"),
    "dissolve": ("#c2bdb4", 1.3, "2 4"),
}


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _num(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else str(round(x, 1))


def _wrap(s: str, n: int) -> list[str]:
    out: list[str] = []
    line = ""
    for ch in s or "":
        line += ch
        if len(line) >= n:
            out.append(line)
            line = ""
    if line:
        out.append(line)
    return out[:2]


def _build_svg(dag: dict[str, Any], rc: dict[str, tuple]) -> str:
    L = _LAYOUT
    nodes = dag.get("nodes", []) or []
    edges = dag.get("edges", []) or []
    pos: dict[str, tuple[float, float]] = {}
    nmap: dict[str, dict] = {}
    for n in nodes:
        cx = L["MX"] + n["col"] * L["COLW"]
        cy = L["MY"] + n["layer"] * L["LAYH"]
        pos[n["id"]] = (cx, cy)
        nmap[n["id"]] = n
    max_x = max((cx + L["BW"] / 2 for cx, _ in pos.values()), default=0)
    max_y = max((cy + L["BH"] / 2 for _, cy in pos.values()), default=0)
    W, H = max_x + 60, max_y + 58

    defs = "".join(
        f'<marker id="m_{k}" markerWidth="9" markerHeight="9" refX="6" refY="3" '
        f'orient="auto"><path d="M0,0 L6,3 L0,6" fill="none" stroke="{spec[0]}" '
        f'stroke-width="1.4"/></marker>'
        for k, spec in _EK.items()
    )
    parts = [
        f'<svg viewBox="0 0 {_num(W)} {_num(H)}" xmlns="http://www.w3.org/2000/svg">'
        f"<defs>{defs}</defs>"
    ]

    for e in edges:
        p, c = pos.get(e.get("from")), pos.get(e.get("to"))
        if not p or not c:
            continue
        x1, y1 = p[0], p[1] + L["BH"] / 2
        x2, y2 = c[0], c[1] - L["BH"] / 2
        my = (y1 + y2) / 2
        col, wid, dash = _EK.get(e.get("kind"), _EK["flow"])
        da = f' stroke-dasharray="{dash}"' if dash else ""
        parts.append(
            f'<path fill="none" stroke="{col}" stroke-width="{wid}"{da} '
            f'marker-end="url(#m_{e.get("kind", "flow")})" '
            f"d=\"M{_num(x1)},{_num(y1)} C{_num(x1)},{_num(my)} "
            f'{_num(x2)},{_num(my)} {_num(x2)},{_num(y2)}"/>'
        )
        if e.get("label"):
            parts.append(
                f'<text x="{_num((x1 + x2) / 2)}" y="{_num(my)}" text-anchor="middle" '
                f'font-size="9.5" fill="#9a6f1f">{_esc(e["label"])}</text>'
            )

    for n in nodes:
        cx, cy = pos[n["id"]]
        fill, stroke = rc.get(n["region"], PALETTE[0])
        x, y = cx - L["BW"] / 2, cy - L["BH"] / 2
        parts.append(f'<a href="#d_{_esc(n["id"])}"><g class="box">')
        parts.append(f'<title>{_esc(n.get("desc", ""))}</title>')
        parts.append(
            f'<rect x="{_num(x)}" y="{_num(y)}" width="{L["BW"]}" height="{L["BH"]}" '
            f'rx="9" fill="{fill}" stroke="{stroke}"/>'
        )
        if n.get("tag"):
            parts.append(
                f'<text class="tag" x="{_num(x + L["BW"] - 8)}" y="{_num(y + 13)}" '
                f'text-anchor="end">{_esc(n["tag"])}</text>'
            )
        lines = _wrap(n["title"], 13)
        for i, ln in enumerate(lines):
            dy = (i * 14 - 2) if len(lines) > 1 else 4
            parts.append(
                f'<text x="{_num(cx)}" y="{_num(cy + dy)}" '
                f'text-anchor="middle">{_esc(ln)}</text>'
            )
        parts.append("</g></a>")

    legend = dag.get("legend", []) or []
    for i, t in enumerate(legend):
        ly = H - 12 - (len(legend) - 1 - i) * 14
        parts.append(
            f'<text x="12" y="{_num(ly)}" font-size="11" fill="#777">{_esc(t)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _build_legend(dag: dict[str, Any], rc: dict[str, tuple]) -> str:
    rows = "".join(
        f'<div><span class="sw" style="background:{rc[k][0]};border:1px solid '
        f'{rc[k][1]}"></span>{_esc(name)}</div>'
        for k, name in (dag.get("regions", {}) or {}).items()
    )
    return rows


def _build_panel(dag: dict[str, Any], rc: dict[str, tuple], vault_name: str) -> str:
    out = ['<div class="hint">ノードにホバーで要約 / クリックで下に詳細</div>']
    for n in dag.get("nodes", []) or []:
        fill, stroke = rc.get(n["region"], PALETTE[0])
        refs = ""
        for t in n.get("trees", []) or []:
            slug = t.get("slug") if isinstance(t, dict) else t
            if not slug:
                continue
            label = (t.get("label") if isinstance(t, dict) else None) or slug
            href = (
                f"obsidian://open?vault={_ul.quote(vault_name)}"
                f"&file={_ul.quote('narratives/' + slug)}"
            )
            refs += f'<a class="ref" href="{href}">{_esc(label)} ↗</a>'
        refs_block = (
            f'<div class="refs"><div class="rlab">詳細へ ― 章/講 tree</div>{refs}</div>'
            if refs
            else ""
        )
        tag = f'<span class="dch">{_esc(n["tag"])}</span>' if n.get("tag") else ""
        out.append(
            f'<div class="detail" id="d_{_esc(n["id"])}">'
            f'<div class="dh"><span class="dot" style="background:{fill};'
            f'border:1px solid {stroke}"></span><b>{_esc(n["title"])}</b>{tag}</div>'
            f'<div class="dd">{_esc(n.get("desc", ""))}</div>{refs_block}</div>'
        )
    return "".join(out)

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
svg a{cursor:pointer}
.box rect{stroke-width:1.5;transition:.12s}
.box:hover rect{filter:brightness(.94);stroke:#1c1c1c}
.box text{font-size:11px;fill:#1c1c1c;pointer-events:none}.box .tag{font-size:9px;fill:#9a958c}
.panel{width:312px;border-left:1px solid #e3e0da;background:#fff;padding:14px 16px;overflow:auto}
.panel .hint{color:#aaa;font-size:11.5px;margin-bottom:12px;border-bottom:1px solid #eee;padding-bottom:10px}
.detail{padding:9px 10px;border-radius:8px;margin:4px -4px;scroll-margin-top:10px}
.detail:target{background:#fbf6e3;box-shadow:0 0 0 2px #cdb95e inset}
.detail .dh{font-size:13px;margin-bottom:5px}
.detail .dh b{font-weight:600}
.detail .dot{display:inline-block;width:9px;height:9px;border-radius:3px;margin-right:6px;vertical-align:0}
.detail .dch{font-size:11px;color:#9a958c;margin-left:6px}
.detail .dd{font-size:12.5px;line-height:1.75;color:#333}
.refs{margin-top:9px}.refs .rlab{font-size:10.5px;color:#999;margin-bottom:5px}
.ref{display:block;font-size:12px;color:#2f6f4f;text-decoration:none;padding:6px 9px;border:1px solid #e3e0da;border-radius:7px;margin:4px 0;background:#fff}
.ref:hover{background:#f1f8f3}
.lg{margin-top:16px;font-size:11.5px;color:#888;border-top:1px solid #eee;padding-top:10px;line-height:1.9}
.lg .sw{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}
"""


def render_html(dag: dict[str, Any], vault_name: str = "ai-wiki") -> str:
    dag = dict(dag)
    dag.setdefault("vault", vault_name)
    title = _esc(dag.get("title", dag.get("slug", "subject DAG")))
    sub = _esc(dag.get("subtitle", dag.get("design", "")))
    rkeys = list((dag.get("regions", {}) or {}).keys())
    rc = {k: PALETTE[i % len(PALETTE)] for i, k in enumerate(rkeys)}
    svg = _build_svg(dag, rc)
    panel = _build_panel(dag, rc, vault_name)
    legend = _build_legend(dag, rc)
    return (
        "<!doctype html><html lang=ja><head><meta charset=utf-8>"
        '<meta name=viewport content="width=device-width,initial-scale=1">'
        f"<title>{title}</title><style>{_CSS}</style></head><body>"
        f'<header><h1>{title}</h1><div class="sub">{sub}</div></header>'
        f'<div class="wrap"><div class="canvas">{svg}</div>'
        f'<div class="panel">{panel}<div class="lg">{legend}</div></div></div>'
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
    index = regen_index(vault)
    return {"ok": True, "html": str(out), "report": report, "index": index}


def regen_index(vault: Path) -> str:
    """maps/ の全 <slug>.json から maps/_index.md (表) を作り直す。

    機械の責務。新しいマップを足して render すれば一覧が常に最新になる。
    リンクは file:// (パーセントエンコード) — Obsidian から外部ブラウザで開く。
    """
    mdir = maps_dir(vault)
    rows: list[tuple[str, str, int, int]] = []
    for p in sorted(mdir.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        slug = p.stem
        title = str(d.get("title", slug)).replace("|", "/")
        url = "file://" + _ul.quote(str(mdir / f"{slug}.html"))
        rows.append((title, url, len(d.get("nodes", []) or []), len(d.get("edges", []) or [])))
    lines = [
        "# 教科 DAG マップ一覧",
        "",
        "各マップは自己完結の静的 HTML(俯瞰地図)。リンクを開くと外部ブラウザで表示。",
        "",
        "| マップ | N | E |",
        "|---|--:|--:|",
    ]
    for title, url, n, e in rows:
        lines.append(f"| [{title}]({url}) | {n} | {e} |")
    out = mdir / "_index.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(out)


def validate_all(vault: Path) -> dict[str, Any]:
    """全マップを validate し、_index.md を再生成する (narratives/derivations と対)。"""
    mdir = maps_dir(vault)
    maps: list[dict[str, Any]] = []
    ok = True
    for p in sorted(mdir.glob("*.json")):
        slug = p.stem
        dag = load(vault, slug)
        if dag is None:
            maps.append({"slug": slug, "ok": False, "error": "load failed"})
            ok = False
            continue
        rep = validate(dag, vault)
        ok = ok and rep["ok"]
        maps.append({
            "slug": slug,
            "ok": rep["ok"],
            "errors": rep["errors"],
            "warnings": rep["warnings"],
            "unwired_trees": rep.get("unwired_trees", []),
        })
    index = regen_index(vault)
    return {"ok": ok, "maps": maps, "index": index}
