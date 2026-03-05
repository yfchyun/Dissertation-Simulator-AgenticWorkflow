#!/usr/bin/env python3
"""Tests for validate_srcs_threshold.py — SRCS threshold validation."""

import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from validate_srcs_threshold import compute_weighted_srcs, validate_scores, SRCS_THRESHOLD


class TestComputeWeightedSRCS(unittest.TestCase):
    """Test weighted SRCS computation."""

    def test_perfect_scores(self):
        scores = {"CS": 100, "GS": 100, "US": 100, "VS": 100}
        result = compute_weighted_srcs(scores, "EMPIRICAL")
        self.assertEqual(result, 100.0)

    def test_zero_scores(self):
        scores = {"CS": 0, "GS": 0, "US": 0, "VS": 0}
        result = compute_weighted_srcs(scores, "EMPIRICAL")
        self.assertEqual(result, 0.0)

    def test_empirical_weights(self):
        scores = {"CS": 80, "GS": 80, "US": 80, "VS": 80}
        result = compute_weighted_srcs(scores, "EMPIRICAL")
        self.assertAlmostEqual(result, 80.0)

    def test_theoretical_weights(self):
        scores = {"CS": 100, "GS": 50, "US": 100, "VS": 100}
        result_emp = compute_weighted_srcs(scores, "EMPIRICAL")
        result_theo = compute_weighted_srcs(scores, "THEORETICAL")
        self.assertGreater(result_emp, 0)
        self.assertGreater(result_theo, 0)

    def test_unknown_claim_type_uses_default(self):
        scores = {"CS": 80, "GS": 80, "US": 80, "VS": 80}
        result = compute_weighted_srcs(scores, "UNKNOWN_TYPE")
        self.assertGreater(result, 0)

    def test_partial_scores(self):
        scores = {"CS": 90, "GS": 70, "US": 60, "VS": 80}
        result = compute_weighted_srcs(scores, "EMPIRICAL")
        self.assertGreater(result, 60)
        self.assertLess(result, 90)

    def test_invalid_score_raises(self):
        scores = {"CS": -10, "GS": 80, "US": 80, "VS": 80}
        with self.assertRaises(ValueError):
            compute_weighted_srcs(scores, "EMPIRICAL")


class TestValidateScores(unittest.TestCase):
    """Test score validation against threshold."""

    def test_above_threshold_passes(self):
        scores = {"CS": 90, "GS": 90, "US": 90, "VS": 90}
        result = validate_scores(scores, "EMPIRICAL")
        self.assertTrue(result["passed"])

    def test_below_threshold_fails(self):
        scores = {"CS": 30, "GS": 30, "US": 30, "VS": 30}
        result = validate_scores(scores, "EMPIRICAL")
        self.assertFalse(result["passed"])

    def test_exact_threshold_passes(self):
        scores = {"CS": 75, "GS": 75, "US": 75, "VS": 75}
        result = validate_scores(scores, "EMPIRICAL")
        self.assertTrue(result["passed"])

    def test_result_includes_weighted_score(self):
        scores = {"CS": 80, "GS": 80, "US": 80, "VS": 80}
        result = validate_scores(scores, "EMPIRICAL")
        self.assertIn("weighted_score", result)
        self.assertAlmostEqual(result["weighted_score"], 80.0)

    def test_result_includes_claim_type(self):
        scores = {"CS": 80, "GS": 80, "US": 80, "VS": 80}
        result = validate_scores(scores, "EMPIRICAL")
        self.assertEqual(result["claim_type"], "EMPIRICAL")

    def test_below_threshold_axes_detected(self):
        scores = {"CS": 90, "GS": 30, "US": 90, "VS": 90}
        result = validate_scores(scores, "EMPIRICAL")
        self.assertIn("GS", result["below_threshold_axes"])

    def test_threshold_constant(self):
        self.assertEqual(SRCS_THRESHOLD, 75)


class TestNoSystemSOTReference(unittest.TestCase):
    def test_no_state_yaml_reference(self):
        content = (SCRIPT_DIR / "validate_srcs_threshold.py").read_text(encoding="utf-8")
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            self.assertNotIn("state.yaml", line, f"Line {i}")
            self.assertNotIn("state.yml", line, f"Line {i}")


if __name__ == "__main__":
    unittest.main()
