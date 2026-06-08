#!/usr/bin/env python3
"""derivation-draft: source (+anchor) + goal → subgoal-labeled spine.

Builds the durable procedural asset: an ordered `[⇣n]` step chain that derives a
target result, with subgoal labels for chunking (subgoal labeling lowers load
and aids transfer) and source-grounded step content (no hallucinated algebra).

Two-model design, to dodge self-preference bias (same pattern as coverage /
faithfulness):
- **generator** (default opus) drafts the spine from the source, using the
  anchor narrative only for the subgoal *structure* (conceptual chunking).
- **judge** (default sonnet, a *different* model) verifies each step against the
  source. Steps the judge cannot confirm are marked `[~]` and the spine is
  committed with verified=false — never silently presented as certain.

Tier is computed from the verdicts, not asserted:
- every step quoted from source           → T1  (verified, high)
- some steps derived-but-judge-confirmed  → gen (verified, mid)
- any step unconfirmable                   → gen (verified=false, low)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import derivation as mod_derivation
import llm
from vault import Page, Vault


def _generate_spine(
    vault: Vault, slug: str, goal: str, source_text: str, anchor_body: str,
    *, model: str | None = None,
) -> tuple[dict, float]:
    result = llm.call_with_template(
        "derivation_draft",
        {
            "slug": slug,
            "goal": goal,
            "source_text": source_text,
            "anchor_structure": anchor_body or "(no anchor narrative provided)",
        },
        model=model,
        parse_json=True,
    )
    llm.log_call(vault.append_log, "derivation_draft", slug, result)
    if result.is_error or not isinstance(result.parsed, dict):
        return {}, result.cost_usd
    return result.parsed, result.cost_usd


def _verify_steps(
    vault: Vault, slug: str, source_text: str, steps: list[dict],
    *, judge_model: str | None = None,
) -> tuple[dict[int, str], float]:
    """Return ({step_n: verdict}, cost). verdict ∈ supported|derived_ok|unverified."""
    steps_json = json.dumps(
        [{"n": s.get("n"), "label": s.get("label", ""), "content": s.get("content", "")}
         for s in steps],
        ensure_ascii=False, indent=2,
    )
    result = llm.call_with_template(
        "derivation_verify",
        {"source_text": source_text, "steps_json": steps_json},
        model=judge_model or "sonnet",
        parse_json=True,
    )
    llm.log_call(vault.append_log, "derivation_verify", slug, result)
    verdicts: dict[int, str] = {}
    if result.is_error or not isinstance(result.parsed, list):
        return verdicts, result.cost_usd
    for item in result.parsed:
        if not isinstance(item, dict):
            continue
        try:
            n = int(item.get("n", 0) or 0)
        except (TypeError, ValueError):
            continue
        if n <= 0:
            continue
        v = str(item.get("verdict", "")).strip()
        if v in ("supported", "derived_ok", "unverified"):
            verdicts[n] = v
    return verdicts, result.cost_usd


def _classify(verdicts: dict[int, str], n_steps: int) -> tuple[str, bool, str]:
    """(tier, verified, confidence) from the judge verdicts."""
    vals = [verdicts.get(i + 1, "unverified") for i in range(n_steps)]
    if all(v == "supported" for v in vals):
        return "T1", True, "high"
    if all(v in ("supported", "derived_ok") for v in vals):
        return "gen", True, "mid"
    return "gen", False, "low"


def _spine_body(goal: str, steps: list[dict], verdicts: dict[int, str]) -> str:
    """Render the spine BODY (no frontmatter). Steps are pre-normalized so
    `n` is an int 1..N."""
    body_lines = ["## GOAL", "", goal.strip(), "", "## SPINE", ""]
    for s in steps:
        n = int(s["n"])
        label = str(s.get("label", "")).strip()
        content = str(s.get("content", "")).strip()
        tail = "  [~]" if verdicts.get(n, "unverified") == "unverified" else ""
        body_lines.append(f"[⇣{n}] {label} → {content}{tail}")
    return "\n".join(body_lines) + "\n"


def draft(
    vault: Vault, source_path: str, *,
    slug: str, anchor: str | None = None, goal: str,
    model: str | None = None, judge_model: str | None = None,
    verify: bool = True,
) -> dict:
    """Generate one derivation spine for `goal` from `source_path`."""
    p = Path(source_path)
    if p.exists():
        source_text = p.read_text(encoding="utf-8")
        source_slug = p.stem
    else:
        spage = vault.read("source", source_path)
        if spage is None:
            return {"ok": False, "error": f"source not found: {source_path}"}
        source_text, source_slug = spage.body, source_path

    anchor_body = ""
    if anchor:
        apage = vault.read("narrative", anchor)
        if apage is not None:
            anchor_body = apage.body

    parsed, gcost = _generate_spine(
        vault, slug, goal, source_text, anchor_body, model=model
    )
    raw_steps = parsed.get("steps")
    steps_list: list = raw_steps if isinstance(raw_steps, list) else []
    goal_out = str(parsed.get("goal") or goal).strip()
    # normalize step numbers to 1..N in given order
    norm_steps: list[dict] = []
    for i, s in enumerate(steps_list, start=1):
        if not isinstance(s, dict):
            continue
        s = dict(s)
        s["n"] = i
        norm_steps.append(s)
    if not norm_steps:
        return {"ok": False, "error": "generator returned no steps", "cost_usd": round(gcost, 4)}

    verdicts: dict[int, str] = {}
    vcost = 0.0
    if verify:
        verdicts, vcost = _verify_steps(
            vault, slug, source_text, norm_steps, judge_model=judge_model
        )
    else:
        # no verification: trust generator's self-reported grounding
        for s in norm_steps:
            verdicts[int(s["n"])] = "supported" if s.get("source_grounded") else "unverified"

    tier, verified, confidence = _classify(verdicts, len(norm_steps))

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    meta = {
        "type": "derivation",
        "slug": slug,
        "title": str(parsed.get("title") or goal_out[:60]),
        "anchor": anchor or "",
        "source": source_slug,
        "tier": tier,
        "verified": verified,
        "confidence": confidence,
        "created": today,
        "updated": today,
    }
    body = _spine_body(goal_out, norm_steps, verdicts)
    page = Page(kind="derivation", slug=slug, meta=meta, body=body)
    out_path = vault.write(page)

    # validate what we wrote (re-read so the frontmatter round-trips)
    written = vault.read("derivation", slug)
    report = mod_derivation.validate_page(written) if written else None

    total = gcost + vcost
    n_unverified = sum(1 for i in range(len(norm_steps))
                       if verdicts.get(i + 1, "unverified") == "unverified")
    vault.append_log(
        "derivation_draft_done",
        {
            "slug": slug, "source": source_slug, "anchor": anchor or "-",
            "steps": len(norm_steps), "tier": tier, "verified": verified,
            "unverified_steps": n_unverified, "cost_usd": f"{total:.4f}",
        },
    )
    return {
        "ok": True,
        "derivation": str(out_path.relative_to(vault.root)),
        "slug": slug,
        "tier": tier,
        "verified": verified,
        "confidence": confidence,
        "steps": len(norm_steps),
        "unverified_steps": n_unverified,
        "validation": report.to_dict() if report else None,
        "cost_usd": round(total, 4),
    }
