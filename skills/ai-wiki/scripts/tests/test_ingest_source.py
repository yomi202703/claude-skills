"""Tests for idempotent md-source ingestion (ingest_md_if_new)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
import ingest as ingest_mod  # noqa: E402
from vault import Vault  # noqa: E402


@pytest.fixture
def vault(tmp_path) -> Vault:
    return Vault(root=tmp_path / "ai-wiki")


def test_ingest_md_if_new_stores_then_reuses(vault, tmp_path):
    src = tmp_path / "lecture.md"
    src.write_text("# Lecture\n\nbody\n", encoding="utf-8")

    first = ingest_mod.ingest_md_if_new(vault, src)
    assert first["reused"] is False
    slug = first["slug"]
    assert vault.exists("source", slug)

    # Re-ingesting the same path must not create a second copy.
    second = ingest_mod.ingest_md_if_new(vault, src)
    assert second["reused"] is True
    assert second["slug"] == slug
    assert len(vault.list_pages("source")) == 1


def test_ingest_md_if_new_distinct_paths_are_separate(vault, tmp_path):
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text("# A\n\nx\n", encoding="utf-8")
    b.write_text("# B\n\ny\n", encoding="utf-8")
    ra = ingest_mod.ingest_md_if_new(vault, a)
    rb = ingest_mod.ingest_md_if_new(vault, b)
    assert ra["slug"] != rb["slug"]
    assert len(vault.list_pages("source")) == 2


def test_ingest_md_if_new_inherits_caller_slug(vault, tmp_path):
    # A temp filename must not dictate the source slug when the caller knows the
    # real identity (the narrative slug). Without override → filename-derived.
    src = tmp_path / "paper.md"
    src.write_text("# Real Title\n\nbody\n", encoding="utf-8")

    default = ingest_mod.ingest_md_if_new(vault, src)
    assert default["slug"].endswith("-paper")  # note-<date>-paper (legacy)

    # With an explicit slug/title, a *different* file ingests under the caller id.
    src2 = tmp_path / "tmpXYZ.md"
    src2.write_text("# Real Title\n\nbody2\n", encoding="utf-8")
    out = ingest_mod.ingest_md_if_new(
        vault, src2, slug="src-deterministic-control-plane", title="Real Title",
    )
    assert out["reused"] is False
    assert out["slug"] == "src-deterministic-control-plane"  # NOT note-<date>-tmpxyz
    page = vault.read("source", out["slug"])
    assert page is not None
    assert page.meta.get("title") == "Real Title"


def test_ingest_md_if_new_slug_collision_gets_suffixed(vault, tmp_path):
    # Two different files requesting the same caller slug must not clobber.
    a = tmp_path / "a.md"
    b = tmp_path / "b.md"
    a.write_text("# A\n\nx\n", encoding="utf-8")
    b.write_text("# B\n\ny\n", encoding="utf-8")
    ra = ingest_mod.ingest_md_if_new(vault, a, slug="src-dup")
    rb = ingest_mod.ingest_md_if_new(vault, b, slug="src-dup")
    assert ra["slug"] == "src-dup"
    assert rb["slug"] != ra["slug"] and rb["slug"].startswith("src-dup")
    assert len(vault.list_pages("source")) == 2


def test_find_existing_md_source_matches_resolved_path(vault, tmp_path):
    src = tmp_path / "deck.md"
    src.write_text("# D\n\nz\n", encoding="utf-8")
    assert ingest_mod.find_existing_md_source(vault, src) is None
    ingest_mod.ingest_md_if_new(vault, src)
    # A non-normalized but equivalent path still resolves to the same source.
    messy = tmp_path / "sub" / ".." / "deck.md"
    assert ingest_mod.find_existing_md_source(vault, messy) is not None
