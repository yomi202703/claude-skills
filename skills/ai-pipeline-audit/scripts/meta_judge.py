from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Any, Literal

JudgeVerdict = Literal["valid", "invalid", "uncertain"]

# Judge roles, in fixed order. families arrays align to this order.
ROLES = ("cheap", "expensive", "tiebreaker")


@dataclass
class Disagreement:
    finding_index: int
    cheap_verdict: JudgeVerdict
    expensive_verdict: JudgeVerdict
    tiebreaker_verdict: JudgeVerdict | None
    final: JudgeVerdict
    dropped_roles: list[str] = field(default_factory=list)  # self-preference guard
    low_diversity: bool = False
    position_bias: bool = False


def _majority(votes: list[JudgeVerdict]) -> JudgeVerdict:
    """A verdict needs at least two agreeing votes; otherwise uncertain.

    A panel of correlated judges amplifies bias rather than cancelling it, so a
    bare single vote is never enough to confirm a finding."""
    if len(votes) < 2:
        return "uncertain"
    counts: dict[JudgeVerdict, int] = {v: votes.count(v) for v in set(votes)}
    best, n = max(counts.items(), key=lambda kv: kv[1])
    return best if n >= 2 else "uncertain"


def reconcile(
    *,
    cheap: list[JudgeVerdict],
    expensive: list[JudgeVerdict],
    tiebreaker: list[JudgeVerdict] | None,
    families: list[str] | None = None,
    evaluatee_families: list[str] | None = None,
    swapped: list[JudgeVerdict] | None = None,
) -> tuple[list[JudgeVerdict], list[Disagreement]]:
    """Reconcile judge verdicts into a final verdict per finding.

    families: one model-family label per role (aligned to ROLES). When two or
        more contributing judges share a family, the finding is marked
        low_diversity — diverse judges (different provider/scale) are what make a
        panel more reliable than a single judge, not panel size.
    evaluatee_families: per-finding family of the thing being judged. A judge
        whose family matches is dropped for that finding (self-preference guard).
    swapped: a second verdict array for the same findings with inputs reordered.
        A flip versus `cheap` flags position_bias for that finding.
    """
    n = len(cheap)
    if len(expensive) != n:
        raise ValueError("cheap and expensive must have same length")
    tb = tiebreaker if tiebreaker is not None else [None] * n
    if len(tb) != n:
        raise ValueError("tiebreaker length mismatch")
    if families is not None and len(families) != len(ROLES):
        raise ValueError("families must have one label per role (cheap, expensive, tiebreaker)")
    if evaluatee_families is not None and len(evaluatee_families) != n:
        raise ValueError("evaluatee_families length mismatch")
    if swapped is not None and len(swapped) != n:
        raise ValueError("swapped length mismatch")

    fam_of: dict[str, str] = dict(zip(ROLES, families)) if families is not None else {}

    finals: list[JudgeVerdict] = []
    disagreements: list[Disagreement] = []
    for i in range(n):
        role_votes: list[tuple[str, JudgeVerdict]] = [
            ("cheap", cheap[i]),
            ("expensive", expensive[i]),
        ]
        tbv = tb[i]
        if tbv is not None:
            role_votes.append(("tiebreaker", tbv))

        dropped: list[str] = []
        if evaluatee_families is not None and families is not None:
            kept: list[tuple[str, JudgeVerdict]] = []
            for role, v in role_votes:
                if fam_of.get(role) == evaluatee_families[i]:
                    dropped.append(role)
                else:
                    kept.append((role, v))
            role_votes = kept

        final = _majority([v for _, v in role_votes])

        low_div = False
        if families is not None and len(role_votes) >= 2:
            contributing = [fam_of.get(role) for role, _ in role_votes]
            low_div = len(set(contributing)) < len(contributing)

        pos_bias = swapped is not None and swapped[i] != cheap[i]

        finals.append(final)
        if cheap[i] != expensive[i] or dropped or low_div or pos_bias:
            disagreements.append(Disagreement(
                finding_index=i,
                cheap_verdict=cheap[i],
                expensive_verdict=expensive[i],
                tiebreaker_verdict=tb[i],
                final=final,
                dropped_roles=dropped,
                low_diversity=low_div,
                position_bias=pos_bias,
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


def calibrate(
    predicted: list[JudgeVerdict],
    labels: list[JudgeVerdict],
) -> dict[str, float]:
    """Estimate TPR / FPR of the reconciled verdict against a labelled set.

    Imperfect judges can invalidate naive pass/fail statistics; a small labelled
    calibration set lets the caller estimate how often the panel is right."""
    if len(predicted) != len(labels):
        raise ValueError("predicted and labels must be same length")
    tp = fp = tn = fn = 0
    for p, l in zip(predicted, labels):
        p_pos, l_pos = p == "valid", l == "valid"
        if l_pos and p_pos:
            tp += 1
        elif l_pos and not p_pos:
            fn += 1
        elif not l_pos and p_pos:
            fp += 1
        else:
            tn += 1
    tpr = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return {"tpr": tpr, "fpr": fpr, "tp": tp, "fp": fp, "tn": tn, "fn": fn}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Reconcile diverse judge verdicts with bias guards."
    )
    ap.add_argument("--input", required=True,
                    help='JSON file: {"findings":[...], "cheap":[...], "expensive":[...], '
                         '"tiebreaker":[...]?, "families":[...]?, "evaluatee_families":[...]?, '
                         '"swapped":[...]?, "calibration":{"predicted":[...],"labels":[...]}?}')
    ns = ap.parse_args(argv)
    with open(ns.input, "r", encoding="utf-8") as f:
        data = json.load(f)
    finals, disagreements = reconcile(
        cheap=data["cheap"],
        expensive=data["expensive"],
        tiebreaker=data.get("tiebreaker"),
        families=data.get("families"),
        evaluatee_families=data.get("evaluatee_families"),
        swapped=data.get("swapped"),
    )
    findings = data.get("findings") or []
    kept = filter_findings(findings, finals, keep=("valid",))
    out: dict[str, Any] = {
        "kept": kept,
        "verdicts": finals,
        "disagreements": [d.__dict__ for d in disagreements],
    }
    cal = data.get("calibration")
    if cal:
        out["calibration"] = calibrate(cal["predicted"], cal["labels"])
    json.dump(out, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
