#!/usr/bin/env python3
"""narrative-draft: md source から narrative tree を生成する (v4, SPEC §12)。

size によって single / chunked / hierarchical を自動選択。
各モードで LLM 呼び出し + CoVe + 決定的 validator を経由して vault に書く。

user は kickoff のみ、commit 後の修正は study 中に user が Claude Code へ依頼。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import coverage_qa
import faithfulness as faithfulness_mod
import llm
import narrative
from vault import Page, Vault, slugify

# ---------- thresholds ----------

# Token estimation: chars/2.5 for mixed JP/EN/math (conservative upper bound).
# SPEC §13.6 thresholds.
TOKEN_ESTIMATE_DIVISOR = 2.5
THRESHOLD_SINGLE_TOKENS = 25_000
THRESHOLD_CHUNKED_TOKENS = 75_000


# ---------- dataclasses ----------


@dataclass
class Section:
    level: int                   # 1/2/3 for #/##/###
    title: str
    body: str                    # raw text of section (excluding header line)
    start: int                   # char offset
    children: list["Section"] = field(default_factory=list)

    def full_text(self) -> str:
        """Section body including subsections (recursive)."""
        if not self.children:
            return self.body
        parts = [self.body]
        for c in self.children:
            parts.append(c.render())
        return "\n".join(parts)

    def render(self) -> str:
        header = "#" * self.level + " " + self.title
        return header + "\n" + self.full_text()

    def token_estimate(self) -> int:
        return estimate_tokens(self.full_text() + self.title)


@dataclass
class DraftReport:
    vault_root: str
    source_path: str
    slug: str
    title: str
    strategy: str                # "single" | "chunked" | "hierarchical"
    total_tokens: int
    narratives_written: list[str]
    total_cost_usd: float
    errors: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "vault_root": self.vault_root,
            "source_path": self.source_path,
            "slug": self.slug,
            "title": self.title,
            "strategy": self.strategy,
            "total_tokens_estimated": self.total_tokens,
            "narratives_written": self.narratives_written,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "errors": self.errors,
            "warnings": self.warnings,
        }


# ---------- tokens / markdown parsing ----------


def estimate_tokens(text: str) -> int:
    """Conservative token count (mixed JP/EN/math)."""
    return int(len(text) / TOKEN_ESTIMATE_DIVISOR)


_HEADER_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def parse_markdown_structure(text: str) -> list[Section]:
    """Parse markdown into a nested Section tree based on # levels.

    Returns top-level sections (depth 1) each containing deeper children.
    Content before any header is attached to a synthetic Section with
    title='' and level=0 if non-empty.
    """
    headers: list[tuple[int, int, str]] = []  # (pos, level, title)
    for m in _HEADER_RE.finditer(text):
        headers.append((m.start(), len(m.group(1)), m.group(2).strip()))

    if not headers:
        # Entire text is one synthetic section
        return [Section(level=0, title="", body=text.strip(), start=0)]

    flat: list[Section] = []
    preamble = text[: headers[0][0]].strip()
    if preamble:
        flat.append(Section(level=0, title="(preamble)", body=preamble, start=0))

    for i, (pos, level, title) in enumerate(headers):
        body_start = text.find("\n", pos)
        body_start = body_start + 1 if body_start >= 0 else len(text)
        body_end = headers[i + 1][0] if i + 1 < len(headers) else len(text)
        body = text[body_start:body_end].strip()
        flat.append(Section(level=level, title=title, body=body, start=pos))

    # Build tree by nesting deeper-level sections under shallower ones
    root: list[Section] = []
    stack: list[Section] = []
    for sec in flat:
        if sec.level == 0:
            root.append(sec)
            stack = []
            continue
        while stack and stack[-1].level >= sec.level:
            stack.pop()
        if stack:
            stack[-1].children.append(sec)
        else:
            root.append(sec)
        stack.append(sec)
    return root


# Leading section number on a heading, with optional MinerU "■ " marker:
# "3 Pre-training" / "■ 3.1.2 Data preprocessing" → captures "3" / "3.1.2".
_NUM_PREFIX_RE = re.compile(r"^(?:■\s*)?(\d+(?:\.\d+)*)\s+")
_MARKER_PREFIX_RE = re.compile(r"^■\s*")


def _is_flat_numbered(headings: list[tuple[int, str]]) -> bool:
    """Detect the converter pathology: a nested document collapsed so that
    every heading sits at level-1 `#`.

    Conservative on purpose — only true when there is more than one level-1
    heading AND at least one of them carries a *dotted* section number (N.M),
    which a well-formed source (single `#` title + `##` sections) never has.
    """
    level1 = [t for lvl, t in headings if lvl == 1]
    if len(level1) <= 1:
        return False
    for t in level1:
        m = _NUM_PREFIX_RE.match(t)
        if m and "." in m.group(1):
            return True
    return False


def normalize_heading_levels(text: str) -> tuple[str, bool]:
    """Reconstruct heading hierarchy from section numbers when a converter
    (e.g. MinerU) flattened every heading to level-1 `#`.

    Numbered headings are re-leveled by their numbering depth (``N`` → ``##``,
    ``N.M`` → ``###`` …); the first non-numbered heading becomes the document
    ``#`` title and any later non-numbered heading (Abstract, References, …)
    becomes a ``##`` chapter. The ``■`` marker MinerU prepends is stripped.

    No-op (returns ``changed=False``) unless ``_is_flat_numbered`` fires, so
    well-structured sources pass through untouched. Returns
    ``(normalized_text, changed)``.
    """
    lines = text.splitlines()
    parsed: list[tuple[int, int, str]] = []  # (line_idx, level, title)
    for i, line in enumerate(lines):
        m = _HEADER_RE.match(line)
        if m:
            parsed.append((i, len(m.group(1)), m.group(2).strip()))

    if not _is_flat_numbered([(lvl, t) for _, lvl, t in parsed]):
        return text, False

    title_done = False
    for idx, _lvl, raw in parsed:
        clean = _MARKER_PREFIX_RE.sub("", raw).strip()
        nm = _NUM_PREFIX_RE.match(raw)
        if nm:
            depth = nm.group(1).count(".") + 1   # 1 → major, 2 → sub, …
            lines[idx] = "#" * (depth + 1) + " " + clean  # major → ##
        elif not title_done:
            lines[idx] = "# " + clean                      # document title
            title_done = True
        else:
            lines[idx] = "## " + clean                     # Abstract / References / …

    out = "\n".join(lines)
    if text.endswith("\n"):
        out += "\n"
    return out, True


# Non-content trailing sections (bibliography / front-matter boilerplate) that
# should never become a narrative tree. Matched against a heading title with
# any leading section number / ■ marker stripped, case-insensitively.
_BACK_MATTER_RE = re.compile(
    r"^\s*(?:■\s*)?(?:\d+(?:\.\d+)*\s+)?"
    r"(?:references?|bibliography|acknowledge?ments?|competing\s+interests?|"
    r"conflicts?\s+of\s+interest|open\s+access|funding|author\s+contributions?|"
    r"declarations?|supplementary(?:\s+material)?|参考文献|謝辞|利益相反)\s*$",
    re.IGNORECASE,
)


def _is_back_matter(title: str | None) -> bool:
    return bool(_BACK_MATTER_RE.match(title or ""))


def _strip_back_matter(sections: list[Section]) -> list[Section]:
    """Recursively drop non-content sections (References, Acknowledgements,
    Open Access, …) so they never become trees or contaminate a content tree
    via the tiny-section merge in ``_extract_section_plan``.
    """
    out: list[Section] = []
    for s in sections:
        if _is_back_matter(s.title):
            continue
        if s.children:
            s.children = _strip_back_matter(s.children)
        out.append(s)
    return out


def select_strategy(total_tokens: int) -> str:
    if total_tokens < THRESHOLD_SINGLE_TOKENS:
        return "single"
    if total_tokens < THRESHOLD_CHUNKED_TOKENS:
        return "chunked"
    return "hierarchical"


def _derive_title(text: str, fallback: str) -> str:
    """First `#` heading, else fallback."""
    for m in _HEADER_RE.finditer(text):
        if len(m.group(1)) == 1:
            return m.group(2).strip()
    return fallback


# ---------- frontmatter assembly ----------


def _build_frontmatter(slug: str, title: str, status: str = "pilot") -> dict:
    today = date.today().isoformat()
    return {
        "type": "narrative",
        "slug": slug,
        "title": title,
        "status": status,
        "created": today,
        "updated": today,
    }


def _wrap_as_narrative(body: str, slug: str, title: str) -> Page:
    meta = _build_frontmatter(slug, title)
    return Page(kind="narrative", slug=slug, meta=meta, body=body.strip() + "\n")


# ---------- CoVe ----------


def _cove_verify(vault: Vault, slug: str, draft_body: str) -> tuple[str, float, list[str]]:
    """Run 1 CoVe pass. Returns (possibly_corrected_body, cost, warnings)."""
    result = llm.call_with_template(
        "narrative_cove",
        {"slug": slug, "draft_body": draft_body},
    )
    llm.log_call(vault.append_log, "narrative_cove", slug, result)
    warnings: list[str] = []
    if result.is_error:
        warnings.append(f"CoVe failed: {result.error_message}")
        return draft_body, result.cost_usd, warnings
    text = result.text.strip()
    if text == "NO_CORRECTIONS_NEEDED" or not text:
        return draft_body, result.cost_usd, warnings
    # Anything else is treated as corrected body
    warnings.append("CoVe applied corrections")
    return text, result.cost_usd, warnings


# ---------- validation + commit ----------

# Telltale fragments of LLM self-commentary that occasionally leak into the
# body (e.g. CoVe returning its reasoning instead of only the corrected
# tree). Matched case-insensitively against the text preceding the first
# structural heading.
_META_LEAK_SIGNATURES = (
    # English verifier leak fragments
    "no_fixes", "no_corrections", "returning the", "corrected body",
    "remediated body", "stray line", "stray non-content",
    "violates the output", "checks out against", "out-of-dictionary",
    "principles + dictionary",
    # Japanese verifier leak fragments (CoVe returns its reasoning in JP, e.g.
    # 「検証しました。…違反が 2 点あります: 1. … に修正」). lower() leaves
    # Japanese untouched, so these match as-is.
    "検証しました", "違反が", "違反は", "違反点", "修正版", "修正後",
    "に修正", "辞書外", "の欠落", "修正しました",
    # Master/section generators sometimes announce the body before emitting it,
    # e.g. 「以下が master narrative の本文です（…）」. A legitimate short intro
    # never talks *about* the body, so these announcement markers are safe.
    "本文です", "本文を出力", "を出力します", "narrative の本文",
)

# First real structural heading line (`## ROOT` or `## 記法`) — line-anchored so
# an inline ``## ROOT`` quoted inside leaked prose is not mistaken for the header.
_STRUCT_HEADER_RE = re.compile(r"^##\s+(?:ROOT|記法)\s*$", re.MULTILINE)


def _strip_meta_preamble(body: str) -> tuple[str, bool]:
    """Drop leaked LLM meta-commentary that precedes the narrative tree.

    A legitimate preamble (if present) is a short Japanese intro paragraph.
    If the text before the first ``## 記法``/``## ROOT`` heading carries any
    meta-leak signature, the whole preamble is discarded — a leaked intro is
    not recoverable, and losing it is less harmful than shipping commentary
    into the vault. Returns ``(clean_body, changed)``.
    """
    # Anchor on a real heading *line* (`^## ROOT` / `^## 記法`), not an inline
    # mention — CoVe's leaked commentary often quotes "`## ROOT`" inside its
    # prose, and a substring search would cut there, mid-sentence.
    m = _STRUCT_HEADER_RE.search(body)
    if m is None:
        return body, False
    idx = m.start()
    preamble = body[:idx].lower()
    if any(sig in preamble for sig in _META_LEAK_SIGNATURES):
        return body[idx:].lstrip("\n"), True
    return body, False


def _validate_and_commit(
    vault: Vault,
    slug: str,
    title: str,
    body: str,
) -> tuple[bool, list[str], list[str]]:
    """Wrap body as narrative Page, validate, write if clean. Returns
    (committed, errors, warnings)."""
    body, stripped = _strip_meta_preamble(body)
    extra = ["stripped leaked meta-commentary preamble from body"] if stripped else []
    page = _wrap_as_narrative(body, slug, title)
    report = narrative.validate_page(page)
    if report.errors:
        return False, report.errors, extra + report.warnings
    vault.write(page)
    return True, [], extra + report.warnings


# ---------- single-shot ----------


def _generate_single(
    vault: Vault,
    slug: str,
    title: str,
    source_text: str,
    use_cove: bool,
    *,
    run_coverage_iterate: bool = True,
    coverage_threshold: float = 0.95,
    max_iterations: int = 3,
) -> tuple[str | None, float, list[str], list[str], dict | None]:
    """Generate a single narrative.

    v5-5 flow: initial gen → QuestEval iterate → CoVe final cleanup → commit.

    Returns (slug_written, cost, errors, warnings, coverage_report_dict).
    """
    gen = llm.call_with_template(
        "narrative_single",
        {"slug": slug, "title": title, "source_text": source_text},
    )
    llm.log_call(vault.append_log, "narrative_single", slug, gen)
    if gen.is_error or not gen.text.strip():
        return None, gen.cost_usd, [gen.error_message or "empty output"], [], None
    body = gen.text
    cost = gen.cost_usd
    warnings: list[str] = []
    coverage_dict: dict | None = None

    # --- QuestEval iterative remediation (v5-5) ---
    if run_coverage_iterate:
        iter_result = coverage_qa.iterate_and_fix(
            vault, slug, title, body, source_text,
            coverage_threshold=coverage_threshold,
            max_iterations=max_iterations,
        )
        body = iter_result.final_body
        cost += iter_result.cost_usd
        coverage_dict = iter_result.to_dict()
        if not iter_result.converged:
            warnings.append(
                f"coverage did not converge after {iter_result.iterations_run} iterations "
                f"(final {iter_result.final_coverage.coverage_pct:.1f}%, target {coverage_threshold * 100:.0f}%)"
            )

    # --- CoVe final consistency cleanup ---
    if use_cove:
        body, cove_cost, cove_warn = _cove_verify(vault, slug, body)
        cost += cove_cost
        warnings.extend(cove_warn)

    committed, errs, val_warn = _validate_and_commit(vault, slug, title, body)
    warnings.extend(val_warn)
    if not committed:
        return None, cost, errs, warnings, coverage_dict
    return slug, cost, [], warnings, coverage_dict


# ---------- chunked ----------


def _concat_sections_for_chunked(sections: list[Section]) -> str:
    """Flatten sections into a single text blob for chunked single-call.

    Chunked differs from single only in that we reorganize the source before
    sending (preamble summary) rather than splitting the LLM call. Opus 1M
    context handles up to ~75K tokens easily.
    """
    return "\n\n".join(s.render() for s in sections)


# ---------- hierarchical ----------


def _extract_section_plan(sections: list[Section]) -> list[Section]:
    """Select section boundaries for sub-narrative generation.

    Primary: level-2 (##) sections. If a ## section itself exceeds the
    single-shot threshold, descend to its level-3 children. If a ## is
    too small (< 5K tokens), merge adjacent small ## sections greedily.
    """
    plan: list[Section] = []
    for s in sections:
        if s.level != 2:
            # If top-level is level-1 "#" or preamble, descend once
            if s.level <= 1 and s.children:
                plan.extend(_extract_section_plan(s.children))
            continue
        if s.token_estimate() > THRESHOLD_SINGLE_TOKENS and s.children:
            plan.extend(s.children)
        else:
            plan.append(s)

    # Merge tiny adjacent sections
    merged: list[Section] = []
    for s in plan:
        if merged and merged[-1].token_estimate() + s.token_estimate() < THRESHOLD_SINGLE_TOKENS // 5:
            prev = merged[-1]
            prev.title = prev.title + " + " + s.title
            prev.body = prev.body + "\n\n" + s.render()
        else:
            merged.append(s)
    return merged


def _sub_slug(master_slug: str, section: Section, index: int) -> str:
    title_slug = slugify(section.title) if section.title else f"section-{index}"
    return f"{master_slug}-{title_slug}"[:80]


def _peer_slug(base_slug: str, section: Section, index: int) -> str:
    """Slug for a peer tree: ``<base>-NN-<title-without-leading-number>``.

    The leading section number (if any) becomes a zero-padded ordering prefix
    so the forest index sorts naturally; it is stripped from the title slug to
    avoid a doubled number (``3 Pre-training`` → ``...-03-pre-training``).
    """
    title = section.title or ""
    nm = re.match(r"^\s*(\d+)", title)
    num = f"{int(nm.group(1)):02d}" if nm else f"{index + 1:02d}"
    title_wo_num = re.sub(r"^\s*\d+(?:\.\d+)*\s*", "", title)
    title_slug = slugify(title_wo_num) if title_wo_num.strip() else f"section-{index}"
    return f"{base_slug}-{num}-{title_slug}"[:80]


def _generate_hierarchical(
    vault: Vault,
    master_slug: str,
    master_title: str,
    master_root_hint: str,
    sections: list[Section],
    use_cove: bool,
    *,
    run_coverage_iterate: bool = True,
    coverage_threshold: float = 0.95,
    max_iterations: int = 3,
) -> tuple[list[str], float, list[dict], list[str], list[dict]]:
    """Generate sub-narratives then master. Returns (written_slugs, cost,
    errors, warnings, coverage_reports).

    v5-5 flow per sub-narrative: section gen → QuestEval iterate → CoVe → commit.
    Master narrative skips coverage (navigation hub, no content claims).
    """
    plan = _extract_section_plan(sections)
    written: list[str] = []
    total_cost = 0.0
    errors: list[dict] = []
    warnings: list[str] = []
    coverage_reports: list[dict] = []
    sub_summaries: list[tuple[str, str]] = []  # (slug, title)

    for i, section in enumerate(plan):
        sub_slug = _sub_slug(master_slug, section, i)
        sub_title = section.title or f"{master_title} 章 {i+1}"
        section_source = section.render()
        gen = llm.call_with_template(
            "narrative_section",
            {
                "slug": sub_slug,
                "title": sub_title,
                "master_root": master_root_hint,
                "section_text": section_source,
            },
        )
        llm.log_call(vault.append_log, "narrative_section", sub_slug, gen)
        total_cost += gen.cost_usd
        if gen.is_error or not gen.text.strip():
            errors.append({"slug": sub_slug, "stage": "section_gen", "error": gen.error_message or "empty"})
            continue
        body = gen.text

        # QuestEval iterative remediation per sub-narrative
        if run_coverage_iterate:
            iter_result = coverage_qa.iterate_and_fix(
                vault, sub_slug, sub_title, body, section_source,
                coverage_threshold=coverage_threshold,
                max_iterations=max_iterations,
            )
            body = iter_result.final_body
            total_cost += iter_result.cost_usd
            coverage_reports.append({"slug": sub_slug, **iter_result.to_dict()})
            if not iter_result.converged:
                warnings.append(
                    f"{sub_slug}: coverage did not converge after {iter_result.iterations_run} iterations "
                    f"(final {iter_result.final_coverage.coverage_pct:.1f}%)"
                )

        if use_cove:
            body, cove_cost, cove_warn = _cove_verify(vault, sub_slug, body)
            total_cost += cove_cost
            warnings.extend([f"{sub_slug}: {w}" for w in cove_warn])
        committed, errs, val_warn = _validate_and_commit(vault, sub_slug, sub_title, body)
        warnings.extend([f"{sub_slug}: {w}" for w in val_warn])
        if not committed:
            errors.append({"slug": sub_slug, "stage": "validate", "errors": errs})
            continue
        written.append(sub_slug)
        sub_summaries.append((sub_slug, sub_title))

    # Master narrative
    if sub_summaries:
        sub_list_text = "\n".join(f"- `[[{s}]]` — {t}" for s, t in sub_summaries)
        master_gen = llm.call_with_template(
            "narrative_master",
            {
                "slug": master_slug,
                "title": master_title,
                "master_root": master_root_hint,
                "sub_narratives_list": sub_list_text,
            },
        )
        llm.log_call(vault.append_log, "narrative_master", master_slug, master_gen)
        total_cost += master_gen.cost_usd
        if not master_gen.is_error and master_gen.text.strip():
            master_body = master_gen.text
            if use_cove:
                master_body, cove_cost, cove_warn = _cove_verify(vault, master_slug, master_body)
                total_cost += cove_cost
                warnings.extend([f"{master_slug}: {w}" for w in cove_warn])
            committed, errs, val_warn = _validate_and_commit(
                vault, master_slug, master_title, master_body
            )
            warnings.extend([f"{master_slug}: {w}" for w in val_warn])
            if committed:
                written.append(master_slug)
            else:
                errors.append({"slug": master_slug, "stage": "validate", "errors": errs})
        else:
            errors.append({
                "slug": master_slug,
                "stage": "master_gen",
                "error": master_gen.error_message or "empty",
            })

    return written, total_cost, errors, warnings, coverage_reports


# ---------- peer-split ----------


def _generate_peer(
    vault: Vault,
    base_slug: str,
    master_title: str,
    sections: list[Section],
    use_cove: bool,
    *,
    run_coverage_iterate: bool = True,
    coverage_threshold: float = 0.95,
    max_iterations: int = 3,
) -> tuple[list[str], float, list[dict], list[str], list[dict]]:
    """Generate one independent *peer* tree per major section — no master hub.

    Each section is a self-contained `single`-strategy narrative (the proven
    path), connected to the rest only through `[[slug]]` wikilinks in the
    forest. This suits broad multi-section sources (e.g. survey papers) where
    the chapters are separate topics rather than one shared problem-spine.

    Returns (written_slugs, cost, errors, warnings, coverage_reports).
    """
    plan = _extract_section_plan(sections)
    written: list[str] = []
    total_cost = 0.0
    errors: list[dict] = []
    warnings: list[str] = []
    coverage_reports: list[dict] = []

    for i, section in enumerate(plan):
        peer_slug = _peer_slug(base_slug, section, i)
        peer_title = section.title or f"{master_title} 章 {i + 1}"
        section_source = section.render()
        slug_out, cost, errs, warns, cov = _generate_single(
            vault, peer_slug, peer_title, section_source, use_cove,
            run_coverage_iterate=run_coverage_iterate,
            coverage_threshold=coverage_threshold,
            max_iterations=max_iterations,
        )
        total_cost += cost
        warnings.extend([f"{peer_slug}: {w}" for w in warns])
        if slug_out:
            written.append(slug_out)
        else:
            errors.append({"slug": peer_slug, "stage": "peer", "errors": errs})
        if cov is not None:
            coverage_reports.append({"slug": peer_slug, **cov})

    return written, total_cost, errors, warnings, coverage_reports


# ---------- top-level entry ----------


_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _find_h2_section(body: str, header_text: str) -> tuple[int, int, str, str] | None:
    """Locate a level-2 section by header text.

    Returns (start_offset, end_offset, section_title, section_body_incl_header)
    or None if not found. `end_offset` is the start of the next `##` header or
    end of body. `section_body` includes the `## <title>` line.
    """
    # Try exact match first, then fuzzy (strip whitespace/brackets)
    target = header_text.strip()
    matches = [(m.start(), m.group(1).strip()) for m in _H2_RE.finditer(body)]
    for i, (start, title) in enumerate(matches):
        if title == target or target in title:
            end = matches[i + 1][0] if i + 1 < len(matches) else len(body)
            # include trailing newline trimming
            block = body[start:end].rstrip() + "\n"
            return start, end, title, block
    return None


def narrative_split(
    vault: Vault,
    parent_slug: str,
    section_heading: str,
    *,
    new_slug: str | None = None,
    use_cove: bool = True,
    dry_run: bool = False,
) -> dict:
    """Extract a subtree from an existing narrative into a peer tree.

    The parent narrative loses the subsection body and gains a wikilink
    stub pointing at the new peer. The new peer is created as a
    self-contained narrative (ROOT = the subsection's topic).

    This is deterministic (no LLM) in its core — LLM is only used for the
    optional ROOT problem synthesis of the new peer when the subsection
    lacks a natural root statement.
    """
    parent = vault.read("narrative", parent_slug)
    if parent is None:
        return {"error": f"parent narrative not found: {parent_slug}"}

    located = _find_h2_section(parent.body, section_heading)
    if located is None:
        return {"error": f"section header not found: {section_heading!r}"}
    start, end, section_title, section_block = located

    # Derive new slug
    nslug = new_slug or f"{parent_slug}-{slugify(section_title)}"[:80]
    if (vault.root / "narratives" / f"{nslug}.md").exists():
        return {"error": f"new slug file already exists: {nslug}"}

    if dry_run:
        return {
            "parent_slug": parent_slug,
            "new_slug": nslug,
            "section_title": section_title,
            "section_body_chars": len(section_block),
            "dry_run": True,
        }

    # Build new peer narrative body. Use section_block content as
    # the `## 1. ...` block inside a minimal wrapper.
    new_body = f"""疑いを前提に読む。本 tree は `{parent_slug}` から切り出された peer tree。

## 記法

```
[?]  問題/障害        [★]  採用された解      [◯]  候補解
[✕]  敗れた候補       [∥]  対立関係         [⛔]  制約/前提
[!]  落とし穴         [∴]  結論/破綻条件    [⤴]  異分野/前段からの借用
[⤵]  副作用          [⟳]  次の問題         [↺]  派生
[??] 未解決の問い    [⊂]  適用範囲/限界    [⊕]  統合/収斂
```

---

## ROOT

```
[?] {section_title} — この subtree が扱う問題
```

---

{section_block.strip()}

---

## 未配送

(切り出し元 `{parent_slug}` 参照可。必要に応じて追記)
"""
    new_meta = _build_frontmatter(nslug, section_title, status="pilot")
    new_page = Page(kind="narrative", slug=nslug, meta=new_meta, body=new_body)
    new_report = narrative.validate_page(new_page)
    if new_report.errors:
        return {
            "error": "new narrative validation failed",
            "errors": new_report.errors,
        }
    vault.write(new_page)

    # Replace section in parent with a stub
    stub = f"## {section_title} [切り出し済]\n\n本節は [[{nslug}]] に分離しました。\n\n"
    new_parent_body = parent.body[:start] + stub + parent.body[end:]
    new_parent_meta = dict(parent.meta)
    new_parent_meta["updated"] = date.today().isoformat()
    parent_page = Page(kind="narrative", slug=parent_slug, meta=new_parent_meta, body=new_parent_body)
    parent_report = narrative.validate_page(parent_page)
    if parent_report.errors:
        # roll back new narrative
        (vault.root / "narratives" / f"{nslug}.md").unlink(missing_ok=True)
        return {
            "error": "parent narrative validation failed after split (rolled back)",
            "errors": parent_report.errors,
        }
    vault.write(parent_page)

    vault.append_log(
        "narrative_split",
        {
            "parent": parent_slug,
            "new_peer": nslug,
            "section": section_title,
            "chars_moved": len(section_block),
        },
    )

    return {
        "parent_slug": parent_slug,
        "new_slug": nslug,
        "section_title": section_title,
        "chars_moved": len(section_block),
        "parent_updated": True,
        "new_peer_created": True,
    }


def narrative_draft(
    vault: Vault,
    source_path: str | Path,
    *,
    slug: str | None = None,
    title: str | None = None,
    use_cove: bool = True,
    dry_run: bool = False,
    force_strategy: str | None = None,
    mode: str = "auto",
    run_coverage: bool = True,
    coverage_threshold: float = 0.95,
    max_iterations: int = 3,
    run_faithfulness: bool = False,
    judge_model: str | None = None,
    annotate_inferred: bool = False,
) -> dict:
    """Generate a narrative tree from a markdown source.

    Strict 1 source = 1 tree (REQUIREMENTS §14.1.1 / SPEC §13.4.1) in ``auto``
    mode. ``peer`` mode is the deliberate exception for broad multi-section
    sources (survey papers): it emits one independent peer tree per major
    section instead, connected only by `[[slug]]` wikilinks.

    Parameters
    ----------
    source_path
        Path to a markdown file.
    slug
        Base slug (default: derived from filename).
    title
        Display title (default: first `#` heading or filename).
    use_cove
        Run 1-pass CoVe verification after each LLM generation.
    dry_run
        Parse + classify but make no LLM calls, no file writes.
    force_strategy
        "single" | "chunked" | "hierarchical", override auto-selection
        (ignored when ``mode='peer'``).
    mode
        "auto" (default): size-based single/chunked/hierarchical, one tree per
        source. "peer": one independent peer tree per major section, no master
        hub — for multi-section papers whose chapters are separate topics.
    run_coverage
        After successful commit, run QuestEval-style coverage per sub narrative
        (hierarchical) or on the single narrative (single/chunked). Master
        narrative is excluded from coverage (it's a navigation hub without
        content-level claims). Gap reports written to `~/ai-wiki/.narrative-gaps/`.
    run_faithfulness
        After commit, run the precision-direction check: each tree's atomic
        claims are judged against its own source (diagnostic only, never
        mutates the tree). Surfaces unsupported claims and synthesized edges
        under `~/ai-wiki/.narrative-faithfulness/`.
    judge_model
        Model for the faithfulness judge. Defaults to a *different* model from
        the opus generator (faithfulness.DEFAULT_JUDGE_MODEL) to dodge
        LLM-as-judge self-preference bias.
    """
    path = Path(source_path).expanduser()
    if not path.exists():
        return DraftReport(
            vault_root=str(vault.root),
            source_path=str(path),
            slug=slug or "",
            title=title or "",
            strategy="",
            total_tokens=0,
            narratives_written=[],
            total_cost_usd=0.0,
            errors=[{"error": f"source not found: {path}"}],
        ).to_dict()

    text = path.read_text(encoding="utf-8")
    # Reconstruct heading hierarchy if a converter flattened everything to `#`
    # (e.g. MinerU PDF output). No-op for well-structured sources.
    text, heading_normalized = normalize_heading_levels(text)
    total_tokens = estimate_tokens(text)
    # Drop bibliography / boilerplate so it never becomes (or contaminates) a
    # tree. total_tokens is measured first so strategy thresholds see full size.
    sections = _strip_back_matter(parse_markdown_structure(text))

    base_slug = slug or slugify(path.stem)
    derived_title = title or _derive_title(text, fallback=path.stem)
    strategy = "peer" if mode == "peer" else (force_strategy or select_strategy(total_tokens))

    # Slug conflict check (SPEC §13.4.1, 1 source = 1 tree invariant).
    # narrative-draft creates NEW narratives; overwriting an existing slug
    # silently would violate REQUIREMENTS §14.1.1. User must explicitly
    # delete or pick another slug.
    conflict_slugs: list[str] = []
    if strategy == "peer":
        # Peer mode never writes base_slug itself — only the per-section peers.
        for i, section in enumerate(_extract_section_plan(sections)):
            ps = _peer_slug(base_slug, section, i)
            if vault.exists("narrative", ps):
                conflict_slugs.append(ps)
    else:
        if vault.exists("narrative", base_slug):
            conflict_slugs.append(base_slug)
        if strategy == "hierarchical":
            for i, section in enumerate(_extract_section_plan(sections)):
                sub = _sub_slug(base_slug, section, i)
                if vault.exists("narrative", sub):
                    conflict_slugs.append(sub)
    if conflict_slugs:
        return DraftReport(
            vault_root=str(vault.root),
            source_path=str(path),
            slug=base_slug,
            title=derived_title,
            strategy=strategy,
            total_tokens=total_tokens,
            narratives_written=[],
            total_cost_usd=0.0,
            errors=[{
                "error": "slug conflict: narrative already exists",
                "conflicts": conflict_slugs,
                "hint": "delete the existing narrative(s) or pass --slug <new-name>",
            }],
        ).to_dict()

    # Map each slug that will be written to the source slice it was generated
    # from, so the post-commit faithfulness check can judge each tree against
    # its own source (not the whole document). Master hubs are intentionally
    # absent (no content-level claims to verify).
    slug_to_source: dict[str, str] = {}
    if strategy == "peer":
        for i, section in enumerate(_extract_section_plan(sections)):
            slug_to_source[_peer_slug(base_slug, section, i)] = section.render()
    elif strategy == "hierarchical":
        for i, section in enumerate(_extract_section_plan(sections)):
            slug_to_source[_sub_slug(base_slug, section, i)] = section.render()
    else:  # single / chunked / fallback all generate one tree from full text
        slug_to_source[base_slug] = text

    report = DraftReport(
        vault_root=str(vault.root),
        source_path=str(path),
        slug=base_slug,
        title=derived_title,
        strategy=strategy,
        total_tokens=total_tokens,
        narratives_written=[],
        total_cost_usd=0.0,
    )

    if heading_normalized:
        report.warnings.append(
            "reconstructed heading hierarchy from section numbers "
            "(source had flattened level-1 headings)"
        )

    if dry_run:
        report.warnings.append("dry_run: no LLM calls, no file writes")
        return report.to_dict()

    coverage_reports: list[dict] = []

    if strategy == "peer":
        written, cost, errors, warnings, covs = _generate_peer(
            vault,
            base_slug,
            derived_title,
            sections,
            use_cove,
            run_coverage_iterate=run_coverage,
            coverage_threshold=coverage_threshold,
            max_iterations=max_iterations,
        )
        report.total_cost_usd = cost
        report.narratives_written.extend(written)
        report.errors.extend(errors)
        report.warnings.extend(warnings)
        coverage_reports.extend(covs)

    elif strategy == "single":
        # Use full text (incl. headers) as source
        slug_out, cost, errs, warnings, cov = _generate_single(
            vault, base_slug, derived_title, text, use_cove,
            run_coverage_iterate=run_coverage,
            coverage_threshold=coverage_threshold,
            max_iterations=max_iterations,
        )
        report.total_cost_usd = cost
        report.warnings.extend(warnings)
        if slug_out:
            report.narratives_written.append(slug_out)
        else:
            report.errors.append({"slug": base_slug, "stage": "single", "errors": errs})
        if cov is not None:
            coverage_reports.append({"slug": base_slug, **cov})

    elif strategy == "chunked":
        # Chunked: still single LLM call (Opus 1M ctx), but source is
        # structurally re-rendered for clarity.
        concat = _concat_sections_for_chunked(sections)
        slug_out, cost, errs, warnings, cov = _generate_single(
            vault, base_slug, derived_title, concat, use_cove,
            run_coverage_iterate=run_coverage,
            coverage_threshold=coverage_threshold,
            max_iterations=max_iterations,
        )
        report.total_cost_usd = cost
        report.warnings.extend(warnings)
        if slug_out:
            report.narratives_written.append(slug_out)
        else:
            report.errors.append({"slug": base_slug, "stage": "chunked", "errors": errs})
        if cov is not None:
            coverage_reports.append({"slug": base_slug, **cov})

    elif not _extract_section_plan(sections):
        # Hierarchical was selected (or forced) but the source has no usable
        # level-2 section boundaries — e.g. a converter (MinerU) flattened every
        # heading to a single `#` level. _generate_hierarchical would silently
        # write zero narratives, so fall back to a single chunked call over the
        # whole text rather than returning an empty, error-free no-op.
        report.strategy = "chunked"
        report.warnings.append(
            "hierarchical strategy found no level-2 (##) section boundaries; "
            "falling back to chunked single-call generation"
        )
        concat = _concat_sections_for_chunked(sections)
        slug_out, cost, errs, warnings, cov = _generate_single(
            vault, base_slug, derived_title, concat, use_cove,
            run_coverage_iterate=run_coverage,
            coverage_threshold=coverage_threshold,
            max_iterations=max_iterations,
        )
        report.total_cost_usd = cost
        report.warnings.extend(warnings)
        if slug_out:
            report.narratives_written.append(slug_out)
        else:
            report.errors.append({"slug": base_slug, "stage": "chunked-fallback", "errors": errs})
        if cov is not None:
            coverage_reports.append({"slug": base_slug, **cov})

    else:  # hierarchical
        master_root_hint = derived_title
        written, cost, errors, warnings, covs = _generate_hierarchical(
            vault,
            base_slug,
            derived_title,
            master_root_hint,
            sections,
            use_cove,
            run_coverage_iterate=run_coverage,
            coverage_threshold=coverage_threshold,
            max_iterations=max_iterations,
        )
        report.total_cost_usd = cost
        report.narratives_written.extend(written)
        report.errors.extend(errors)
        report.warnings.extend(warnings)
        coverage_reports.extend(covs)

    # --- Faithfulness pass (precision direction; opt-in) ---
    # Diagnostic only: judges each committed tree's atomic claims against its
    # own source, with a different judge model to dodge self-preference bias.
    # Never mutates the tree. Surfaces unsupported claims + synthesized edges.
    faithfulness_reports: list[dict] = []
    if run_faithfulness:
        jm = judge_model or faithfulness_mod.DEFAULT_JUDGE_MODEL
        for written_slug in report.narratives_written:
            src = slug_to_source.get(written_slug)
            if not src:
                continue  # e.g. master hub — no content claims to verify
            committed = vault.read("narrative", written_slug)
            if committed is None:
                continue
            fr = faithfulness_mod.run(
                vault, written_slug, committed.body, src, judge_model=jm,
            )
            report.total_cost_usd += fr.get("cost_usd", 0.0)
            faithfulness_reports.append(fr)
            if fr.get("unsupported", 0):
                # Real hallucination signal — loud.
                report.warnings.append(
                    f"{written_slug}: fact precision {fr.get('fact_faithfulness_pct', 0):.0f}% — "
                    f"{fr.get('unsupported', 0)} unsupported claim(s), verify "
                    f"(see {fr.get('report_path', '')})"
                )
            elif fr.get("edge_source_silent", 0):
                # Synthesized spine edges are expected for problem-driven trees;
                # informational, not an alarm.
                report.warnings.append(
                    f"{written_slug}: {fr.get('edge_source_silent', 0)} synthesized spine "
                    f"edge(s) (interpretive — verify against source; "
                    f"see {fr.get('report_path', '')})"
                )
            # Optionally mark synthesized edges in-tree with [~] (idempotent).
            if annotate_inferred:
                new_body, n_marked = faithfulness_mod.annotate_inferred(
                    committed.body, fr.get("items", []),
                )
                if n_marked:
                    annotated = Page(
                        kind="narrative", slug=written_slug,
                        meta={**committed.meta, "updated": date.today().isoformat()},
                        body=new_body,
                    )
                    val = narrative.validate_page(annotated)
                    if val.errors:
                        report.warnings.append(
                            f"{written_slug}: [~] annotation skipped (validation: {val.errors})"
                        )
                    else:
                        vault.write(annotated)
                        report.warnings.append(
                            f"{written_slug}: marked {n_marked} synthesized edge(s) with [~]"
                        )

    vault.append_log(
        "narrative_draft",
        {
            "slug": base_slug,
            "strategy": report.strategy,
            "written": len(report.narratives_written),
            "cost_usd": f"{report.total_cost_usd:.4f}",
            "errors": len(report.errors),
            "coverage_runs": len(coverage_reports),
            "faithfulness_runs": len(faithfulness_reports),
        },
    )
    out = report.to_dict()
    out["coverage"] = coverage_reports
    out["faithfulness"] = faithfulness_reports
    return out
