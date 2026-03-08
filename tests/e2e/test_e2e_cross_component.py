"""Track 3: Cross-Component Integration E2E Tests.

Tests data flow between:
  checklist_manager ↔ query_workflow ↔ generate_context_summary ↔ validate_grounded_claim
"""

import json
import os
import re
import sys
from pathlib import Path

import pytest

from conftest import run_cm, run_qw, read_sot, write_sot, SCRIPTS_DIR


class TestChecklist2Query:
    """E2E: Data written by checklist_manager must be readable by query_workflow."""

    def test_dashboard_reads_thesis_sot(self, thesis_project):
        proj, _ = thesis_project
        result = run_qw("--dashboard", "--project-dir", str(proj))
        data = json.loads(result.stdout)
        assert data["mode"] == "dashboard"
        assert data["current_step"] == 0
        assert data["workflow_status"] == "running"

    def test_dashboard_shows_gates(self, thesis_project):
        import checklist_manager as cm
        proj, _ = thesis_project
        cm.record_gate_result(proj, "gate-1", "pass")
        result = run_qw("--dashboard", "--project-dir", str(proj))
        data = json.loads(result.stdout)
        assert "gates" in data
        assert data["gates"]["gate-1"] == "pass"

    def test_dashboard_shows_hitl(self, thesis_project):
        proj, _ = thesis_project
        run_cm("--record-hitl", "hitl-1", "--project-dir", str(proj))
        result = run_qw("--dashboard", "--project-dir", str(proj))
        data = json.loads(result.stdout)
        assert "hitl_checkpoints" in data
        assert data["hitl_checkpoints"]["hitl-1"] == "completed"

    def test_dashboard_shows_research_type(self, thesis_project):
        proj, _ = thesis_project
        result = run_qw("--dashboard", "--project-dir", str(proj))
        data = json.loads(result.stdout)
        assert data["research_type"] == "quantitative"

    def test_dashboard_after_advance(self, thesis_project):
        proj, _ = thesis_project
        run_cm("--advance", "--step", "5", "--project-dir", str(proj))
        result = run_qw("--dashboard", "--project-dir", str(proj))
        data = json.loads(result.stdout)
        assert data["current_step"] == 5

    def test_blocked_shows_failed_gate(self, thesis_project):
        import checklist_manager as cm
        proj, _ = thesis_project
        cm.record_gate_result(proj, "gate-1", "fail")
        result = run_qw("--blocked", "--project-dir", str(proj))
        data = json.loads(result.stdout)
        blockers = data.get("blockers", [])
        gate_blockers = [b for b in blockers if b.get("type") == "gate_fail"]
        assert len(gate_blockers) >= 1
        assert gate_blockers[0]["gate"] == "gate-1"

    def test_blocked_shows_hitl_blocked(self, thesis_project):
        proj, _ = thesis_project
        run_cm("--record-hitl", "hitl-3", "--hitl-status", "blocked", "--project-dir", str(proj))
        result = run_qw("--blocked", "--project-dir", str(proj))
        data = json.loads(result.stdout)
        blockers = data.get("blockers", [])
        hitl_blockers = [b for b in blockers if b.get("type") == "hitl_blocked"]
        assert len(hitl_blockers) >= 1

    def test_fallback_events_count(self, thesis_project):
        import checklist_manager as cm
        proj, _ = thesis_project
        sot = read_sot(proj)
        sot["fallback_history"] = [
            {"tier": "subagent", "step": 5, "reason": "team_failure"},
            {"tier": "direct", "step": 8, "reason": "subagent_failure"},
        ]
        write_sot(proj, sot)
        result = run_qw("--dashboard", "--project-dir", str(proj))
        data = json.loads(result.stdout)
        assert data.get("fallback_events") == 2


class TestContextSummaryIntegration:
    """E2E: generate_context_summary reads thesis SOT correctly."""

    def test_thesis_summary_function(self, thesis_project):
        """Call get_thesis_state_summary directly."""
        proj, _ = thesis_project
        sys.path.insert(0, str(SCRIPTS_DIR))
        from _context_lib import get_thesis_state_summary
        # Need to pass the PARENT of thesis-output
        aw_root = proj.parent.parent  # tmp_path (contains thesis-output/)
        summary = get_thesis_state_summary(str(aw_root))
        assert "test-project" in summary
        assert "step 0/" in summary
        assert "status=running" in summary

    def test_thesis_summary_shows_gates(self, thesis_project):
        import checklist_manager as cm
        proj, _ = thesis_project
        cm.record_gate_result(proj, "gate-1", "pass")
        from _context_lib import get_thesis_state_summary
        aw_root = proj.parent.parent
        summary = get_thesis_state_summary(str(aw_root))
        assert "gate-1:pass" in summary

    def test_thesis_summary_shows_hitl(self, thesis_project):
        proj, _ = thesis_project
        run_cm("--record-hitl", "hitl-0", "--project-dir", str(proj))
        from _context_lib import get_thesis_state_summary
        aw_root = proj.parent.parent
        summary = get_thesis_state_summary(str(aw_root))
        assert "hitl-0" in summary

    def test_thesis_summary_empty_if_no_projects(self, tmp_path):
        from _context_lib import get_thesis_state_summary
        summary = get_thesis_state_summary(str(tmp_path))
        assert summary == ""


class TestGroundedClaimValidation:
    """E2E: validate_grounded_claim regex matches all agent claim ID formats."""

    def _extract_ids(self, text):
        """Use the actual extraction regex from validate_grounded_claim.py."""
        pattern = re.compile(r'id:\s*["\']?([A-Za-z]+(?:-[A-Za-z]+)*-?\d+)["\']?')
        return pattern.findall(text)

    def _validate_id(self, cid):
        """Use the actual validation pattern from validate_grounded_claim.py."""
        pattern = re.compile(r"^[A-Z]{1,4}(?:-[A-Z]{1,4})?-?\d{3}$")
        return bool(pattern.match(cid))

    def test_standard_ids(self):
        text = 'id: "LS-001"\nid: "TFA-012"\nid: "GI-005"'
        ids = self._extract_ids(text)
        assert ids == ["LS-001", "TFA-012", "GI-005"]
        for cid in ids:
            assert self._validate_id(cid), f"{cid} failed validation"

    def test_sub_prefix_ids(self):
        text = 'id: "SA-TA001"\nid: "VRA-H001"\nid: "FDA-PB001"\nid: "CMB-M001"'
        ids = self._extract_ids(text)
        assert len(ids) == 4
        for cid in ids:
            assert self._validate_id(cid), f"{cid} failed validation"

    def test_methodology_family_ids(self):
        text = 'id: "MS-PS001"\nid: "MS-QA001"\nid: "MS-IS001"'
        ids = self._extract_ids(text)
        assert len(ids) == 3
        for cid in ids:
            assert self._validate_id(cid), f"{cid} failed validation"

    def test_srcs_compound_id(self):
        text = 'id: "PC-SRCS-001"'
        ids = self._extract_ids(text)
        assert ids == ["PC-SRCS-001"]
        assert self._validate_id("PC-SRCS-001")

    def test_literature_family_ids(self):
        text = 'id: "LS-001"\nid: "LS-T001"\nid: "LS-A001"'
        ids = self._extract_ids(text)
        assert len(ids) == 3
        for cid in ids:
            assert self._validate_id(cid), f"{cid} failed validation"
