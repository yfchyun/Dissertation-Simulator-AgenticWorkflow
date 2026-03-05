#!/usr/bin/env python3
"""Tests for teammate_health_check.py — Teammate activity monitoring."""

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from teammate_health_check import (
    check_teammate_health,
    STATUS_HEALTHY,
    STATUS_IDLE,
    DEFAULT_TIMEOUT_SECONDS,
)


class TestNoProject(unittest.TestCase):
    """Test behavior with no project."""

    def test_no_session_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = check_teammate_health(tmpdir)
            self.assertEqual(result["overall_status"], "no_project")

    def test_no_active_team(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sot = {"active_team": None}
            (Path(tmpdir) / "session.json").write_text(json.dumps(sot))
            result = check_teammate_health(tmpdir)
            self.assertEqual(result["overall_status"], "no_active_team")


class TestHealthyTeam(unittest.TestCase):
    """Test healthy teammate detection."""

    def _setup_project(self, tmpdir, file_age_seconds=0):
        sot = {"active_team": "wave-1-team"}
        (Path(tmpdir) / "session.json").write_text(json.dumps(sot))
        wave_dir = Path(tmpdir) / "wave-results" / "wave-1"
        wave_dir.mkdir(parents=True)
        test_file = wave_dir / "01-literature-search-strategy.md"
        test_file.write_text("# Test output")
        if file_age_seconds > 0:
            import os
            old_time = time.time() - file_age_seconds
            os.utime(str(test_file), (old_time, old_time))
        return test_file

    def test_recent_output_is_healthy(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._setup_project(tmpdir)
            result = check_teammate_health(tmpdir, timeout_seconds=300)
            self.assertEqual(result["overall_status"], STATUS_HEALTHY)

    def test_old_output_is_idle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._setup_project(tmpdir, file_age_seconds=600)
            result = check_teammate_health(tmpdir, timeout_seconds=300)
            self.assertEqual(result["overall_status"], STATUS_IDLE)

    def test_no_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sot = {"active_team": "wave-1-team"}
            (Path(tmpdir) / "session.json").write_text(json.dumps(sot))
            result = check_teammate_health(tmpdir)
            self.assertEqual(result["overall_status"], "no_outputs")

    def test_active_team_included(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._setup_project(tmpdir)
            result = check_teammate_health(tmpdir)
            self.assertEqual(result["active_team"], "wave-1-team")

    def test_timeout_included(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._setup_project(tmpdir)
            result = check_teammate_health(tmpdir, timeout_seconds=120)
            self.assertEqual(result["timeout_seconds"], 120)

    def test_teammate_file_details(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._setup_project(tmpdir)
            result = check_teammate_health(tmpdir)
            self.assertGreater(len(result["teammates"]), 0)
            teammate = result["teammates"][0]
            self.assertIn("file", teammate)
            self.assertIn("status", teammate)
            self.assertIn("age_seconds", teammate)


class TestDefaultTimeout(unittest.TestCase):
    def test_default_is_300(self):
        self.assertEqual(DEFAULT_TIMEOUT_SECONDS, 300)


class TestNoSystemSOTReference(unittest.TestCase):
    def test_no_state_yaml_reference(self):
        content = (SCRIPT_DIR / "teammate_health_check.py").read_text(encoding="utf-8")
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            self.assertNotIn("state.yaml", line, f"Line {i}")
            self.assertNotIn("state.yml", line, f"Line {i}")


if __name__ == "__main__":
    unittest.main()
