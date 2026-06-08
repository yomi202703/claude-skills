"""Tests for v5 refactored core modules (vault, schema, pillars, pipeline, ingest)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

import ingest  # noqa: E402
import pillars as mod_pillars  # noqa: E402
import pipeline as mod_pipeline  # noqa: E402
import schema  # noqa: E402
from vault import PAGE_KINDS, SUBDIRS, Page, Vault  # noqa: E402


# ---------- Vault ----------


@pytest.fixture
def vault(tmp_path) -> Vault:
    return Vault(root=tmp_path / "ai-wiki")


def test_v5_subdirs_only_has_narratives_sources(vault: Vault):
    assert SUBDIRS == ("narratives", "sources")
    for sub in SUBDIRS:
        assert (vault.root / sub).is_dir()


def test_v5_no_reps_or_ignore_aux(vault: Vault):
    """reps/ and ignore.json were removed in 2026-04-30 cleanup."""
    assert not (vault.root / "reps").exists()
    assert not (vault.root / "ignore.json").exists()


def test_v5_removed_kinds_rejected(vault: Vault):
    # derivation (procedural-knowledge layer) added 2026-06; old kinds stay gone
    assert PAGE_KINDS == ("narrative", "source", "note", "derivation")
    with pytest.raises(ValueError, match="unknown page kind"):
        vault.exists("concept", "x")
    with pytest.raises(ValueError, match="unknown page kind"):
        vault.exists("map", "x")
    with pytest.raises(ValueError, match="unknown page kind"):
        vault.exists("entity", "x")


def test_v5_note_kind_is_supported(vault: Vault):
    page = Page(
        kind="note",
        slug="fwl-partial-regression",
        meta={"type": "note", "slug": "fwl-partial-regression"},
        body="Hand-written study note.",
    )
    vault.write(page)
    got = vault.read("note", "fwl-partial-regression")
    assert got is not None
    assert "Hand-written" in got.body
    assert (vault.root / "notes" / "fwl-partial-regression.md").is_file()


def test_v5_source_roundtrip(vault: Vault):
    page = Page(
        kind="source",
        slug="arxiv-2604.99999",
        meta={"type": "source", "slug": "arxiv-2604.99999"},
        body="abstract text",
    )
    vault.write(page)
    assert vault.list_pages("source") == ["arxiv-2604.99999"]


# ---------- Schema (lint / update_index) ----------


def test_v5_lint_stats_only_count_kept_kinds(vault: Vault):
    vault.write(Page(
        kind="narrative", slug="n1",
        meta={"type": "narrative", "slug": "n1"},
        body="[[shared]] [[local]]",
    ))
    vault.write(Page(
        kind="source", slug="s1",
        meta={"type": "source", "slug": "s1"},
        body="",
    ))
    rep = schema.lint(vault)
    assert rep["stats"] == {"narratives": 1, "sources": 1, "notes": 0}


def test_v5_lint_detects_dead_link_from_narrative(vault: Vault):
    vault.write(Page(
        kind="narrative", slug="host",
        meta={"type": "narrative", "slug": "host"},
        body="See [[missing-slug]]",
    ))
    rep = schema.lint(vault)
    dead = [d["to"] for d in rep["dead_links"]]
    assert "missing-slug" in dead


def test_v5_lint_resolved_when_note_exists(vault: Vault):
    vault.write(Page(kind="narrative", slug="host",
                     meta={"type": "narrative", "slug": "host"},
                     body="[[fwl]]"))
    vault.write(Page(kind="note", slug="fwl",
                     meta={"type": "note", "slug": "fwl"},
                     body="body"))
    rep = schema.lint(vault)
    dead = [d["to"] for d in rep["dead_links"]]
    assert "fwl" not in dead


def test_v5_update_index_writes_stats_block(vault: Vault):
    vault.write(Page(kind="narrative", slug="n1",
                     meta={"type": "narrative", "slug": "n1"},
                     body="[[a]] [[b]]"))
    schema.update_index(vault)
    text = (vault.root / "index.md").read_text(encoding="utf-8")
    assert "Wiki Index" in text
    assert "narratives: 1" in text


# ---------- Pillars ----------


def test_v5_pillars_count_narrative_wikilinks_only(vault: Vault):
    vault.write(Page(kind="narrative", slug="n1",
                     meta={"type": "narrative", "slug": "n1"},
                     body="[[ols]] [[ols]] [[fwl]]"))
    vault.write(Page(kind="narrative", slug="n2",
                     meta={"type": "narrative", "slug": "n2"},
                     body="[[ols]]"))
    # Sources should not contribute
    vault.write(Page(kind="source", slug="s1",
                     meta={"type": "source", "slug": "s1"},
                     body="[[zzz]]"))
    result = mod_pillars.compute_pillars(vault)
    top_slugs = {item["slug"]: item["backlinks"] for item in result["top"]}
    assert top_slugs.get("ols") == 3
    assert top_slugs.get("fwl") == 1
    assert "zzz" not in top_slugs  # source wikilinks excluded


def test_v5_pillars_exclude_self_references(vault: Vault):
    # narrative pointing at another narrative: narrative slug should be excluded from pillars
    vault.write(Page(kind="narrative", slug="n1",
                     meta={"type": "narrative", "slug": "n1"},
                     body="link to [[n2]]"))
    vault.write(Page(kind="narrative", slug="n2",
                     meta={"type": "narrative", "slug": "n2"},
                     body=""))
    result = mod_pillars.compute_pillars(vault)
    top_slugs = [item["slug"] for item in result["top"]]
    assert "n2" not in top_slugs


def test_v5_pillars_flags_has_note(vault: Vault):
    vault.write(Page(kind="narrative", slug="n1",
                     meta={"type": "narrative", "slug": "n1"},
                     body="[[fwl]] [[unknown]]"))
    vault.write(Page(kind="note", slug="fwl",
                     meta={"type": "note", "slug": "fwl"},
                     body=""))
    result = mod_pillars.compute_pillars(vault)
    by_slug = {item["slug"]: item for item in result["top"]}
    assert by_slug["fwl"]["has_note"] is True
    assert by_slug["unknown"]["has_note"] is False


# ---------- Pipeline (v5: 3 stage) ----------


def test_v5_pipeline_default_skips_ingest(vault: Vault):
    result = mod_pipeline.run_pipeline(vault)
    stage_names = [s["stage"] for s in result["stages"]]
    assert stage_names == ["ingest", "lint", "narratives"]
    assert result["stages"][0]["skipped"] is True
    assert result["fatal_error"] is None


def test_v5_pipeline_runs_all_stages_ok(vault: Vault):
    result = mod_pipeline.run_pipeline(vault)
    ok_stages = [s for s in result["stages"] if s.get("ok")]
    assert len(ok_stages) == 3


def test_v5_pipeline_logs_entry(vault: Vault):
    mod_pipeline.run_pipeline(vault)
    log = (vault.root / "log.md").read_text(encoding="utf-8")
    assert "pipeline" in log
    assert "stages_run=3" in log


# ---------- Ingest (v5 simplified) ----------


FAKE_ARXIV_META = {
    "arxiv_id": "2604.99999",
    "title": "Fake Paper",
    "authors": ["A", "B"],
    "published": "2026-04-01",
    "abstract": "A fake abstract.",
    "url": "http://arxiv.org/abs/2604.99999",
}


def test_v5_ingest_arxiv_returns_raw_stage(vault: Vault):
    with patch.object(ingest, "fetch_arxiv_metadata", return_value=FAKE_ARXIV_META):
        result = ingest.ingest(vault, "arxiv:2604.99999")
    assert result["kind"] == "arxiv"
    assert result["slug"] == "arxiv-2604.99999"
    assert result["stage"] == "raw"
    assert vault.exists("source", "arxiv-2604.99999")


def test_v5_ingest_md_path_returns_raw_stage(vault: Vault, tmp_path):
    src = tmp_path / "memo.md"
    src.write_text("content", encoding="utf-8")
    result = ingest.ingest(vault, str(src))
    assert result["kind"] == "md_path"
    assert result["slug"].startswith("note-")
    assert result["stage"] == "raw"


def test_v5_detect_source_kind_no_digest_md():
    # v5 removed digest_md detection — regular md paths are md_path only
    with pytest.raises(ValueError):
        ingest.detect_source_kind("nonexistent-file.md")


def test_v5_ingest_arxiv_function(vault: Vault):
    with patch.object(ingest, "fetch_arxiv_metadata", return_value=FAKE_ARXIV_META):
        r = ingest.ingest_arxiv(vault, "arxiv:2604.99999")
    assert r["slug"] == "arxiv-2604.99999"
    assert r["stage"] == "raw"


def test_v5_ingest_arxiv_dry_run_does_not_write(vault: Vault):
    with patch.object(ingest, "fetch_arxiv_metadata") as mock:
        r = ingest.ingest_arxiv(vault, "arxiv:2604.99999", dry_run=True)
    mock.assert_not_called()
    assert r["stage"] == "dry_run"
    assert not vault.exists("source", "arxiv-2604.99999")
