#!/usr/bin/env python3
"""Vault I/O primitives for ai-wiki (v5).

Handles file system layout per SPEC §13.1:
  ~/ai-wiki/
    narratives/   sources/   [notes/]
    index.md    log.md    manifest.json

v5 paradigm (2026-04-24) removed: concepts/, entities/, maps/, hot-cache.md
(content no longer generated). `notes/` is created lazily on first write.

reps/ + ignore.json were removed in 2026-04-30 cleanup (carried over from
v1 drill / extraction features, never accessed under v5).

Design notes:
- Frontmatter parse is stdlib-only (no PyYAML dep). Supports flat key: value
  and list values (as `[a, b, c]` inline arrays). No nested dicts yet.
- Wikilinks recognize `[[page-slug]]` and `[[page-slug|display alias]]` forms.
- Slug generation: lowercase, spaces → hyphens, non-ASCII retained (JP page OK
  but prefer English slug for primary).
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ---------- Path conventions ----------

DEFAULT_VAULT = Path(os.environ.get("AI_WIKI_ROOT", Path.home() / "ai-wiki"))

SUBDIRS = ("narratives", "sources")
OPTIONAL_SUBDIRS = ("notes",)  # created lazily

PAGE_KINDS = ("narrative", "source", "note")
_KIND_TO_SUBDIR = {
    "narrative": "narratives",
    "source": "sources",
    "note": "notes",
}


# ---------- Frontmatter parse (stdlib only) ----------

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.DOTALL)
_KV_RE = re.compile(r"^([A-Za-z_][\w\-]*)\s*:\s*(.*)$")


def _parse_scalar(raw: str) -> str | int | bool | list[str] | None:
    """Parse a YAML-lite scalar value."""
    s = raw.strip()
    if not s:
        return None
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [x.strip().strip('"').strip("'") for x in inner.split(",")]
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    if s.isdigit():
        return int(s)
    if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        return s[1:-1]
    return s


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (metadata_dict, body_without_frontmatter)."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta_raw, body = m.group(1), m.group(2)
    meta: dict = {}
    for line in meta_raw.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        mk = _KV_RE.match(line)
        if not mk:
            continue
        key, val = mk.group(1), mk.group(2)
        meta[key] = _parse_scalar(val)
    return meta, body


def _format_scalar(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(str(x) for x in v) + "]"
    return str(v)


def dump_frontmatter(meta: dict, body: str) -> str:
    """Serialize a page with `---` delimited frontmatter and markdown body."""
    if not meta:
        return body
    lines = ["---"]
    for k, v in meta.items():
        lines.append(f"{k}: {_format_scalar(v)}")
    lines.append("---")
    if body and not body.startswith("\n"):
        lines.append("")
    return "\n".join(lines) + ("\n" + body.lstrip("\n") if body else "\n")


# ---------- Slug + wikilink ----------

_SLUG_STRIP_RE = re.compile(r"[^\w\s\-]+", re.UNICODE)
_WIKILINK_RE = re.compile(r"\[\[([^\[\]|]+?)(?:\|([^\[\]]+?))?\]\]")


def slugify(text: str) -> str:
    """Convert free text into a kebab-case slug.

    Keeps non-ASCII letters (Japanese etc.). Strips punctuation, collapses
    whitespace to hyphens, lowercases ASCII.
    """
    s = text.strip()
    s = _SLUG_STRIP_RE.sub("", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s.lower() if s.isascii() else s


def parse_wikilinks(body: str) -> list[tuple[str, str | None]]:
    """Return list of (target_slug, display_or_None) pairs found in body."""
    out: list[tuple[str, str | None]] = []
    for m in _WIKILINK_RE.finditer(body):
        target = m.group(1).strip()
        display = m.group(2).strip() if m.group(2) else None
        out.append((target, display))
    return out


# ---------- Page dataclasses ----------


@dataclass
class Page:
    kind: str  # narrative | source | note
    slug: str
    meta: dict = field(default_factory=dict)
    body: str = ""

    def to_text(self) -> str:
        return dump_frontmatter(self.meta, self.body)

    def wikilinks(self) -> list[tuple[str, str | None]]:
        return parse_wikilinks(self.body)


# ---------- Vault ----------


class Vault:
    """File system interface for the ai-wiki vault (v5).

    Parameters
    ----------
    root
        Vault root path. Defaults to $AI_WIKI_ROOT or ~/ai-wiki/.
    create_if_missing
        If True, create subdirectories on first access.
    """

    def __init__(self, root: Path | str | None = None, create_if_missing: bool = True):
        self.root = Path(root) if root else DEFAULT_VAULT
        if create_if_missing:
            self.ensure_structure()

    # -- structure --

    def ensure_structure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for sub in SUBDIRS:
            (self.root / sub).mkdir(exist_ok=True)
        for aux in ("index.md", "log.md"):
            p = self.root / aux
            if not p.exists():
                p.write_text("", encoding="utf-8")
        manifest = self.root / "manifest.json"
        if not manifest.exists():
            manifest.write_text("{}", encoding="utf-8")

    # -- page I/O --

    def _page_path(self, kind: str, slug: str) -> Path:
        if kind not in PAGE_KINDS:
            raise ValueError(f"unknown page kind: {kind}")
        return self.root / _KIND_TO_SUBDIR[kind] / f"{slug}.md"

    def read(self, kind: str, slug: str) -> Page | None:
        p = self._page_path(kind, slug)
        if not p.exists():
            return None
        text = p.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        return Page(kind=kind, slug=slug, meta=meta, body=body)

    def write(self, page: Page) -> Path:
        p = self._page_path(page.kind, page.slug)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(page.to_text(), encoding="utf-8")
        return p

    def exists(self, kind: str, slug: str) -> bool:
        return self._page_path(kind, slug).exists()

    def list_pages(self, kind: str) -> list[str]:
        """Return slugs for all pages of a given kind."""
        if kind not in PAGE_KINDS:
            raise ValueError(f"unknown page kind: {kind}")
        d = self.root / _KIND_TO_SUBDIR[kind]
        if not d.exists():
            return []
        return sorted(p.stem for p in d.glob("*.md") if not p.name.startswith("."))

    # -- auxiliary files --

    def read_manifest(self) -> dict:
        p = self.root / "manifest.json"
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            return {}

    def write_manifest(self, data: dict) -> None:
        p = self.root / "manifest.json"
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def append_log(self, op: str, details: dict | None = None) -> None:
        """Append a line to log.md."""
        p = self.root / "log.md"
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        summary = " | ".join(f"{k}={v}" for k, v in (details or {}).items())
        line = f"{ts} | {op} | {summary}\n"
        with p.open("a", encoding="utf-8") as f:
            f.write(line)

