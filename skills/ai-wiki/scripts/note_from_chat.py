#!/usr/bin/env python3
"""note-from-chat: Claude desktop/web の対話 export を friction-driven note に変換する (v5)。

Flow:
  1. heuristic で chat-export 形状を検出 (UI noise patterns)
  2. study 名から関連 narrative の有無を判定
  3. LLM 1 call で reformat + slug 提案 + (narrative あれば) anchor 提案
  4. notes/<slug>.md に書き込み
  5. --apply-anchor 指定時、narrative にも wikilink を追加

dispatcher.py から呼ばれる。`--study` は必須 (agent 側で user に確認する想定)。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import llm
from vault import Page, Vault, slugify

# ---------- detection heuristic ----------

_CHAT_PATTERNS = [
    r"あなたの入力\s*:",
    r"Claude\s*が返答しました\s*:",
    r"^\d{1,2}:\d{2}\s*$",  # bare timestamps on their own line
    r"^You\s*:\s*$",
    r"^Assistant\s*:\s*$",
]


def detect_chat_export(text: str) -> tuple[bool, float, list[str]]:
    """Score whether the text looks like a Claude chat export.

    Returns (is_chat, score, hits). score in [0, 1]. is_chat = score >= 0.4.
    """
    hits: list[str] = []
    score = 0.0
    for pat in _CHAT_PATTERNS:
        if re.search(pat, text, re.MULTILINE):
            hits.append(pat)
            score += 0.25

    # Broken-LaTeX heuristic: many single-character lines (math fragmented).
    short_lines = sum(1 for ln in text.splitlines() if 0 < len(ln.strip()) <= 2)
    total_lines = max(1, sum(1 for ln in text.splitlines() if ln.strip()))
    short_ratio = short_lines / total_lines
    if short_ratio > 0.5:
        hits.append(f"broken-latex (short_line_ratio={short_ratio:.2f})")
        score += 0.5
    elif short_ratio > 0.3:
        hits.append(f"broken-latex (short_line_ratio={short_ratio:.2f})")
        score += 0.3

    score = min(1.0, score)
    return score >= 0.4, score, hits


# ---------- result dataclass ----------


@dataclass
class NoteFromChatReport:
    vault_root: str
    chat_path: str
    study: str
    note_slug: str | None
    note_path: str | None
    detected_as_chat: bool
    detection_score: float
    detection_hits: list[str]
    related_narrative: str | None
    anchor: dict | None
    anchor_applied: bool
    cost_usd: float
    input_tokens: int
    output_tokens: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "vault_root": self.vault_root,
            "chat_path": self.chat_path,
            "study": self.study,
            "note_slug": self.note_slug,
            "note_path": self.note_path,
            "detected_as_chat": self.detected_as_chat,
            "detection_score": round(self.detection_score, 2),
            "detection_hits": self.detection_hits,
            "related_narrative": self.related_narrative,
            "anchor": self.anchor,
            "anchor_applied": self.anchor_applied,
            "cost_usd": round(self.cost_usd, 4),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "errors": self.errors,
            "warnings": self.warnings,
        }


# ---------- helpers ----------


def _load_related_narrative(vault: Vault, study: str) -> tuple[str | None, str | None]:
    """Return (narrative_slug, narrative_body) or (None, None) if not found."""
    page = vault.read("narrative", study)
    if page is None:
        return None, None
    return page.slug, page.body


def _build_note_frontmatter(
    slug: str, title: str, study: str, anchor_target: str | None
) -> dict:
    today = date.today().isoformat()
    meta: dict = {
        "type": "note",
        "slug": slug,
        "title": title,
        "study": study,
        "created": today,
    }
    if anchor_target:
        meta["related"] = [f"[[{anchor_target}]]"]
    return meta


def _section_header_to_anchor(header: str) -> str:
    """`## 1. Foo` → `1. Foo` (Obsidian wikilink anchor format)."""
    return re.sub(r"^#+\s+", "", header.strip())


def _patch_narrative_with_wikilink(
    vault: Vault,
    narrative_slug: str,
    section_header: str,
    wikilink_line: str,
) -> tuple[bool, str]:
    """Append wikilink_line right under the matched H2 section. Returns (ok, msg)."""
    page = vault.read("narrative", narrative_slug)
    if page is None:
        return False, f"narrative {narrative_slug} not found"
    body = page.body
    target = section_header.strip()
    # Find the H2 line
    lines = body.splitlines()
    idx = -1
    for i, ln in enumerate(lines):
        if ln.strip() == target:
            idx = i
            break
    if idx < 0:
        return False, f"section header not found: {target!r}"
    # Idempotency: skip if wikilink already present in body
    if wikilink_line.strip() in body:
        return False, "wikilink already present (no-op)"
    # Insert after the header line and any immediately following blank line
    insert_at = idx + 1
    # Skip one blank line if present
    if insert_at < len(lines) and lines[insert_at].strip() == "":
        insert_at += 1
    lines.insert(insert_at, "")
    lines.insert(insert_at + 1, wikilink_line.rstrip())
    new_body = "\n".join(lines)
    if not new_body.endswith("\n"):
        new_body += "\n"
    page.body = new_body
    vault.write(page)
    return True, "applied"


# ---------- main ----------


def note_from_chat(
    vault: Vault,
    chat_path: str | Path,
    *,
    study: str,
    slug_override: str | None = None,
    no_anchor: bool = False,
    apply_anchor: bool = False,
    skip_detect_check: bool = False,
    dry_run: bool = False,
) -> dict:
    chat_path = Path(chat_path)
    report = NoteFromChatReport(
        vault_root=str(vault.root),
        chat_path=str(chat_path),
        study=study,
        note_slug=None,
        note_path=None,
        detected_as_chat=False,
        detection_score=0.0,
        detection_hits=[],
        related_narrative=None,
        anchor=None,
        anchor_applied=False,
        cost_usd=0.0,
        input_tokens=0,
        output_tokens=0,
    )

    if not chat_path.exists():
        report.errors.append(f"chat export not found: {chat_path}")
        return report.to_dict()

    text = chat_path.read_text(encoding="utf-8")
    is_chat, score, hits = detect_chat_export(text)
    report.detected_as_chat = is_chat
    report.detection_score = score
    report.detection_hits = hits

    if not is_chat and not skip_detect_check:
        report.errors.append(
            f"input does not look like a chat export (score={score:.2f}). "
            "use --no-detect-check to force."
        )
        return report.to_dict()

    narrative_slug, narrative_body = _load_related_narrative(vault, study)
    report.related_narrative = narrative_slug

    if dry_run:
        report.warnings.append("dry_run: no LLM call, no write")
        return report.to_dict()

    # ---- LLM call ----
    related_block = narrative_body if narrative_body else "<NONE>"
    result = llm.call_with_template(
        "note_from_chat",
        {
            "study": study,
            "related_narrative": related_block,
            "chat_export": text,
        },
    )
    llm.log_call(vault.append_log, "note_from_chat", study, result)
    report.cost_usd = result.cost_usd
    report.input_tokens = result.input_tokens
    report.output_tokens = result.output_tokens

    if result.is_error:
        report.errors.append(f"LLM error: {result.error_message}")
        return report.to_dict()

    parsed = result.parsed
    if not isinstance(parsed, dict):
        report.errors.append("LLM output not parseable as JSON object")
        return report.to_dict()

    proposed_slug = slug_override or parsed.get("slug")
    title = parsed.get("title", "").strip()
    body = parsed.get("body", "").strip()
    anchor = parsed.get("anchor") if not no_anchor else None
    summary = parsed.get("summary", "")

    if not proposed_slug or not title or not body:
        report.errors.append(
            f"LLM output missing required fields (slug/title/body): "
            f"slug={bool(proposed_slug)}, title={bool(title)}, body={bool(body)}"
        )
        return report.to_dict()

    # Sanitize slug
    slug = slugify(str(proposed_slug))
    if not slug:
        report.errors.append(f"slug sanitization failed: {proposed_slug!r}")
        return report.to_dict()

    # Slug conflict check
    if vault.exists("note", slug):
        report.errors.append(
            f"note slug conflict: notes/{slug}.md already exists. "
            "use --slug to override."
        )
        return report.to_dict()

    # Build anchor wikilink target (slug#section) if anchor is present
    anchor_target = None
    if isinstance(anchor, dict) and anchor.get("narrative_slug") and anchor.get("section_header"):
        anchor_section = _section_header_to_anchor(anchor["section_header"])
        anchor_target = f"{anchor['narrative_slug']}#{anchor_section}"

    meta = _build_note_frontmatter(slug, title, study, anchor_target)
    page = Page(kind="note", slug=slug, meta=meta, body=body + "\n")
    note_path = vault.write(page)
    report.note_slug = slug
    report.note_path = str(note_path)

    if isinstance(anchor, dict):
        # Substitute the actual slug into wikilink_line if it contains a placeholder
        wl = anchor.get("wikilink_line", "")
        wl = wl.replace("<note-slug>", slug).replace("{{slug}}", slug)
        anchor_record = {
            "narrative_slug": anchor.get("narrative_slug"),
            "section_header": anchor.get("section_header"),
            "wikilink_line": wl,
            "rationale": anchor.get("rationale", ""),
        }
        report.anchor = anchor_record
        if apply_anchor and anchor_record["narrative_slug"]:
            ok, msg = _patch_narrative_with_wikilink(
                vault,
                anchor_record["narrative_slug"],
                anchor_record["section_header"] or "",
                anchor_record["wikilink_line"],
            )
            report.anchor_applied = ok
            if not ok:
                report.warnings.append(f"anchor not applied: {msg}")

    if summary:
        vault.append_log("note_from_chat", {"slug": slug, "study": study, "summary": summary})

    return report.to_dict()
