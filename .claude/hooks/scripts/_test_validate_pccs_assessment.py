#!/usr/bin/env python3
"""Tests for validate_pccs_assessment.py — CA1-CA8 LLM assessment validation."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from validate_pccs_assessment import validate_assessment


def _make_claim_map(*claim_ids: str) -> dict:
    return {"claims": [{"claim_id": cid} for cid in claim_ids]}


def _make_evaluator_entry(
    claim_id: str = "EMP-001",
    quality_score: int = 80,
    specificity: int = 20,
    evidence_alignment: int = 20,
    logical_soundness: int = 20,
    contribution: int = 20,
) -> dict:
    return {
        "claim_id": claim_id,
        "quality_score": quality_score,
        "specificity": specificity,
        "evidence_alignment": evidence_alignment,
        "logical_soundness": logical_soundness,
        "contribution": contribution,
    }


class TestCA1ClaimIdExistence(unittest.TestCase):
    def test_valid_ids(self):
        cm = _make_claim_map("EMP-001", "EMP-002")
        assessment = {"assessments": [
            _make_evaluator_entry("EMP-001"),
            _make_evaluator_entry("EMP-002"),
        ]}
        result = validate_assessment(assessment, cm, "evaluator")
        ca1 = next(c for c in result["checks"] if c["id"] == "CA1")
        self.assertTrue(ca1["passed"])

    def test_unknown_id(self):
        cm = _make_claim_map("EMP-001")
        assessment = {"assessments": [_make_evaluator_entry("FAKE-999")]}
        result = validate_assessment(assessment, cm, "evaluator")
        ca1 = next(c for c in result["checks"] if c["id"] == "CA1")
        self.assertFalse(ca1["passed"])


class TestCA2ScoreRange(unittest.TestCase):
    def test_valid_range(self):
        cm = _make_claim_map("EMP-001")
        assessment = {"assessments": [_make_evaluator_entry(quality_score=50)]}
        result = validate_assessment(assessment, cm, "evaluator")
        ca2 = next(c for c in result["checks"] if c["id"] == "CA2")
        self.assertTrue(ca2["passed"])

    def test_out_of_range(self):
        cm = _make_claim_map("EMP-001")
        assessment = {"assessments": [_make_evaluator_entry(quality_score=150)]}
        result = validate_assessment(assessment, cm, "evaluator")
        ca2 = next(c for c in result["checks"] if c["id"] == "CA2")
        self.assertFalse(ca2["passed"])


class TestCA5NoDuplicates(unittest.TestCase):
    def test_duplicates(self):
        cm = _make_claim_map("EMP-001")
        assessment = {"assessments": [
            _make_evaluator_entry("EMP-001"),
            _make_evaluator_entry("EMP-001"),
        ]}
        result = validate_assessment(assessment, cm, "evaluator")
        ca5 = next(c for c in result["checks"] if c["id"] == "CA5")
        self.assertFalse(ca5["passed"])


class TestCA6SubScorePresence(unittest.TestCase):
    def test_all_present(self):
        cm = _make_claim_map("EMP-001")
        assessment = {"assessments": [_make_evaluator_entry()]}
        result = validate_assessment(assessment, cm, "evaluator")
        ca6 = next(c for c in result["checks"] if c["id"] == "CA6")
        self.assertTrue(ca6["passed"])

    def test_missing_sub_score(self):
        cm = _make_claim_map("EMP-001")
        entry = _make_evaluator_entry()
        del entry["specificity"]
        assessment = {"assessments": [entry]}
        result = validate_assessment(assessment, cm, "evaluator")
        ca6 = next(c for c in result["checks"] if c["id"] == "CA6")
        self.assertFalse(ca6["passed"])

    def test_not_applied_to_critic(self):
        """CA6-CA8 should NOT run in critic mode."""
        cm = _make_claim_map("EMP-001")
        assessment = {"judgments": [{"claim_id": "EMP-001", "adjusted_score": 80}]}
        result = validate_assessment(assessment, cm, "critic")
        check_ids = {c["id"] for c in result["checks"]}
        self.assertNotIn("CA6", check_ids)
        self.assertNotIn("CA7", check_ids)
        self.assertNotIn("CA8", check_ids)


class TestCA7SubScoreRange(unittest.TestCase):
    def test_valid_range(self):
        cm = _make_claim_map("EMP-001")
        assessment = {"assessments": [_make_evaluator_entry(
            specificity=25, evidence_alignment=0, logical_soundness=15, contribution=10
        )]}
        result = validate_assessment(assessment, cm, "evaluator")
        ca7 = next(c for c in result["checks"] if c["id"] == "CA7")
        self.assertTrue(ca7["passed"])

    def test_out_of_range(self):
        cm = _make_claim_map("EMP-001")
        assessment = {"assessments": [_make_evaluator_entry(specificity=30)]}
        result = validate_assessment(assessment, cm, "evaluator")
        ca7 = next(c for c in result["checks"] if c["id"] == "CA7")
        self.assertFalse(ca7["passed"])

    def test_negative_sub_score(self):
        cm = _make_claim_map("EMP-001")
        assessment = {"assessments": [_make_evaluator_entry(contribution=-5)]}
        result = validate_assessment(assessment, cm, "evaluator")
        ca7 = next(c for c in result["checks"] if c["id"] == "CA7")
        self.assertFalse(ca7["passed"])


class TestCA8SumConsistency(unittest.TestCase):
    def test_consistent_sum(self):
        cm = _make_claim_map("EMP-001")
        # 20+20+20+20 = 80 == quality_score
        assessment = {"assessments": [_make_evaluator_entry(quality_score=80)]}
        result = validate_assessment(assessment, cm, "evaluator")
        ca8 = next(c for c in result["checks"] if c["id"] == "CA8")
        self.assertTrue(ca8["passed"])

    def test_inconsistent_sum(self):
        cm = _make_claim_map("EMP-001")
        # 20+20+20+20 = 80, but quality_score=85 → mismatch
        assessment = {"assessments": [_make_evaluator_entry(quality_score=85)]}
        result = validate_assessment(assessment, cm, "evaluator")
        ca8 = next(c for c in result["checks"] if c["id"] == "CA8")
        self.assertFalse(ca8["passed"])
        self.assertFalse(result["passed"])

    def test_partial_sub_scores_skip_ca8(self):
        """If some sub-scores are missing, CA8 should not fail (CA6 handles it)."""
        cm = _make_claim_map("EMP-001")
        entry = _make_evaluator_entry(quality_score=60)
        del entry["contribution"]
        assessment = {"assessments": [entry]}
        result = validate_assessment(assessment, cm, "evaluator")
        ca8 = next(c for c in result["checks"] if c["id"] == "CA8")
        # CA8 should pass because it can't validate without all sub-scores
        self.assertTrue(ca8["passed"])


class TestCriticMode(unittest.TestCase):
    def test_valid_critic(self):
        cm = _make_claim_map("EMP-001")
        assessment = {"judgments": [{"claim_id": "EMP-001", "adjusted_score": 75}]}
        result = validate_assessment(assessment, cm, "critic")
        self.assertTrue(result["passed"])

    def test_critic_missing_score(self):
        cm = _make_claim_map("EMP-001")
        assessment = {"judgments": [{"claim_id": "EMP-001"}]}
        result = validate_assessment(assessment, cm, "critic")
        ca3 = next(c for c in result["checks"] if c["id"] == "CA3")
        self.assertFalse(ca3["passed"])


class TestOverallResult(unittest.TestCase):
    def test_all_pass(self):
        cm = _make_claim_map("EMP-001")
        assessment = {"assessments": [_make_evaluator_entry()]}
        result = validate_assessment(assessment, cm, "evaluator")
        self.assertTrue(result["passed"])
        self.assertEqual(result["entries_count"], 1)

    def test_empty_entries(self):
        cm = _make_claim_map("EMP-001")
        assessment = {"assessments": []}
        result = validate_assessment(assessment, cm, "evaluator")
        ca4 = next(c for c in result["checks"] if c["id"] == "CA4")
        self.assertFalse(ca4["passed"])


if __name__ == "__main__":
    unittest.main()
