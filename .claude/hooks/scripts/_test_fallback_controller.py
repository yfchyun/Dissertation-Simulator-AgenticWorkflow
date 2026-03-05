#!/usr/bin/env python3
"""Tests for fallback_controller.py — 3-tier fallback switching.

All tests create a minimal thesis SOT in the temp directory since
fallback_controller now stores events in SOT's fallback_history field.
"""

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from fallback_controller import (
    TIER_TEAM,
    TIER_SUBAGENT,
    TIER_DIRECT,
    TIER_ORDER,
    MAX_RETRIES_PER_TIER,
    DEFAULT_TIMEOUT_SECONDS,
    get_current_tier,
    get_retry_count,
    next_tier,
    check_tier_status,
    escalate_tier,
    record_retry,
    record_success,
    load_fallback_log,
    save_fallback_log,
)
from checklist_manager import create_initial_sot, write_thesis_sot


def _init_sot(tmpdir: str) -> None:
    """Create a minimal thesis SOT in tmpdir for testing."""
    sot = create_initial_sot("test-project")
    write_thesis_sot(Path(tmpdir), sot)


class TestTierOrder(unittest.TestCase):
    """Test tier constants and ordering."""

    def test_three_tiers(self):
        self.assertEqual(len(TIER_ORDER), 3)

    def test_order_team_first(self):
        self.assertEqual(TIER_ORDER[0], TIER_TEAM)

    def test_order_direct_last(self):
        self.assertEqual(TIER_ORDER[-1], TIER_DIRECT)

    def test_next_tier_from_team(self):
        self.assertEqual(next_tier(TIER_TEAM), TIER_SUBAGENT)

    def test_next_tier_from_subagent(self):
        self.assertEqual(next_tier(TIER_SUBAGENT), TIER_DIRECT)

    def test_next_tier_from_direct(self):
        self.assertIsNone(next_tier(TIER_DIRECT))

    def test_next_tier_unknown(self):
        self.assertIsNone(next_tier("unknown"))


class TestFallbackLog(unittest.TestCase):
    """Test log persistence via SOT."""

    def test_empty_log_no_sot(self):
        """Without SOT, load returns empty list gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log = load_fallback_log(tmpdir)
            self.assertEqual(log, [])

    def test_empty_log_with_sot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _init_sot(tmpdir)
            log = load_fallback_log(tmpdir)
            self.assertEqual(log, [])

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _init_sot(tmpdir)
            log = [{"step": 1, "tier": TIER_TEAM, "action": "retry"}]
            save_fallback_log(tmpdir, log)
            loaded = load_fallback_log(tmpdir)
            self.assertEqual(loaded, log)

    def test_stored_in_sot(self):
        """Verify data is stored in SOT's fallback_history field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _init_sot(tmpdir)
            save_fallback_log(tmpdir, [{"test": True}])
            sot_path = Path(tmpdir) / "session.json"
            with open(sot_path) as f:
                sot = json.load(f)
            self.assertEqual(sot["fallback_history"], [{"test": True}])


class TestGetCurrentTier(unittest.TestCase):
    """Test current tier detection."""

    def test_default_is_team(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _init_sot(tmpdir)
            tier = get_current_tier(tmpdir, 1)
            self.assertEqual(tier, TIER_TEAM)

    def test_after_escalation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _init_sot(tmpdir)
            escalate_tier(tmpdir, 1, "test")
            tier = get_current_tier(tmpdir, 1)
            self.assertEqual(tier, TIER_SUBAGENT)

    def test_different_steps_independent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _init_sot(tmpdir)
            escalate_tier(tmpdir, 1, "test")
            tier_1 = get_current_tier(tmpdir, 1)
            tier_2 = get_current_tier(tmpdir, 2)
            self.assertEqual(tier_1, TIER_SUBAGENT)
            self.assertEqual(tier_2, TIER_TEAM)


class TestRetryCount(unittest.TestCase):
    """Test retry counting."""

    def test_zero_retries_initially(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _init_sot(tmpdir)
            count = get_retry_count(tmpdir, 1, TIER_TEAM)
            self.assertEqual(count, 0)

    def test_retry_increments(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _init_sot(tmpdir)
            record_retry(tmpdir, 1, TIER_TEAM, "test")
            record_retry(tmpdir, 1, TIER_TEAM, "test")
            count = get_retry_count(tmpdir, 1, TIER_TEAM)
            self.assertEqual(count, 2)

    def test_retries_per_tier_independent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _init_sot(tmpdir)
            record_retry(tmpdir, 1, TIER_TEAM, "test")
            count_team = get_retry_count(tmpdir, 1, TIER_TEAM)
            count_sub = get_retry_count(tmpdir, 1, TIER_SUBAGENT)
            self.assertEqual(count_team, 1)
            self.assertEqual(count_sub, 0)


class TestCheckTierStatus(unittest.TestCase):
    """Test tier status checking."""

    def test_healthy_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _init_sot(tmpdir)
            result = check_tier_status(tmpdir, 1)
            self.assertFalse(result["should_escalate"])
            self.assertEqual(result["reason"], "healthy")

    def test_retry_budget_exhausted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _init_sot(tmpdir)
            for _ in range(MAX_RETRIES_PER_TIER):
                record_retry(tmpdir, 1, TIER_TEAM, "test")
            result = check_tier_status(tmpdir, 1)
            self.assertTrue(result["should_escalate"])
            self.assertIn("retry_budget_exhausted", result["reason"])
            self.assertEqual(result["next_tier"], TIER_SUBAGENT)


class TestEscalateTier(unittest.TestCase):
    """Test tier escalation."""

    def test_escalate_team_to_subagent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _init_sot(tmpdir)
            result = escalate_tier(tmpdir, 1, "test")
            self.assertTrue(result["success"])
            self.assertEqual(result["old_tier"], TIER_TEAM)
            self.assertEqual(result["new_tier"], TIER_SUBAGENT)

    def test_escalate_to_direct(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _init_sot(tmpdir)
            escalate_tier(tmpdir, 1, "test")
            result = escalate_tier(tmpdir, 1, "test")
            self.assertTrue(result["success"])
            self.assertEqual(result["new_tier"], TIER_DIRECT)

    def test_cannot_escalate_past_direct(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _init_sot(tmpdir)
            escalate_tier(tmpdir, 1, "test")  # → subagent
            escalate_tier(tmpdir, 1, "test")  # → direct
            result = escalate_tier(tmpdir, 1, "test")  # → ?
            self.assertFalse(result["success"])
            self.assertIn("error", result)


class TestRecordSuccess(unittest.TestCase):
    """Test success recording."""

    def test_success_recorded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            _init_sot(tmpdir)
            record_success(tmpdir, 1, TIER_TEAM)
            log = load_fallback_log(tmpdir)
            self.assertEqual(len(log), 1)
            self.assertEqual(log[0]["action"], "success")
            self.assertEqual(log[0]["tier"], TIER_TEAM)


class TestNoSystemSOTReference(unittest.TestCase):
    def test_no_state_yaml_reference(self):
        content = (SCRIPT_DIR / "fallback_controller.py").read_text(encoding="utf-8")
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            self.assertNotIn("state.yaml", line, f"Line {i}")
            self.assertNotIn("state.yml", line, f"Line {i}")


if __name__ == "__main__":
    unittest.main()
