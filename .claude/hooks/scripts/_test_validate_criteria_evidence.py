#!/usr/bin/env python3
"""Tests for validate_criteria_evidence.py — VE1-VE5 P1 evidence cross-check.

Run: python3 -m pytest _test_validate_criteria_evidence.py -v
  or: python3 _test_validate_criteria_evidence.py
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from validate_criteria_evidence import (
    check_ve1_heading_count,
    check_ve2_no_placeholder,
    check_ve3_item_count,
    check_ve4_trace_markers,
    check_ve5_field_presence,
    parse_verification_log,
    validate_criteria_evidence,
)


class TestVE1HeadingCount(unittest.TestCase):
    """VE1: Section/heading count verification."""

    def test_sufficient_headings_pass(self):
        result = check_ve1_heading_count(
            "5개 섹션 포함",
            "# Title\n## Intro\n## Analysis\n## Comparison\n## Rec\n## Ref\n"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "VE1")
        self.assertEqual(result["p1_result"], "PASS")

    def test_insufficient_headings_fail(self):
        result = check_ve1_heading_count(
            "5 sections included",
            "# Title\n## Intro\n## Analysis\n"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["p1_result"], "FAIL")
        self.assertIn("3", result["detail"])

    def test_non_heading_criterion_returns_none(self):
        result = check_ve1_heading_count(
            "all URLs valid",
            "# Title\n## Intro\n"
        )
        self.assertIsNone(result)

    def test_at_least_pattern(self):
        result = check_ve1_heading_count(
            "at least 3 sections present",
            "# A\n## B\n## C\n## D\n"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["p1_result"], "PASS")

    def test_gte_pattern(self):
        result = check_ve1_heading_count(
            "≥ 4 headings",
            "# A\n## B\n### C\n#### D\n"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["p1_result"], "PASS")


class TestVE2NoPlaceholder(unittest.TestCase):
    """VE2: Placeholder/invalid URL absence verification."""

    def test_clean_output_pass(self):
        result = check_ve2_no_placeholder(
            "no placeholder URLs present",
            "Visit https://real-site.com for details.\n"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["p1_result"], "PASS")

    def test_placeholder_detected_fail(self):
        result = check_ve2_no_placeholder(
            "placeholder 없음",
            "See https://example.com/api for the endpoint.\n"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["p1_result"], "FAIL")

    def test_todo_detected_fail(self):
        result = check_ve2_no_placeholder(
            "no TODO or placeholder markers",
            "## Analysis\nTODO: complete this section\n"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["p1_result"], "FAIL")

    def test_non_placeholder_criterion_returns_none(self):
        result = check_ve2_no_placeholder(
            "5 sections included",
            "some content"
        )
        self.assertIsNone(result)


class TestVE3ItemCount(unittest.TestCase):
    """VE3: Item/row/element count verification."""

    def test_sufficient_list_items_pass(self):
        result = check_ve3_item_count(
            "≥ 3 항목",
            "- Item 1\n- Item 2\n- Item 3\n- Item 4\n"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["p1_result"], "PASS")

    def test_insufficient_items_fail(self):
        result = check_ve3_item_count(
            "at least 5 items",
            "- Item 1\n- Item 2\n"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["p1_result"], "FAIL")

    def test_table_rows_count(self):
        result = check_ve3_item_count(
            "3개 이상 데이터",
            "| Name | Price |\n|------|-------|\n| A | 10 |\n| B | 20 |\n| C | 30 |\n"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["p1_result"], "PASS")

    def test_competitor_pattern(self):
        result = check_ve3_item_count(
            "경쟁사 3곳 이상",
            "- CompetitorA: pricing\n- CompetitorB: pricing\n- CompetitorC: pricing\n"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["p1_result"], "PASS")

    def test_non_count_criterion_returns_none(self):
        result = check_ve3_item_count(
            "all URLs valid",
            "- item 1\n- item 2\n"
        )
        self.assertIsNone(result)


class TestVE4TraceMarkers(unittest.TestCase):
    """VE4: [trace:step-N] marker count verification."""

    def test_sufficient_markers_pass(self):
        result = check_ve4_trace_markers(
            "[trace:step-N] 마커 ≥ 3개",
            "Content [trace:step-1:intro] here.\n"
            "More [trace:step-2:analysis] content.\n"
            "Final [trace:step-3:conclusion] point.\n"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["p1_result"], "PASS")

    def test_insufficient_markers_fail(self):
        result = check_ve4_trace_markers(
            "at least 5 [trace:step-N] markers",
            "Content [trace:step-1] here.\n"
            "More [trace:step-2] content.\n"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["p1_result"], "FAIL")

    def test_non_trace_criterion_returns_none(self):
        result = check_ve4_trace_markers(
            "5 sections present",
            "[trace:step-1] content"
        )
        self.assertIsNone(result)


class TestVE5FieldPresence(unittest.TestCase):
    """VE5: Specific field/keyword presence verification."""

    def test_all_fields_present_pass(self):
        result = check_ve5_field_presence(
            "contains fields (name, price, features)",
            "The name of the product is X.\nThe price is $10.\nKey features include...\n"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["p1_result"], "PASS")

    def test_missing_field_fail(self):
        result = check_ve5_field_presence(
            "필드 (name, price, features) 포함",
            "The name of the product is X.\nKey features include...\n"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["p1_result"], "FAIL")
        self.assertIn("price", result["detail"])

    def test_non_field_criterion_returns_none(self):
        result = check_ve5_field_presence(
            "5 sections present",
            "some content"
        )
        self.assertIsNone(result)


class TestParseVerificationLog(unittest.TestCase):
    """Test verification log parsing."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_parse_table_format(self):
        content = (
            "# Verification Log\n\n"
            "| Criterion | Result | Evidence |\n"
            "|-----------|--------|----------|\n"
            "| 5 sections present | PASS | found 6 headings |\n"
            "| No placeholder URLs | PASS | clean output |\n\n"
            "## Overall Result: PASS\n"
        )
        path = self.tmpdir / "verify.md"
        path.write_text(content)
        criteria = parse_verification_log(str(path))
        self.assertEqual(len(criteria), 2)
        self.assertEqual(criteria[0]["name"], "5 sections present")
        self.assertEqual(criteria[0]["result"], "PASS")

    def test_parse_missing_file(self):
        criteria = parse_verification_log("/nonexistent/path.md")
        self.assertEqual(criteria, [])


