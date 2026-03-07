#!/usr/bin/env python3
"""Tests for validate_fork_safety.py — P1 fork safety validation.

Run: python3 -m pytest _test_validate_fork_safety.py -v
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

import validate_fork_safety as vfs
from validate_fork_safety import BASH_DEPENDENCY_PATTERNS


class TestParseFrontmatter(unittest.TestCase):
    """Test YAML frontmatter parsing."""

    def test_standard_frontmatter(self):
        content = "---\nname: test\ndescription: A test\n---\n\n# Body"
        fm, body = vfs.parse_frontmatter(content)
        self.assertEqual(fm["name"], "test")
        self.assertEqual(fm["description"], "A test")
        self.assertIn("# Body", body)

    def test_fork_frontmatter(self):
        content = "---\ndescription: Test\ncontext: fork\nagent: translator\n---\n\nBody"
        fm, body = vfs.parse_frontmatter(content)
        self.assertEqual(fm["context"], "fork")
        self.assertEqual(fm["agent"], "translator")

    def test_no_frontmatter(self):
        content = "# Just a heading\n\nSome text."
        fm, body = vfs.parse_frontmatter(content)
        self.assertEqual(fm, {})
        self.assertEqual(body, content)

    def test_quoted_values(self):
        content = '---\nname: "my-skill"\ndescription: \'A skill\'\n---\n\nBody'
        fm, body = vfs.parse_frontmatter(content)
        self.assertEqual(fm["name"], "my-skill")
        self.assertEqual(fm["description"], "A skill")

    def test_empty_content(self):
        fm, body = vfs.parse_frontmatter("")
        self.assertEqual(fm, {})
        self.assertEqual(body, "")

    def test_unclosed_frontmatter(self):
        content = "---\nname: test\nno closing"
        fm, body = vfs.parse_frontmatter(content)
        self.assertEqual(fm, {})


class TestParseAgentTools(unittest.TestCase):
    """Test agent tools parsing."""

    def test_parse_standard_agent(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write("---\nname: test-agent\ntools: Read, Write, Glob, Grep\n---\n\nBody")
            f.flush()
            tools = vfs.parse_agent_tools(f.name)
        os.unlink(f.name)
        self.assertEqual(tools, ["Read", "Write", "Glob", "Grep"])

    def test_parse_agent_with_bash(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write("---\ntools: Read, Write, Bash, Glob\n---\n\nBody")
            f.flush()
            tools = vfs.parse_agent_tools(f.name)
        os.unlink(f.name)
        self.assertIn("Bash", tools)

    def test_nonexistent_agent(self):
        tools = vfs.parse_agent_tools("/nonexistent/agent.md")
        self.assertIsNone(tools)

    def test_no_tools_field(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write("---\nname: no-tools\n---\n\nBody")
            f.flush()
            tools = vfs.parse_agent_tools(f.name)
        os.unlink(f.name)
        self.assertEqual(tools, [])


class TestValidateFileNoFork(unittest.TestCase):
    """Files without context: fork should always pass."""

    def test_inline_command_passes(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write("---\ndescription: A normal command\n---\n\n# Body\nDo stuff.")
            f.flush()
            is_pass, msgs = vfs.validate_file(f.name, "/tmp")
        os.unlink(f.name)
        self.assertTrue(is_pass)
        self.assertEqual(msgs, [])

    def test_no_frontmatter_passes(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write("# Just a file\nNo frontmatter at all.")
            f.flush()
            is_pass, msgs = vfs.validate_file(f.name, "/tmp")
        os.unlink(f.name)
        self.assertTrue(is_pass)


class TestFS2_SOTWriteDetection(unittest.TestCase):
    """FS-2: Detect SOT write patterns in forked commands."""

    def _validate_fork_body(self, body: str) -> bool:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write(f"---\ndescription: Test\ncontext: fork\n---\n\n{body}")
            f.flush()
            is_pass, _ = vfs.validate_file(f.name, "/tmp")
        os.unlink(f.name)
        return is_pass

    def test_session_json_reference_fails(self):
        self.assertFalse(self._validate_fork_body(
            "Record learning progress in session.json under learning_progress."
        ))

    def test_state_yaml_reference_fails(self):
        self.assertFalse(self._validate_fork_body(
            "Write the result to state.yaml for persistence."
        ))

    def test_checklist_advance_fails(self):
        self.assertFalse(self._validate_fork_body(
            "python3 checklist_manager.py --advance --step 5"
        ))

    def test_checklist_gate_fails(self):
        self.assertFalse(self._validate_fork_body(
            "python3 checklist_manager.py --gate --phase 1"
        ))

    def test_checklist_hitl_fails(self):
        self.assertFalse(self._validate_fork_body(
            "python3 checklist_manager.py --hitl --step 3"
        ))

    def test_update_sot_text_fails(self):
        self.assertFalse(self._validate_fork_body(
            "Update the SOT with the new results."
        ))

    def test_record_in_sot_fails(self):
        self.assertFalse(self._validate_fork_body(
            "Record quiz results in SOT under learning_progress.quiz_results"
        ))

    def test_track_progress_in_sot_fails(self):
        self.assertFalse(self._validate_fork_body(
            "### Step 3: Track Progress in SOT\nRecord learning progress."
        ))

    def test_checklist_status_read_passes(self):
        """Read-only SOT access is safe in fork."""
        self.assertTrue(self._validate_fork_body(
            "python3 checklist_manager.py --status --project-dir ."
        ))

    def test_read_sot_text_passes(self):
        self.assertTrue(self._validate_fork_body(
            "Read the SOT to determine current state."
        ))

    def test_no_sot_reference_passes(self):
        self.assertTrue(self._validate_fork_body(
            "Analyze the codebase and produce a report file."
        ))


class TestFS3_BashDependency(unittest.TestCase):
    """FS-3: Bash dependency with incompatible agent."""

    def test_bash_with_no_agent_passes(self):
        """No agent specified → general-purpose (has Bash) → safe."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write(
                "---\ndescription: Test\ncontext: fork\n---\n\n"
                "```bash\npython3 validate_something.py\n```"
            )
            f.flush()
            is_pass, _ = vfs.validate_file(f.name, "/tmp")
        os.unlink(f.name)
        self.assertTrue(is_pass)

    def test_bash_with_general_purpose_passes(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write(
                "---\ndescription: Test\ncontext: fork\n"
                "agent: general-purpose\n---\n\n"
                "```bash\npython3 script.py\n```"
            )
            f.flush()
            is_pass, _ = vfs.validate_file(f.name, "/tmp")
        os.unlink(f.name)
        self.assertTrue(is_pass)

    def test_bash_with_bashless_agent_fails(self):
        """Agent without Bash + Bash dependency → FAIL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create agent without Bash
            agents_dir = os.path.join(tmpdir, ".claude", "agents")
            os.makedirs(agents_dir)
            agent_path = os.path.join(agents_dir, "translator.md")
            with open(agent_path, "w") as af:
                af.write("---\nname: translator\ntools: Read, Write, Glob, Grep\n---\n\nBody")

            # Create command with Bash dependency
            cmd_path = os.path.join(tmpdir, "test-cmd.md")
            with open(cmd_path, "w") as cf:
                cf.write(
                    "---\ndescription: Test\ncontext: fork\n"
                    "agent: translator\n---\n\n"
                    "python3 validate_translation.py --check"
                )

            is_pass, msgs = vfs.validate_file(cmd_path, tmpdir)
            self.assertFalse(is_pass)
            self.assertTrue(any("[FS-3]" in m for m in msgs))

    def test_bash_with_builtin_explore_passes(self):
        """Explore is built-in with Bash — should pass without .md file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write(
                "---\ndescription: Test\ncontext: fork\n"
                "agent: Explore\n---\n\n"
                "```bash\npython3 analyze.py\n```"
            )
            f.flush()
            is_pass, _ = vfs.validate_file(f.name, "/tmp")
        os.unlink(f.name)
        self.assertTrue(is_pass)

    def test_bash_with_builtin_plan_passes(self):
        """Plan is built-in with Bash — should pass without .md file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write(
                "---\ndescription: Test\ncontext: fork\n"
                "agent: Plan\n---\n\n"
                "python3 compute_something.py --check"
            )
            f.flush()
            is_pass, _ = vfs.validate_file(f.name, "/tmp")
        os.unlink(f.name)
        self.assertTrue(is_pass)


class TestFS4_HITLDetection(unittest.TestCase):
    """FS-4: HITL patterns should fail in fork context."""

    def _validate_fork_body(self, body: str) -> bool:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write(f"---\ndescription: Test\ncontext: fork\n---\n\n{body}")
            f.flush()
            is_pass, _ = vfs.validate_file(f.name, "/tmp")
        os.unlink(f.name)
        return is_pass

    def test_ask_user_question_fails(self):
        self.assertFalse(self._validate_fork_body(
            "Use AskUserQuestion to confirm the selection."
        ))

    def test_hitl_checkpoint_fails(self):
        self.assertFalse(self._validate_fork_body(
            "This is HITL-3 checkpoint. Wait for human approval."
        ))

    def test_human_approval_fails(self):
        self.assertFalse(self._validate_fork_body(
            "Present the results for human approval before proceeding."
        ))

    def test_user_approval_fails(self):
        self.assertFalse(self._validate_fork_body(
            "Wait for user approval on the design."
        ))

    def test_no_hitl_passes(self):
        self.assertTrue(self._validate_fork_body(
            "Generate report and save to output.md."
        ))


class TestFS5_AgentExistence(unittest.TestCase):
    """FS-5: Agent specified in frontmatter must exist."""

    def test_nonexistent_agent_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, ".claude", "agents"))
            cmd_path = os.path.join(tmpdir, "test.md")
            with open(cmd_path, "w") as f:
                f.write(
                    "---\ndescription: Test\ncontext: fork\n"
                    "agent: nonexistent-agent\n---\n\n"
                    "Do independent analysis."
                )

            is_pass, msgs = vfs.validate_file(cmd_path, tmpdir)
            self.assertFalse(is_pass)
            self.assertTrue(any("[FS-5]" in m for m in msgs))

    def test_existing_agent_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_dir = os.path.join(tmpdir, ".claude", "agents")
            os.makedirs(agents_dir)
            with open(os.path.join(agents_dir, "my-agent.md"), "w") as af:
                af.write("---\nname: my-agent\ntools: Read, Glob, Grep\n---\n\nBody")

            cmd_path = os.path.join(tmpdir, "test.md")
            with open(cmd_path, "w") as f:
                f.write(
                    "---\ndescription: Test\ncontext: fork\n"
                    "agent: my-agent\n---\n\n"
                    "Read files and produce analysis."
                )

            is_pass, _ = vfs.validate_file(cmd_path, tmpdir)
            self.assertTrue(is_pass)

    def test_builtin_agents_skip_check(self):
        """Explore, Plan, general-purpose don't need .md files."""
        for agent in ["Explore", "Plan", "general-purpose"]:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".md", delete=False
            ) as f:
                f.write(
                    f"---\ndescription: Test\ncontext: fork\n"
                    f"agent: {agent}\n---\n\n"
                    f"Do stuff."
                )
                f.flush()
                is_pass, _ = vfs.validate_file(f.name, "/tmp")
            os.unlink(f.name)
            self.assertTrue(is_pass, f"Built-in agent '{agent}' should pass")


