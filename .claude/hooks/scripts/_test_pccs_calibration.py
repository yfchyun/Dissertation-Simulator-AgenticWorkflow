#!/usr/bin/env python3
"""Tests for pccs_calibration.py — calibration delta computation."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pccs_calibration import compute_calibration, VERDICT_TO_SCORE, L1_RESULT_TO_SCORE


class TestVerdictMapping(unittest.TestCase):
    """Test ground truth score mappings."""

    def test_tier1_mappings(self):
        self.assertEqual(VERDICT_TO_SCORE["verified"], 90)
        self.assertEqual(VERDICT_TO_SCORE["partially verified"], 60)
        self.assertEqual(VERDICT_TO_SCORE["unable to verify"], 40)
        self.assertEqual(VERDICT_TO_SCORE["outdated"], 30)
        self.assertEqual(VERDICT_TO_SCORE["false"], 10)

    def test_tier2_mappings(self):
        self.assertEqual(L1_RESULT_TO_SCORE["pass"], 85)
        self.assertEqual(L1_RESULT_TO_SCORE["fail"], 30)


class TestComputeCalibration(unittest.TestCase):
    """Test calibration computation."""

    def test_no_data(self):
        """No logs → cal_delta = 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = compute_calibration(tmpdir, 63, 85.0)
            self.assertEqual(result["cal_delta"], 0.0)
            self.assertEqual(result["tier1_samples"], 0)
            self.assertEqual(result["tier2_samples"], 0)

    def test_empty_logs_dirs(self):
        """Empty log directories → cal_delta = 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "dialogue-logs").mkdir()
            (Path(tmpdir) / "verification-logs").mkdir()
            result = compute_calibration(tmpdir, 63, 85.0)
            self.assertEqual(result["cal_delta"], 0.0)

    def test_tier2_verification_logs(self):
        """Verification logs with PASS/FAIL should produce tier2 samples."""
        with tempfile.TemporaryDirectory() as tmpdir:
            vdir = Path(tmpdir) / "verification-logs"
            vdir.mkdir()
            # Write a verification log with PASS results
            (vdir / "step-5-verify.md").write_text(
                "| Criterion | PASS | Evidence |\n"
                "| Criterion 2 | PASS | Evidence 2 |\n"
                "| Criterion 3 | FAIL | No evidence |\n"
            )
            result = compute_calibration(tmpdir, 63, 85.0)
            self.assertGreater(result["tier2_samples"], 0)
            self.assertIsNotNone(result["tier2_delta"])

    def test_computed_at_step(self):
        """Step number should be recorded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = compute_calibration(tmpdir, 99, 90.0)
            self.assertEqual(result["computed_at_step"], 99)
            self.assertEqual(result["agent_mean_confidence"], 90.0)

    def test_tier1_fc_suffix_filename(self):
        """Fact-checker files named step-{N}-r{K}-fc.md should be scanned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ddir = Path(tmpdir) / "dialogue-logs"
            ddir.mkdir()
            # Write a fact-checker log with the actual naming convention
            (ddir / "step-5-r1-fc.md").write_text(
                "claim_id: EMP-001\n"
                "verdict: Verified\n\n"
                "claim_id: EMP-002\n"
                "verdict: False\n"
            )
            result = compute_calibration(tmpdir, 63, 85.0)
            self.assertGreater(result["tier1_samples"], 0,
                               "Files ending with -fc.md must be detected as fact-checker logs")
            self.assertIsNotNone(result["tier1_delta"])

    def test_tier1_fact_check_in_name(self):
        """Legacy filenames containing 'fact-check' should also be scanned."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ddir = Path(tmpdir) / "dialogue-logs"
            ddir.mkdir()
            (ddir / "step-3-fact-check.md").write_text(
                "claim_id: METH-001\n"
                "verdict: Partially Verified\n"
            )
            result = compute_calibration(tmpdir, 63, 85.0)
            self.assertGreater(result["tier1_samples"], 0,
                               "Files with 'fact-check' in name must be detected")

    def test_tier1_non_fc_file_ignored(self):
        """Non fact-checker files in dialogue-logs should be ignored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ddir = Path(tmpdir) / "dialogue-logs"
            ddir.mkdir()
            # Reviewer file — should NOT be scanned for Tier 1
            (ddir / "step-5-r1-rv.md").write_text(
                "claim_id: EMP-001\n"
                "verdict: Verified\n"
            )
            result = compute_calibration(tmpdir, 63, 85.0)
            self.assertEqual(result["tier1_samples"], 0,
                             "Reviewer files (-rv.md) must not be counted as Tier 1")

    def test_tier1_and_tier2_combined(self):
        """Both tiers contribute to cal_delta with weighted combination."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Tier 1: fact-checker says Verified (score=90)
            ddir = Path(tmpdir) / "dialogue-logs"
            ddir.mkdir()
            (ddir / "step-5-r1-fc.md").write_text(
                "claim_id: EMP-001\nverdict: Verified\n"
            )
            # Tier 2: L1 says PASS (score=85)
            vdir = Path(tmpdir) / "verification-logs"
            vdir.mkdir()
            (vdir / "step-5-verify.md").write_text(
                "| Criterion | PASS | Evidence |\n"
            )
            # agent_mean=90: tier1_delta=90-90=0, tier2_delta=90-85=5
            # weighted = (0*2.0 + 5*1.0) / 3.0 = 1.666... ≈ 1.7
            result = compute_calibration(tmpdir, 63, 90.0)
            self.assertGreater(result["tier1_samples"], 0)
            self.assertGreater(result["tier2_samples"], 0)
            self.assertEqual(result["tier1_delta"], 0.0)
            self.assertEqual(result["tier2_delta"], 5.0)
            self.assertAlmostEqual(result["cal_delta"], 1.7, places=1)


if __name__ == "__main__":
    unittest.main()
