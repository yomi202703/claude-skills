"""Tests for card capture (cards.py)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cards as mod_cards  # noqa: E402
from vault import Vault  # noqa: E402


def _vault(tmp_path) -> Vault:
    return Vault(root=tmp_path / "vault")


def test_add_card_creates_deck_with_header(tmp_path):
    v = _vault(tmp_path)
    res = mod_cards.add_card(v, "lec6", "問い？", "答え")
    assert res["ok"] is True
    assert res["deck_total"] == 1
    deck = Path(res["deck"])
    text = deck.read_text(encoding="utf-8")
    assert text.startswith("#separator:tab")
    assert "#notetype:Basic" in text
    assert "#deck:lec6" in text
    assert "#columns:Front\tBack" in text
    # exactly 2 columns (one tab) on the data line
    assert "問い？\t答え\n" in text


def test_append_only_no_dedup(tmp_path):
    """Identical cards must both persist — append-only by design."""
    v = _vault(tmp_path)
    mod_cards.add_card(v, "lec6", "Q", "A")
    res = mod_cards.add_card(v, "lec6", "Q", "A")
    assert res["deck_total"] == 2


def test_multiline_back_becomes_br(tmp_path):
    v = _vault(tmp_path)
    res = mod_cards.add_card(v, "lec6", "Q", "a\nb\nc")
    assert res["added"]["back"] == "a<br>b<br>c"
    # one logical card = one physical line (after the 3 header lines)
    lines = Path(res["deck"]).read_text(encoding="utf-8").splitlines()
    assert sum(1 for ln in lines if not ln.startswith("#")) == 1


def test_tabs_in_field_do_not_break_columns(tmp_path):
    v = _vault(tmp_path)
    mod_cards.add_card(v, "lec6", "a\tb", "c\td")
    listing = mod_cards.list_cards(v, "lec6")
    card = listing["decks"][0]["cards"][0]
    assert card["front"] == "a    b"
    assert card["back"] == "c    d"


def test_missing_field_rejected(tmp_path):
    v = _vault(tmp_path)
    assert mod_cards.add_card(v, "lec6", "", "A")["ok"] is False
    assert mod_cards.add_card(v, "lec6", "Q", "  ")["ok"] is False


def test_list_all_decks(tmp_path):
    v = _vault(tmp_path)
    mod_cards.add_card(v, "lec6", "Q1", "A1")
    mod_cards.add_card(v, "lec7", "Q2", "A2")
    res = mod_cards.list_cards(v)
    assert res["total"] == 2
    assert {d["slug"] for d in res["decks"]} == {"lec6", "lec7"}


def test_list_empty_when_no_cards_dir(tmp_path):
    v = _vault(tmp_path)
    assert mod_cards.list_cards(v) == {"decks": [], "total": 0}


