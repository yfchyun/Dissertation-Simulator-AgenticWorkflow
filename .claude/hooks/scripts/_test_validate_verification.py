#!/usr/bin/env python3
"""Tests for validate_verification.py — Verification Gate validation (V1a-V1e).

Run: python3 -m pytest _test_validate_verification.py -v
  or: python3 _test_validate_verification.py
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import validate_verification as vv


class TestVerificationValidation(unittest.TestCase):
    """Test Verification Gate validation rules V1a-V1c."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.verify_dir = self.tmpdir / "verification-logs"
        self.verify_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_verify_log(self, step, content):
        path = self.verify_dir / f"step-{step}-verify.md"
        path.write_text(content, encoding="utf-8")
        return path

    def _make_valid_verification(self, step=1):
        return (
            f"# Verification Log — Step {step}\n\n"
            f"## Criteria Check\n\n"
            f"| Criterion | Result | Evidence |\n"
            f"|-----------|--------|----------|\n"
            f"| Output exists | PASS | File size: 2048 bytes |\n"
            f"| Min quality | PASS | Contains 5 GroundedClaims |\n"
            f"| Format valid | PASS | YAML schema validated |\n\n"
            f"## Overall Result: PASS\n"
        )

    def test_valid_verification_log(self):
        from _context_lib import validate_verification_log
        self._write_verify_log(1, self._make_valid_verification())
        is_valid, warnings = validate_verification_log(str(self.tmpdir), 1)
        self.assertTrue(is_valid, f"Valid verification log should pass: {warnings}")

    def test_missing_file(self):
        from _context_lib import validate_verification_log
        is_valid, warnings = validate_verification_log(str(self.tmpdir), 999)
        self.assertFalse(is_valid)

    def test_empty_file(self):
        from _context_lib import validate_verification_log
        self._write_verify_log(1, "")
        is_valid, warnings = validate_verification_log(str(self.tmpdir), 1)
        self.assertFalse(is_valid)


class TestGenerateVerificationLog(unittest.TestCase):
    """Test that generate_verification_log() produces V1a-V1c compliant output."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.verify_dir = self.tmpdir / "verification-logs"
        self.verify_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_generated_log_passes_v1a_v1e(self):
        """Generated log must pass validate_verification_log() (V1a-V1e)."""
        from _context_lib import generate_verification_log, validate_verification_log

        content = generate_verification_log(42, [
            {"criterion": "L0: Output exists", "result": "PASS", "evidence": "file.md exists, 2048 bytes on disk"},
            {"criterion": "pACS above threshold", "result": "PASS", "evidence": "pACS = 75, GREEN zone (F=80, C=75, L=82)"},
            {"criterion": "GroundedClaim compliance", "result": "PASS", "evidence": "12 claims validated, all with source refs"},
        ])
        path = self.verify_dir / "step-42-verify.md"
        path.write_text(content, encoding="utf-8")

        is_valid, warnings = validate_verification_log(str(self.tmpdir), 42)
        self.assertTrue(is_valid, f"Generated log should pass V1a-V1e: {warnings}")

    def test_auto_derives_fail(self):
        """If any criterion is FAIL, overall must be FAIL."""
        from _context_lib import generate_verification_log

        content = generate_verification_log(10, [
            {"criterion": "L0: Output exists", "result": "PASS", "evidence": "ok"},
            {"criterion": "pACS threshold", "result": "FAIL", "evidence": "pACS = 38"},
        ])
        self.assertIn("## Overall Result: FAIL", content)

    def test_auto_derives_pass(self):
        """If all criteria PASS, overall must be PASS."""
        from _context_lib import generate_verification_log

        content = generate_verification_log(10, [
            {"criterion": "L0: Output exists", "result": "PASS", "evidence": "ok"},
        ])
        self.assertIn("## Overall Result: PASS", content)

    def test_minimum_size(self):
        """Generated log must be at least 100 bytes (V1a size check)."""
        from _context_lib import generate_verification_log

        content = generate_verification_log(1, [
            {"criterion": "Test", "result": "PASS", "evidence": "evidence text here"},
        ])
        self.assertGreaterEqual(len(content.encode("utf-8")), 100)

    def test_pipe_escaping(self):
        """Pipe characters in evidence must be escaped to prevent table breakage."""
        from _context_lib import generate_verification_log

        content = generate_verification_log(1, [
            {"criterion": "Test", "result": "PASS", "evidence": "a|b|c"},
        ])
        self.assertNotIn("| a|b|c |", content)
        self.assertIn("a\\|b\\|c", content)

    def test_empty_criteria(self):
        """Empty criteria list should produce valid markdown."""
        from _context_lib import generate_verification_log

        content = generate_verification_log(1, [])
        self.assertIn("# Verification Log", content)
        self.assertIn("## Overall Result: PASS", content)


class TestV1dEvidenceQuality(unittest.TestCase):
    """Test V1d: Evidence must be >= 20 chars to prevent lazy verification."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.verify_dir = self.tmpdir / "verification-logs"
        self.verify_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_short_evidence_triggers_v1d_fail(self):
        """Evidence shorter than 20 chars should trigger V1d FAIL."""
        from _context_lib import validate_verification_log

        content = (
            "# Verification Log — Step 1\n\n"
            "| Criterion | Result | Evidence |\n"
            "|-----------|--------|----------|\n"
            "| Data collected | PASS | ok |\n\n"
            "## Overall Result: PASS\n"
        )
        (self.verify_dir / "step-1-verify.md").write_text(content)
        is_valid, warnings = validate_verification_log(str(self.tmpdir), 1)
        self.assertFalse(is_valid)
        self.assertTrue(any("V1d FAIL" in w for w in warnings))

    def test_substantive_evidence_passes_v1d(self):
        """Evidence >= 20 chars should pass V1d."""
        from _context_lib import validate_verification_log

        content = (
            "# Verification Log — Step 1\n\n"
            "| Criterion | Result | Evidence |\n"
            "|-----------|--------|----------|\n"
            "| Data collected from 3 sources | PASS | 5 rows from source A, 4 rows from source B, 3 rows from source C |\n\n"
            "## Overall Result: PASS\n"
        )
        (self.verify_dir / "step-1-verify.md").write_text(content)
        is_valid, warnings = validate_verification_log(str(self.tmpdir), 1)
        self.assertTrue(is_valid, f"Substantive evidence should pass: {warnings}")

    def test_checklist_format_skips_v1d(self):
        """V1d only applies to table format (evidence column). Checklist has no evidence column."""
        from _context_lib import validate_verification_log

        content = (
            "# Verification Log — Step 1\n\n"
            "- [x] Data collected: PASS\n"
            "- [x] Format valid: PASS\n\n"
            "## Overall Result: PASS\n"
        )
        (self.verify_dir / "step-1-verify.md").write_text(content)
        is_valid, warnings = validate_verification_log(str(self.tmpdir), 1)
        # No V1d warnings for checklist format (no evidence column to check)
        self.assertFalse(any("V1d" in w for w in warnings))


