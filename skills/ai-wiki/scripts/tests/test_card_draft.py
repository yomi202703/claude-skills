"""Tests for the deterministic symbol-walk node extractor (card_draft.extract_nodes).

The LLM phrasing step is not tested here; the coverage guarantee lives entirely
in extract_nodes, so that is what we pin down.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import card_draft as cd  # noqa: E402

SAMPLE = """---
title: x
---

intro prose with no symbols, should yield nothing.

## 記法

```
[?]  問題       [★]  採用解
```

## ROOT

```
[?] ROOT: どう移植するか?
   │
   ⛔ 大趣意 = 一人の災難を大勢に
   │
   → 福澤が見聞でこの工夫に出会う
```

## 1. 概念をどう紹介するか

```
[?] 仕組みを載せる語彙が無い
 │
 ├─ [◯] 暫定訳「災難請合」
 │      生涯請合・火災請合の3種
 └─ [★] 「保険」という語の確立
        ∴ 恒の産を作らしむる方便
```

⟳ **だから次の問題**: どんな組織で実体化するのか。

## 2. どの器で実体化するか

```
[?] 二形態が候補になる
 ├─ [◯] 相互扶助
 ├─ ∥ 対立: 相互扶助 ∥ 近代的保険会社
 └─ [✕] 過渡形態の死亡請合規則
```

## 未配送

```
[?] これはカード化されない
```
"""


def _nodes():
    return cd.extract_nodes(SAMPLE)


def test_skips_legend_and_undelivered_sections():
    nodes = _nodes()
    # The [?] under 記法 and under 未配送 must not appear.
    sections = {n.section for n in nodes}
    assert "記法" not in sections
    assert "未配送" not in sections


def test_every_bracket_symbol_becomes_a_node():
    nodes = _nodes()
    # Count bracketed anchors in content sections:
    # ROOT: [?]  (⛔ and → are bare, fold into the [?] node)
    # §1: [?] [◯] [★]
    # §2: [?] [◯] [✕]   (∥ here is bare, not [∥])
    bracket_nodes = [n for n in nodes if n.symbol != "⟳"]
    assert len(bracket_nodes) == 7, [(n.symbol, n.text[:20]) for n in nodes]


def test_transition_line_captured_as_node():
    nodes = _nodes()
    trans = [n for n in nodes if n.symbol == "⟳"]
    assert len(trans) == 1
    assert "どんな組織" in trans[0].text


def test_continuation_lines_fold_into_node():
    nodes = _nodes()
    # ROOT [?] should absorb the bare ⛔ and → continuation lines.
    root = next(n for n in nodes if n.section == "ROOT" and n.symbol == "?")
    assert "大趣意" in root.text
    assert "福澤" in root.text


def test_star_node_absorbs_subbullets():
    nodes = _nodes()
    star = next(n for n in nodes if n.symbol == "★" and n.section.startswith("1"))
    assert "保険" in star.text
    assert "方便" in star.text  # the ∴ continuation line


def test_symbol_token_stripped_from_text():
    nodes = _nodes()
    for n in nodes:
        assert not n.text.lstrip().startswith("[")


def test_sections_are_tracked():
    nodes = _nodes()
    secs = {n.section for n in nodes}
    assert any(s.startswith("1.") for s in secs)
    assert any(s.startswith("2.") for s in secs)
    assert "ROOT" in secs


def test_deterministic():
    assert [n.text for n in cd.extract_nodes(SAMPLE)] == [n.text for n in cd.extract_nodes(SAMPLE)]


def test_empty_body():
    assert cd.extract_nodes("") == []
