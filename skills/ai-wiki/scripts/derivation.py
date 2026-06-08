#!/usr/bin/env python3
"""Derivation spine operations (procedural-knowledge layer).

A *derivation* is the procedural counterpart of a narrative. Where a narrative
captures declarative understanding (what / why) as a working-hypothesis tree, a
derivation captures a *procedure* — the ordered, subgoal-labeled chain of steps
that takes a goal expression to its result (an algebraic derivation, a proof, a
worked calculation).

Stored under `derivations/<slug>.md`. Two provenance inputs, distinct roles
(see SKILL.md "Derivation layer"):
- **source** gives the step *content* (the actual algebra). It is the single
  source of truth and the verification target. A derivation is NOT built from a
  narrative tree, because the tree (1-3 sentence nodes) does not contain the
  algebra — building from it would hallucinate steps.
- **narrative (anchor)** gives the subgoal *structure* (the conceptual chunking)
  and the wikilink anchor, so the procedure stays bound to understanding.

Responsibilities (deterministic only): validate frontmatter + structure, check
the `[⇣n]` step chain is contiguous, regenerate `derivations/_index.md`.
Non-responsibilities: writing spine content (LLM/user), verifying math (judge).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from vault import Page, Vault

# ---------- Step marker ----------

# `[⇣n]` = derivation step n (the procedural counterpart of narrative symbols).
# Numeric suffix, so it is intentionally NOT in narrative.py's fixed bracketed
# set (whose regex rejects word chars and would never match `⇣1`). Derivations
# are a separate page kind and never run through the narrative validator.
STEP_RE = re.compile(r"\[⇣(\d+)\]")

# `[~]` carried over from narratives = an unverified / model-inferred step
# (the source did not state it; generated and not confirmed by the judge).
UNVERIFIED_TOKEN = "[~]"

_REQUIRED_FRONTMATTER = (
    "type", "slug", "title", "anchor", "source", "tier", "verified",
    "created", "updated",
)

# Routing tiers (see derivation_scan / derivation_draft).
VALID_TIERS = ("T1", "cross", "gen")
# T1   = harvested: full steps present in the source (safe, no hallucination).
# cross= steps live in a *different* source (deferred "see textbook X").
# gen  = source skipped the derivation ("omitted", "too tedious"); LLM-generated,
#        must be judge-verified; unconfirmed steps marked [~].

_GOAL_HEADER_RE = re.compile(r"^##\s+GOAL\s*$", re.MULTILINE)
_SPINE_HEADER_RE = re.compile(r"^##\s+SPINE\s*$", re.MULTILINE)


@dataclass
class ValidationReport:
    slug: str
    errors: list[str]
    warnings: list[str]
    tier: str
    verified: bool

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "tier": self.tier,
            "verified": self.verified,
            "ok": self.ok,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def validate_frontmatter(meta: dict, slug: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for key in _REQUIRED_FRONTMATTER:
        if key not in meta or meta[key] in (None, ""):
            errors.append(f"missing required frontmatter field: {key}")
    kind = meta.get("type")
    if kind is not None and kind != "derivation":
        errors.append(f"frontmatter 'type' must be 'derivation', got {kind!r}")
    slug_meta = meta.get("slug")
    if slug_meta is not None and slug_meta != slug:
        errors.append(f"frontmatter 'slug' ({slug_meta!r}) != filename ({slug!r})")
    tier = meta.get("tier")
    if tier is not None and tier not in VALID_TIERS:
        warnings.append(f"tier should be one of {VALID_TIERS}, got {tier!r}")
    return errors, warnings


def extract_steps(body: str) -> list[int]:
    """Return the ordered list of step numbers found via `[⇣n]` markers."""
    return [int(m.group(1)) for m in STEP_RE.finditer(body)]


def check_step_chain(steps: list[int]) -> list[str]:
    """A spine must have ≥1 step, numbered contiguously from 1 in order.

    The chain is the whole point: procedural knowledge is an ordered transform,
    not an unordered bag (atomizing it kills transfer). So we enforce 1,2,3,…
    """
    errors: list[str] = []
    if not steps:
        errors.append("no `[⇣n]` steps found in `## SPINE`")
        return errors
    expected = list(range(1, len(steps) + 1))
    if steps != expected:
        errors.append(
            f"step chain not contiguous 1..N in order: got {steps}, expected {expected}"
        )
    return errors


def has_goal_section(body: str) -> bool:
    return bool(_GOAL_HEADER_RE.search(body))


def has_spine_section(body: str) -> bool:
    return bool(_SPINE_HEADER_RE.search(body))


def validate_page(page: Page) -> ValidationReport:
    errors, warnings = validate_frontmatter(page.meta, page.slug)
    if not has_goal_section(page.body):
        errors.append("missing '## GOAL' section")
    if not has_spine_section(page.body):
        errors.append("missing '## SPINE' section")
    else:
        errors.extend(check_step_chain(extract_steps(page.body)))

    verified = bool(page.meta.get("verified"))
    has_unverified = UNVERIFIED_TOKEN in page.body
    # Integrity: a spine flagged verified must not still carry [~] unverified
    # steps; a spine carrying [~] must not claim verified=true.
    if verified and has_unverified:
        warnings.append(
            "frontmatter verified=true but body still contains [~] unverified steps"
        )
    if not verified and page.meta.get("tier") == "T1":
        warnings.append("tier=T1 (harvested from source) but verified=false")

    tier = str(page.meta.get("tier") or "unknown")
    return ValidationReport(
        slug=page.slug, errors=errors, warnings=warnings,
        tier=tier, verified=verified,
    )


# ---------- Forest operations ----------


def list_derivations(vault: Vault) -> list[str]:
    return [s for s in vault.list_pages("derivation") if not s.startswith("_")]


def read_derivation(vault: Vault, slug: str) -> Page | None:
    return vault.read("derivation", slug)


def validate_all(vault: Vault) -> list[ValidationReport]:
    reports: list[ValidationReport] = []
    for slug in list_derivations(vault):
        page = read_derivation(vault, slug)
        if page is None:
            continue
        reports.append(validate_page(page))
    return reports


def forest_index_markdown(vault: Vault) -> str:
    """Generate `derivations/_index.md`, grouped by anchor narrative."""
    lines: list[str] = [
        "<!-- auto-generated by dispatcher.py derivations. Do not edit manually. -->",
        "",
        "# Derivation index",
        "",
        f"_Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC_",
        "",
    ]
    by_anchor: dict[str, list[Page]] = {}
    for slug in list_derivations(vault):
        page = read_derivation(vault, slug)
        if page is None:
            continue
        anchor = str(page.meta.get("anchor") or "(no anchor)")
        by_anchor.setdefault(anchor, []).append(page)

    for anchor in sorted(by_anchor):
        lines.append(f"## [[{anchor}]]")
        lines.append("")
        for page in by_anchor[anchor]:
            title = str(page.meta.get("title") or page.slug)
            tier = str(page.meta.get("tier") or "")
            verified = "✓" if page.meta.get("verified") else "✗"
            steps = len(extract_steps(page.body))
            lines.append(
                f"- [[{page.slug}]] {title} — tier:{tier} verified:{verified} steps:{steps}"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def write_forest_index(vault: Vault) -> Path:
    path = vault.root / "derivations" / "_index.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(forest_index_markdown(vault), encoding="utf-8")
    return path


def derivations_summary(vault: Vault) -> dict:
    reports = validate_all(vault)
    index_path = write_forest_index(vault)
    vault.append_log(
        "derivations",
        {
            "count": len(reports),
            "errors": sum(len(r.errors) for r in reports),
            "warnings": sum(len(r.warnings) for r in reports),
        },
    )
    return {
        "vault_root": str(vault.root),
        "index_path": str(index_path.relative_to(vault.root)),
        "count": len(reports),
        "derivations": [r.to_dict() for r in reports],
    }
