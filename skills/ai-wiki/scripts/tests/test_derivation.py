"""Tests for the deterministic parts of the derivation layer.

LLM steps (scan extraction, spine generation, judge verification) are not
exercised here; the structural guarantees live in the validator + the
deterministic skip-marker sweep + tier routing, so those are what we pin down.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import derivation as dv  # noqa: E402
import derivation_scan as ds  # noqa: E402
from vault import Page  # noqa: E402


# ---------- validator ----------

GOOD_BODY = """## GOAL

E[β̂₁] = β₁ + β₂ s_XW/s_X²

## SPINE

[⇣1] 出発点 → β̂₁ = β₁ + Σ(Xᵢ−X̄)uᵢ*/Σ(Xᵢ−X̄)²
[⇣2] 代入し3項に分解 → uᵢ*=β₂Wᵢ+uᵢ を代入
[⇣3] 中心化 → Σ(Xᵢ−X̄)Wᵢ = Σ(Xᵢ−X̄)(Wᵢ−W̄)
[⇣4] 期待値を取る → E[β̂₁] = β₁ + β₂ s_XW/s_X²
"""

GOOD_META = {
    "type": "derivation", "slug": "omv-bias", "title": "欠落変数バイアス",
    "anchor": "計量経済学基礎-chapter-5", "source": "計量経済学基礎-chapter-5",
    "tier": "T1", "verified": True, "confidence": "high",
    "created": "2026-06-08", "updated": "2026-06-08",
}


def _page(meta, body, slug="omv-bias"):
    return Page(kind="derivation", slug=slug, meta=dict(meta), body=body)


def test_valid_spine_passes():
    r = dv.validate_page(_page(GOOD_META, GOOD_BODY))
    assert r.ok, r.errors
    assert r.tier == "T1"
    assert r.verified is True


def test_step_chain_extracted_in_order():
    assert dv.extract_steps(GOOD_BODY) == [1, 2, 3, 4]


def test_missing_goal_section_errors():
    body = GOOD_BODY.replace("## GOAL", "## NOTGOAL")
    r = dv.validate_page(_page(GOOD_META, body))
    assert not r.ok
    assert any("GOAL" in e for e in r.errors)


def test_missing_spine_section_errors():
    body = "## GOAL\n\nx\n"
    r = dv.validate_page(_page(GOOD_META, body))
    assert not r.ok
    assert any("SPINE" in e for e in r.errors)


def test_noncontiguous_step_chain_errors():
    body = """## GOAL

x

## SPINE

[⇣1] a → b
[⇣3] c → d
"""
    r = dv.validate_page(_page(GOOD_META, body))
    assert not r.ok
    assert any("contiguous" in e for e in r.errors)


def test_missing_frontmatter_field_errors():
    meta = dict(GOOD_META)
    del meta["anchor"]
    r = dv.validate_page(_page(meta, GOOD_BODY))
    assert not r.ok
    assert any("anchor" in e for e in r.errors)


def test_verified_true_with_unverified_token_warns():
    body = GOOD_BODY.rstrip() + "  [~]\n"
    r = dv.validate_page(_page(GOOD_META, body))
    # still structurally valid, but warns about the inconsistency
    assert any("[~]" in w for w in r.warnings)


def test_slug_mismatch_errors():
    r = dv.validate_page(_page(GOOD_META, GOOD_BODY, slug="other"))
    assert not r.ok
    assert any("slug" in e for e in r.errors)


# ---------- scan: deterministic skip-marker sweep ----------


def test_detect_skip_lines_finds_markers():
    body = (
        "重回帰OLSの計算方法は本章末の補足参照。最小化は面倒です。\n"
        "欠落変数バイアスの証明は補足を参照。\n"
        "ここは普通の本文。\n"
        "the rest is left as an exercise.\n"
    )
    skips = ds.detect_skip_lines(body)
    # exactly the three marker-bearing lines are flagged; the plain line is not
    flagged_lines = {s.line_no for s in skips}
    assert flagged_lines == {1, 2, 4}
    markers = {s.marker for s in skips}
    assert any("exercise" in m for m in markers)
    # the plain line (L3) must NOT be flagged
    assert 3 not in flagged_lines


# ---------- scan: tier routing ----------


def test_route_steps_present_is_T1():
    t = ds.Target(result="x", result_present=True, steps_present=True,
                  skip_marker="", anchor_section="")
    ds._route(t)
    assert t.tier == "T1" and t.confidence == "high"


def test_route_cross_source_on_reference_marker():
    t = ds.Target(result="x", result_present=True, steps_present=False,
                  skip_marker="Hansen参照", anchor_section="")
    ds._route(t)
    assert t.tier == "cross"


def test_route_gap_generates_when_skipped():
    t = ds.Target(result="x", result_present=True, steps_present=False,
                  skip_marker="面倒", anchor_section="")
    ds._route(t)
    assert t.tier == "gen" and t.confidence == "low"


# ---------- classify: judge verdicts → tier ----------


def test_classify_all_supported_is_T1():
    import derivation_draft as dd
    v = {1: "supported", 2: "supported"}
    assert dd._classify(v, 2) == ("T1", True, "high")


def test_classify_derived_ok_is_verified_gen():
    import derivation_draft as dd
    v = {1: "supported", 2: "derived_ok"}
    assert dd._classify(v, 2) == ("gen", True, "mid")


def test_classify_unverified_is_unverified_gen():
    import derivation_draft as dd
    v = {1: "supported", 2: "unverified"}
    assert dd._classify(v, 2) == ("gen", False, "low")
