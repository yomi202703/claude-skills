from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any, Literal

JudgeVerdict = Literal["valid", "invalid", "uncertain"]


@dataclass
class Disagreement:
    finding_index: int
    cheap_verdict: JudgeVerdict
    expensive_verdict: JudgeVerdict
    tiebreaker_verdict: JudgeVerdict | None
    final: JudgeVerdict


def reconcile(
    *,
    cheap: list[JudgeVerdict],
    expensive: list[JudgeVerdict],
    tiebreaker: list[JudgeVerdict] | None,
) -> tuple[list[JudgeVerdict], list[Disagreement]]:
    if len(cheap) != len(expensive):
        raise ValueError("cheap and expensive must have same length")
    tb = tiebreaker if tiebreaker is not None else [None] * len(cheap)
    if len(tb) != len(cheap):
        raise ValueError("tiebreaker length mismatch")

    finals: list[JudgeVerdict] = []
    disagreements: list[Disagreement] = []
    for i, (c, e, t) in enumerate(zip(cheap, expensive, tb)):
        if c == e:
            finals.append(c)
            continue
        if t is None:
            final: JudgeVerdict = "uncertain"
        else:
            votes = [c, e, t]
            counts = {v: votes.count(v) for v in set(votes)}
            best = max(counts.items(), key=lambda kv: kv[1])
            final = best[0] if best[1] >= 2 else "uncertain"
        finals.append(final)
        disagreements.append(Disagreement(
            finding_index=i,
            cheap_verdict=c,
            expensive_verdict=e,
            tiebreaker_verdict=t,
            final=final,
        ))
    return finals, disagreements


def filter_findings(
    findings: list[dict[str, Any]],
    verdicts: list[JudgeVerdict],
    *,
    keep: tuple[str, ...] = ("valid",),
) -> list[dict[str, Any]]:
    if len(findings) != len(verdicts):
        raise ValueError("findings and verdicts must be same length")
    return [f for f, v in zip(findings, verdicts) if v in keep]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Reconcile cheap / expensive / tie-breaker verdicts."
    )
    ap.add_argument("--input", required=True,
                    help='JSON file: {"findings":[...], "cheap":[...], "expensive":[...], "tiebreaker":[...]?}')
    ns = ap.parse_args(argv)
    with open(ns.input, "r", encoding="utf-8") as f:
        data = json.load(f)
    finals, disagreements = reconcile(
        cheap=data["cheap"],
        expensive=data["expensive"],
        tiebreaker=data.get("tiebreaker"),
    )
    findings = data.get("findings") or []
    kept = filter_findings(findings, finals, keep=("valid",))
    json.dump({
        "kept": kept,
        "verdicts": finals,
        "disagreements": [d.__dict__ for d in disagreements],
    }, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
