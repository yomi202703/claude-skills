#!/usr/bin/env python3
"""Symbol-walk card generation: narrative tree → atomic Q-A deck.

The narrative DSL's bracketed symbols ([?] [★] [✕] [∴] [⟳] …) are a structural
index of the tree's atomic knowledge units. This module walks them
**deterministically** — every bracketed-symbol node (plus every ⟳ section
transition) becomes at least one card — so coverage is guaranteed by
construction, not by LLM discretion or by what happened to come up in a drill.
That removes the two failure modes we kept hitting: blind spots from cherry-
picked questions, and the redundancy of carding conversation misses one by one.

Division of responsibility, on purpose:
- **WHAT to card = deterministic** (`extract_nodes`, pure Python, no LLM). The
  set of cards is pinned to the tree the user actually reads.
- **HOW to phrase = LLM** (`draft_cards`). The model only turns each node's
  prose into a clean atomic question keyed to its symbol's role; it never
  decides which nodes deserve a card. Python then verifies every node got ≥1.

The symbol determines the *question type*, so causal spine cards (⟳ "why does A
lead to B"), consequence cards (∴), rejected-candidate cards (✕) etc. all fall
out for free — the same questions a human tutor would ask, generated structurally.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

import cards as mod_cards
import llm
from vault import Vault

# The fixed bracketed-symbol set (must match narrative.py's contract / legend).
# Longest-first alternation so [??] wins over [?].
_SYMBOLS = ["??", "?", "★", "◯", "✕", "∥", "⛔", "!", "∴", "⤴", "⤵", "⟳", "↺", "⊂", "⊕", "~"]
_SYM_RE = re.compile(r"\[(" + "|".join(re.escape(s) for s in _SYMBOLS) + r")\]")

# A bare "⟳ **だから次の問題**:" line between sections — the causal spine turn.
_TRANSITION_RE = re.compile(r"^\s*⟳\s+\*\*")

# Leading tree-drawing scaffold to strip from node text.
_TREE_CHARS_RE = re.compile(r"^[\s│├└─┌┐┘┤┬┴┼·]*")

# Sections that are not study content.
_SKIP_SECTIONS = {"記法", "未配送"}

_FENCE_RE = re.compile(r"^\s*```")
_H2_RE = re.compile(r"^##\s+(.*?)\s*$")


@dataclass
class Node:
    id: str
    symbol: str          # the bracketed symbol, or "⟳" for a transition line
    text: str            # cleaned node text (may span continuation sub-bullets)
    section: str         # owning "## ..." heading


def _strip_scaffold(line: str) -> str:
    return _TREE_CHARS_RE.sub("", line).rstrip()


def _is_skippable(section: str) -> bool:
    """True for non-content sections (legend, undelivered). `section` is the
    bare heading text, e.g. '記法', '未配送', '1. ...'."""
    h = section.strip()
    return any(h == s or h.startswith(s) for s in _SKIP_SECTIONS)


def extract_nodes(body: str) -> list[Node]:
    """Walk the narrative body and return one Node per bracketed-symbol anchor
    (and per ⟳ transition line). Deterministic: same body → same nodes.

    A node's text spans its anchor line plus following continuation lines
    (deeper sub-bullets, inline ∴/→ lines) until the next anchor, fence close,
    transition, or heading. The `## 記法` legend and `## 未配送` sections are
    skipped as non-content.
    """
    lines = body.splitlines()
    nodes: list[Node] = []
    counter = 0

    section = "ROOT"
    in_fence = False
    skip_section = False

    # pending accumulates continuation lines for the most recent node
    pending: Node | None = None
    pending_lines: list[str] = []

    def flush() -> None:
        nonlocal pending, pending_lines
        if pending is not None:
            text = "\n".join(t for t in (s.strip() for s in pending_lines) if t)
            pending.text = text
            nodes.append(pending)
        pending = None
        pending_lines = []

    for raw in lines:
        h = _H2_RE.match(raw)
        if h and not in_fence:
            flush()
            section = h.group(1).strip()
            skip_section = _is_skippable(section)
            continue

        if _FENCE_RE.match(raw):
            flush()
            in_fence = not in_fence
            continue

        if skip_section:
            continue

        # Transition line (outside fences): its own node.
        if not in_fence and _TRANSITION_RE.match(raw):
            flush()
            counter += 1
            pending = Node(id=f"n{counter}", symbol="⟳", text="", section=section)
            pending_lines = [_strip_scaffold(raw)]
            continue

        m = _SYM_RE.search(raw)
        if m:
            flush()
            counter += 1
            sym = m.group(1)
            # node text = everything from the symbol token onward, scaffold removed
            after = raw[m.end():].strip()
            pending = Node(id=f"n{counter}", symbol=sym, text="", section=section)
            pending_lines = [after]
            continue

        # Continuation line for the current node (sub-bullet, inline ∴/→, etc.)
        if pending is not None:
            stripped = _strip_scaffold(raw)
            if stripped:
                pending_lines.append(stripped)

    flush()
    return nodes


def _group_by_section(nodes: list[Node]) -> list[tuple[str, list[Node]]]:
    groups: list[tuple[str, list[Node]]] = []
    cur_sec: str | None = None
    cur: list[Node] = []
    for n in nodes:
        if n.section != cur_sec:
            if cur:
                groups.append((cur_sec or "", cur))
            cur_sec, cur = n.section, []
        cur.append(n)
    if cur:
        groups.append((cur_sec or "", cur))
    return groups


def _phrase_section(
    vault: Vault, slug: str, title: str, section: str, nodes: list[Node],
    *, model: str | None = None,
) -> tuple[dict[str, list[tuple[str, str]]], float]:
    """Ask the LLM to phrase a section's nodes into atomic Q-A cards.
    Returns ({node_id: [(q, a), ...]}, cost)."""
    nodes_json = json.dumps(
        [{"id": n.id, "symbol": n.symbol, "text": n.text} for n in nodes],
        ensure_ascii=False,
        indent=2,
    )
    result = llm.call_with_template(
        "card_draft",
        {"title": title, "slug": slug, "section": section, "nodes_json": nodes_json},
        model=model,
        parse_json=True,
    )
    llm.log_call(vault.append_log, "card_draft", slug, result)
    out: dict[str, list[tuple[str, str]]] = {}
    if result.is_error or not isinstance(result.parsed, list):
        return out, result.cost_usd
    for item in result.parsed:
        if not isinstance(item, dict):
            continue
        nid = str(item.get("node_id", "")).strip()
        q = str(item.get("q", "")).strip()
        a = str(item.get("a", "")).strip()
        if nid and q and a:
            out.setdefault(nid, []).append((q, a))
    return out, result.cost_usd


def draft_cards(vault: Vault, slug: str, *, model: str | None = None) -> dict:
    """Generate a full deck for a narrative by walking its symbols.

    Coverage contract: every extracted node is *attempted*; the report lists any
    node that came back with no card so nothing is silently dropped. Append-only
    to `cards/<slug>.tsv` (consistent with add_card) — re-running adds cards
    again, so clear the deck first if regenerating.
    """
    page = vault.read("narrative", slug)
    if page is None:
        return {"ok": False, "error": f"narrative {slug!r} not found"}
    title = str(page.meta.get("title") or slug)

    nodes = extract_nodes(page.body)
    if not nodes:
        return {"ok": False, "error": "no bracketed-symbol nodes found"}

    cards_by_node: dict[str, list[tuple[str, str]]] = {}
    total_cost = 0.0
    for section, sec_nodes in _group_by_section(nodes):
        phrased, cost = _phrase_section(vault, slug, title, section, sec_nodes, model=model)
        total_cost += cost
        cards_by_node.update(phrased)

    # Coverage check: retry uncovered nodes once, as a single batch.
    uncovered = [n for n in nodes if n.id not in cards_by_node]
    if uncovered:
        phrased, cost = _phrase_section(vault, slug, title, "(retry)", uncovered, model=model)
        total_cost += cost
        cards_by_node.update(phrased)
    uncovered = [n for n in nodes if n.id not in cards_by_node]

    # Write, preserving node order.
    written = 0
    for n in nodes:
        for q, a in cards_by_node.get(n.id, []):
            r = mod_cards.add_card(vault, slug, q, a)
            if r.get("ok"):
                written += 1

    vault.append_log(
        "card_draft_done",
        {
            "slug": slug,
            "nodes": len(nodes),
            "carded": len(nodes) - len(uncovered),
            "cards": written,
            "cost_usd": f"{total_cost:.4f}",
        },
    )
    return {
        "ok": True,
        "deck": str((vault.root / "cards" / f"{slug}.tsv")),
        "nodes_total": len(nodes),
        "nodes_carded": len(nodes) - len(uncovered),
        "uncovered_nodes": [{"id": n.id, "symbol": n.symbol, "text": n.text[:60]} for n in uncovered],
        "cards_written": written,
        "cost_usd": round(total_cost, 4),
    }
