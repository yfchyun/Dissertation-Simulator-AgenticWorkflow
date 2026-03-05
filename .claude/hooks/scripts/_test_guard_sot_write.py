#!/usr/bin/env python3
"""Tests for guard_sot_write.py — thesis SOT write protection.

Run: python3 -m pytest _test_guard_sot_write.py -v
"""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

import guard_sot_write as guard


class TestIsThesisSOTPath(unittest.TestCase):
    """Test is_thesis_sot_path() path matching."""

    def test_matches_standard_path(self):
        self.assertTrue(guard.is_thesis_sot_path(
            "/project/thesis-output/my-thesis/session.json",
            "/project",
        ))

    def test_matches_nested_path(self):
        self.assertTrue(guard.is_thesis_sot_path(
            "/project/thesis-output/deep/nested/session.json",
            "/project",
        ))

    def test_rejects_root_session_json(self):
        """session.json at project root is NOT thesis SOT."""
        self.assertFalse(guard.is_thesis_sot_path(
            "/project/session.json",
            "/project",
        ))

    def test_rejects_different_filename(self):
        self.assertFalse(guard.is_thesis_sot_path(
            "/project/thesis-output/my-thesis/config.json",
            "/project",
        ))

    def test_rejects_non_thesis_output(self):
        self.assertFalse(guard.is_thesis_sot_path(
            "/project/other-dir/my-thesis/session.json",
            "/project",
        ))

    def test_rejects_short_path(self):
        self.assertFalse(guard.is_thesis_sot_path(
            "/project/session.json",
            "/project",
        ))

    def test_handles_empty_strings(self):
        self.assertFalse(guard.is_thesis_sot_path("", ""))


class TestIsOrchestratorContext(unittest.TestCase):
    """Test is_orchestrator_context() detection."""

    def test_main_session_is_orchestrator(self):
        """Main session (no teammate flag) is treated as orchestrator."""
        env = {
            "CLAUDE_AGENT_TEAMS_TEAMMATE": "",
            "THESIS_ORCHESTRATOR": "",
        }
        with patch.dict(os.environ, env, clear=False):
            self.assertTrue(guard.is_orchestrator_context())

    def test_explicit_orchestrator(self):
        env = {
            "THESIS_ORCHESTRATOR": "1",
            "CLAUDE_AGENT_TEAMS_TEAMMATE": "",
        }
        with patch.dict(os.environ, env, clear=False):
            self.assertTrue(guard.is_orchestrator_context())

    def test_teammate_is_not_orchestrator(self):
        env = {
            "CLAUDE_AGENT_TEAMS_TEAMMATE": "1",
            "THESIS_ORCHESTRATOR": "",
        }
        with patch.dict(os.environ, env, clear=False):
            self.assertFalse(guard.is_orchestrator_context())

    def test_teammate_with_orchestrator_flag(self):
        """Explicit orchestrator flag overrides teammate status."""
        env = {
            "CLAUDE_AGENT_TEAMS_TEAMMATE": "1",
            "THESIS_ORCHESTRATOR": "1",
        }
        with patch.dict(os.environ, env, clear=False):
            self.assertTrue(guard.is_orchestrator_context())


class TestMainFunction(unittest.TestCase):
    """Test main() end-to-end scenarios."""

    def _make_env(self, tool_name="Write", file_path="", project_dir="/project",
                  is_teammate=False, is_orchestrator=False):
        tool_input = json.dumps({"file_path": file_path})
        env = {
            "CLAUDE_TOOL_NAME": tool_name,
            "CLAUDE_TOOL_INPUT": tool_input,
            "CLAUDE_PROJECT_DIR": project_dir,
            "CLAUDE_AGENT_TEAMS_TEAMMATE": "1" if is_teammate else "",
            "THESIS_ORCHESTRATOR": "1" if is_orchestrator else "",
        }
        return env

    def test_allows_non_write_tools(self):
        env = self._make_env(tool_name="Read")
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(guard.main(), 0)

    def test_allows_non_sot_write(self):
        env = self._make_env(
            file_path="/project/thesis-output/my-thesis/chapter1.md"
        )
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(guard.main(), 0)

    def test_allows_orchestrator_sot_write(self):
        env = self._make_env(
            file_path="/project/thesis-output/my-thesis/session.json",
            is_orchestrator=True,
        )
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(guard.main(), 0)

    def test_allows_main_session_sot_write(self):
        """Main session (not teammate) can write SOT."""
        env = self._make_env(
            file_path="/project/thesis-output/my-thesis/session.json",
            is_teammate=False,
        )
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(guard.main(), 0)

    def test_blocks_teammate_sot_write(self):
        env = self._make_env(
            file_path="/project/thesis-output/my-thesis/session.json",
            is_teammate=True,
        )
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(guard.main(), 2)

    def test_blocks_edit_tool_too(self):
        env = self._make_env(
            tool_name="Edit",
            file_path="/project/thesis-output/my-thesis/session.json",
            is_teammate=True,
        )
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(guard.main(), 2)

    def test_allows_teammate_non_sot_write(self):
        """Teammates CAN write their own output files."""
        env = self._make_env(
            file_path="/project/thesis-output/my-thesis/wave-results/wave-1/01-search.md",
            is_teammate=True,
        )
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(guard.main(), 0)

    def test_handles_invalid_json_input(self):
        env = {
            "CLAUDE_TOOL_NAME": "Write",
            "CLAUDE_TOOL_INPUT": "not-json",
            "CLAUDE_PROJECT_DIR": "/project",
            "CLAUDE_AGENT_TEAMS_TEAMMATE": "",
            "THESIS_ORCHESTRATOR": "",
        }
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(guard.main(), 0)

    def test_handles_missing_file_path(self):
        env = {
            "CLAUDE_TOOL_NAME": "Write",
            "CLAUDE_TOOL_INPUT": json.dumps({}),
            "CLAUDE_PROJECT_DIR": "/project",
            "CLAUDE_AGENT_TEAMS_TEAMMATE": "",
            "THESIS_ORCHESTRATOR": "",
        }
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(guard.main(), 0)

    def test_handles_missing_project_dir(self):
        env = {
            "CLAUDE_TOOL_NAME": "Write",
            "CLAUDE_TOOL_INPUT": json.dumps({"file_path": "/x/session.json"}),
            "CLAUDE_PROJECT_DIR": "",
            "CLAUDE_AGENT_TEAMS_TEAMMATE": "",
            "THESIS_ORCHESTRATOR": "",
        }
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(guard.main(), 0)


class TestNoSystemSOTReference(unittest.TestCase):
    """Verify this script does NOT reference system SOT filenames (R6)."""

    def test_no_system_sot_reference(self):
        script_path = Path(__file__).parent / "guard_sot_write.py"
        content = script_path.read_text()
        for forbidden in ["state.yaml", "state.yml"]:
            self.assertNotIn(forbidden, content.lower(),
                             f"Script must not reference '{forbidden}'")


if __name__ == "__main__":
    unittest.main()
