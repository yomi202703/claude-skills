#!/usr/bin/env python3
"""Ingest for v5 — source md → sources/<slug>.md only.

v5 paradigm (2026-04-24): concepts extraction removed (no concepts/ anymore),
ai-digest batch removed (ai-digest is independent now). Ingest writes the
source page as truth, nothing else. Narrative generation is an explicit
separate step (`narrative-draft`).
"""
from __future__ import annotations

import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from vault import Page, Vault, slugify

ARXIV_ID_RE = re.compile(r"^(?:arxiv[:\s])?(\d{4}\.\d{4,5})(?:v\d+)?$", re.IGNORECASE)
ARXIV_API = "http://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom"}


# ---------- Source kind detection ----------


def detect_source_kind(source: str) -> tuple[str, str]:
    """Return (kind, normalized_ref) for a source string.

    Kinds: arxiv | md_path
    """
    m = ARXIV_ID_RE.match(source.strip())
    if m:
        return "arxiv", m.group(1)
    p = Path(source).expanduser()
    if p.exists() and p.suffix == ".md":
        return "md_path", str(p.resolve())
    raise ValueError(f"unknown source kind: {source!r}")


# ---------- Stage 1 fetchers ----------


def fetch_arxiv_metadata(arxiv_id: str) -> dict:
    """Fetch arxiv paper metadata + abstract via arxiv API."""
    url = f"{ARXIV_API}?id_list={arxiv_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "ai-wiki/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    root = ET.fromstring(data)
    entry = root.find("a:entry", NS)
    if entry is None:
        raise RuntimeError(f"no entry for arxiv:{arxiv_id}")
    title_el = entry.find("a:title", NS)
    summary_el = entry.find("a:summary", NS)
    published_el = entry.find("a:published", NS)
    authors: list[str] = []
    for a in entry.findall("a:author", NS):
        name_el = a.find("a:name", NS)
        if name_el is not None and name_el.text:
            authors.append(name_el.text)
    id_el = entry.find("a:id", NS)
    url_abs = (id_el.text or "").strip() if id_el is not None else f"http://arxiv.org/abs/{arxiv_id}"
    return {
        "arxiv_id": arxiv_id,
        "title": " ".join((title_el.text or "").split()) if title_el is not None else "",
        "authors": authors,
        "published": (published_el.text or "")[:10] if published_el is not None else "",
        "abstract": " ".join((summary_el.text or "").split()) if summary_el is not None else "",
        "url": url_abs,
    }


