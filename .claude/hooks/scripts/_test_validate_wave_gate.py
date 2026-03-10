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

    def test_multi_hyphen_claim_id(self):
        self.assertEqual(count_claims('id: EMP-NEURO-001'), 1)
        self.assertEqual(count_claims('id: CR-LOGIC-001'), 1)
        self.assertEqual(count_claims('id: MC-IV-002'), 1)

    def test_claim_id_prefix(self):
        self.assertEqual(count_claims('claim_id: PHIL-T001'), 1)

    def test_bold_bracket_format(self):
        self.assertEqual(count_claims('**[PHIL-T001]** claim_id: PHIL-T001'), 1)


class TestExtractClaimIds(unittest.TestCase):
    """Test claim ID extraction."""

    def test_extract_ids(self):
        content = 'id: LS-001\nid: SWA-002'
        ids = extract_claim_ids(content)
        self.assertEqual(ids, ["LS-001", "SWA-002"])

    def test_extract_multi_hyphen(self):
        content = 'id: EMP-NEURO-001\nid: CR-LOGIC-002\nclaim_id: PHIL-T003'
        ids = extract_claim_ids(content)
        self.assertEqual(ids, ["EMP-NEURO-001", "CR-LOGIC-002", "PHIL-T003"])

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


class TestConsolidatedMode(unittest.TestCase):
    """Test gate validation with consolidated output files."""

    def _make_content(self, claim_ids: list[str]) -> str:
        """Create valid content with the given claim IDs."""
        claims = "\n".join(f"id: {cid}" for cid in claim_ids)
        return f"# Output\n{'content ' * 50}\n{claims}\n"

    def test_consolidated_files_pass(self):
        """Gate passes with consolidated files meeting all thresholds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wave_dir = Path(tmpdir) / "wave-results" / "wave-1"
            wave_dir.mkdir(parents=True)
            files = [
                ("step-039-to-042-literature-searcher.md", ["LS-001", "LS-002", "LS-003"]),
                ("step-043-to-046-seminal-works-analyst.md", ["SWA-001", "SWA-002", "SWA-003"]),
                ("step-047-to-050-trend-analyst.md", ["TRA-001", "TRA-002", "TRA-003"]),
                ("step-051-to-054-methodology-scanner.md", ["MS-001", "MS-002", "MS-003"]),
            ]
            for fname, cids in files:
                (wave_dir / fname).write_text(self._make_content(cids))
            result = validate_gate(tmpdir, "gate-1")
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["files_checked"], 4)

    def test_consolidated_files_counted_correctly(self):
        """Total claims counted from consolidated files only."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wave_dir = Path(tmpdir) / "wave-results" / "wave-1"
            wave_dir.mkdir(parents=True)
            for i, name in enumerate([
                "step-039-to-042-literature-searcher.md",
                "step-043-to-046-seminal-works-analyst.md",
                "step-047-to-050-trend-analyst.md",
                "step-051-to-054-methodology-scanner.md",
            ]):
                cids = [f"X-{i:02d}{j}" for j in range(5)]
                (wave_dir / name).write_text(self._make_content(cids))
            result = validate_gate(tmpdir, "gate-1")
            self.assertEqual(result["total_claims"], 20)

    def test_mixed_state_uses_consolidated_only(self):
        """Mixed state (consolidated + individual): uses consolidated, warns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wave_dir = Path(tmpdir) / "wave-results" / "wave-1"
            wave_dir.mkdir(parents=True)
            # 4 consolidated files
            for name in [
                "step-039-to-042-literature-searcher.md",
                "step-043-to-046-seminal-works-analyst.md",
                "step-047-to-050-trend-analyst.md",
                "step-051-to-054-methodology-scanner.md",
            ]:
                (wave_dir / name).write_text(self._make_content(["LS-001", "LS-002", "LS-003"]))
            # 1 stale individual file
            (wave_dir / "01-literature-search-strategy.md").write_text(
                self._make_content(["LS-001", "LS-002", "LS-003"])
            )
            result = validate_gate(tmpdir, "gate-1")
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["files_checked"], 4)  # consolidated only
            self.assertTrue(any("Mixed state" in w for w in result["warnings"]))

    def test_mixed_state_no_duplicate_claims(self):
        """Mixed state: individual files excluded, so no duplicate claim IDs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wave_dir = Path(tmpdir) / "wave-results" / "wave-1"
            wave_dir.mkdir(parents=True)
            # Consolidated with unique claims
            for i, name in enumerate([
                "step-039-to-042-literature-searcher.md",
                "step-043-to-046-seminal-works-analyst.md",
                "step-047-to-050-trend-analyst.md",
                "step-051-to-054-methodology-scanner.md",
            ]):
                (wave_dir / name).write_text(self._make_content([f"X-{i}01", f"X-{i}02", f"X-{i}03"]))
            # Individual with SAME claim IDs (would cause duplicates if included)
            (wave_dir / "stale.md").write_text(self._make_content(["X-001", "X-002", "X-003"]))
            result = validate_gate(tmpdir, "gate-1")
            dup_warnings = [w for w in result["warnings"] if "Duplicate" in w]
            self.assertEqual(len(dup_warnings), 0)

    def test_consolidated_ko_files_excluded(self):
        """Korean translations of consolidated files are excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wave_dir = Path(tmpdir) / "wave-results" / "wave-1"
            wave_dir.mkdir(parents=True)
            for name in [
                "step-039-to-042-literature-searcher.md",
                "step-043-to-046-seminal-works-analyst.md",
                "step-047-to-050-trend-analyst.md",
                "step-051-to-054-methodology-scanner.md",
            ]:
                (wave_dir / name).write_text(self._make_content(["LS-001", "LS-002", "LS-003"]))
                ko_name = name.replace(".md", ".ko.md")
                (wave_dir / ko_name).write_text("# Korean")
            result = validate_gate(tmpdir, "gate-1")
            self.assertEqual(result["files_checked"], 4)

    def test_insufficient_consolidated_falls_back_to_all(self):
        """If fewer consolidated files than min_files, use all .md files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wave_dir = Path(tmpdir) / "wave-results" / "wave-1"
            wave_dir.mkdir(parents=True)
            # Only 2 consolidated (need 4)
            for name in [
                "step-039-to-042-literature-searcher.md",
                "step-043-to-046-seminal-works-analyst.md",
            ]:
                (wave_dir / name).write_text(self._make_content(["LS-001", "LS-002", "LS-003"]))
            # 2 individual
            for name in ["file-a.md", "file-b.md"]:
                (wave_dir / name).write_text(self._make_content(["LS-001", "LS-002", "LS-003"]))
            result = validate_gate(tmpdir, "gate-1")
            # All 4 files counted (fallback to all)
            self.assertEqual(result["files_checked"], 4)

    def test_consolidated_l0_size_check(self):
        """L0 size check applies to consolidated files too."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wave_dir = Path(tmpdir) / "wave-results" / "wave-1"
            wave_dir.mkdir(parents=True)
            names = [
                "step-039-to-042-literature-searcher.md",
                "step-043-to-046-seminal-works-analyst.md",
                "step-047-to-050-trend-analyst.md",
                "step-051-to-054-methodology-scanner.md",
            ]
            for i, name in enumerate(names):
                if i == 0:
                    (wave_dir / name).write_text("tiny")  # Below MIN_OUTPUT_SIZE
                else:
                    (wave_dir / name).write_text(self._make_content(["LS-001", "LS-002", "LS-003"]))
            result = validate_gate(tmpdir, "gate-1")
            self.assertEqual(result["status"], "fail")
            self.assertTrue(any("L0" in e for e in result["errors"]))

    def test_consolidated_regex_rejects_invalid_names(self):
        """Invalid consolidated filenames are not treated as consolidated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wave_dir = Path(tmpdir) / "wave-results" / "wave-1"
            wave_dir.mkdir(parents=True)
            # Invalid: trailing hyphen in agent name
            (wave_dir / "step-039-to-042-bad-.md").write_text(self._make_content(["LS-001", "LS-002", "LS-003"]))
            # Invalid: non-3-digit
            (wave_dir / "step-39-to-42-agent.md").write_text(self._make_content(["LS-001", "LS-002", "LS-003"]))
            # These 2 shouldn't be treated as consolidated → 0 consolidated < 4 min_files
            # So gate falls back to all_md (2 files) < 4 → fail
            result = validate_gate(tmpdir, "gate-1")
            self.assertEqual(result["status"], "fail")


if __name__ == "__main__":
    unittest.main()
