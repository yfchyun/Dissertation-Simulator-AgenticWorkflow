#!/usr/bin/env python3
"""Tests for validate_wave_gate.py — Cross-Validation Gate validation."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from validate_wave_gate import (
    validate_gate,
    GATE_CONFIG,
    count_claims,
    extract_claim_ids,
    check_inconsistencies,
    MIN_OUTPUT_SIZE,
)


class TestGateConfig(unittest.TestCase):
    """Test gate configuration constants."""

    def test_five_gates_defined(self):
        self.assertEqual(len(GATE_CONFIG), 5)

    def test_gate_1_config(self):
        config = GATE_CONFIG["gate-1"]
        self.assertEqual(config["wave"], 1)
        self.assertEqual(config["min_claims_per_file"], 3)
        self.assertEqual(config["min_files"], 4)

    def test_srcs_full_config(self):
        config = GATE_CONFIG["srcs-full"]
        self.assertEqual(config["wave"], 4)
        self.assertGreater(config["min_claims_per_file"], 0)

    def test_all_gates_have_description(self):
        for name, config in GATE_CONFIG.items():
            self.assertIn("description", config, f"Gate {name} missing description")


class TestCountClaims(unittest.TestCase):
    """Test claim counting."""

    def test_no_claims(self):
        self.assertEqual(count_claims("No claims here"), 0)

    def test_single_claim(self):
        self.assertEqual(count_claims('id: LS-001'), 1)

    def test_multiple_claims(self):
        content = 'id: LS-001\nid: LS-002\nid: SWA-001'
        self.assertEqual(count_claims(content), 3)

    def test_quoted_claim_id(self):
        self.assertEqual(count_claims("id: 'LS-001'"), 1)
        self.assertEqual(count_claims('id: "LS-001"'), 1)


class TestExtractClaimIds(unittest.TestCase):
    """Test claim ID extraction."""

    def test_extract_ids(self):
        content = 'id: LS-001\nid: SWA-002'
        ids = extract_claim_ids(content)
        self.assertEqual(ids, ["LS-001", "SWA-002"])

    def test_empty_content(self):
        self.assertEqual(extract_claim_ids(""), [])


class TestCheckInconsistencies(unittest.TestCase):
    """Test cross-file consistency checks."""

    def test_no_duplicates(self):
        claims = {
            "file1.md": ["LS-001", "LS-002"],
            "file2.md": ["SWA-001", "SWA-002"],
        }
        result = check_inconsistencies(claims)
        self.assertEqual(len(result), 0)

    def test_duplicate_detected(self):
        claims = {
            "file1.md": ["LS-001", "LS-002"],
            "file2.md": ["LS-001", "SWA-001"],
        }
        result = check_inconsistencies(claims)
        self.assertEqual(len(result), 1)
        self.assertIn("LS-001", result[0])


class TestValidateGate(unittest.TestCase):
    """Test gate validation."""

    def test_unknown_gate(self):
        result = validate_gate("/tmp", "nonexistent-gate")
        self.assertEqual(result["status"], "fail")

    def test_missing_wave_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = validate_gate(tmpdir, "gate-1")
            self.assertEqual(result["status"], "fail")

    def test_insufficient_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wave_dir = Path(tmpdir) / "wave-results" / "wave-1"
            wave_dir.mkdir(parents=True)
            # Only 1 file, need 4
            (wave_dir / "test.md").write_text("# Test\n" + "x" * 200 + "\nid: LS-001\nid: LS-002\nid: LS-003")
            result = validate_gate(tmpdir, "gate-1")
            self.assertEqual(result["status"], "fail")

    def test_valid_gate_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wave_dir = Path(tmpdir) / "wave-results" / "wave-1"
            wave_dir.mkdir(parents=True)
            for i in range(4):
                f = wave_dir / f"file-{i}.md"
                f.write_text("# Test\n" + "content " * 50 + "\nid: LS-001\nid: LS-002\nid: LS-003\n")
            result = validate_gate(tmpdir, "gate-1")
            self.assertEqual(result["status"], "pass")

    def test_l0_size_check(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wave_dir = Path(tmpdir) / "wave-results" / "wave-1"
            wave_dir.mkdir(parents=True)
            for i in range(4):
                f = wave_dir / f"file-{i}.md"
                if i == 0:
                    f.write_text("tiny")  # Below MIN_OUTPUT_SIZE
                else:
                    f.write_text("# Test\n" + "content " * 50 + "\nid: LS-001\nid: LS-002\nid: LS-003\n")
            result = validate_gate(tmpdir, "gate-1")
            self.assertEqual(result["status"], "fail")
            self.assertTrue(any("L0" in e for e in result["errors"]))

    def test_ko_files_excluded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wave_dir = Path(tmpdir) / "wave-results" / "wave-1"
            wave_dir.mkdir(parents=True)
            for i in range(4):
                f = wave_dir / f"file-{i}.md"
                f.write_text("# Test\n" + "content " * 50 + "\nid: LS-001\nid: LS-002\nid: LS-003\n")
                ko = wave_dir / f"file-{i}.ko.md"
                ko.write_text("# Korean translation")
            result = validate_gate(tmpdir, "gate-1")
            self.assertEqual(result["files_checked"], 4)  # .ko.md excluded

    def test_result_includes_total_claims(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wave_dir = Path(tmpdir) / "wave-results" / "wave-1"
            wave_dir.mkdir(parents=True)
            for i in range(4):
                f = wave_dir / f"file-{i}.md"
                f.write_text("# Test\n" + "content " * 50 + "\nid: LS-001\nid: LS-002\nid: LS-003\n")
            result = validate_gate(tmpdir, "gate-1")
            self.assertEqual(result["total_claims"], 12)


class TestNoSystemSOTReference(unittest.TestCase):
    def test_no_state_yaml_reference(self):
        content = (SCRIPT_DIR / "validate_wave_gate.py").read_text(encoding="utf-8")
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            self.assertNotIn("state.yaml", line, f"Line {i}")
            self.assertNotIn("state.yml", line, f"Line {i}")


if __name__ == "__main__":
    unittest.main()