class TestSafeForkedSkill(unittest.TestCase):
    """Integration: a properly designed forked skill should pass all checks."""

    def test_ideal_fork_passes(self):
        """Skill that reads files, produces output, no SOT/Bash/HITL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agents_dir = os.path.join(tmpdir, ".claude", "agents")
            os.makedirs(agents_dir)
            with open(os.path.join(agents_dir, "analyzer.md"), "w") as af:
                af.write("---\nname: analyzer\ntools: Read, Glob, Grep\n---\n\nAnalyze.")

            skill_path = os.path.join(tmpdir, "SKILL.md")
            with open(skill_path, "w") as f:
                f.write(
                    "---\nname: code-analyzer\n"
                    "description: Analyzes codebase structure.\n"
                    "context: fork\n"
                    "agent: analyzer\n---\n\n"
                    "# Code Analyzer\n\n"
                    "## Protocol\n"
                    "1. Read all source files using Glob and Read\n"
                    "2. Analyze structure and dependencies\n"
                    "3. Write analysis report to output/analysis.md\n"
                )

            is_pass, msgs = vfs.validate_file(skill_path, tmpdir)
            self.assertTrue(is_pass)

    def test_unsafe_fork_fails_multiple(self):
        """Skill with SOT write + HITL should report multiple violations."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write(
                "---\ndescription: Bad fork\ncontext: fork\n---\n\n"
                "1. Update the SOT with results\n"
                "2. Ask the user for approval\n"
                "3. python3 checklist_manager.py --advance\n"
            )
            f.flush()
            is_pass, msgs = vfs.validate_file(f.name, "/tmp")
        os.unlink(f.name)
        self.assertFalse(is_pass)
        # Should have FS-2 (SOT) and FS-4 (HITL) violations
        violation_text = "\n".join(msgs)
        self.assertIn("[FS-2]", violation_text)
        self.assertIn("[FS-4]", violation_text)


