#!/usr/bin/env python3
"""Tests for _claim_patterns.py — centralized claim ID patterns."""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _claim_patterns import (
    CLAIM_ID_VALIDATE_RE,
    CLAIM_ID_INLINE_RE,
    count_claims,
    extract_claim_ids,
)


class TestClaimIdValidateRe(unittest.TestCase):
    """Test the validation regex (with anchors, for single ID strings)."""

    def test_simple_ids(self):
        for cid in ["LS-001", "GI-007", "CMB-014", "SWA-002", "TRA-003"]:
            self.assertRegex(cid, CLAIM_ID_VALIDATE_RE, f"{cid} should match")

    def test_multi_hyphen_ids(self):
        for cid in ["EMP-NEURO-001", "CR-LOGIC-001", "MC-IV-002"]:
            self.assertRegex(cid, CLAIM_ID_VALIDATE_RE, f"{cid} should match")

    def test_no_dash_before_digits(self):
        self.assertRegex("PHIL-T001", CLAIM_ID_VALIDATE_RE)

    def test_synth_ids(self):
        self.assertRegex("SYNTH-001", CLAIM_ID_VALIDATE_RE)
        self.assertRegex("SYNTH-009", CLAIM_ID_VALIDATE_RE)

    def test_rejects_lowercase(self):
        self.assertNotRegex("ls-001", CLAIM_ID_VALIDATE_RE)

    def test_rejects_single_digit(self):
        self.assertNotRegex("LS-1", CLAIM_ID_VALIDATE_RE)

    def test_rejects_no_digits(self):
        self.assertNotRegex("LS-ABC", CLAIM_ID_VALIDATE_RE)

    def test_rejects_too_long_prefix(self):
        self.assertNotRegex("ABCDEFG-001", CLAIM_ID_VALIDATE_RE)

    def test_four_digit_ids(self):
        self.assertRegex("LS-0001", CLAIM_ID_VALIDATE_RE)

    def test_rejects_five_digits(self):
        self.assertNotRegex("LS-00001", CLAIM_ID_VALIDATE_RE)


class TestCountClaims(unittest.TestCase):
    """Test count_claims function."""

    def test_no_claims(self):
        self.assertEqual(count_claims("No claims here"), 0)

    def test_simple_claims(self):
        self.assertEqual(count_claims("id: LS-001"), 1)
        self.assertEqual(count_claims("id: LS-001\nid: LS-002"), 2)

    def test_multi_hyphen(self):
        self.assertEqual(count_claims("id: EMP-NEURO-001"), 1)
        self.assertEqual(count_claims("id: CR-LOGIC-001\nid: MC-IV-002"), 2)

    def test_claim_id_prefix(self):
        self.assertEqual(count_claims("claim_id: PHIL-T001"), 1)

    def test_quoted(self):
        self.assertEqual(count_claims('id: "LS-001"'), 1)
        self.assertEqual(count_claims("id: 'LS-001'"), 1)

    def test_bold_bracket_not_double_counted(self):
        self.assertEqual(
            count_claims('**[PHIL-T001]** claim_id: PHIL-T001'), 1
        )

    def test_mixed_formats(self):
        content = """
id: LS-001
id: EMP-NEURO-002
claim_id: PHIL-T003
id: "SYNTH-004"
"""
        self.assertEqual(count_claims(content), 4)


class TestExtractClaimIds(unittest.TestCase):
    """Test extract_claim_ids function."""

    def test_simple(self):
        self.assertEqual(extract_claim_ids("id: LS-001"), ["LS-001"])

    def test_multi_hyphen(self):
        content = "id: EMP-NEURO-001\nid: CR-LOGIC-002"
        self.assertEqual(
            extract_claim_ids(content),
            ["EMP-NEURO-001", "CR-LOGIC-002"],
        )

    def test_claim_id_prefix(self):
        self.assertEqual(
            extract_claim_ids("claim_id: PHIL-T001"), ["PHIL-T001"]
        )

    def test_empty(self):
        self.assertEqual(extract_claim_ids(""), [])
        self.assertEqual(extract_claim_ids("no claims"), [])


if __name__ == "__main__":
    unittest.main()
