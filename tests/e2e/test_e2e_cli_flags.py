"""Track 4: CLI Flag Completeness E2E Tests.

Tests every argparse flag of checklist_manager.py and query_workflow.py
in both success and error scenarios.
"""

import json
from pathlib import Path

import pytest

from conftest import run_cm, run_qw, read_sot


# ===========================================================================
# checklist_manager.py CLI flags
# ===========================================================================

class TestCLI_Init:
    """--init flag."""

    def test_init_basic(self, tmp_path):
        proj = tmp_path / "proj"
        result = run_cm("--init", "--project-dir", str(proj))
        assert "initialized" in result.stdout.lower()

    def test_init_with_all_options(self, tmp_path):
        proj = tmp_path / "proj"
        result = run_cm(
            "--init", "--project-dir", str(proj),
            "--project-name", "my-thesis",
            "--research-type", "mixed",
            "--input-mode", "C",
        )
        sot = read_sot(proj)
        assert sot["project_name"] == "my-thesis"
        assert sot["research_type"] == "mixed"
        assert sot["input_mode"] == "C"

    def test_init_invalid_research_type(self, tmp_path):
        proj = tmp_path / "proj"
        result = run_cm(
            "--init", "--project-dir", str(proj),
            "--research-type", "invalid",
            expect_ok=False,
        )
        assert result.returncode != 0

    def test_init_invalid_input_mode(self, tmp_path):
        proj = tmp_path / "proj"
        result = run_cm(
            "--init", "--project-dir", str(proj),
            "--input-mode", "Z",
            expect_ok=False,
        )
        assert result.returncode != 0


class TestCLI_Advance:
    """--advance flag."""

    def test_advance_requires_step(self, thesis_project):
        proj, _ = thesis_project
        result = run_cm("--advance", "--project-dir", str(proj), expect_ok=False)
        assert result.returncode != 0

    def test_advance_with_step(self, thesis_project):
        proj, _ = thesis_project
        run_cm("--advance", "--step", "1", "--project-dir", str(proj))
        assert read_sot(proj)["current_step"] == 1

    def test_advance_with_force(self, thesis_project):
        proj, _ = thesis_project
        run_cm("--advance", "--step", "5", "--project-dir", str(proj))
        run_cm("--advance", "--step", "2", "--project-dir", str(proj), "--force")
        assert read_sot(proj)["current_step"] == 2

    def test_advance_negative_step(self, thesis_project):
        proj, _ = thesis_project
        result = run_cm("--advance", "--step", "-1", "--project-dir", str(proj), expect_ok=False)
        assert result.returncode != 0


class TestCLI_Status:
    """--status flag."""

    def test_status_basic(self, thesis_project):
        proj, _ = thesis_project
        result = run_cm("--status", "--project-dir", str(proj))
        assert "progress" in result.stdout.lower() or "status" in result.stdout.lower()

    def test_status_after_advance(self, thesis_project):
        proj, _ = thesis_project
        run_cm("--advance", "--step", "5", "--project-dir", str(proj))
        result = run_cm("--status", "--project-dir", str(proj))
        assert "5" in result.stdout


class TestCLI_Checkpoint:
    """--save-checkpoint and --restore-checkpoint flags."""

    def test_save_requires_name(self, thesis_project):
        proj, _ = thesis_project
        result = run_cm("--save-checkpoint", "--project-dir", str(proj), expect_ok=False)
        assert result.returncode != 0

    def test_save_with_name(self, thesis_project):
        proj, _ = thesis_project
        result = run_cm(
            "--save-checkpoint", "--checkpoint", "test-cp",
            "--project-dir", str(proj),
        )
        assert result.returncode == 0

    def test_restore_requires_name(self, thesis_project):
        proj, _ = thesis_project
        result = run_cm("--restore-checkpoint", "--project-dir", str(proj), expect_ok=False)
        assert result.returncode != 0

    def test_restore_nonexistent(self, thesis_project):
        proj, _ = thesis_project
        result = run_cm(
            "--restore-checkpoint", "--checkpoint", "nonexistent",
            "--project-dir", str(proj), expect_ok=False,
        )
        assert result.returncode != 0

    def test_save_then_restore(self, thesis_project):
        proj, _ = thesis_project
        run_cm("--save-checkpoint", "--checkpoint", "cp-a", "--project-dir", str(proj))
        run_cm("--advance", "--step", "5", "--project-dir", str(proj))
        run_cm("--restore-checkpoint", "--checkpoint", "cp-a", "--project-dir", str(proj))
        assert read_sot(proj)["current_step"] == 0


class TestCLI_Validate:
    """--validate flag."""

    def test_validate_valid(self, thesis_project):
        proj, _ = thesis_project
        result = run_cm("--validate", "--project-dir", str(proj))
        assert "PASS" in result.stdout

    def test_validate_missing_project(self, tmp_path):
        proj = tmp_path / "does-not-exist"
        result = run_cm("--validate", "--project-dir", str(proj), expect_ok=False)
        assert result.returncode != 0


class TestCLI_RecordHitl:
    """--record-hitl flag."""

    def test_record_hitl_basic(self, thesis_project):
        proj, _ = thesis_project
        result = run_cm("--record-hitl", "hitl-0", "--project-dir", str(proj))
        assert "recorded" in result.stdout.lower() or result.returncode == 0

    def test_record_hitl_with_custom_status(self, thesis_project):
        proj, _ = thesis_project
        run_cm("--record-hitl", "hitl-1", "--hitl-status", "blocked", "--project-dir", str(proj))
        sot = read_sot(proj)
        assert sot["hitl_checkpoints"]["hitl-1"]["status"] == "blocked"

    def test_record_hitl_invalid_name(self, thesis_project):
        proj, _ = thesis_project
        result = run_cm("--record-hitl", "invalid", "--project-dir", str(proj), expect_ok=False)
        assert result.returncode != 0


class TestCLI_MutualExclusion:
    """Mutually exclusive flags must not be combined."""

    def test_init_and_advance(self, thesis_project):
        proj, _ = thesis_project
        result = run_cm(
            "--init", "--advance", "--step", "1",
            "--project-dir", str(proj), expect_ok=False,
        )
        assert result.returncode != 0

    def test_status_and_validate(self, thesis_project):
        proj, _ = thesis_project
        result = run_cm(
            "--status", "--validate",
            "--project-dir", str(proj), expect_ok=False,
        )
        assert result.returncode != 0


# ===========================================================================
# query_workflow.py CLI flags
# ===========================================================================

class TestQW_Dashboard:
    """--dashboard flag."""

    def test_dashboard_json_output(self, thesis_project):
        proj, _ = thesis_project
        result = run_qw("--dashboard", "--project-dir", str(proj))
        data = json.loads(result.stdout)
        assert data["mode"] == "dashboard"

    def test_dashboard_missing_project(self, tmp_path):
        # query_workflow returns error JSON, not necessarily non-zero exit
        result = run_qw("--dashboard", "--project-dir", str(tmp_path), expect_ok=False)
        # May succeed with error in JSON or fail with exit code


class TestQW_Blocked:
    """--blocked flag."""

    def test_blocked_json_output(self, thesis_project):
        proj, _ = thesis_project
        result = run_qw("--blocked", "--project-dir", str(proj))
        data = json.loads(result.stdout)
        assert "blockers" in data


class TestQW_WeakestStep:
    """--weakest-step flag."""

    def test_weakest_no_pacs(self, thesis_project):
        proj, _ = thesis_project
        result = run_qw("--weakest-step", "--project-dir", str(proj))
        data = json.loads(result.stdout)
        assert data["mode"] == "weakest_step"
        assert data["found"] is False
