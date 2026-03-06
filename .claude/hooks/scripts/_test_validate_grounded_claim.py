#!/usr/bin/env python3
"""Tests for validate_grounded_claim.py — GRA Layer 1 validation."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
SCRIPT = SCRIPT_DIR / "validate_grounded_claim.py"


def run_hook(tool_name: str, file_path: str, content: str = "",
             project_dir: str = "/project") -> subprocess.CompletedProcess:
    """Simulate PostToolUse hook invocation."""
    env = os.environ.copy()
    env["CLAUDE_TOOL_NAME"] = tool_name
    env["CLAUDE_TOOL_INPUT"] = json.dumps({"file_path": file_path, "content": content})
    env["CLAUDE_PROJECT_DIR"] = project_dir
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        env=env,
    )


class TestNonWaveFiles(unittest.TestCase):
    """Files outside wave-results should be ignored."""

    def test_non_wave_file_passes(self):
        result = run_hook("Write", "/tmp/some-file.md")
        self.assertEqual(result.returncode, 0)

    def test_python_file_passes(self):
        result = run_hook("Write", "/tmp/test.py")
        self.assertEqual(result.returncode, 0)

    def test_non_write_tool_passes(self):
        result = run_hook("Read", "/tmp/wave-results/wave-1/test.md")
        self.assertEqual(result.returncode, 0)


class TestWaveFileValidation(unittest.TestCase):
    """Wave result files should be validated."""

    def test_valid_grounded_claim(self):
        content = """# Literature Search Strategy

## GroundedClaim
- id: LS-001
- claim_type: empirical
- claim: "Test claim with source"
- sources:
  - author: "Smith"
    year: 2023
    doi: "10.1234/test"
- confidence: 0.85
- uncertainty: "Limited sample size"
"""
        result = run_hook("Write", "/project/thesis-output/test/wave-results/wave-1/01-literature-search-strategy.md", content)
        self.assertEqual(result.returncode, 0)

    def test_empty_content_warns(self):
        result = run_hook("Write", "/project/thesis-output/test/wave-results/wave-1/test.md", "")
        self.assertEqual(result.returncode, 0)  # Never blocks, only warns


class TestHallucinationFirewall(unittest.TestCase):
    """Test blocked pattern detection."""

    def test_fabricated_study_warning(self):
        content = "According to the fabricated study by Smith (2023)..."
        result = run_hook("Write", "/project/thesis-output/test/wave-results/wave-1/test.md", content)
        self.assertEqual(result.returncode, 0)

    def test_hypothetical_source_warning(self):
        content = "Based on a hypothetical source, we find..."
        result = run_hook("Write", "/project/thesis-output/test/wave-results/wave-1/test.md", content)
        self.assertEqual(result.returncode, 0)

    def test_clean_content_no_warning(self):
        content = """# Analysis
Based on Smith (2023), doi: 10.1234/test, the findings show...
- id: LS-001
- claim_type: empirical
- sources:
  - author: Smith
    year: 2023
"""
        result = run_hook("Write", "/project/thesis-output/test/wave-results/wave-1/test.md", content)
        self.assertEqual(result.returncode, 0)


class TestClaimIdFormat(unittest.TestCase):
    """Test claim ID format validation."""

    def test_valid_claim_ids(self):
        content = """
- id: LS-001
- id: SWA-002
- id: TRA-003
"""
        result = run_hook("Write", "/project/thesis-output/test/wave-results/wave-1/test.md", content)
        self.assertEqual(result.returncode, 0)

    def test_invalid_claim_id_format(self):
        content = "- id: invalid-format\n- id: 123"
        result = run_hook("Write", "/project/thesis-output/test/wave-results/wave-1/test.md", content)
        self.assertEqual(result.returncode, 0)  # Warns but doesn't block

    def test_multi_hyphen_claim_ids(self):
        content = """
- id: EMP-NEURO-001
- id: CR-LOGIC-002
- id: MC-IV-003
"""
        result = run_hook("Write", "/project/thesis-output/test/wave-results/wave-2/test.md", content)
        self.assertEqual(result.returncode, 0)

    def test_blockquote_claim_id(self):
        content = '> **[PHIL-T001]** claim_id: PHIL-T001\n'
        result = run_hook("Write", "/project/thesis-output/test/wave-results/wave-1/test.md", content)
        self.assertEqual(result.returncode, 0)


class TestNoSystemSOTReference(unittest.TestCase):
    """Ensure script does not reference system SOT filenames."""

    def test_no_state_yaml_reference(self):
        content = SCRIPT.read_text(encoding="utf-8")
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            self.assertNotIn("state.yaml", line,
                             f"Line {i} references system SOT")
            self.assertNotIn("state.yml", line,
                             f"Line {i} references system SOT")


if __name__ == "__main__":
    unittest.main()
