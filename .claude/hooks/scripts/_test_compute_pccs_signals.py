#!/usr/bin/env python3
"""Tests for compute_pccs_signals.py — Phase A P1 signal extraction."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from compute_pccs_signals import compute_claim_map, compute_p1_signals


class TestComputeP1Signals(unittest.TestCase):
    """Test per-claim P1 signal computation."""

    def test_well_sourced_empirical(self):
        """Well-sourced EMPIRICAL claim should get high P1 score."""
        claim = {
            "claim_id": "EMP-001",
            "claim_type": "EMPIRICAL",
            "canonical_type": "EMPIRICAL",
            "confidence_raw": "95",
            "confidence_numeric": 95,
            "has_source": True,
            "has_citation": True,
            "source_text": "Author (2020)",
        }
        content = "id: EMP-001 some text (Author, 2020) with citation"
        result = compute_p1_signals(claim, content)
        self.assertGreaterEqual(result["p1_score"], 80)
        self.assertTrue(result["p1_signals"]["a1_has_citation"])
        self.assertTrue(result["p1_signals"]["a5_confidence_explicit"])
        self.assertTrue(result["p1_signals"]["a6_type_recognized"])
        self.assertFalse(result["p1_signals"]["a3_blocked"])

    def test_blocked_claim(self):
        """Claim with absolute language should get a3_blocked=True and low score."""
        claim = {
            "claim_id": "LS-001",
            "claim_type": None,
            "canonical_type": "UNKNOWN",
            "confidence_raw": None,
            "confidence_numeric": 50,
            "has_source": False,
            "has_citation": False,
            "source_text": "",
        }
        content = "id: LS-001 all studies agree that this is true without exception"
        result = compute_p1_signals(claim, content)
        self.assertTrue(result["p1_signals"]["a3_blocked"])
        self.assertLessEqual(result["p1_score"], 30)

    def test_missing_confidence(self):
        """Claim without explicit confidence should get a5=False."""
        claim = {
            "claim_id": "LS-002",
            "claim_type": "FACTUAL",
            "canonical_type": "FACTUAL",
            "confidence_raw": None,
            "confidence_numeric": 50,
            "has_source": True,
            "has_citation": True,
            "source_text": "Author (2020)",
        }
        content = "id: LS-002 text about something"
        result = compute_p1_signals(claim, content)
        self.assertFalse(result["p1_signals"]["a5_confidence_explicit"])

    def test_trace_marker_present(self):
        """Claim near a trace marker should get a2=True."""
        claim = {
            "claim_id": "TF-001",
            "claim_type": "THEORETICAL",
            "canonical_type": "THEORETICAL",
            "confidence_raw": "85",
            "confidence_numeric": 85,
            "has_source": True,
            "has_citation": True,
            "source_text": "Author (2019)",
        }
        content = "[trace:step-5] This builds on... id: TF-001 the theory states..."
        result = compute_p1_signals(claim, content)
        self.assertTrue(result["p1_signals"]["a2_has_trace"])

    def test_score_range(self):
        """P1 score should always be in [0, 100]."""
        # Worst case: all negative signals
        claim = {
            "claim_id": "BAD-001",
            "claim_type": None,
            "canonical_type": "UNKNOWN",
            "confidence_raw": None,
            "confidence_numeric": 50,
            "has_source": False,
            "has_citation": False,
            "source_text": "",
        }
        content = "id: BAD-001 all studies agree 100%certain no exceptions"
        result = compute_p1_signals(claim, content)
        self.assertGreaterEqual(result["p1_score"], 0)
        self.assertLessEqual(result["p1_score"], 100)


class TestComputeClaimMap(unittest.TestCase):
    """Test full claim-map generation."""

    def test_yaml_file(self):
        """YAML format file should produce valid claim-map."""
        content = """```yaml
- id: EMP-001
  claim_type: EMPIRICAL
  confidence: 95
  claim: "Something important."
  source: "Author (2020)"
- id: EMP-002
  claim_type: ANALYTICAL
  confidence: 88
  claim: "Another thing."
  source: "Author2 (2021)"
```"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            tmp_path = f.name

        try:
            result = compute_claim_map(tmp_path, step=63)
            self.assertEqual(result["step"], 63)
            self.assertEqual(result["total_claims"], 2)
            self.assertEqual(len(result["claims"]), 2)

            c1 = result["claims"][0]
            self.assertEqual(c1["claim_id"], "EMP-001")
            self.assertEqual(c1["canonical_type"], "EMPIRICAL")
            self.assertEqual(c1["confidence_numeric"], 95)
            self.assertIn("p1_signals", c1)
            self.assertIn("p1_score", c1)

            c2 = result["claims"][1]
            self.assertEqual(c2["canonical_type"], "INTERPRETIVE")  # ANALYTICAL → INTERPRETIVE
        finally:
            os.unlink(tmp_path)

    def test_blockquote_file(self):
        """Blockquote format file should produce valid claim-map."""
        content = """> **[PHIL-T001]** claim_id: PHIL-T001
> claim_text: "Turing reframed the question."
> source: "Turing (1950)"
> confidence: high
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(content)
            tmp_path = f.name

        try:
            result = compute_claim_map(tmp_path, step=47)
            self.assertEqual(result["total_claims"], 1)
            c = result["claims"][0]
            self.assertEqual(c["claim_id"], "PHIL-T001")
            self.assertEqual(c["confidence_numeric"], 90)  # "high" → 90
            self.assertEqual(c["canonical_type"], "UNKNOWN")  # no claim_type in blockquote
        finally:
            os.unlink(tmp_path)

    def test_nonexistent_file(self):
        """Missing file should produce error dict, not crash."""
        result = compute_claim_map("/nonexistent/file.md", step=1)
        self.assertEqual(result["total_claims"], 0)
        self.assertIn("error", result)

    def test_empty_file(self):
        """Empty file should produce zero claims."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Just a heading\n\nNo claims here.")
            tmp_path = f.name

        try:
            result = compute_claim_map(tmp_path, step=1)
            self.assertEqual(result["total_claims"], 0)
        finally:
            os.unlink(tmp_path)


if __name__ == "__main__":
    unittest.main()
