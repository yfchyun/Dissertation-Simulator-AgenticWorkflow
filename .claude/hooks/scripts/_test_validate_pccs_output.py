#!/usr/bin/env python3
"""Tests for validate_pccs_output.py — PC1-PC6 structural validation."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from validate_pccs_output import validate_pccs_report


def _make_report(
    claims=None,
    summary=None,
    decision=None,
    step=1,
    file_name="test.md",
):
    """Helper to build a pCCS report for testing."""
    if claims is None:
        claims = [
            {
                "claim_id": "LS-001",
                "canonical_type": "FACTUAL",
                "p1_score": 90.0,
                "raw_agent": 92,
                "llm_assessment": None,
                "cal_delta": 0.0,
                "blocked": False,
                "pccs": 85.5,
                "color": "GREEN",
            }
        ]
    if summary is None:
        green = sum(1 for c in claims if c.get("color") == "GREEN")
        yellow = sum(1 for c in claims if c.get("color") == "YELLOW")
        red = sum(1 for c in claims if c.get("color") == "RED")
        mean = sum(c["pccs"] for c in claims) / max(len(claims), 1)
        summary = {
            "total_claims": len(claims),
            "green": green,
            "yellow": yellow,
            "red": red,
            "mean_pccs": round(mean, 1),
        }
    if decision is None:
        decision = {"action": "proceed", "red_claim_ids": []}
    return {
        "step": step,
        "file": file_name,
        "summary": summary,
        "decision": decision,
        "claims": claims,
        "pcae": {
            "e1_numeric_contradictions": [],
            "e2_duplicate_claims": [],
            "e3_source_conflicts": [],
        },
    }


class TestPC1RequiredFields(unittest.TestCase):
    def test_valid_report(self):
        result = validate_pccs_report(_make_report())
        pc1 = next(c for c in result["checks"] if c["id"] == "PC1")
        self.assertTrue(pc1["passed"])

    def test_missing_claims(self):
        report = _make_report()
        del report["claims"]
        result = validate_pccs_report(report)
        pc1 = next(c for c in result["checks"] if c["id"] == "PC1")
        self.assertFalse(pc1["passed"])


class TestPC2ScoreRanges(unittest.TestCase):
    def test_valid_scores(self):
        result = validate_pccs_report(_make_report())
        pc2 = next(c for c in result["checks"] if c["id"] == "PC2")
        self.assertTrue(pc2["passed"])

    def test_pccs_over_100(self):
        claims = [{"claim_id": "X-001", "canonical_type": "FACTUAL",
                    "p1_score": 90.0, "pccs": 105.0, "color": "GREEN",
                    "raw_agent": 90, "cal_delta": 0, "blocked": False, "llm_assessment": None}]
        result = validate_pccs_report(_make_report(claims=claims))
        pc2 = next(c for c in result["checks"] if c["id"] == "PC2")
        self.assertFalse(pc2["passed"])

    def test_pccs_negative(self):
        claims = [{"claim_id": "X-001", "canonical_type": "FACTUAL",
                    "p1_score": 90.0, "pccs": -5.0, "color": "RED",
                    "raw_agent": 90, "cal_delta": 0, "blocked": False, "llm_assessment": None}]
        result = validate_pccs_report(_make_report(claims=claims))
        pc2 = next(c for c in result["checks"] if c["id"] == "PC2")
        self.assertFalse(pc2["passed"])


class TestPC3ColorClassification(unittest.TestCase):
    def test_correct_colors(self):
        claims = [
            {"claim_id": "A-001", "canonical_type": "F", "p1_score": 90, "pccs": 85.0,
             "color": "GREEN", "raw_agent": 90, "cal_delta": 0, "blocked": False, "llm_assessment": None},
            {"claim_id": "B-001", "canonical_type": "F", "p1_score": 60, "pccs": 55.0,
             "color": "YELLOW", "raw_agent": 60, "cal_delta": 0, "blocked": False, "llm_assessment": None},
            {"claim_id": "C-001", "canonical_type": "F", "p1_score": 30, "pccs": 35.0,
             "color": "RED", "raw_agent": 30, "cal_delta": 0, "blocked": False, "llm_assessment": None},
        ]
        result = validate_pccs_report(_make_report(claims=claims))
        pc3 = next(c for c in result["checks"] if c["id"] == "PC3")
        self.assertTrue(pc3["passed"])

    def test_wrong_color(self):
        claims = [{"claim_id": "X-001", "canonical_type": "F", "p1_score": 90, "pccs": 85.0,
                    "color": "RED", "raw_agent": 90, "cal_delta": 0, "blocked": False, "llm_assessment": None}]
        result = validate_pccs_report(_make_report(claims=claims))
        pc3 = next(c for c in result["checks"] if c["id"] == "PC3")
        self.assertFalse(pc3["passed"])


class TestPC4DecisionConsistency(unittest.TestCase):
    def test_proceed_with_no_reds(self):
        result = validate_pccs_report(_make_report())
        pc4 = next(c for c in result["checks"] if c["id"] == "PC4")
        self.assertTrue(pc4["passed"])

    def test_rewrite_claims_with_1_red(self):
        claims = [
            {"claim_id": "A-001", "canonical_type": "FACTUAL", "p1_score": 30, "pccs": 30.0,
             "color": "RED", "raw_agent": 30, "cal_delta": 0, "blocked": False, "llm_assessment": None},
        ]
        decision = {"action": "rewrite_claims", "red_claim_ids": ["A-001"]}
        result = validate_pccs_report(_make_report(claims=claims, decision=decision))
        pc4 = next(c for c in result["checks"] if c["id"] == "PC4")
        self.assertTrue(pc4["passed"])

    def test_wrong_action(self):
        """0 reds but action=rewrite_step → PC4 fail."""
        decision = {"action": "rewrite_step", "red_claim_ids": []}
        result = validate_pccs_report(_make_report(decision=decision))
        pc4 = next(c for c in result["checks"] if c["id"] == "PC4")
        self.assertFalse(pc4["passed"])


class TestPC5SummaryCounts(unittest.TestCase):
    def test_correct_counts(self):
        result = validate_pccs_report(_make_report())
        pc5 = next(c for c in result["checks"] if c["id"] == "PC5")
        self.assertTrue(pc5["passed"])

    def test_wrong_total(self):
        report = _make_report()
        report["summary"]["total_claims"] = 999
        result = validate_pccs_report(report)
        pc5 = next(c for c in result["checks"] if c["id"] == "PC5")
        self.assertFalse(pc5["passed"])


class TestPC6UniqueClaimIds(unittest.TestCase):
    def test_unique(self):
        result = validate_pccs_report(_make_report())
        pc6 = next(c for c in result["checks"] if c["id"] == "PC6")
        self.assertTrue(pc6["passed"])

    def test_duplicates(self):
        claims = [
            {"claim_id": "LS-001", "canonical_type": "F", "p1_score": 90, "pccs": 85,
             "color": "GREEN", "raw_agent": 90, "cal_delta": 0, "blocked": False, "llm_assessment": None},
            {"claim_id": "LS-001", "canonical_type": "F", "p1_score": 80, "pccs": 75,
             "color": "GREEN", "raw_agent": 80, "cal_delta": 0, "blocked": False, "llm_assessment": None},
        ]
        result = validate_pccs_report(_make_report(claims=claims))
        pc6 = next(c for c in result["checks"] if c["id"] == "PC6")
        self.assertFalse(pc6["passed"])


if __name__ == "__main__":
    unittest.main()
