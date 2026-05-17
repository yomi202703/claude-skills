#!/usr/bin/env python3
"""Narrative tree operations.

Handles ai-wiki's v3 narrative trees stored under `narratives/`.
Narratives are problem-driven, single-spine, working-hypothesis trees.
See SPEC §11 and REQUIREMENTS §12.11-§12.14.

Responsibilities (deterministic only):
- Validate narrative frontmatter and structure
- Lint body for symbol dictionary compliance
- Generate forest index (`narratives/_index.md`)

Non-responsibilities:
- Writing narrative content (that is the LLM / user's job)
- Resolving cross-tree wikilinks (concept-level concerns belong in lint/pillars)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from vault import Page, Vault

# ---------- Fixed symbol dictionary (SPEC §11.3) ----------

# Bracketed markers that appear as [X] tokens inside tree bodies.
FIXED_BRACKETED_SYMBOLS: frozenset[str] = frozenset(
    {"?", "★", "◯", "✕", "∥", "⛔", "!", "∴", "⤴", "⤵", "⟳", "↺",
     "??", "⊂", "⊕"}
)

# Additional edge markers allowed inline (not bracketed).
FIXED_INLINE_SYMBOLS: frozenset[str] = frozenset({"→", "⇒"})

# Regex: bracket-enclosed 1-2 chars that are neither ASCII alphanumeric
# nor whitespace. Matches `[?]`, `[★]`, `[◎]`, etc., but NOT `[1]`, `[abc]`.
# We catch ALL such tokens, then compare against the allowed set.
_BRACKET_SYMBOL_RE = re.compile(r"\[([^\w\s\[\]]{1,2})\]")

# Regex: narrative frontmatter required fields.
_REQUIRED_FRONTMATTER = ("type", "slug", "title", "status", "created", "updated")

# Regex: forbidden frontmatter fields (working-hypothesis principle).
_FORBIDDEN_FRONTMATTER = (
    "source_lectures",
    "source_pages_total",
    "current_coverage",
    "source_kind",
    "source_refs",
    "arxiv_refs",
    "provenance",
)

# ROOT section detection: looks for a level-2 header containing "ROOT"
# (case-insensitive), typically `## ROOT` in our template.
_ROOT_HEADER_RE = re.compile(r"^##\s+ROOT\s*$", re.MULTILINE)

# Legend block detection: `## 記法` header followed by a code block.
_LEGEND_HEADER_RE = re.compile(r"^##\s+記法\s*$", re.MULTILINE)


# ---------- Validation ----------


@dataclass
class ValidationReport:
    slug: str
    errors: list[str]
    warnings: list[str]
    status: str  # "stable" | "pilot" | "frozen" | "unknown"

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "status": self.status,
            "ok": self.ok,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def validate_frontmatter(meta: dict, slug: str) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for frontmatter of a narrative."""
    errors: list[str] = []
    warnings: list[str] = []
    for key in _REQUIRED_FRONTMATTER:
        if key not in meta or meta[key] in (None, ""):
            errors.append(f"missing required frontmatter field: {key}")
    kind = meta.get("type")
    if kind is not None and kind != "narrative":
        errors.append(f"frontmatter 'type' must be 'narrative', got {kind!r}")
    slug_meta = meta.get("slug")
    if slug_meta is not None and slug_meta != slug:
        errors.append(f"frontmatter 'slug' ({slug_meta!r}) does not match filename ({slug!r})")
    status = meta.get("status")
    if status is not None and status not in ("pilot", "stable", "frozen"):
        warnings.append(f"status should be pilot|stable|frozen, got {status!r}")
    for key in _FORBIDDEN_FRONTMATTER:
        if key in meta:
            warnings.append(
                f"frontmatter field {key!r} violates working-hypothesis principle (§12.14)"
            )
    return errors, warnings


def detect_undefined_symbols(body: str) -> list[str]:
    """Return list of bracketed symbol tokens in body that are not in the
    fixed dictionary. Preserves order of first appearance, dedupes.
    """
    seen: set[str] = set()
    out: list[str] = []
    for m in _BRACKET_SYMBOL_RE.finditer(body):
        sym = m.group(1)
        if sym in FIXED_BRACKETED_SYMBOLS:
            continue
        if sym in seen:
            continue
        seen.add(sym)
        out.append(sym)
    return out


def has_root_section(body: str) -> bool:
    return bool(_ROOT_HEADER_RE.search(body))


def has_legend_section(body: str) -> bool:
    return bool(_LEGEND_HEADER_RE.search(body))


def validate_page(page: Page) -> ValidationReport:
    """Run all narrative checks on a Page object."""
    errors, warnings = validate_frontmatter(page.meta, page.slug)
    if not has_root_section(page.body):
        errors.append("missing '## ROOT' section")
    if not has_legend_section(page.body):
        warnings.append("missing '## 記法' legend block (recommended by SPEC §11.5)")
    undefined = detect_undefined_symbols(page.body)
    if undefined:
        warnings.append(
            "undefined bracketed symbols (outside fixed dictionary): "
            + ", ".join(f"[{s}]" for s in undefined)
        )
    status = str(page.meta.get("status") or "unknown")
    return ValidationReport(slug=page.slug, errors=errors, warnings=warnings, status=status)


# ---------- Forest operations ----------


def list_narratives(vault: Vault) -> list[str]:
    """Return slugs of all narratives in the vault (sorted).

    Excludes system files with `_` prefix (e.g., `_index.md`).
    """
    return [s for s in vault.list_pages("narrative") if not s.startswith("_")]


def read_narrative(vault: Vault, slug: str) -> Page | None:
    return vault.read("narrative", slug)


def validate_all(vault: Vault) -> list[ValidationReport]:
    reports: list[ValidationReport] = []
    for slug in list_narratives(vault):
        page = read_narrative(vault, slug)
        if page is None:
            continue
        reports.append(validate_page(page))
    return reports


def forest_index_markdown(vault: Vault) -> str:
    """Generate the markdown for `narratives/_index.md`.

    Output is flat (no hierarchy). Each narrative is listed with wikilink,
    title, and status.
    """
    lines: list[str] = [
        "<!-- auto-generated by /wiki-narratives. Do not edit manually. -->",
        "",
        "# Narrative forest index",
        "",
        f"_Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC_",
        "",
        "## 列挙",
        "",
    ]
    for slug in list_narratives(vault):
        if slug.startswith("_"):
            continue  # skip _index itself
        page = read_narrative(vault, slug)
        if page is None:
            continue
        title = str(page.meta.get("title") or slug)
        status = str(page.meta.get("status") or "")
        status_tag = f" ({status})" if status else ""
        lines.append(f"- [[{slug}]] {title}{status_tag}")
    lines.append("")  # trailing newline
    return "\n".join(lines)


def write_forest_index(vault: Vault) -> Path:
    path = vault.root / "narratives" / "_index.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(forest_index_markdown(vault), encoding="utf-8")
    return path


# ---------- Top-level command ----------


def narratives_summary(vault: Vault) -> dict:
    """Produce a JSON summary: list + validation + regenerated index path."""
    reports = validate_all(vault)
    slugs = [r.slug for r in reports]
    index_path = write_forest_index(vault)
    vault.append_log(
        "narratives",
        {
            "count": len(slugs),
            "errors": sum(len(r.errors) for r in reports),
            "warnings": sum(len(r.warnings) for r in reports),
        },
    )
    return {
        "vault_root": str(vault.root),
        "index_path": str(index_path.relative_to(vault.root)),
        "count": len(slugs),
        "narratives": [r.to_dict() for r in reports],
    }
