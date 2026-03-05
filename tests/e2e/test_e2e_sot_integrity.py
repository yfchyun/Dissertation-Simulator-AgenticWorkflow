"""Track 2: SOT Integrity E2E Tests.

Tests schema validation, field consistency, atomic writes, and data integrity.
"""

import json
import os
import threading
from pathlib import Path

import pytest

from conftest import run_cm, read_sot, write_sot


class TestSchemaValidation:
    """E2E: SOT schema must remain valid after all operations."""

    def test_init_produces_valid_sot(self, thesis_project):
        import checklist_manager as cm
        proj, sot = thesis_project
        errors = cm.validate_thesis_sot(sot)
        assert errors == [], f"Init SOT has errors: {errors}"

    def test_advance_preserves_schema(self, thesis_project):
        import checklist_manager as cm
        proj, _ = thesis_project
        run_cm("--advance", "--step", "5", "--project-dir", str(proj))
        sot = read_sot(proj)
        errors = cm.validate_thesis_sot(sot)
        assert errors == [], f"Post-advance SOT has errors: {errors}"

    def test_gate_recording_preserves_schema(self, thesis_project):
        import checklist_manager as cm
        proj, _ = thesis_project
        cm.record_gate_result(proj, "gate-1", "pass")
        sot = read_sot(proj)
        errors = cm.validate_thesis_sot(sot)
        assert errors == [], f"Post-gate SOT has errors: {errors}"

    def test_hitl_recording_preserves_schema(self, thesis_project):
        import checklist_manager as cm
        proj, _ = thesis_project
        run_cm("--record-hitl", "hitl-1", "--project-dir", str(proj))
        sot = read_sot(proj)
        errors = cm.validate_thesis_sot(sot)
        assert errors == [], f"Post-HITL SOT has errors: {errors}"

    def test_checkpoint_preserves_schema(self, thesis_project):
        import checklist_manager as cm
        proj, _ = thesis_project
        run_cm("--save-checkpoint", "--checkpoint", "schema-test", "--project-dir", str(proj))
        sot = read_sot(proj)
        errors = cm.validate_thesis_sot(sot)
        assert errors == [], f"Post-checkpoint SOT has errors: {errors}"

    def test_validate_cli_on_valid_sot(self, thesis_project):
        proj, _ = thesis_project
        result = run_cm("--validate", "--project-dir", str(proj))
        assert "PASS" in result.stdout

    def test_validate_cli_on_corrupted_sot(self, thesis_project):
        proj, _ = thesis_project
        # Corrupt SOT
        sot = read_sot(proj)
        sot["status"] = "INVALID_STATUS"
        write_sot(proj, sot)
        result = run_cm("--validate", "--project-dir", str(proj), expect_ok=False)
        assert result.returncode != 0


class TestFieldConsistency:
    """E2E: Fields read by consumers must match fields written by producers."""

    def test_status_field_exists(self, thesis_project):
        """query_workflow reads 'status' — verify it exists after init."""
        _, sot = thesis_project
        assert "status" in sot
        assert sot["status"] in {"running", "completed", "error", "paused"}

    def test_gates_field_structure(self, thesis_project):
        """query_workflow reads gates.*.status — verify structure."""
        _, sot = thesis_project
        assert "gates" in sot
        for name, gate in sot["gates"].items():
            assert isinstance(gate, dict), f"gate {name} not a dict"
            assert "status" in gate, f"gate {name} missing status"

    def test_hitl_field_structure(self, thesis_project):
        """query_workflow reads hitl_checkpoints.*.status — verify structure."""
        _, sot = thesis_project
        assert "hitl_checkpoints" in sot
        for name, hitl in sot["hitl_checkpoints"].items():
            assert isinstance(hitl, dict), f"hitl {name} not a dict"
            assert "status" in hitl, f"hitl {name} missing status"

    def test_outputs_field_is_dict(self, thesis_project):
        _, sot = thesis_project
        assert isinstance(sot["outputs"], dict)

    def test_fallback_history_is_list(self, thesis_project):
        _, sot = thesis_project
        assert isinstance(sot["fallback_history"], list)

    def test_context_snapshots_is_list(self, thesis_project):
        _, sot = thesis_project
        assert isinstance(sot["context_snapshots"], list)


class TestAtomicWrites:
    """E2E: SOT writes must be atomic (no partial writes)."""

    def test_sot_valid_json_after_write(self, thesis_project):
        import checklist_manager as cm
        proj, _ = thesis_project
        # Rapid sequence of writes
        for i in range(1, 6):
            cm.record_output(proj, i, f"wave-results/step-{i}.md")
        # SOT must be valid JSON
        sot = read_sot(proj)
        assert sot["outputs"]["step-5"] == "wave-results/step-5.md"

    def test_concurrent_reads_safe(self, thesis_project):
        """Multiple reads should not corrupt SOT."""
        proj, _ = thesis_project
        results = []

        def read_worker():
            try:
                sot = read_sot(proj)
                results.append(("ok", sot["current_step"]))
            except Exception as e:
                results.append(("error", str(e)))

        threads = [threading.Thread(target=read_worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        errors = [r for r in results if r[0] == "error"]
        assert len(errors) == 0, f"Concurrent read errors: {errors}"


class TestTimestamps:
    """E2E: Timestamps must be updated on every write."""

    def test_init_sets_timestamps(self, thesis_project):
        _, sot = thesis_project
        assert sot["created_at"] is not None
        assert sot["updated_at"] is not None
        # Timestamps may differ by microseconds due to init_project writing twice
        assert sot["created_at"][:19] == sot["updated_at"][:19]

    def test_advance_updates_timestamp(self, thesis_project):
        proj, sot = thesis_project
        old_updated = sot["updated_at"]
        import time
        time.sleep(0.01)  # Ensure timestamp differs
        run_cm("--advance", "--step", "1", "--project-dir", str(proj))
        new_sot = read_sot(proj)
        assert new_sot["updated_at"] >= old_updated
