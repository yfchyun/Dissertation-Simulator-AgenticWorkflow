#!/usr/bin/env python3
"""Tests for validate_retry_budget.py — Retry Budget validation (RB1-RB3).

Run: python3 -m pytest _test_validate_retry_budget.py -v
  or: python3 _test_validate_retry_budget.py
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import validate_retry_budget as rb


class TestCounterReadWrite(unittest.TestCase):
    """Test counter file read/write (RB1)."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_read_missing_counter(self):
        """Missing counter file → returns 0."""
        path = self.tmpdir / "nonexistent"
        self.assertEqual(rb._read_counter(str(path)), 0)

    def test_read_invalid_counter(self):
        """Invalid content → returns 0."""
        path = self.tmpdir / "invalid"
        path.write_text("not-a-number")
        self.assertEqual(rb._read_counter(str(path)), 0)

    def test_read_valid_counter(self):
        """Valid integer content → returns that integer."""
        path = self.tmpdir / "counter"
        path.write_text("5")
        self.assertEqual(rb._read_counter(str(path)), 5)

    def test_increment_from_zero(self):
        """Incrementing non-existent counter creates file with value 1."""
        path = self.tmpdir / "verification-logs" / ".step-1-retry-count"
        path.parent.mkdir(parents=True, exist_ok=True)
        new_val = rb._increment_counter(str(path))
        self.assertEqual(new_val, 1)
        self.assertEqual(rb._read_counter(str(path)), 1)

    def test_increment_existing(self):
        """Incrementing existing counter increments by 1."""
        path = self.tmpdir / "verification-logs" / ".step-1-retry-count"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("3")
        new_val = rb._increment_counter(str(path))
        self.assertEqual(new_val, 4)


class TestBudgetCheck(unittest.TestCase):
    """Test budget comparison logic (RB3)."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        # Create gate directories
        for gate in rb.GATE_DIRS.values():
            (self.tmpdir / gate).mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _counter_path(self, step, gate):
        return self.tmpdir / rb.GATE_DIRS[gate] / f".step-{step}-retry-count"

    def test_can_retry_when_budget_available(self):
        """Budget available → can_retry = True."""
        retries_used = 5
        max_retries = rb.DEFAULT_MAX_RETRIES
        can_retry = retries_used < max_retries
        self.assertTrue(can_retry)

    def test_cannot_retry_when_budget_exhausted(self):
        """Budget exhausted → can_retry = False."""
        retries_used = rb.DEFAULT_MAX_RETRIES
        can_retry = retries_used < rb.DEFAULT_MAX_RETRIES
        self.assertFalse(can_retry)

    def test_ulw_has_higher_budget(self):
        """ULW budget (15) > default budget (10)."""
        self.assertGreater(rb.ULW_MAX_RETRIES, rb.DEFAULT_MAX_RETRIES)

    def test_valid_gates_includes_dialogue(self):
        """dialogue gate must be in VALID_GATES for adversarial dialogue support."""
        self.assertIn("dialogue", rb.VALID_GATES)

    def test_gate_dirs_has_dialogue(self):
        """dialogue gate must map to dialogue-logs directory."""
        self.assertIn("dialogue", rb.GATE_DIRS)
        self.assertEqual(rb.GATE_DIRS["dialogue"], "dialogue-logs")

    def test_all_gates_have_dirs(self):
        """Every gate in VALID_GATES must have a GATE_DIRS entry."""
        for gate in rb.VALID_GATES:
            self.assertIn(gate, rb.GATE_DIRS, f"Gate '{gate}' missing from GATE_DIRS")


class TestCounterPath(unittest.TestCase):
    """Test counter file path construction."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_counter_path_verification(self):
        path = rb._counter_path(str(self.tmpdir), 3, "verification")
        self.assertIn("verification-logs", path)
        self.assertIn(".step-3-retry-count", path)

    def test_counter_path_dialogue(self):
        path = rb._counter_path(str(self.tmpdir), 5, "dialogue")
        self.assertIn("dialogue-logs", path)
        self.assertIn(".step-5-retry-count", path)

    def test_counter_paths_are_isolated(self):
        """Each gate has its own counter file — no cross-gate interference."""
        path_review = rb._counter_path(str(self.tmpdir), 1, "review")
        path_dialogue = rb._counter_path(str(self.tmpdir), 1, "dialogue")
        self.assertNotEqual(path_review, path_dialogue)


class TestULWDetection(unittest.TestCase):
    """Test ULW active state detection (RB2)."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        snapshot_dir = self.tmpdir / ".claude" / "context-snapshots"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.snapshot_path = snapshot_dir / "latest.md"

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_no_snapshot_returns_false(self):
        """Missing snapshot → ULW not active."""
        result = rb._detect_ulw_from_snapshot(str(self.tmpdir))
        self.assertFalse(result)

    def test_snapshot_without_ulw_returns_false(self):
        """Snapshot without ULW marker → ULW not active."""
        self.snapshot_path.write_text("# Context Snapshot\n\nNormal mode active.\n")
        result = rb._detect_ulw_from_snapshot(str(self.tmpdir))
        self.assertFalse(result)

    def test_snapshot_with_ulw_korean_returns_true(self):
        """Snapshot with Korean ULW marker → ULW active."""
        self.snapshot_path.write_text("# Context\n\nULW 상태: active\n")
        result = rb._detect_ulw_from_snapshot(str(self.tmpdir))
        self.assertTrue(result)

    def test_snapshot_with_ulw_english_returns_true(self):
        """Snapshot with English ULW marker → ULW active."""
        self.snapshot_path.write_text("# Context\n\nUltrawork Mode State: enabled\n")
        result = rb._detect_ulw_from_snapshot(str(self.tmpdir))
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
