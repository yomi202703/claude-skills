"""Compute pillar structure for v5 — narrative-centric backlink counting.

Counts `[[slug]]` references appearing inside narrative bodies. The `slug`
can be any wikilink target (dead or alive). Frequently-referenced slugs
are pillars — candidates for future note/<slug>.md promotion.

v5 paradigm (2026-04-24): concepts/ and maps/ removed, emerging/decayed
metrics depended on concept frontmatter and are no longer meaningful.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from vault import Vault, parse_wikilinks


def _narrative_wikilink_counts(vault: Vault) -> Counter[str]:
    counts: Counter[str] = Counter()
    for slug in vault.list_pages("narrative"):
        if slug.startswith("_"):
            continue
        page = vault.read("narrative", slug)
        if page is None:
            continue
        for target, _display in parse_wikilinks(page.body):
            counts[target] += 1
    return counts


def compute_pillars(vault: Vault, *, top_n: int = 20) -> dict[str, Any]:
    """Return the backlink-weighted pillar ranking for narrative wikilinks."""
    backlinks = _narrative_wikilink_counts(vault)
    narrative_slugs = {s for s in vault.list_pages("narrative") if not s.startswith("_")}
    note_slugs = set(vault.list_pages("note"))

    top: list[dict[str, Any]] = []
    for slug, n in backlinks.most_common():
        # narratives shouldn't appear as pillars of themselves
        if slug in narrative_slugs:
            continue
        top.append({
            "slug": slug,
            "backlinks": n,
            "has_note": slug in note_slugs,
        })
        if len(top) >= top_n:
            break

    return {"top": top}