class TestIntegration(unittest.TestCase):
    """Integration tests for full validate_criteria_evidence flow."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.verify_dir = self.tmpdir / "verification-logs"
        self.verify_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_hallucination_detected(self):
        """Agent says PASS for 5 sections, but output has only 2 → HALLUCINATION."""
        # Verification log claims 5 sections PASS
        verify_content = (
            "# Verification Log — Step 1\n\n"
            "| Criterion | Result | Evidence |\n"
            "|-----------|--------|----------|\n"
            "| 5 sections present | PASS | all 5 sections found in output |\n\n"
            "## Overall Result: PASS\n"
        )
        (self.verify_dir / "step-1-verify.md").write_text(verify_content)

        # Actual output has only 2 headings
        output_file = self.tmpdir / "output.md"
        output_file.write_text("# Title\n## Intro\nSome content only.\n")

        result = validate_criteria_evidence(
            str(self.tmpdir), 1, str(output_file)
        )
        self.assertEqual(result["hallucinations_detected"], 1)
        self.assertFalse(result["passed"])
        self.assertEqual(result["results"][0]["status"], "HALLUCINATION_DETECTED")

    def test_confirmed_pass(self):
        """Agent says PASS and P1 confirms → CONFIRMED."""
        verify_content = (
            "# Verification Log — Step 2\n\n"
            "| Criterion | Result | Evidence |\n"
            "|-----------|--------|----------|\n"
            "| ≥ 3 sections present | PASS | found 4 sections in the output document |\n\n"
            "## Overall Result: PASS\n"
        )
        (self.verify_dir / "step-2-verify.md").write_text(verify_content)

        output_file = self.tmpdir / "output.md"
        output_file.write_text(
            "# Title\n## Section A\nContent.\n## Section B\nContent.\n"
            "## Section C\nContent.\n## Section D\nContent.\n"
        )

        result = validate_criteria_evidence(
            str(self.tmpdir), 2, str(output_file)
        )
        self.assertEqual(result["hallucinations_detected"], 0)
        self.assertTrue(result["passed"])
        self.assertEqual(result["results"][0]["status"], "CONFIRMED")

    def test_non_verifiable_criteria_skipped(self):
        """Criteria that don't match VE patterns should be skipped."""
        verify_content = (
            "# Verification Log — Step 3\n\n"
            "| Criterion | Result | Evidence |\n"
            "|-----------|--------|----------|\n"
            "| Analysis depth is sufficient | PASS | thorough analysis provided with examples |\n\n"
            "## Overall Result: PASS\n"
        )
        (self.verify_dir / "step-3-verify.md").write_text(verify_content)

        output_file = self.tmpdir / "output.md"
        output_file.write_text("# Analysis\nSome content.\n")

        result = validate_criteria_evidence(
            str(self.tmpdir), 3, str(output_file)
        )
        self.assertEqual(result["verifiable_criteria"], 0)
        self.assertEqual(result["verified"], 0)
        self.assertTrue(result["passed"])

    def test_missing_output_file_graceful(self):
        """Missing output file should not crash — graceful skip."""
        verify_content = (
            "# Verification Log — Step 4\n\n"
            "| Criterion | Result | Evidence |\n"
            "|-----------|--------|----------|\n"
            "| 3 sections present | PASS | found sections |\n\n"
            "## Overall Result: PASS\n"
        )
        (self.verify_dir / "step-4-verify.md").write_text(verify_content)

        result = validate_criteria_evidence(
            str(self.tmpdir), 4, "/nonexistent/file.md"
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["verifiable_criteria"], 0)

    def test_placeholder_hallucination(self):
        """Agent says no placeholders, but output has example.com → HALLUCINATION."""
        verify_content = (
            "# Verification Log — Step 5\n\n"
            "| Criterion | Result | Evidence |\n"
            "|-----------|--------|----------|\n"
            "| no placeholder URLs present | PASS | all URLs checked and valid in output |\n\n"
            "## Overall Result: PASS\n"
        )
        (self.verify_dir / "step-5-verify.md").write_text(verify_content)

        output_file = self.tmpdir / "output.md"
        output_file.write_text(
            "# Resources\n"
            "- API: https://example.com/api/v1\n"
            "- Docs: https://real-site.com/docs\n"
        )

        result = validate_criteria_evidence(
            str(self.tmpdir), 5, str(output_file)
        )
        self.assertEqual(result["hallucinations_detected"], 1)
        self.assertFalse(result["passed"])

    def test_multiple_criteria_mixed(self):
        """Mix of verifiable and non-verifiable criteria."""
        verify_content = (
            "# Verification Log — Step 6\n\n"
            "| Criterion | Result | Evidence |\n"
            "|-----------|--------|----------|\n"
            "| ≥ 3 sections present | PASS | found 4 sections in complete document |\n"
            "| Analysis is thorough | PASS | comprehensive analysis with data support |\n"
            "| no placeholder links | PASS | all links verified as real and working |\n\n"
            "## Overall Result: PASS\n"
        )
        (self.verify_dir / "step-6-verify.md").write_text(verify_content)

        output_file = self.tmpdir / "output.md"
        output_file.write_text(
            "# Title\n## Intro\nContent.\n## Method\nContent.\n"
            "## Results\nContent.\n## Conclusion\nContent.\n"
        )

        result = validate_criteria_evidence(
            str(self.tmpdir), 6, str(output_file)
        )
        # VE1 (headings) and VE2 (no placeholder) are verifiable
        self.assertGreaterEqual(result["verifiable_criteria"], 1)
        self.assertTrue(result["passed"])


class TestNoSystemSOTWrite(unittest.TestCase):
    """Ensure script never writes to SOT."""

    def test_no_state_yaml_write(self):
        src = Path(__file__).parent / "validate_criteria_evidence.py"
        content = src.read_text(encoding="utf-8")
        # Should not contain write mode open calls
        self.assertNotIn(', "w"', content)
        self.assertNotIn(", 'w'", content)
        self.assertNotIn("write_text(", content)
        self.assertNotIn("write_bytes(", content)
        # Read-only access is fine (detect_output_path reads SOT)
        self.assertIn("read-only", content.lower())


if __name__ == "__main__":
    unittest.main()
