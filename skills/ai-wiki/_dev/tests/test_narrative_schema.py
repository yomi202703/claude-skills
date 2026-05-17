"""Regression tests for narrative tree schema (SPEC §11).

Anchors the canonical pilot (`_dev/corpus/narrative-pilot.md`) against
the narrative validator. If the validator changes behavior, the golden
baseline under `test_narrative_schema/` diffs.

Also tests forest index generation against the canonical example.
"""
from __future__ import annotations

from pathlib import Path

from narrative import (
    detect_undefined_symbols,
    forest_index_markdown,
    has_legend_section,
    has_root_section,
    validate_page,
)
from vault import Page, Vault, parse_frontmatter


# ---------- Canonical pilot ----------


def _load_pilot(corpus: Path) -> Page:
    text = (corpus / "narrative-pilot.md").read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    return Page(kind="narrative", slug="causal-inference-keio", meta=meta, body=body)


def test_pilot_is_valid(corpus: Path):
    """The canonical pilot must pass all narrative validations."""
    page = _load_pilot(corpus)
    report = validate_page(page)
    assert report.errors == [], f"pilot has errors: {report.errors}"
    assert report.status == "pilot"


def test_pilot_has_all_required_sections(corpus: Path):
    page = _load_pilot(corpus)
    assert has_root_section(page.body)
    assert has_legend_section(page.body)


def test_pilot_uses_only_fixed_symbols(corpus: Path):
    page = _load_pilot(corpus)
    undefined = detect_undefined_symbols(page.body)
    assert undefined == [], f"pilot uses undefined bracketed symbols: {undefined}"


def test_pilot_frontmatter_schema(corpus: Path, data_regression):
    """Golden baseline for pilot frontmatter. Breaks if pilot's metadata
    structure drifts (e.g., someone adds `source_*` fields)."""
    page = _load_pilot(corpus)
    # omit volatile `updated` timestamp
    payload = {k: v for k, v in page.meta.items() if k != "updated"}
    data_regression.check(payload)


def test_pilot_validation_report(corpus: Path, data_regression):
    """Golden baseline for full validation output of the pilot."""
    page = _load_pilot(corpus)
    report = validate_page(page)
    data_regression.check(report.to_dict())


# ---------- Forest index ----------


def test_forest_index_with_pilot(corpus: Path, tmp_path, data_regression):
    """Seeded vault with the pilot produces a stable forest index."""
    vault = Vault(root=tmp_path / "ai-wiki")
    target = vault.root / "narratives" / "causal-inference-keio.md"
    target.write_text(
        (corpus / "narrative-pilot.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    md = forest_index_markdown(vault)
    # strip volatile timestamp line before regression
    lines = [line for line in md.splitlines() if not line.startswith("_Last updated:")]
    data_regression.check({"lines": lines})