class TestV1eCompoundCriteria(unittest.TestCase):
    """Test V1e: Compound criteria detection (WARNING only)."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.verify_dir = self.tmpdir / "verification-logs"
        self.verify_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_compound_criterion_triggers_v1e_warning(self):
        """Criteria with 'and' conjunction should trigger V1e WARNING."""
        from _context_lib import validate_verification_log

        content = (
            "# Verification Log — Step 1\n\n"
            "| Criterion | Result | Evidence |\n"
            "|-----------|--------|----------|\n"
            "| Data collected and analysis complete | PASS | collected 5 rows and produced comparison table |\n\n"
            "## Overall Result: PASS\n"
        )
        (self.verify_dir / "step-1-verify.md").write_text(content)
        is_valid, warnings = validate_verification_log(str(self.tmpdir), 1)
        # V1e is WARNING only — should NOT cause is_valid=False
        self.assertTrue(is_valid, f"V1e warning should not invalidate: {warnings}")
        self.assertTrue(any("V1e WARNING" in w for w in warnings))

    def test_atomic_criterion_no_v1e_warning(self):
        """Atomic criteria without conjunctions should not trigger V1e."""
        from _context_lib import validate_verification_log

        content = (
            "# Verification Log — Step 1\n\n"
            "| Criterion | Result | Evidence |\n"
            "|-----------|--------|----------|\n"
            "| Source A data >= 3 rows | PASS | 5 rows collected from source A endpoint |\n\n"
            "## Overall Result: PASS\n"
        )
        (self.verify_dir / "step-1-verify.md").write_text(content)
        is_valid, warnings = validate_verification_log(str(self.tmpdir), 1)
        self.assertTrue(is_valid)
        self.assertFalse(any("V1e" in w for w in warnings))


class TestNoSystemSOTReference(unittest.TestCase):
    def test_no_state_yaml_reference(self):
        src = Path(__file__).parent / "validate_verification.py"
        content = src.read_text(encoding="utf-8")
        self.assertNotIn("state.yaml", content,
                         "validate_verification.py must not reference system SOT")


if __name__ == "__main__":
    unittest.main()
