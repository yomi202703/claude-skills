#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only adapter over the host domain's judgment outputs (S8).

THIS IS THE FILE THE HOST ADAPTS. Reads must be side-effect-free (S8): never
mutate state, never auto-claim, never write back. Return the unit list, each
unit's input text + evidence spans, and the judge outputs (proposer + the
production judge under test).

The DemoAdapter below is an in-memory fixture so the template runs as-is.
Replace it with a real adapter (SQL / file reads) for your domain — keep the
same method signatures so server.py is unchanged.
"""
from __future__ import annotations

from typing import Protocol


class Adapter(Protocol):
    def units(self) -> list[dict]:
        """[{unit_key, label}] — one row per review unit (S7)."""
        ...

    def unit_input(self, unit_key: str) -> dict:
        """{text, evidence:[{idx, span_label}]} — input + evidence to highlight."""
        ...

    def judges(self, unit_key: str, axis_key: str) -> dict:
        """Machine outputs for one unit/axis. NEVER shown to a reviewer before
        commit (S3); revealed only after commit (S4) and in developer mode.
        {proposer:{verdict,reason,evidence}, production:{verdict,reason,evidence}}"""
        ...


class DemoAdapter:
    """Fixture: 6 units, 2 axes, with agreement and divergence mixed, so the
    developer surface (unit list + evidence + every judge + Problems queue) has
    something real to navigate out of the box. Replace with a real adapter."""

    _UNITS = [{"unit_key": f"通話-{i:03d}", "label": f"通話-{i:03d}"} for i in range(1, 7)]
    _INPUT = {
        "通話-001": {
            "text": "0: 顧客が残高を尋ねる\n1: 担当者が「元本保証で必ず増える」と述べる\n2: 顧客が同意",
            "evidence": [{"idx": 1, "span_label": "元本保証で必ず増える"}],
        },
        "通話-002": {
            "text": "0: 定例の状況確認\n1: 担当者が決済日を確認",
            "evidence": [],
        },
        "通話-003": {
            "text": "0: 顧客がためらう\n1: 担当者が「今日中に決めてください」と言う\n2: 担当者が「今夜で締め切ります」と繰り返す",
            "evidence": [{"idx": 1, "span_label": "今日中に決めて"}, {"idx": 2, "span_label": "今夜で締め切り"}],
        },
        "通話-004": {
            "text": "0: 担当者が商品を説明\n1: 担当者が「過去の実績は将来を保証しません」と述べる\n2: 顧客がリスクを了承",
            "evidence": [{"idx": 1, "span_label": "リスク開示あり"}],
        },
        "通話-005": {
            "text": "0: 顧客が損失を心配\n1: 担当者が「大丈夫ですよ、心配いりません」と言う",
            "evidence": [{"idx": 1, "span_label": "大丈夫ですよ"}],
        },
        "通話-006": {
            "text": "0: 顧客が苦情を申し立てる\n1: 担当者が記録し受付番号を伝える",
            "evidence": [{"idx": 1, "span_label": "受付番号を発行"}],
        },
    }
    _JUDGES = {
        # 一致
        ("通話-001", "concern"): {
            "proposer": {"verdict": "要確認", "reason": "元本保証を断定している", "evidence": [1]},
            "production": {"verdict": "要確認", "reason": "保証を示す表現あり", "evidence": [1]},
        },
        ("通話-001", "evidence_quality"): {
            "proposer": {"verdict": "十分", "reason": "1行目に明確な保証発言", "evidence": [1]},
            "production": {"verdict": "十分", "reason": "引用が明確", "evidence": [1]},
        },
        # 懸念で食い違い（提案器=問題なし / 本番=要確認）
        ("通話-002", "concern"): {
            "proposer": {"verdict": "問題なし", "reason": "定例の確認のみ", "evidence": []},
            "production": {"verdict": "要確認", "reason": "決済への言及あり", "evidence": [1]},
        },
        ("通話-002", "evidence_quality"): {
            "proposer": {"verdict": "なし", "reason": "判断対象なし", "evidence": []},
            "production": {"verdict": "薄い", "reason": "決済の行は根拠が弱い", "evidence": [1]},
        },
        # 懸念は一致、根拠の質で食い違い
        ("通話-003", "concern"): {
            "proposer": {"verdict": "要確認", "reason": "強い急かし", "evidence": [1, 2]},
            "production": {"verdict": "要確認", "reason": "圧力的な勧誘", "evidence": [1]},
        },
        ("通話-003", "evidence_quality"): {
            "proposer": {"verdict": "十分", "reason": "急かしの根拠が2か所", "evidence": [1, 2]},
            "production": {"verdict": "薄い", "reason": "1か所しか拾えていない", "evidence": [1]},
        },
        # 一致（問題なし）
        ("通話-004", "concern"): {
            "proposer": {"verdict": "問題なし", "reason": "リスクを適切に開示", "evidence": [1]},
            "production": {"verdict": "問題なし", "reason": "適合的な開示", "evidence": [1]},
        },
        ("通話-004", "evidence_quality"): {
            "proposer": {"verdict": "十分", "reason": "開示箇所を引用", "evidence": [1]},
            "production": {"verdict": "十分", "reason": "明確", "evidence": [1]},
        },
        # 懸念で食い違い（提案器=要確認 / 本番=問題なし）
        ("通話-005", "concern"): {
            "proposer": {"verdict": "要確認", "reason": "損失への安易な打ち消し", "evidence": [1]},
            "production": {"verdict": "問題なし", "reason": "口語的で助言ではない", "evidence": []},
        },
        ("通話-005", "evidence_quality"): {
            "proposer": {"verdict": "薄い", "reason": "曖昧な安心づけ", "evidence": [1]},
            "production": {"verdict": "薄い", "reason": "情報量が低い", "evidence": [1]},
        },
        # 懸念は一致、根拠の質で食い違い
        ("通話-006", "concern"): {
            "proposer": {"verdict": "問題なし", "reason": "苦情を手順どおり処理", "evidence": [1]},
            "production": {"verdict": "問題なし", "reason": "定型的な対応", "evidence": [1]},
        },
        ("通話-006", "evidence_quality"): {
            "proposer": {"verdict": "十分", "reason": "受付番号を記録", "evidence": [1]},
            "production": {"verdict": "なし", "reason": "記録の行を見落とし", "evidence": []},
        },
    }

    def units(self) -> list[dict]:
        return list(self._UNITS)

    def unit_input(self, unit_key: str) -> dict:
        return self._INPUT.get(unit_key, {"text": "", "evidence": []})

    def judges(self, unit_key: str, axis_key: str) -> dict:
        return self._JUDGES.get((unit_key, axis_key), {"proposer": {}, "production": {}})


def divergence(judges: dict) -> bool:
    """True when proposer and production judge disagree (drives the queue, S4)."""
    p = (judges.get("proposer") or {}).get("verdict")
    q = (judges.get("production") or {}).get("verdict")
    return p is not None and q is not None and p != q
