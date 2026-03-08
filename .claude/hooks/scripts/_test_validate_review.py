#!/usr/bin/env python3
"""Tests for validate_review.py — Adversarial Review validation (R1-R5).

Run: python3 -m pytest _test_validate_review.py -v
  or: python3 _test_validate_review.py
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import validate_review as vr


class TestReviewValidation(unittest.TestCase):
    """Test Adversarial Review validation rules R1-R5."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.review_dir = self.tmpdir / "review-logs"
        self.review_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_review_log(self, step, content):
        path = self.review_dir / f"step-{step}-review.md"
        path.write_text(content, encoding="utf-8")
        return path

    def _make_valid_review(self, step=1, verdict="PASS"):
        return (
            f"# Review Report — Step {step}\n\n"
            f"## Pre-mortem\n\n"
            f"Potential risks were assessed before review.\n\n"
            f"## Issues Found\n\n"
            f"| # | Severity | Description |\n"
            f"|---|----------|-------------|\n"
            f"| 1 | Minor | Citation format inconsistency (p.3) |\n\n"
            f"## Independent pACS\n\n"
            f"- F: 80\n- C: 75\n- L: 85\n\n"
            f"## Verdict: {verdict}\n"
        )

    def test_valid_review_log(self):
        self._write_review_log(1, self._make_valid_review())
        is_valid, verdict, issues_count, warnings = vr.validate_review_output(
            str(self.tmpdir), 1)
        self.assertTrue(is_valid, f"Valid review log should pass: {warnings}")

    def test_missing_file(self):
        is_valid, verdict, issues_count, warnings = vr.validate_review_output(
            str(self.tmpdir), 999)
        self.assertFalse(is_valid)

    def test_empty_file(self):
        self._write_review_log(1, "")
        is_valid, verdict, issues_count, warnings = vr.validate_review_output(
            str(self.tmpdir), 1)
        self.assertFalse(is_valid)


class TestNoSystemSOTReference(unittest.TestCase):
    def test_no_state_yaml_reference(self):
        src = Path(__file__).parent / "validate_review.py"
        content = src.read_text(encoding="utf-8")
        self.assertNotIn("state.yaml", content,
                         "validate_review.py must not reference system SOT")


class TestValidateFileCoverage(unittest.TestCase):
    """Tests for validate_file_coverage() — CR6 check (P1 deterministic).

    validate_file_coverage(review_path, files_to_check) returns
    (is_valid: bool, missing_files: list[str], warnings: list[str]).
    """

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.review_file = self.tmpdir / "step-5-review.md"

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_review(self, content):
        self.review_file.write_text(content, encoding="utf-8")

    def test_all_files_mentioned(self):
        """All requested files appear in report → valid=True, missing=[]."""
        from _context_lib import validate_file_coverage
        self._write_review(
            "# Code Review\n\n"
            "## Files Reviewed\n"
            "- `src/main.py`: reviewed logic\n"
            "- `src/utils.py`: reviewed helpers\n\n"
            "## Verdict: PASS\n"
        )
        is_valid, missing, warnings = validate_file_coverage(
            str(self.review_file), ["src/main.py", "src/utils.py"]
        )
        self.assertTrue(is_valid)
        self.assertEqual(missing, [])

    def test_one_file_missing(self):
        """One file not mentioned → valid=False, missing=[basename of that file].

        Note: validate_file_coverage strips to basename for matching.
        'src/utils.py' → searches for 'utils.py' in content → missing=['utils.py'].
        """
        from _context_lib import validate_file_coverage
        self._write_review(
            "# Code Review\n\n"
            "- `src/main.py`: reviewed\n\n"
            "## Verdict: PASS\n"
        )
        is_valid, missing, warnings = validate_file_coverage(
            str(self.review_file), ["src/main.py", "src/utils.py"]
        )
        self.assertFalse(is_valid)
        self.assertIn("utils.py", missing)   # basename returned
        self.assertNotIn("main.py", missing)

    def test_all_files_missing(self):
        """No requested files mentioned → all appear in missing list."""
        from _context_lib import validate_file_coverage
        self._write_review("# Code Review\n\nNo files mentioned.\n")
        is_valid, missing, warnings = validate_file_coverage(
            str(self.review_file), ["a.py", "b.py"]
        )
        self.assertFalse(is_valid)
        self.assertIn("a.py", missing)
        self.assertIn("b.py", missing)

    def test_empty_files_list_always_valid(self):
        """Empty files_to_check → always valid (no files required)."""
        from _context_lib import validate_file_coverage
        self._write_review("# Code Review\n\nContent.\n")
        is_valid, missing, warnings = validate_file_coverage(
            str(self.review_file), []
        )
        self.assertTrue(is_valid)
        self.assertEqual(missing, [])

    def test_missing_review_file(self):
        """Non-existent review file → valid=False with warning."""
        from _context_lib import validate_file_coverage
        is_valid, missing, warnings = validate_file_coverage(
            str(self.tmpdir / "nonexistent.md"), ["some.py"]
        )
        self.assertFalse(is_valid)
        self.assertTrue(len(warnings) > 0)

    def test_file_name_partial_match(self):
        """File name appears as substring in review content → counts as covered."""
        from _context_lib import validate_file_coverage
        self._write_review(
            "Reviewed checklist_manager.py in detail.\n\n## Verdict: PASS\n"
        )
        is_valid, missing, warnings = validate_file_coverage(
            str(self.review_file), ["checklist_manager.py"]
        )
        self.assertTrue(is_valid)
        self.assertEqual(missing, [])

    def test_warnings_include_missing_files(self):
        """Warnings must name the missing files for Orchestrator remediation."""
        from _context_lib import validate_file_coverage
        self._write_review("# Review\n\nOnly mentions main.py\n")
        is_valid, missing, warnings = validate_file_coverage(
            str(self.review_file), ["main.py", "missing_file.py"]
        )
        self.assertFalse(is_valid)
        self.assertTrue(
            any("missing_file.py" in w for w in warnings),
            f"Warning must mention missing file: {warnings}"
        )


if __name__ == "__main__":
    unittest.main()