def stage1_arxiv(vault: Vault, arxiv_id: str, ingested_from: str = "manual") -> Page:
    """Fetch and save an arxiv paper as a source page."""
    slug = f"arxiv-{arxiv_id}"
    if vault.exists("source", slug):
        existing = vault.read("source", slug)
        vault.append_log("ingest_noop", {"slug": slug, "reason": "source already present"})
        return existing  # type: ignore[return-value]

    meta_paper = fetch_arxiv_metadata(arxiv_id)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    body_parts = [
        f"# arxiv:{arxiv_id} — {meta_paper['title']}",
        "",
        "## abstract (原文、verbatim)",
        meta_paper["abstract"],
    ]
    page = Page(
        kind="source",
        slug=slug,
        meta={
            "type": "source",
            "slug": slug,
            "source_kind": "arxiv_paper",
            "arxiv_id": arxiv_id,
            "title": meta_paper["title"],
            "authors": meta_paper["authors"],
            "published": meta_paper["published"],
            "url": meta_paper["url"],
            "ingested_at": now,
            "ingested_from": ingested_from,
        },
        body="\n".join(body_parts),
    )
    vault.write(page)

    manifest = vault.read_manifest()
    sources = manifest.setdefault("sources", {})
    sources[slug] = {
        "ingested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ingested_from": ingested_from,
        "status": "raw",
    }
    manifest.setdefault("version", 1)
    manifest["last_ingest"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    vault.write_manifest(manifest)

    vault.append_log("ingest_stage1", {"slug": slug, "kind": "arxiv", "status": "raw"})
    return page


def stage1_md_path(
    vault: Vault,
    path: str,
    ingested_from: str = "manual",
    *,
    slug: str | None = None,
    title: str | None = None,
) -> Page:
    """Save a local .md file as a source page.

    ``slug`` lets a caller tie the source to a known identity (e.g. the narrative
    slug it is being drafted into) instead of the default ``note-<date>-<stem>``,
    which derives from the on-disk filename and is meaningless when the input is
    a temp file. When omitted, the legacy filename-derived slug is used.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    content = p.read_text(encoding="utf-8")
    if slug:
        base = slugify(slug)
    else:
        base = f"note-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-{slugify(p.stem)}"
    slug = base
    if vault.exists("source", slug):
        slug = f"{base}-{int(datetime.now(timezone.utc).timestamp())}"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    meta = {
        "type": "source",
        "slug": slug,
        "source_kind": "note_md",
        "original_path": str(p),
        "ingested_at": now,
        "ingested_from": ingested_from,
    }
    if title:
        meta["title"] = title
    page = Page(
        kind="source",
        slug=slug,
        meta=meta,
        body=content,
    )
    vault.write(page)
    manifest = vault.read_manifest()
    sources = manifest.setdefault("sources", {})
    sources[slug] = {
        "ingested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ingested_from": ingested_from,
        "status": "raw",
    }
    manifest.setdefault("version", 1)
    manifest["last_ingest"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    vault.write_manifest(manifest)
    vault.append_log("ingest_stage1", {"slug": slug, "kind": "md_path", "status": "raw"})
    return page


# ---------- Public API ----------


def ingest_arxiv(vault: Vault, source: str, *, dry_run: bool = False, ingested_from: str = "manual") -> dict:
    """Ingest a single arxiv paper into sources/. v5 contract."""
    kind, ref = detect_source_kind(source)
    if kind != "arxiv":
        raise ValueError(f"expected arxiv reference, got {kind}: {source!r}")
    slug = f"arxiv-{ref}"
    if dry_run:
        return {"source": source, "slug": slug, "kind": "arxiv", "stage": "dry_run"}
    page = stage1_arxiv(vault, ref, ingested_from=ingested_from)
    return {"source": source, "slug": page.slug, "kind": "arxiv", "stage": "raw"}


def ingest(vault: Vault, source: str, **opts) -> dict:
    """Dispatch a source to the correct stage1 function. v5: no extract/resolve."""
    kind, ref = detect_source_kind(source)
    ingested_from = opts.get("ingested_from", "manual")
    if kind == "arxiv":
        page = stage1_arxiv(vault, ref, ingested_from=ingested_from)
    elif kind == "md_path":
        page = stage1_md_path(vault, ref, ingested_from=ingested_from)
    else:  # pragma: no cover
        raise ValueError(f"unsupported kind: {kind}")
    return {"source": source, "slug": page.slug, "kind": kind, "stage": "raw"}


def find_existing_md_source(vault: Vault, path: str | Path) -> str | None:
    """Return the slug of an already-ingested source page that came from the
    same file (matched by absolute ``original_path``), else None.

    Lets callers ingest idempotently — re-running narrative-draft on a source
    that is already in ``sources/`` must not pile up duplicate copies. Matching
    is on the resolved original path stored in the source page's frontmatter.
    """
    target = str(Path(path).expanduser().resolve())
    for slug in vault.list_pages("source"):
        page = vault.read("source", slug)
        if page is None:
            continue
        op = page.meta.get("original_path")
        if op and str(Path(str(op)).expanduser().resolve()) == target:
            return slug
    return None


def ingest_md_if_new(
    vault: Vault,
    path: str | Path,
    *,
    ingested_from: str = "manual",
    slug: str | None = None,
    title: str | None = None,
) -> dict:
    """Idempotently store a local ``.md`` into ``sources/``.

    Returns ``{"slug": <slug>, "reused": bool}``. If a source page already
    records the same ``original_path``, no new page is written and the existing
    slug is returned with ``reused=True``. ``slug``/``title`` are forwarded to
    :func:`stage1_md_path` for first-time ingests so the source can inherit the
    caller's identity instead of a filename-derived ``note-<date>-<stem>`` slug.
    """
    existing = find_existing_md_source(vault, path)
    if existing is not None:
        return {"slug": existing, "reused": True}
    page = stage1_md_path(vault, str(path), ingested_from=ingested_from, slug=slug, title=title)
    return {"slug": page.slug, "reused": False}
