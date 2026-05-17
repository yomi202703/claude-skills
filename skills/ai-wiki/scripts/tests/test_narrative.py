"""Tests for narrative.py (offline, no network)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from narrative import (  # noqa: E402
    FIXED_BRACKETED_SYMBOLS,
    ValidationReport,
    detect_undefined_symbols,
    forest_index_markdown,
    has_legend_section,
    has_root_section,
    list_narratives,
    narratives_summary,
    read_narrative,
    validate_all,
    validate_frontmatter,
    validate_page,
    write_forest_index,
)
from vault import Page, Vault  # noqa: E402

# ---------- Fixtures ----------


@pytest.fixture
def vault(tmp_path) -> Vault:
    return Vault(root=tmp_path / "ai-wiki")


MINIMAL_BODY = """\
# テスト narrative

疑いを前提に読む。

## 記法

```
[?]  問題       [★]  採用
```

---

## ROOT

```
[?] テスト問題
```

---

## 1. ステップ

```
[★] 解: foo = bar
```
"""

MINIMAL_META = {
    "type": "narrative",
    "slug": "test-narrative",
    "title": "テスト narrative",
    "status": "pilot",
    "created": "2026-04-23",
    "updated": "2026-04-23",
}


def _write_narrative(vault: Vault, slug: str, meta: dict, body: str) -> None:
    """Helper to write a narrative page."""
    m = dict(meta)
    m["slug"] = slug
    page = Page(kind="narrative", slug=slug, meta=m, body=body)
    vault.write(page)


# ---------- Symbol detection ----------


def test_detect_undefined_symbols_allows_all_fixed():
    body = " ".join(f"[{s}]" for s in FIXED_BRACKETED_SYMBOLS)
    assert detect_undefined_symbols(body) == []


def test_detect_undefined_symbols_catches_unknown():
    body = "[★] ok [◎] bad [✗] bad"
    out = detect_undefined_symbols(body)
    assert "◎" in out
    assert "✗" in out
    assert "★" not in out


def test_detect_undefined_symbols_ignores_regular_brackets():
    # [abc] and [123] and [A] should not be flagged (alphanumeric)
    body = "[abc] [123] [A1] [hello world]"
    assert detect_undefined_symbols(body) == []


def test_detect_undefined_symbols_dedupes():
    body = "[◎] one [◎] two [◎] three"
    out = detect_undefined_symbols(body)
    assert out == ["◎"]


# ---------- Section detection ----------


def test_has_root_section_true():
    assert has_root_section("## ROOT\n\n```\n[?] foo\n```\n") is True


def test_has_root_section_false():
    assert has_root_section("## Intro\n## Header\n") is False


def test_has_root_section_case_sensitive_exact():
    # Requires uppercase ROOT (per template)
    assert has_root_section("## root\n") is False


def test_has_legend_section_true():
    assert has_legend_section("## 記法\n```\n...\n```") is True


def test_has_legend_section_false():
    assert has_legend_section("## 記号辞書\n") is False


# ---------- Frontmatter validation ----------


def test_validate_frontmatter_happy_path():
    errors, warnings = validate_frontmatter(MINIMAL_META, "test-narrative")
    assert errors == []
    assert warnings == []


def test_validate_frontmatter_missing_field():
    meta = dict(MINIMAL_META)
    del meta["title"]
    errors, _ = validate_frontmatter(meta, "test-narrative")
    assert any("title" in e for e in errors)


def test_validate_frontmatter_wrong_type():
    meta = dict(MINIMAL_META)
    meta["type"] = "concept"
    errors, _ = validate_frontmatter(meta, "test-narrative")
    assert any("type" in e for e in errors)


def test_validate_frontmatter_slug_mismatch():
    errors, _ = validate_frontmatter(MINIMAL_META, "different-slug")
    assert any("slug" in e.lower() for e in errors)


def test_validate_frontmatter_unknown_status():
    meta = dict(MINIMAL_META)
    meta["status"] = "wip"
    _, warnings = validate_frontmatter(meta, "test-narrative")
    assert any("status" in w for w in warnings)


def test_validate_frontmatter_forbidden_field_warns():
    meta: dict = dict(MINIMAL_META)
    meta["source_lectures"] = ["LS1"]
    _, warnings = validate_frontmatter(meta, "test-narrative")
    assert any("source_lectures" in w for w in warnings)


# ---------- Full page validation ----------


def test_validate_page_happy_path():
    page = Page(kind="narrative", slug="test-narrative", meta=MINIMAL_META, body=MINIMAL_BODY)
    report = validate_page(page)
    assert report.ok is True
    assert report.errors == []
    assert report.status == "pilot"


def test_validate_page_missing_root_is_error():
    body_no_root = "## 記法\n```\n[?] foo\n```\n"
    page = Page(kind="narrative", slug="test-narrative", meta=MINIMAL_META, body=body_no_root)
    report = validate_page(page)
    assert report.ok is False
    assert any("ROOT" in e for e in report.errors)


def test_validate_page_undefined_symbols_warn():
    body = MINIMAL_BODY + "\n[◎] bad\n"
    page = Page(kind="narrative", slug="test-narrative", meta=MINIMAL_META, body=body)
    report = validate_page(page)
    assert report.ok is True  # errors clean
    assert any("undefined" in w for w in report.warnings)


# ---------- Vault integration ----------


def test_vault_has_narratives_subdir(vault: Vault):
    assert (vault.root / "narratives").is_dir()


def test_vault_narrative_roundtrip(vault: Vault):
    _write_narrative(vault, "foo", MINIMAL_META, MINIMAL_BODY)
    page = vault.read("narrative", "foo")
    assert page is not None
    assert page.kind == "narrative"
    assert page.meta["title"] == "テスト narrative"


def test_list_narratives_empty(vault: Vault):
    assert list_narratives(vault) == []


def test_list_narratives_returns_slugs(vault: Vault):
    _write_narrative(vault, "alpha", MINIMAL_META, MINIMAL_BODY)
    _write_narrative(vault, "beta", MINIMAL_META, MINIMAL_BODY)
    assert list_narratives(vault) == ["alpha", "beta"]


def test_list_narratives_excludes_underscore_system_files(vault: Vault):
    """_index.md and other _-prefixed files are system-owned, not narratives."""
    _write_narrative(vault, "alpha", MINIMAL_META, MINIMAL_BODY)
    # Drop an _index.md (as forest_index_markdown would)
    (vault.root / "narratives" / "_index.md").write_text("dummy", encoding="utf-8")
    assert list_narratives(vault) == ["alpha"]


def test_read_narrative_missing_returns_none(vault: Vault):
    assert read_narrative(vault, "nonexistent") is None


def test_validate_all_reports(vault: Vault):
    _write_narrative(vault, "alpha", MINIMAL_META, MINIMAL_BODY)
    # broken: missing ROOT
    _write_narrative(vault, "broken", MINIMAL_META, "## 記法\n")
    reports = validate_all(vault)
    slugs = {r.slug: r for r in reports}
    assert slugs["alpha"].ok
    assert not slugs["broken"].ok


# ---------- Forest index ----------


def test_forest_index_empty_vault(vault: Vault):
    md = forest_index_markdown(vault)
    assert "Narrative forest index" in md
    assert "## 列挙" in md


def test_forest_index_lists_narratives(vault: Vault):
    _write_narrative(vault, "alpha", MINIMAL_META, MINIMAL_BODY)
    meta_b = dict(MINIMAL_META)
    meta_b["title"] = "Beta タイトル"
    meta_b["status"] = "stable"
    _write_narrative(vault, "beta", meta_b, MINIMAL_BODY)
    md = forest_index_markdown(vault)
    assert "[[alpha]]" in md
    assert "[[beta]]" in md
    assert "Beta タイトル" in md
    assert "(stable)" in md


def test_forest_index_excludes_index_file(vault: Vault):
    # _index.md itself should not appear in its own listing
    _write_narrative(vault, "real", MINIMAL_META, MINIMAL_BODY)
    # simulate having _index already
    (vault.root / "narratives" / "_index.md").write_text("dummy", encoding="utf-8")
    md = forest_index_markdown(vault)
    assert "[[_index]]" not in md
    assert "[[real]]" in md


def test_write_forest_index_creates_file(vault: Vault):
    _write_narrative(vault, "alpha", MINIMAL_META, MINIMAL_BODY)
    path = write_forest_index(vault)
    assert path.exists()
    assert path.name == "_index.md"
    assert "alpha" in path.read_text(encoding="utf-8")


# ---------- Summary command ----------


def test_narratives_summary_structure(vault: Vault):
    _write_narrative(vault, "alpha", MINIMAL_META, MINIMAL_BODY)
    result = narratives_summary(vault)
    assert result["count"] == 1
    assert result["index_path"].endswith("_index.md")
    assert result["narratives"][0]["slug"] == "alpha"
    assert result["narratives"][0]["ok"] is True


def test_narratives_summary_logs_operation(vault: Vault):
    _write_narrative(vault, "alpha", MINIMAL_META, MINIMAL_BODY)
    narratives_summary(vault)
    log = (vault.root / "log.md").read_text(encoding="utf-8")
    assert "narratives" in log


# ---------- ValidationReport to_dict ----------


def test_validation_report_to_dict():
    r = ValidationReport(slug="x", errors=["e"], warnings=["w"], status="pilot")
    d = r.to_dict()
    assert d == {
        "slug": "x",
        "status": "pilot",
        "ok": False,
        "errors": ["e"],
        "warnings": ["w"],
    }
