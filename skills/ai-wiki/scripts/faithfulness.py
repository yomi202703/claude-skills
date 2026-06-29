#!/usr/bin/env python3
"""Faithfulness check: does the narrative tree assert anything NOT grounded in
the source? (the precision direction QuestEval defines, which coverage_qa omits)

coverage_qa measures *recall* (source → QA → is it in the tree). This module
measures *precision/faithfulness* (tree → atomic claims → is each in the source).
The narrative DSL gives atomic decomposition for free (reuse card_draft node
walk), so unlike FActScore we need no prose-splitting step.

De-biasing (LLM-as-judge self-preference, perplexity/familiarity bias): the
judge defaults to a *different* model than the generator, receives claims as
neutral text stripped of the DSL (de-facto authorship obfuscation), and is
forced to quote a verbatim source span for any "supported" verdict.

A second pass (judge_soundness) judges the *structure*: faithfulness flags the
synthesized spine edges as source_silent (provenance — "not stated"), but says
nothing about whether the A→B move is *valid*. The soundness pass closes that —
sound | dubious | unsound — over exactly those edges. It is the only check on
the spine topology (coverage = recall, faithfulness = claim precision), the most
pedagogically load-bearing and most plausibly-wrong layer, which the user never
cross-checks.

Output is diagnostic (a hidden report + percentages), never an auto-edit: the
tree is a working hypothesis, and verification is the machine's job not the
user's (SKILL hard rule #5).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import card_draft
import llm
from vault import Vault

FAITHFULNESS_DIR_NAME = ".narrative-faithfulness"

# Default judge model: a *different* model from the opus generator, to dodge
# self-preference bias (arxiv 2410.21819). Override via judge_model arg.
DEFAULT_JUDGE_MODEL = "sonnet"

# Node symbols that encode a relation/causal claim rather than a standalone
# term — these carry the highest hallucination risk (synthesized spine edges).
_EDGE_SYMBOLS = frozenset({"⟳", "∴", "⤴", "⤵", "⊕", "↺", "∥"})


@dataclass
class ClaimVerdict:
    claim: str
    kind: str            # "edge" | "fact"
    symbol: str
    section: str
    verdict: str         # "supported" | "unsupported" | "source_silent"
    evidence: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FaithfulnessReport:
    slug: str
    total: int
    supported: int
    unsupported: int
    source_silent: int
    faithfulness_pct: float | None  # supported / total (blended); None ⇒ judge failed
    edge_unsupported: int          # unsupported claims that are edges
    edge_source_silent: int        # synthesized (model-inferred) edges
    # Fact-only precision is the real hallucination signal. A problem-driven
    # tree's spine edges (⟳/→/⇒) are *expected* to be source_silent — the
    # narrative framing the source doesn't state literally is the tree's value —
    # so they must NOT be blended into the headline faithfulness number.
    fact_total: int = 0
    fact_supported: int = 0
    fact_faithfulness_pct: float | None = 0.0   # None ⇒ judge failed (unmeasured, not 100%)
    # True when the claim judge call failed: precision numbers are N/A, not a pass.
    # (The soundness pass is a separate call and may still have succeeded.)
    judge_failed: bool = False
    # Structural soundness: a *second* judgment over the source_silent edges
    # (the synthesized spine). faithfulness asks "is it stated" (no, by design);
    # soundness asks "is the A→B move valid given the source". This is the only
    # check on the spine topology — the most pedagogically load-bearing, most
    # plausibly-wrong layer, which neither coverage (recall) nor faithfulness
    # (claim precision) validates, and which the user never cross-checks.
    soundness_total: int = 0
    soundness_sound: int = 0
    soundness_dubious: int = 0
    soundness_unsound: int = 0
    soundness_items: list[dict] = field(default_factory=list)
    judge_model: str = ""
    items: list[ClaimVerdict] = field(default_factory=list)
    cost_usd: float = 0.0
    report_path: str = ""

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "total": self.total,
            "supported": self.supported,
            "unsupported": self.unsupported,
            "source_silent": self.source_silent,
            "faithfulness_pct": self.faithfulness_pct,
            "judge_failed": self.judge_failed,
            "fact_total": self.fact_total,
            "fact_supported": self.fact_supported,
            "fact_faithfulness_pct": self.fact_faithfulness_pct,
            "edge_unsupported": self.edge_unsupported,
            "edge_source_silent": self.edge_source_silent,
            "soundness_total": self.soundness_total,
            "soundness_sound": self.soundness_sound,
            "soundness_dubious": self.soundness_dubious,
            "soundness_unsound": self.soundness_unsound,
            "soundness_items": self.soundness_items,
            "judge_model": self.judge_model,
            "cost_usd": round(self.cost_usd, 4),
            "report_path": self.report_path,
            "items": [x.to_dict() for x in self.items],
        }


def _classify(symbol: str, text: str) -> str:
    if symbol in _EDGE_SYMBOLS or "→" in text or "⇒" in text:
        return "edge"
    return "fact"


def extract_claims(body: str) -> list[ClaimVerdict]:
    """Atomic claims from the tree, reusing the deterministic node walk.

    Returns ClaimVerdict shells (verdict filled in later). Empty-text nodes are
    dropped. `## 記法` / `## 未配送` are already skipped by extract_nodes.
    """
    claims: list[ClaimVerdict] = []
    for node in card_draft.extract_nodes(body):
        text = (node.text or "").strip()
        if not text:
            continue
        claims.append(ClaimVerdict(
            claim=text,
            kind=_classify(node.symbol, text),
            symbol=node.symbol,
            section=node.section,
            verdict="",
        ))
    return claims


def annotate_inferred(body: str, items: list[dict]) -> tuple[str, int]:
    """Mark synthesized spine edges in the tree with `[~]` (model-inferred).

    Pure + idempotent. Only `source_silent` *edge* claims are annotated: an
    ` [~]` is appended to the matching `⟳` transition line so a reader/SRS sees
    the causal link is the LLM's framing, not source-grounded. Facts and
    unsupported claims are left for the report (deleting/editing content is out
    of scope — the tree is a working hypothesis). Returns (new_body, n_marked).
    """
    flagged = {
        (it.get("claim") or "").splitlines()[0].strip()
        for it in items
        if it.get("verdict") == "source_silent" and it.get("kind") == "edge"
        and (it.get("claim") or "").strip()
    }
    if not flagged:
        return body, 0
    out: list[str] = []
    n = 0
    for line in body.splitlines():
        if (card_draft._TRANSITION_RE.match(line)
                and "[~]" not in line):
            cleaned = card_draft._strip_scaffold(line).strip()
            if cleaned in flagged:
                line = line.rstrip() + " [~]"
                n += 1
        out.append(line)
    new_body = "\n".join(out)
    if body.endswith("\n") and not new_body.endswith("\n"):
        new_body += "\n"
    return new_body, n


def _faithfulness_dir(vault: Vault) -> Path:
    d = vault.root / FAITHFULNESS_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def report_path(vault: Vault, slug: str) -> Path:
    return _faithfulness_dir(vault) / f"{slug}.md"


def judge_claims(
    vault: Vault,
    slug: str,
    claims: list[ClaimVerdict],
    source_text: str,
    *,
    judge_model: str = DEFAULT_JUDGE_MODEL,
) -> tuple[list[ClaimVerdict], float, bool]:
    """Send neutralized claims + source to the judge model. Fills each claim's
    verdict/evidence in place (input order preserved). Returns (claims, cost,
    judge_ok) — judge_ok is False when the judge call failed, so the caller can
    report precision as N/A instead of a misleading 100% (no contradictions found
    only because nothing was checked)."""
    if not claims:
        return claims, 0.0, True
    claims_json = json.dumps(
        [{"i": i, "claim": c.claim} for i, c in enumerate(claims)],
        ensure_ascii=False, indent=2,
    )
    result = llm.call_with_template(
        "narrative_faithfulness",
        {"slug": slug, "source_text": source_text, "claims_json": claims_json},
        model=judge_model,
    )
    llm.log_call(vault.append_log, "narrative_faithfulness", slug, result)
    cost = result.cost_usd
    parsed = result.parsed if not result.is_error else None
    if not isinstance(parsed, list):
        # Judge failed → mark all unverified-as-source_silent (do not claim support)
        # and signal judge_ok=False so the caller reports precision as N/A.
        for c in claims:
            c.verdict = "source_silent"
            c.evidence = "judge failed"
        return claims, cost, False
    for i, c in enumerate(claims):
        item = parsed[i] if i < len(parsed) and isinstance(parsed[i], dict) else {}
        v = str(item.get("verdict", "source_silent"))
        if v not in ("supported", "unsupported", "source_silent"):
            v = "source_silent"
        c.verdict = v
        c.evidence = str(item.get("evidence", "")).strip()
    return claims, cost, True


def judge_soundness(
    vault: Vault,
    slug: str,
    edges: list[ClaimVerdict],
    narrative_body: str,
    source_text: str,
    *,
    judge_model: str = DEFAULT_JUDGE_MODEL,
) -> tuple[list[dict], float]:
    """Soundness pass over the synthesized spine edges (the source_silent edges
    faithfulness already isolated). For each, a judge decides whether the A→B
    move is valid given the source — sound | dubious | unsound — NOT whether it
    is stated (it is not, by design). The narrative body is passed so the judge
    sees each edge in its spine context. Diagnostic only. Returns (items, cost)
    where each item is {claim, section, verdict, reason}."""
    if not edges:
        return [], 0.0
    edges_json = json.dumps(
        [{"i": i, "edge": c.claim, "section": c.section} for i, c in enumerate(edges)],
        ensure_ascii=False, indent=2,
    )
    result = llm.call_with_template(
        "narrative_soundness",
        {
            "slug": slug,
            "source_text": source_text,
            "narrative_body": narrative_body,
            "edges_json": edges_json,
        },
        model=judge_model,
    )
    llm.log_call(vault.append_log, "narrative_soundness", slug, result)
    cost = result.cost_usd
    parsed = result.parsed if not result.is_error else None
    items: list[dict] = []
    for i, c in enumerate(edges):
        item = parsed[i] if isinstance(parsed, list) and i < len(parsed) and isinstance(parsed[i], dict) else {}
        v = str(item.get("verdict", ""))
        if v not in ("sound", "dubious", "unsound"):
            # Judge failed / unparseable → treat as dubious (do not silently bless)
            v = "dubious"
        items.append({
            "claim": c.claim,
            "section": c.section,
            "verdict": v,
            "reason": str(item.get("reason", "")).strip() or ("judge failed" if parsed is None else ""),
        })
    return items, cost


def write_report(vault: Vault, slug: str, report: FaithfulnessReport) -> Path:
    path = report_path(vault, slug)
    lines: list[str] = [
        "<!-- auto-generated faithfulness check. Hidden from Obsidian. -->",
        "",
        f"# {slug} faithfulness",
        "",
        f"_Last checked: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC_ "
        f"(judge: {report.judge_model})",
        "",
        (
            "**事実精度: 判定不能 (judge API 失敗) — 数値は N/A。tree 品質の指標ではない。**"
            if report.judge_failed else
            f"**事実精度 (hallucination 指標): {report.fact_faithfulness_pct:.1f}%** "
            f"— 事実 node {report.fact_total} 件中 矛盾/捏造 {report.edge_unsupported + (report.unsupported - report.edge_unsupported)} 件"
        ),
        "",
        f"合成エッジ (解釈的 spine, 要照合): {report.edge_source_silent} 本",
        "",
        f"_内訳: {report.total} claims / supported {report.supported} / "
        f"unsupported {report.unsupported} / source_silent {report.source_silent}_",
        "",
    ]
    unsupported = [x for x in report.items if x.verdict == "unsupported"]
    silent_edges = [x for x in report.items
                    if x.verdict == "source_silent" and x.kind == "edge"]
    silent_facts = [x for x in report.items
                    if x.verdict == "source_silent" and x.kind == "fact"]

    if unsupported:
        lines += ["## ⚠ source と矛盾 / 非依拠の断定 (unsupported) — 誤りの可能性大", ""]
        for x in unsupported:
            lines.append(f"- [{x.section}] {x.claim}")
        lines.append("")

    if silent_facts:
        lines += ["## source に出典の無い事実 (source_silent / fact) — 要照合", ""]
        for x in silent_facts:
            lines.append(f"- [{x.section}] {x.claim}")
        lines.append("")

    if silent_edges:
        lines += ["## ~ モデルが合成した spine エッジ (source_silent / edge) — 解釈なので要検証", ""]
        for x in silent_edges:
            lines.append(f"- [{x.section}] {x.claim}")
        lines.append("")

    unsound = [x for x in report.soundness_items if x["verdict"] == "unsound"]
    dubious = [x for x in report.soundness_items if x["verdict"] == "dubious"]
    if report.soundness_total:
        lines += [
            f"## spine 健全性 (合成エッジ {report.soundness_total} 本の運びの当否) "
            f"— unsound {report.soundness_unsound} / dubious {report.soundness_dubious} / "
            f"sound {report.soundness_sound}",
            "",
        ]
        for x in unsound:
            lines.append(f"- ✕ unsound [{x['section']}] {x['claim']} — {x['reason']}")
        for x in dubious:
            lines.append(f"- ~ dubious [{x['section']}] {x['claim']} — {x['reason']}")
        if not unsound and not dubious:
            lines.append("- 全エッジ sound。spine の運びに飛躍は検出されず。")
        lines.append("")

    lines += [
        "## 読み方",
        "",
        "- **spine 健全性** が構造の検算。`unsound` は B が A から follow しない＝枠組みの誤りの可能性大、`dubious` は飛躍/未明示前提あり。問題駆動 tree で一番教育的に効く層で、coverage も事実精度も見ない箇所。",
        "- **事実精度** が本命の hallucination 指標。`unsupported` の fact があれば誤りの可能性大。",
        "- **合成エッジ** は problem-driven tree の宿命: source は「問題→次の問題」を明示しない。"
        "これは tree の付加価値(解釈)であって誤りではないが、source 非依拠なので鵜呑みにせず照合する。",
        "- 意図的な補完・常識的接続ならこの report は無視して OK。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def run(
    vault: Vault,
    slug: str,
    narrative_body: str,
    source_text: str,
    *,
    judge_model: str = DEFAULT_JUDGE_MODEL,
) -> dict:
    """Full faithfulness workflow for one narrative body. Diagnostic only —
    never mutates the narrative. Returns the report dict."""
    claims = extract_claims(narrative_body)
    claims, cost, judge_ok = judge_claims(vault, slug, claims, source_text, judge_model=judge_model)

    supported = sum(1 for c in claims if c.verdict == "supported")
    unsupported = sum(1 for c in claims if c.verdict == "unsupported")
    source_silent = sum(1 for c in claims if c.verdict == "source_silent")
    total = len(claims)

    facts = [c for c in claims if c.kind == "fact"]
    fact_total = len(facts)
    fact_supported = sum(1 for c in facts if c.verdict == "supported")
    # Fact precision counts a fact as faithful unless it is positively
    # unsupported (contradicted/fabricated). source_silent facts are uncited
    # but not necessarily wrong; the hard signal is `unsupported`.
    fact_unsupported = sum(1 for c in facts if c.verdict == "unsupported")

    # When the judge call failed every claim defaults to source_silent, which
    # would otherwise read as a perfect 100% precision (no contradictions found —
    # because none were looked for). Report N/A (None) instead of a false pass.
    if not judge_ok:
        pct = None
        fact_pct = None
    else:
        pct = round(supported / total * 100.0, 1) if total else 0.0
        fact_pct = round((fact_total - fact_unsupported) / fact_total * 100.0, 1) if fact_total else 0.0

    # Soundness pass over the synthesized spine (the source_silent edges).
    silent_edge_claims = [c for c in claims
                          if c.verdict == "source_silent" and c.kind == "edge"]
    soundness_items, soundness_cost = judge_soundness(
        vault, slug, silent_edge_claims, narrative_body, source_text,
        judge_model=judge_model,
    )
    cost += soundness_cost

    report = FaithfulnessReport(
        slug=slug,
        total=total,
        supported=supported,
        unsupported=unsupported,
        source_silent=source_silent,
        faithfulness_pct=pct,
        edge_unsupported=sum(1 for c in claims if c.verdict == "unsupported" and c.kind == "edge"),
        edge_source_silent=sum(1 for c in claims if c.verdict == "source_silent" and c.kind == "edge"),
        fact_total=fact_total,
        fact_supported=fact_supported,
        fact_faithfulness_pct=fact_pct,
        judge_failed=not judge_ok,
        soundness_total=len(soundness_items),
        soundness_sound=sum(1 for x in soundness_items if x["verdict"] == "sound"),
        soundness_dubious=sum(1 for x in soundness_items if x["verdict"] == "dubious"),
        soundness_unsound=sum(1 for x in soundness_items if x["verdict"] == "unsound"),
        soundness_items=soundness_items,
        judge_model=judge_model,
        items=claims,
        cost_usd=cost,
    )
    path = write_report(vault, slug, report)
    report.report_path = str(path.relative_to(vault.root))

    vault.append_log(
        "faithfulness_check",
        {
            "slug": slug,
            "total": total,
            "supported": supported,
            "unsupported": unsupported,
            "source_silent": source_silent,
            "faithfulness_pct": ("n/a" if pct is None else f"{pct:.1f}"),
            "judge_failed": "yes" if not judge_ok else "no",
            "soundness_total": report.soundness_total,
            "soundness_unsound": report.soundness_unsound,
            "soundness_dubious": report.soundness_dubious,
            "judge_model": judge_model,
            "cost_usd": f"{cost:.4f}",
        },
    )
    return report.to_dict()
