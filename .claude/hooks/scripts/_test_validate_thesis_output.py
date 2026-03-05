#!/usr/bin/env python3
"""Tests for validate_thesis_output.py — P1 structural validation."""

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from validate_thesis_output import (
    validate_wave,
    WAVE_OUTPUTS,
    FILE_CLAIM_PREFIXES,
    MIN_OUTPUT_SIZE,
)


class TestWaveOutputMapping(unittest.TestCase):
    """Test WAVE_OUTPUTS constants."""

    def test_five_waves_defined(self):
        self.assertEqual(len(WAVE_OUTPUTS), 5)

    def test_wave_1_has_4_files(self):
        self.assertEqual(len(WAVE_OUTPUTS[1]), 4)

    def test_wave_2_has_4_files(self):
        self.assertEqual(len(WAVE_OUTPUTS[2]), 4)

    def test_wave_3_has_4_files(self):
        self.assertEqual(len(WAVE_OUTPUTS[3]), 4)

    def test_wave_4_has_2_files(self):
        self.assertEqual(len(WAVE_OUTPUTS[4]), 2)

    def test_wave_5_has_1_file(self):
        self.assertEqual(len(WAVE_OUTPUTS[5]), 1)

    def test_all_files_have_md_extension(self):
        for wave, files in WAVE_OUTPUTS.items():
            for f in files:
                self.assertTrue(f.endswith(".md"), f"Wave {wave}: {f}")


class TestClaimPrefixes(unittest.TestCase):
    """Test FILE_CLAIM_PREFIXES mapping."""

    def test_15_files_mapped(self):
        self.assertEqual(len(FILE_CLAIM_PREFIXES), 15)

    def test_all_wave_files_have_prefix(self):
        for wave, files in WAVE_OUTPUTS.items():
            for f in files:
                self.assertIn(f, FILE_CLAIM_PREFIXES,
                              f"Wave {wave}: {f} missing prefix")

    def test_known_prefixes(self):
        self.assertEqual(FILE_CLAIM_PREFIXES["01-literature-search-strategy.md"], "LS")
        self.assertEqual(FILE_CLAIM_PREFIXES["09-critical-review.md"], "CR")
        self.assertEqual(FILE_CLAIM_PREFIXES["15-plagiarism-report.md"], "PC")


class TestValidateWave(unittest.TestCase):
    """Test wave validation logic."""

    def test_nonexistent_project(self):
        result = validate_wave("/nonexistent/path", 1)
        self.assertFalse(result["passed"])

    def test_invalid_wave_number(self):
        result = validate_wave("/tmp", 99)
        self.assertFalse(result["passed"])

    def test_empty_wave_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wave_dir = Path(tmpdir) / "wave-results" / "wave-1"
            wave_dir.mkdir(parents=True)
            result = validate_wave(tmpdir, 1)
            self.assertFalse(result["passed"])
            self.assertTrue(any("Insufficient" in e or "Missing" in e
                                for e in result["errors"]))

    def test_valid_wave_1(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wave_dir = Path(tmpdir) / "wave-results" / "wave-1"
            wave_dir.mkdir(parents=True)
            for filename in WAVE_OUTPUTS[1]:
                f = wave_dir / filename
                f.write_text("# Test\n" + "content " * 50 + "\n- id: LS-001\n")
            result = validate_wave(tmpdir, 1)
            self.assertTrue(result["passed"])

    def test_too_small_file_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wave_dir = Path(tmpdir) / "wave-results" / "wave-1"
            wave_dir.mkdir(parents=True)
            for i, filename in enumerate(WAVE_OUTPUTS[1]):
                f = wave_dir / filename
                if i == 0:
                    f.write_text("tiny")  # Too small
                else:
                    f.write_text("# Test\n" + "content " * 50)
            result = validate_wave(tmpdir, 1)
            self.assertFalse(result["passed"])
            self.assertTrue(any("TO-L0" in e for e in result["errors"]))

    def test_wrong_claim_prefix_warning(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wave_dir = Path(tmpdir) / "wave-results" / "wave-1"
            wave_dir.mkdir(parents=True)
            for filename in WAVE_OUTPUTS[1]:
                f = wave_dir / filename
                f.write_text("# Test\n" + "content " * 50 + "\n- id: WRONG-001\n")
            result = validate_wave(tmpdir, 1)
            self.assertTrue(any("TO3" in w for w in result["warnings"]))

    def test_missing_korean_translation_warning(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wave_dir = Path(tmpdir) / "wave-results" / "wave-1"
            wave_dir.mkdir(parents=True)
            for filename in WAVE_OUTPUTS[1]:
                f = wave_dir / filename
                f.write_text("# Test\n" + "content " * 50)
            result = validate_wave(tmpdir, 1)
            self.assertTrue(any("TO4" in w for w in result["warnings"]))


class TestNoSystemSOTReference(unittest.TestCase):
    def test_no_state_yaml_reference(self):
        content = (SCRIPT_DIR / "validate_thesis_output.py").read_text(encoding="utf-8")
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            self.assertNotIn("state.yaml", line, f"Line {i}")
            self.assertNotIn("state.yml", line, f"Line {i}")


if __name__ == "__main__":
    unittest.main()
