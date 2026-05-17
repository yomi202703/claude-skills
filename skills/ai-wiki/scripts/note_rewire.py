#!/usr/bin/env python3
"""note-rewire: 既存 standalone notes を後発の narrative に紐付け直す doctor (v5)。

Flow:
  1. notes/ をスキャンし frontmatter `study:` field を持つ note を集める
  2. study ごとに narratives/<study>.md の有無を確認
  3. 該当 narrative がある study について、note 群をまとめて LLM に渡し、
     各 note の anchor 提案 (どの ## 節に紐付けるべきか) を取得
  4. デフォルトは dry-run (提案 JSON のみ)。--apply 指定時に narrative を
     編集して wikilink を追加する

dispatcher.py から呼ばれる。
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import llm
from note_from_chat import _patch_narrative_with_wikilink
from vault import Vault


# ---------- result dataclass ----------


@dataclass
class RewireReport:
    vault_root: str
    studies_processed: list[str]
    proposals: list[dict] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    applied: list[dict] = field(default_factory=list)
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "vault_root": self.vault_root,
            "studies_processed": self.studies_processed,
            "proposals": self.proposals,
            "skipped": self.skipped,
            "applied": self.applied,
            "cost_usd": round(self.cost_usd, 4),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "errors": self.errors,
            "warnings": self.warnings,
        }


# ---------- helpers ----------


def _gather_notes_by_study(
    vault: Vault, study_filter: str | None
) -> dict[str, list[tuple[str, str]]]:
    """Return {study: [(note_slug, note_body), ...]}."""
    by_study: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for slug in vault.list_pages("note"):
        page = vault.read("note", slug)
        if page is None:
            continue
        study_val = page.meta.get("study")
        if not study_val:
            continue
        study_str = str(study_val)
        if study_filter and study_str != study_filter:
            continue
        by_study[study_str].append((slug, page.body))
    return by_study


def _build_notes_block(notes: list[tuple[str, str]]) -> str:
    parts = []
    for slug, body in notes:
        parts.append(f"=== NOTE: {slug} ===\n{body.strip()}")
    return "\n\n".join(parts)


# ---------- main ----------


def note_rewire(
    vault: Vault,
    *,
    study_filter: str | None = None,
    apply: bool = False,
) -> dict:
    report = RewireReport(
        vault_root=str(vault.root),
        studies_processed=[],
    )

    by_study = _gather_notes_by_study(vault, study_filter)
    if not by_study:
        report.warnings.append(
            "no notes with `study:` frontmatter found"
            + (f" for study={study_filter!r}" if study_filter else "")
        )
        return report.to_dict()

    for study, notes in sorted(by_study.items()):
        narrative_page = vault.read("narrative", study)
        if narrative_page is None:
            for slug, _ in notes:
                report.skipped.append({
                    "note_slug": slug,
                    "study": study,
                    "reason": f"narrative {study} not yet built",
                })
            continue

        report.studies_processed.append(study)

        result = llm.call_with_template(
            "note_rewire",
            {
                "study": study,
                "narrative_body": narrative_page.body,
                "notes_concatenated": _build_notes_block(notes),
            },
        )
        llm.log_call(vault.append_log, "note_rewire", study, result)
        report.cost_usd += result.cost_usd
        report.input_tokens += result.input_tokens
        report.output_tokens += result.output_tokens

        if result.is_error:
            report.errors.append(f"LLM error for study {study}: {result.error_message}")
            continue

        parsed = result.parsed
        if not isinstance(parsed, dict):
            report.errors.append(f"LLM output not JSON object for study {study}")
            continue

        anchors = parsed.get("anchors") or []
        skipped = parsed.get("skipped") or []

        for a in anchors:
            if not isinstance(a, dict):
                continue
            wl = (a.get("wikilink_line") or "").replace(
                "<note-slug>", a.get("note_slug", "")
            )
            proposal = {
                "study": study,
                "note_slug": a.get("note_slug"),
                "narrative_slug": a.get("narrative_slug") or study,
                "section_header": a.get("section_header"),
                "wikilink_line": wl,
                "rationale": a.get("rationale", ""),
            }
            report.proposals.append(proposal)

            if apply and proposal["note_slug"] and proposal["section_header"]:
                ok, msg = _patch_narrative_with_wikilink(
                    vault,
                    proposal["narrative_slug"],
                    proposal["section_header"],
                    proposal["wikilink_line"],
                )
                if ok:
                    report.applied.append({
                        "note_slug": proposal["note_slug"],
                        "narrative_slug": proposal["narrative_slug"],
                        "section_header": proposal["section_header"],
                    })
                else:
                    report.warnings.append(
                        f"apply failed for {proposal['note_slug']}: {msg}"
                    )

        for s in skipped:
            if isinstance(s, dict):
                report.skipped.append({
                    "study": study,
                    "note_slug": s.get("note_slug"),
                    "reason": s.get("reason", "unspecified"),
                })

    return report.to_dict()
