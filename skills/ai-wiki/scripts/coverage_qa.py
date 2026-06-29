#!/usr/bin/env python3
"""Coverage check via QuestEval-style QA generation + verification (v4, §13.7).

Flow:
  1. Generate QA set from source text (Claude Opus)
  2. Store QA set under `~/ai-wiki/.narrative-qa/<slug>.json` (hidden metadata)
  3. Judge coverage: pass narrative body + QA to Claude, get per-QA status
     (covered / partial / missing)
  4. Write gap report to `~/ai-wiki/.narrative-gaps/<slug>.md`

Gap report is informational (not a commit gate). User scans it during study
to find narrative holes that match their intuition of "this feels missing".
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import llm
from vault import Vault

# ---------- hidden metadata directories ----------

QA_DIR_NAME = ".narrative-qa"
GAPS_DIR_NAME = ".narrative-gaps"

# Coverage is judged by a *different* model from the opus generator, to dodge
# self-preference bias / in-context reward hacking when a model grades text it
# wrote itself (arxiv 2407.04549, 2506.02592). Mirrors faithfulness.DEFAULT_JUDGE_MODEL.
DEFAULT_JUDGE_MODEL = "sonnet"

# If more than this fraction of QA judgments errored (judge API failure /
# truncated output), the coverage number is computed on too small a sample to
# trust — report it as unavailable rather than emit a misleading low score.
MAX_ERROR_RATIO = 0.5


@dataclass
class QAItem:
    q: str
    a: str

    def to_dict(self) -> dict:
        return {"q": self.q, "a": self.a}


@dataclass
class CoverageStatus:
    q: str
    status: str  # "covered" | "partial" | "missing" | "error"
    note: str = ""


@dataclass
class CoverageReport:
    slug: str
    total: int
    covered: int
    partial: int
    missing: int
    coverage_pct: float | None  # None ⇒ unmeasured (judge API failed); NOT 0% coverage
    # Judge-call failures (API error / truncated output). These are *unevaluated*
    # items, not genuine misses — they are excluded from the coverage denominator
    # so a transient judge outage can never masquerade as 0% coverage.
    errored: int = 0
    # True when coverage could not be trusted (all/most QA judgments errored).
    # Consumers must treat coverage_pct as N/A and must NOT run gap remediation.
    unavailable: bool = False
    items: list[CoverageStatus] = field(default_factory=list)
    cost_usd: float = 0.0
    qa_set_path: str = ""
    gap_report_path: str = ""
    # Hold-out: coverage measured on a fresh, independent QA set the fixer never
    # saw. This is the *honest* number; coverage_pct is the optimized one.
    holdout_coverage_pct: float | None = None
    holdout_total: int = 0
    holdout_covered: int = 0

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "total": self.total,
            "covered": self.covered,
            "partial": self.partial,
            "missing": self.missing,
            "errored": self.errored,
            "unavailable": self.unavailable,
            "coverage_pct": self.coverage_pct,
            "holdout_coverage_pct": self.holdout_coverage_pct,
            "holdout_total": self.holdout_total,
            "holdout_covered": self.holdout_covered,
            "cost_usd": round(self.cost_usd, 4),
            "qa_set_path": self.qa_set_path,
            "gap_report_path": self.gap_report_path,
            "items": [asdict(x) for x in self.items],
        }


# ---------- paths ----------


def _qa_dir(vault: Vault) -> Path:
    d = vault.root / QA_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _gaps_dir(vault: Vault) -> Path:
    d = vault.root / GAPS_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def qa_set_path(vault: Vault, slug: str, holdout: bool = False) -> Path:
    # holdout set = an independent QA draw used only to *measure* final coverage,
    # never to drive fixes — defeats teaching-to-the-test (arxiv 2311.01964).
    suffix = ".holdout.json" if holdout else ".json"
    return _qa_dir(vault) / f"{slug}{suffix}"


def gap_report_path(vault: Vault, slug: str) -> Path:
    return _gaps_dir(vault) / f"{slug}.md"


# ---------- QA generation ----------


def generate_qa_set(vault: Vault, slug: str, title: str, source_text: str) -> tuple[list[QAItem], float]:
    """Call Claude to generate QA pairs from source. Returns (qa_list, cost)."""
    result = llm.call_with_template(
        "coverage_qa_gen",
        {"slug": slug, "title": title, "source_text": source_text},
    )
    llm.log_call(vault.append_log, "coverage_qa_gen", slug, result)
    if result.is_error:
        return [], result.cost_usd
    parsed = result.parsed
    if not isinstance(parsed, list):
        return [], result.cost_usd
    out: list[QAItem] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        q = item.get("q")
        a = item.get("a")
        if isinstance(q, str) and q.strip() and isinstance(a, str) and a.strip():
            out.append(QAItem(q=q.strip(), a=a.strip()))
    return out, result.cost_usd


def save_qa_set(vault: Vault, slug: str, items: list[QAItem], holdout: bool = False) -> Path:
    path = qa_set_path(vault, slug, holdout=holdout)
    payload = {
        "slug": slug,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "qa_pairs": [x.to_dict() for x in items],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_qa_set(vault: Vault, slug: str, holdout: bool = False) -> list[QAItem]:
    path = qa_set_path(vault, slug, holdout=holdout)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [QAItem(q=p["q"], a=p["a"]) for p in data.get("qa_pairs", []) if "q" in p and "a" in p]


# ---------- aggregation ----------


def _tally(statuses: list[CoverageStatus]) -> tuple[int, int, int, int]:
    """Return (covered, partial, missing, errored) over a status list."""
    covered = sum(1 for s in statuses if s.status == "covered")
    partial = sum(1 for s in statuses if s.status == "partial")
    missing = sum(1 for s in statuses if s.status == "missing")
    errored = sum(1 for s in statuses if s.status == "error")
    return covered, partial, missing, errored


def _coverage_pct(covered: int, partial: int, missing: int, errored: int) -> tuple[float | None, bool]:
    """Compute (coverage_pct, unavailable) excluding judge-errored items from the
    denominator. Returns (None, True) when nothing could be evaluated or the error
    rate is too high to trust — never a spurious 0% from a judge outage. When no
    items errored this is identical to the legacy covered/total ratio."""
    total = covered + partial + missing + errored
    evaluated = covered + partial + missing
    if total == 0 or evaluated == 0 or (errored / total) > MAX_ERROR_RATIO:
        return None, True
    return round(covered / evaluated * 100.0, 1), False


def _fmt_pct(pct: float | None) -> str:
    return "n/a" if pct is None else f"{pct:.1f}"


# ---------- Coverage check ----------


def check_coverage(
    vault: Vault,
    slug: str,
    narrative_body: str,
    qa_items: list[QAItem],
    judge_model: str = DEFAULT_JUDGE_MODEL,
) -> tuple[list[CoverageStatus], float]:
    """Ask Claude to judge each QA against the narrative. Returns
    (statuses_in_input_order, cost). The judge runs on a *different* model from
    the opus generator (default sonnet) to avoid self-preference bias."""
    if not qa_items:
        return [], 0.0
    qa_json = json.dumps([x.to_dict() for x in qa_items], ensure_ascii=False, indent=2)
    result = llm.call_with_template(
        "coverage_qa_check",
        {"slug": slug, "narrative_body": narrative_body, "qa_items_json": qa_json},
        model=judge_model,
    )
    llm.log_call(vault.append_log, "coverage_qa_check", slug, result)
    if result.is_error or not isinstance(result.parsed, list):
        # Judge call failed — these items are UNEVALUATED, not missing. Mark them
        # "error" so they are excluded from the coverage denominator (a judge
        # outage must never read as 0% coverage).
        return [CoverageStatus(q=x.q, status="error", note="coverage check failed") for x in qa_items], result.cost_usd

    parsed = result.parsed
    statuses: list[CoverageStatus] = []
    for i, qa in enumerate(qa_items):
        if i >= len(parsed):
            # Judge ran out before reaching this item — unevaluated, not a miss.
            statuses.append(CoverageStatus(q=qa.q, status="error", note="judge output truncated"))
            continue
        item = parsed[i] if isinstance(parsed[i], dict) else {}
        status = str(item.get("status", "missing"))
        if status not in ("covered", "partial", "missing"):
            status = "missing"
        note = str(item.get("note", ""))
        statuses.append(CoverageStatus(q=qa.q, status=status, note=note))
    return statuses, result.cost_usd


# ---------- Gap report ----------


def write_gap_report(
    vault: Vault,
    slug: str,
    report: CoverageReport,
) -> Path:
    path = gap_report_path(vault, slug)
    lines: list[str] = [
        f"<!-- auto-generated by /wiki-coverage-narrative. Hidden from Obsidian. -->",
        "",
        f"# {slug} coverage gaps",
        "",
        f"_Last checked: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC_",
        "",
        f"{report.total} QA / "
        f"{report.covered} covered ({_fmt_pct(report.coverage_pct)}%) / "
        f"{report.partial} partial / {report.missing} missing / "
        f"{report.errored} error",
        "",
    ]
    if report.unavailable:
        lines += [
            "> ⚠ coverage UNMEASURED — judge API failed on too many items "
            f"({report.errored}/{report.total}). The percentage above is N/A; "
            "this is not a tree-quality signal. Re-run when the judge model is healthy.",
            "",
        ]
    missing = [s for s in report.items if s.status == "missing"]
    partial = [s for s in report.items if s.status == "partial"]

    if missing:
        lines.append("## 答えられなかった問い (missing)")
        lines.append("")
        for s in missing:
            lines.append(f"- {s.q}")
            if s.note:
                lines.append(f"  - 判定根拠: {s.note}")
        lines.append("")

    if partial:
        lines.append("## 部分的にしか扱われていない問い (partial)")
        lines.append("")
        for s in partial:
            lines.append(f"- {s.q}")
            if s.note:
                lines.append(f"  - 判定根拠: {s.note}")
        lines.append("")

    lines.append("## 修正指示のヒント")
    lines.append("")
    lines.append(
        "上記の問いは narrative に未収録 or 不十分な可能性があります。"
        "study 中に違和感と一致するものがあれば Claude Code に修正指示してください。"
        "意図的な省略ならこの report は無視して OK。"
    )
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---------- top-level entry ----------


def run_coverage(
    vault: Vault,
    slug: str,
    source_path: str | Path | None,
    *,
    regenerate_qa: bool = False,
    judge_model: str = DEFAULT_JUDGE_MODEL,
) -> dict:
    """Full coverage workflow for a narrative.

    Parameters
    ----------
    slug
        Target narrative slug. Must exist under `~/ai-wiki/narratives/<slug>.md`.
    source_path
        Path to the original markdown source. Required on first run (to
        generate the QA set). Subsequent runs can omit this arg to re-use
        the cached QA set, unless `regenerate_qa=True`.
    regenerate_qa
        Force regeneration of the QA set even if a cached version exists.
    """
    narrative_page = vault.read("narrative", slug)
    if narrative_page is None:
        return {"slug": slug, "error": f"narrative {slug!r} not found"}

    # --- Step 1: QA set (generate or load cached) ---
    qa_items = [] if regenerate_qa else load_qa_set(vault, slug)
    qa_cost = 0.0
    if not qa_items:
        if not source_path:
            return {
                "slug": slug,
                "error": (
                    "no cached QA set; --source is required for first-time coverage run"
                ),
            }
        src_path = Path(source_path).expanduser()
        if not src_path.exists():
            return {"slug": slug, "error": f"source not found: {src_path}"}
        source_text = src_path.read_text(encoding="utf-8")
        title = str(narrative_page.meta.get("title") or slug)
        qa_items, qa_cost = generate_qa_set(vault, slug, title, source_text)
        if not qa_items:
            return {"slug": slug, "error": "QA generation failed or produced empty set"}
        save_qa_set(vault, slug, qa_items)

    # --- Step 2: coverage check ---
    statuses, check_cost = check_coverage(
        vault, slug, narrative_page.body, qa_items, judge_model=judge_model
    )

    # --- Step 3: aggregate + write gap report ---
    covered, partial, missing, errored = _tally(statuses)
    total = len(statuses)
    coverage_pct, unavailable = _coverage_pct(covered, partial, missing, errored)

    report = CoverageReport(
        slug=slug,
        total=total,
        covered=covered,
        partial=partial,
        missing=missing,
        coverage_pct=coverage_pct,
        errored=errored,
        unavailable=unavailable,
        items=statuses,
        cost_usd=qa_cost + check_cost,
        qa_set_path=str(qa_set_path(vault, slug).relative_to(vault.root)),
    )
    gap_path = write_gap_report(vault, slug, report)
    report.gap_report_path = str(gap_path.relative_to(vault.root))

    vault.append_log(
        "coverage_check",
        {
            "slug": slug,
            "covered": covered,
            "partial": partial,
            "missing": missing,
            "errored": errored,
            "total": total,
            "coverage_pct": _fmt_pct(coverage_pct),
            "cost_usd": f"{report.cost_usd:.4f}",
        },
    )

    return report.to_dict()


# ---------- iterative gap remediation (v5-5) ----------


@dataclass
class IterateResult:
    final_body: str
    iterations_run: int
    final_coverage: CoverageReport
    cost_usd: float
    converged: bool

    def to_dict(self) -> dict:
        return {
            "iterations_run": self.iterations_run,
            "converged": self.converged,
            "final_coverage": self.final_coverage.to_dict(),
            "cost_usd": round(self.cost_usd, 4),
        }


def _apply_gap_fix(
    vault: Vault,
    slug: str,
    title: str,
    narrative_body: str,
    source_text: str,
    statuses: list[CoverageStatus],
) -> tuple[str, float]:
    """Ask Claude to revise narrative_body to address missing/partial gaps.

    Returns (revised_body, cost). If no fix is applied or error, returns
    (original_body, cost).
    """
    gaps = [s for s in statuses if s.status in ("missing", "partial")]
    if not gaps:
        return narrative_body, 0.0
    gaps_json = json.dumps(
        [{"q": s.q, "status": s.status, "note": s.note} for s in gaps],
        ensure_ascii=False,
        indent=2,
    )
    result = llm.call_with_template(
        "coverage_qa_fix",
        {
            "slug": slug,
            "title": title,
            "narrative_body": narrative_body,
            "gaps_json": gaps_json,
            "source_text": source_text,
        },
    )
    llm.log_call(vault.append_log, "coverage_qa_fix", slug, result)
    if result.is_error:
        return narrative_body, result.cost_usd
    text = result.text.strip()
    if not text or text == "NO_FIXES_APPLIED":
        return narrative_body, result.cost_usd
    return text, result.cost_usd


def iterate_and_fix(
    vault: Vault,
    slug: str,
    title: str,
    narrative_body: str,
    source_text: str,
    *,
    coverage_threshold: float = 0.95,
    max_iterations: int = 3,
    judge_model: str = DEFAULT_JUDGE_MODEL,
    holdout: bool = True,
) -> IterateResult:
    """Iterate QuestEval remediation until coverage ≥ threshold or max_iterations.

    Flow per iteration:
      1. QA set (generate or load cached)
      2. check_coverage
      3. if coverage_pct/100 >= threshold: return (converged)
      4. _apply_gap_fix → revised body
      5. next iteration re-checks with same QA set

    The QA set is generated once (first iteration) and reused across rounds.
    Final narrative body is returned; caller handles commit + CoVe afterward.
    """
    body = narrative_body
    total_cost = 0.0
    iterations_run = 0
    converged = False

    # Generate or load QA set (once)
    qa_items = load_qa_set(vault, slug)
    if not qa_items:
        qa_items, qa_cost = generate_qa_set(vault, slug, title, source_text)
        total_cost += qa_cost
        if qa_items:
            save_qa_set(vault, slug, qa_items)

    if not qa_items:
        # QA generation failed; return original body with empty report
        empty_report = CoverageReport(
            slug=slug, total=0, covered=0, partial=0, missing=0,
            coverage_pct=None, unavailable=True, cost_usd=total_cost,
        )
        return IterateResult(
            final_body=body,
            iterations_run=0,
            final_coverage=empty_report,
            cost_usd=total_cost,
            converged=False,
        )

    statuses: list[CoverageStatus] = []
    coverage_pct: float | None = None
    unavailable = False

    for i in range(max_iterations):
        iterations_run = i + 1
        statuses, check_cost = check_coverage(vault, slug, body, qa_items, judge_model=judge_model)
        total_cost += check_cost
        covered, partial, missing, errored = _tally(statuses)
        coverage_pct, unavailable = _coverage_pct(covered, partial, missing, errored)

        if unavailable:
            # Judge unreliable this round — do NOT spend on gap remediation
            # against noise; abort the loop and report coverage as unmeasured.
            break

        if coverage_pct is not None and coverage_pct / 100.0 >= coverage_threshold:
            converged = True
            break

        # Attempt gap fix
        body, fix_cost = _apply_gap_fix(
            vault, slug, title, body, source_text, statuses,
        )
        total_cost += fix_cost

    # Final aggregation
    covered, partial, missing, errored = _tally(statuses)
    total = len(statuses)
    coverage_pct, unavailable = _coverage_pct(covered, partial, missing, errored)

    final_report = CoverageReport(
        slug=slug,
        total=total,
        covered=covered,
        partial=partial,
        missing=missing,
        coverage_pct=coverage_pct,
        errored=errored,
        unavailable=unavailable,
        items=statuses,
        cost_usd=total_cost,
        qa_set_path=str(qa_set_path(vault, slug).relative_to(vault.root)),
    )

    # --- Hold-out validation (anti teaching-to-the-test) ---
    # Measure the *final* body against an independent QA set the fixer never
    # optimized against. coverage_pct above is the in-sample (optimistic) number;
    # holdout_coverage_pct is the honest out-of-sample one. Measurement only —
    # we never fix against the hold-out set.
    if holdout:
        ho_items = load_qa_set(vault, slug, holdout=True)
        if not ho_items:
            ho_items, ho_gen_cost = generate_qa_set(vault, slug, title, source_text)
            total_cost += ho_gen_cost
            if ho_items:
                save_qa_set(vault, slug, ho_items, holdout=True)
        if ho_items:
            ho_statuses, ho_check_cost = check_coverage(
                vault, slug, body, ho_items, judge_model=judge_model
            )
            total_cost += ho_check_cost
            ho_covered, ho_partial, ho_missing, ho_errored = _tally(ho_statuses)
            ho_pct = _coverage_pct(ho_covered, ho_partial, ho_missing, ho_errored)[0]
            final_report.holdout_total = len(ho_statuses)
            final_report.holdout_covered = ho_covered
            final_report.holdout_coverage_pct = ho_pct  # None ⇒ judge failed, not 0%

    # Keep the report's cost in lockstep with the returned IterateResult.cost_usd
    # across every path (holdout off / on / gen-failed), so the two never diverge.
    final_report.cost_usd = total_cost

    # Persist gap report even for converged case (shows what's left)
    gap_path = write_gap_report(vault, slug, final_report)
    final_report.gap_report_path = str(gap_path.relative_to(vault.root))

    vault.append_log(
        "coverage_iterate",
        {
            "slug": slug,
            "iterations": iterations_run,
            "converged": "yes" if converged else "no",
            "unavailable": "yes" if final_report.unavailable else "no",
            "coverage_pct": _fmt_pct(final_report.coverage_pct),
            "holdout_pct": _fmt_pct(final_report.holdout_coverage_pct),
            "cost_usd": f"{total_cost:.4f}",
        },
    )

    return IterateResult(
        final_body=body,
        iterations_run=iterations_run,
        final_coverage=final_report,
        cost_usd=total_cost,
        converged=converged,
    )
