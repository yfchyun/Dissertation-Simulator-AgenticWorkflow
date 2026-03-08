#!/usr/bin/env python3
"""Tests for guard_sot_write.py — SOT write protection (thesis + system).

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


class TestIsSOTPath(unittest.TestCase):
    """Test is_sot_path() path matching for both thesis and system SOT."""

    # --- Thesis SOT ---

    def test_thesis_sot_standard_path(self):
        self.assertTrue(guard.is_sot_path(
            "/project/thesis-output/my-thesis/session.json",
            "/project",
        ))

    def test_thesis_sot_nested_path(self):
        self.assertTrue(guard.is_sot_path(
            "/project/thesis-output/deep/nested/session.json",
            "/project",
        ))

    def test_rejects_root_session_json(self):
        """session.json at project root is NOT thesis SOT."""
        self.assertFalse(guard.is_sot_path(
            "/project/session.json",
            "/project",
        ))

    def test_rejects_different_filename(self):
        self.assertFalse(guard.is_sot_path(
            "/project/thesis-output/my-thesis/config.json",
            "/project",
        ))

    def test_rejects_non_thesis_output_dir(self):
        self.assertFalse(guard.is_sot_path(
            "/project/other-dir/my-thesis/session.json",
            "/project",
        ))

    # --- System SOT ---

    def test_system_sot_project_root(self):
        """state.yaml at project root IS system SOT."""
        self.assertTrue(guard.is_sot_path(
            "/project/state.yaml",
            "/project",
        ))

    def test_system_sot_one_level_deep(self):
        """state.yaml one level deep IS system SOT (workflow subdir)."""
        self.assertTrue(guard.is_sot_path(
            "/project/my-workflow/state.yaml",
            "/project",
        ))

    def test_rejects_deep_nested_state_yaml(self):
        """state.yaml deeply nested is NOT system SOT (false positive prevention)."""
        self.assertFalse(guard.is_sot_path(
            "/project/config/nested/state.yaml",
            "/project",
        ))

    def test_rejects_dotdir_state_yaml(self):
        """state.yaml in hidden dirs (e.g. .claude/) is NOT system SOT."""
        self.assertFalse(guard.is_sot_path(
            "/project/.claude/state.yaml",
            "/project",
        ))

    def test_rejects_skills_state_yaml(self):
        """state.yaml deep in .claude/skills is NOT system SOT."""
        self.assertFalse(guard.is_sot_path(
            "/project/.claude/skills/workflow-generator/references/state.yaml",
            "/project",
        ))

    # --- Edge cases ---

    def test_handles_empty_strings(self):
        self.assertFalse(guard.is_sot_path("", ""))

    def test_handles_different_projects(self):
        """Path outside project dir is NOT SOT."""
        self.assertFalse(guard.is_sot_path(
            "/other-project/state.yaml",
            "/project",
        ))


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

    # --- Thesis SOT ---

    def test_allows_orchestrator_thesis_sot_write(self):
        env = self._make_env(
            file_path="/project/thesis-output/my-thesis/session.json",
            is_orchestrator=True,
        )
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(guard.main(), 0)

    def test_allows_main_session_thesis_sot_write(self):
        """Main session (not teammate) can write thesis SOT."""
        env = self._make_env(
            file_path="/project/thesis-output/my-thesis/session.json",
            is_teammate=False,
        )
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(guard.main(), 0)

    def test_blocks_teammate_thesis_sot_write(self):
        env = self._make_env(
            file_path="/project/thesis-output/my-thesis/session.json",
            is_teammate=True,
        )
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(guard.main(), 2)

    def test_blocks_edit_thesis_sot(self):
        env = self._make_env(
            tool_name="Edit",
            file_path="/project/thesis-output/my-thesis/session.json",
            is_teammate=True,
        )
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(guard.main(), 2)

    # --- System SOT ---

    def test_allows_orchestrator_system_sot_write(self):
        env = self._make_env(
            file_path="/project/state.yaml",
            is_orchestrator=True,
        )
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(guard.main(), 0)

    def test_allows_main_session_system_sot_write(self):
        """Main session (not teammate) can write system SOT."""
        env = self._make_env(
            file_path="/project/state.yaml",
            is_teammate=False,
        )
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(guard.main(), 0)

    def test_blocks_teammate_system_sot_write(self):
        env = self._make_env(
            file_path="/project/state.yaml",
            is_teammate=True,
        )
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(guard.main(), 2)

    def test_blocks_teammate_system_sot_one_level(self):
        env = self._make_env(
            file_path="/project/my-workflow/state.yaml",
            is_teammate=True,
        )
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(guard.main(), 2)

    def test_allows_teammate_deep_state_yaml(self):
        """state.yaml deep in subdirs is NOT SOT — teammate can write."""
        env = self._make_env(
            file_path="/project/config/nested/state.yaml",
            is_teammate=True,
        )
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(guard.main(), 0)

    def test_allows_teammate_non_sot_write(self):
        """Teammates CAN write their own output files."""
        env = self._make_env(
            file_path="/project/thesis-output/my-thesis/wave-results/wave-1/01-search.md",
            is_teammate=True,
        )
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(guard.main(), 0)

    # --- Error handling ---

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


if __name__ == "__main__":
    unittest.main()
