#!/usr/bin/env python3
"""Card capture for ai-wiki.

A discovery-drill *divergence* (an answer that does not reach the source) is the
trigger to persist a flashcard. The chat is ephemeral; the card is the durable
asset, so the only thing this module does is append cards to a per-narrative deck
that imports directly into Anki.

Design decisions (deliberate, see SKILL.md "Cards" / discovery drill):
- **Append-only. No dedup, no node bookkeeping.** A single narrative node can
  legitimately spawn many distinct questions (the chain, an analogy, a formula
  fill-in, a term cue...). Deduping or "marking a node done" would either
  collapse genuinely different cards or give a false sense of coverage. So we
  never manage by node — every miss becomes its own line. Literal duplicates are
  harmless (varied retrieval cues even help) and left in.
- **Deck = `<vault>/cards/<slug>.tsv`**, one deck per narrative, mirroring the
  source 1:1. Anki-importable (tab-separated) and still human-readable.

This is *not* scoring. We do not adjudicate the learner; "not correct" is merely
the gate that fires card capture (ai-wiki hard rule #2).
"""
from __future__ import annotations

from pathlib import Path

from vault import Vault

CARDS_SUBDIR = "cards"

# Anki import directives, written once as the file header. `#` lines are
# configuration the text importer reads (and skips as notes). Two data columns
# (Front, Back) only — keeping it to exactly the Basic note type's fields means
# Anki auto-maps positionally with zero dialog fiddling, which is the whole point
# (a stray third column is what lets the answer leak into Tags). `#deck:` auto-
# creates/routes into a per-narrative deck instead of dumping into Default.
def _header(slug: str) -> str:
    return (
        "#separator:tab\n"
        "#html:true\n"
        "#notetype:Basic\n"
        f"#deck:{slug}\n"
        "#columns:Front\tBack\n"
    )


def _cards_path(vault: Vault, slug: str) -> Path:
    return vault.root / CARDS_SUBDIR / f"{slug}.tsv"


def _sanitize(field: str) -> str:
    """Make a value safe for a single TSV cell.

    Tabs would break columns; newlines would break the one-note-per-line
    contract. We keep the content readable by turning newlines into <br>
    (rendered because the header sets #html:true).
    """
    return field.replace("\t", "    ").replace("\r\n", "\n").replace("\n", "<br>").strip()


def add_card(vault: Vault, slug: str, front: str, back: str) -> dict:
    """Append one card to the narrative's deck. Creates the deck on first write.

    The deck is 2-col (Front, Back) so Anki import never mis-routes; provenance
    lives in the deck/narrative name, not a fragile third column.

    Parameters
    ----------
    slug   : narrative slug the card came from (deck filename).
    front  : the cue — the question or the description prompting recall.
    back   : the answer — the term / causal explanation.
    """
    front_s, back_s = _sanitize(front), _sanitize(back)
    if not front_s or not back_s:
        return {"ok": False, "error": "front and back are both required"}

    path = _cards_path(vault, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    line = "\t".join([front_s, back_s]) + "\n"
    with path.open("a", encoding="utf-8") as f:
        if new_file:
            f.write(_header(slug))
        f.write(line)

    count = _count_cards(path)
    vault.append_log("card-add", {"slug": slug, "total": count})
    return {
        "ok": True,
        "deck": str(path),
        "added": {"front": front_s, "back": back_s},
        "deck_total": count,
    }


def _count_cards(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(
        1
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    )


def list_cards(vault: Vault, slug: str | None = None) -> dict:
    """Return decks and their cards. Single deck if slug given, else all."""
    cards_dir = vault.root / CARDS_SUBDIR
    if not cards_dir.exists():
        return {"decks": [], "total": 0}

    slugs = [slug] if slug else sorted(p.stem for p in cards_dir.glob("*.tsv"))
    decks = []
    total = 0
    for s in slugs:
        path = _cards_path(vault, s)
        if not path.exists():
            continue
        cards = []
        for ln in path.read_text(encoding="utf-8").splitlines():
            if not ln.strip() or ln.startswith("#"):
                continue
            parts = ln.split("\t")
            cards.append(
                {
                    "front": parts[0] if len(parts) > 0 else "",
                    "back": parts[1] if len(parts) > 1 else "",
                }
            )
        decks.append({"slug": s, "path": str(path), "count": len(cards), "cards": cards})
        total += len(cards)
    return {"decks": decks, "total": total}