class TestFindAllTargets(unittest.TestCase):
    """Test project-wide file discovery."""

    def test_finds_skills_and_commands(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = os.path.join(tmpdir, ".claude", "skills", "my-skill")
            commands_dir = os.path.join(tmpdir, ".claude", "commands")
            os.makedirs(skills_dir)
            os.makedirs(commands_dir)

            Path(os.path.join(skills_dir, "SKILL.md")).touch()
            Path(os.path.join(commands_dir, "cmd1.md")).touch()
            Path(os.path.join(commands_dir, "cmd2.md")).touch()

            targets = vfs.find_all_targets(tmpdir)
            self.assertEqual(len(targets), 3)

    def test_empty_project(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            targets = vfs.find_all_targets(tmpdir)
            self.assertEqual(targets, [])


class TestCheckPatterns(unittest.TestCase):
    """Test pattern matching utility."""

    def test_matches_found(self):
        text = "python3 validate_translation.py --check"
        matches = vfs.check_patterns(text, [r"python3\s+", r"validate_\w+\.py"])
        self.assertEqual(len(matches), 2)

    def test_no_matches(self):
        text = "Just read the file and analyze."
        matches = vfs.check_patterns(text, BASH_DEPENDENCY_PATTERNS)
        self.assertEqual(len(matches), 0)


if __name__ == "__main__":
    unittest.main()
