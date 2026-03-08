#!/usr/bin/env python3
"""Tests for validate_dialogue_state.py — Adversarial Dialogue State validation (DA1-DA5).

Run: python3 -m pytest _test_validate_dialogue_state.py -v
  or: python3 _test_validate_dialogue_state.py
"""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import validate_dialogue_state as ds


class TestDialogueStateBase(unittest.TestCase):
    """Base class with helper methods for dialogue state tests."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.dlg_dir = self.tmpdir / "dialogue-logs"
        self.dlg_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_fc(self, step, round_num, verdict="PASS"):
        path = self.dlg_dir / f"step-{step}-r{round_num}-fc.md"
        path.write_text(
            f"# Fact-Check Report — Step {step} Round {round_num}\n\n"
            f"## Verdict: {verdict}\n\nSome fact-check content here.\n",
            encoding="utf-8",
        )
        return path

    def _write_rv(self, step, round_num, verdict="PASS"):
        path = self.dlg_dir / f"step-{step}-r{round_num}-rv.md"
        path.write_text(
            f"# Review Report — Step {step} Round {round_num}\n\n"
            f"## Verdict: {verdict}\n\nSome review content here.\n",
            encoding="utf-8",
        )
        return path

    def _write_cr(self, step, round_num, verdict="PASS"):
        path = self.dlg_dir / f"step-{step}-r{round_num}-cr.md"
        path.write_text(
            f"# Code Review — Step {step} Round {round_num}\n\n"
            f"## Verdict: {verdict}\n\nSome code review content here.\n",
            encoding="utf-8",
        )
        return path

    def _write_draft(self, step, round_num, content=None):
        path = self.dlg_dir / f"step-{step}-draft-r{round_num}.md"
        path.write_text(content or f"# Draft — Step {step} Round {round_num}\n\nDraft content.\n", encoding="utf-8")
        return path

    def _write_sot(self, dialogue_state=None):
        sot = {"current_step": 1}
        if dialogue_state is not None:
            sot["dialogue_state"] = dialogue_state
        sot_path = self.tmpdir / "session.json"
        sot_path.write_text(json.dumps(sot, ensure_ascii=False), encoding="utf-8")
        return sot_path


class TestDA1FilesExist(TestDialogueStateBase):
    """DA1: All round files must exist for rounds 1..K."""

    def test_research_round1_all_files_present(self):
        """Research domain: fc + rv files present → DA1 PASS."""
        self._write_fc(5, 1)
        self._write_rv(5, 1)
        result = ds.validate_dialogue_state(str(self.tmpdir), 5, 1)
        self.assertEqual(result["checks"]["DA1"], "PASS")

    def test_research_round1_fc_missing(self):
        """Research domain: fc file missing → DA1 FAIL."""
        self._write_rv(5, 1)  # rv present but fc missing
        result = ds.validate_dialogue_state(str(self.tmpdir), 5, 1)
        self.assertEqual(result["checks"]["DA1"], "FAIL")
        self.assertFalse(result["valid"])

    def test_development_round1_cr_present(self):
        """Development domain: cr file present → DA1 PASS."""
        self._write_sot({"domain": "development", "rounds_used": 1})
        self._write_cr(5, 1)
        result = ds.validate_dialogue_state(str(self.tmpdir), 5, 1)
        self.assertEqual(result["checks"]["DA1"], "PASS")
        self.assertEqual(result["domain"], "development")

    def test_development_round1_cr_missing(self):
        """Development domain: cr file missing → DA1 FAIL."""
        self._write_sot({"domain": "development"})
        result = ds.validate_dialogue_state(str(self.tmpdir), 5, 1)
        self.assertEqual(result["checks"]["DA1"], "FAIL")

    def test_research_multi_round_all_present(self):
        """Research domain: 3 rounds, all files present → DA1 PASS."""
        for r in range(1, 4):
            self._write_fc(3, r)
            self._write_rv(3, r)
        result = ds.validate_dialogue_state(str(self.tmpdir), 3, 3)
        self.assertEqual(result["checks"]["DA1"], "PASS")

    def test_research_multi_round_r2_missing(self):
        """Research domain: round 2 files missing → DA1 FAIL."""
        self._write_fc(3, 1)
        self._write_rv(3, 1)
        # Round 2 missing
        self._write_fc(3, 3)
        self._write_rv(3, 3)
        result = ds.validate_dialogue_state(str(self.tmpdir), 3, 3)
        self.assertEqual(result["checks"]["DA1"], "FAIL")


class TestDA2DraftTimestamp(TestDialogueStateBase):
    """DA2: draft-rK.md must precede critic-rK files (Research domain only)."""

    def test_draft_before_critic(self):
        """Draft created before critic → DA2 PASS."""
        draft = self._write_draft(5, 1)
        time.sleep(0.05)
        fc = self._write_fc(5, 1)
        rv = self._write_rv(5, 1)
        result = ds.validate_dialogue_state(str(self.tmpdir), 5, 1)
        self.assertIn(result["checks"]["DA2"], ("PASS",))

    def test_development_domain_skips_da2(self):
        """Development domain → DA2 skipped."""
        self._write_sot({"domain": "development"})
        self._write_cr(5, 1)
        result = ds.validate_dialogue_state(str(self.tmpdir), 5, 1)
        self.assertIn("SKIP", result["checks"]["DA2"])

    def test_missing_draft_generates_warning_not_fail(self):
        """Missing draft file → DA2 warning, not FAIL (file may not exist yet)."""
        self._write_fc(5, 1)
        self._write_rv(5, 1)
        result = ds.validate_dialogue_state(str(self.tmpdir), 5, 1)
        # DA2 should not be FAIL when draft is missing (just warning)
        self.assertNotEqual(result["checks"]["DA2"], "FAIL")


class TestDA3ConsensusCheck(TestDialogueStateBase):
    """DA3: --check-consensus validates final critic verdict = PASS."""

    def test_consensus_pass_when_final_verdict_pass(self):
        """Final critic verdict PASS + check_consensus → DA3 PASS."""
        self._write_fc(5, 2, verdict="PASS")
        self._write_rv(5, 2, verdict="PASS")
        result = ds.validate_dialogue_state(str(self.tmpdir), 5, 2, check_consensus=True)
        self.assertEqual(result["checks"]["DA3"], "PASS")

    def test_consensus_fail_when_final_verdict_fail(self):
        """Final critic verdict FAIL + check_consensus → DA3 FAIL."""
        self._write_fc(5, 2, verdict="FAIL")
        self._write_rv(5, 2, verdict="PASS")
        result = ds.validate_dialogue_state(str(self.tmpdir), 5, 2, check_consensus=True)
        self.assertEqual(result["checks"]["DA3"], "FAIL")

    def test_da3_skipped_without_flag(self):
        """Without check_consensus flag → DA3 skipped."""
        result = ds.validate_dialogue_state(str(self.tmpdir), 5, 1)
        self.assertIn("SKIP", result["checks"]["DA3"])


class TestDA4SOTConsistency(TestDialogueStateBase):
    """DA4: SOT outcome must match final critic verdict."""

    def test_consensus_sot_with_pass_verdict(self):
        """SOT outcome=consensus + final verdict PASS → DA4 PASS."""
        self._write_sot({
            "domain": "research",
            "outcome": "consensus",
            "rounds_used": 1,
        })
        self._write_fc(5, 1, verdict="PASS")
        self._write_rv(5, 1, verdict="PASS")
        result = ds.validate_dialogue_state(str(self.tmpdir), 5, 1)
        self.assertEqual(result["checks"]["DA4"], "PASS")

    def test_escalated_sot_with_fail_verdict(self):
        """SOT outcome=escalated + final verdict FAIL → DA4 PASS."""
        self._write_sot({
            "domain": "research",
            "outcome": "escalated",
            "rounds_used": 3,
        })
        self._write_fc(5, 1, verdict="FAIL")
        self._write_rv(5, 1, verdict="FAIL")
        result = ds.validate_dialogue_state(str(self.tmpdir), 5, 1)
        self.assertEqual(result["checks"]["DA4"], "PASS")

    def test_consensus_sot_mismatch_fail_verdict(self):
        """SOT outcome=consensus + final verdict FAIL → DA4 FAIL."""
        self._write_sot({
            "domain": "research",
            "outcome": "consensus",
            "rounds_used": 1,
        })
        self._write_fc(5, 1, verdict="FAIL")
        self._write_rv(5, 1, verdict="PASS")
        result = ds.validate_dialogue_state(str(self.tmpdir), 5, 1)
        self.assertEqual(result["checks"]["DA4"], "FAIL")

    def test_no_sot_skips_da4(self):
        """No SOT → DA4 skipped."""
        self._write_fc(5, 1)
        self._write_rv(5, 1)
        result = ds.validate_dialogue_state(str(self.tmpdir), 5, 1)
        self.assertIn("SKIP", result["checks"]["DA4"])


class TestDA5RoundsCounter(TestDialogueStateBase):
    """DA5: SOT rounds_used <= max_rounds."""

    def test_rounds_within_budget(self):
        """rounds_used < max_rounds → DA5 PASS."""
        self._write_sot({
            "domain": "research",
            "rounds_used": 2,
            "max_rounds": 3,
        })
        self._write_fc(5, 2)
        self._write_rv(5, 2)
        result = ds.validate_dialogue_state(str(self.tmpdir), 5, 2)
        self.assertEqual(result["checks"]["DA5"], "PASS")

    def test_rounds_at_budget_boundary(self):
        """rounds_used == max_rounds → DA5 PASS (boundary is allowed)."""
        self._write_sot({
            "domain": "research",
            "rounds_used": 3,
            "max_rounds": 3,
        })
        for r in range(1, 4):
            self._write_fc(5, r)
            self._write_rv(5, r)
        result = ds.validate_dialogue_state(str(self.tmpdir), 5, 3)
        self.assertEqual(result["checks"]["DA5"], "PASS")

    def test_rounds_exceed_budget(self):
        """rounds_used > max_rounds → DA5 FAIL."""
        self._write_sot({
            "domain": "research",
            "rounds_used": 5,
            "max_rounds": 3,
        })
        for r in range(1, 4):
            self._write_fc(5, r)
            self._write_rv(5, r)
        result = ds.validate_dialogue_state(str(self.tmpdir), 5, 3)
        self.assertEqual(result["checks"]["DA5"], "FAIL")

    def test_no_sot_skips_da5(self):
        """No SOT → DA5 skipped."""
        self._write_fc(5, 1)
        self._write_rv(5, 1)
        result = ds.validate_dialogue_state(str(self.tmpdir), 5, 1)
        self.assertIn("SKIP", result["checks"]["DA5"])


class TestValidOutput(TestDialogueStateBase):
    """Test valid field in output."""

    def test_all_pass_means_valid(self):
        """All checks passing → valid = True."""
        self._write_sot({
            "domain": "research",
            "rounds_used": 1,
            "max_rounds": 3,
        })
        self._write_draft(5, 1)
        time.sleep(0.05)
        self._write_fc(5, 1, verdict="PASS")
        self._write_rv(5, 1, verdict="PASS")
        result = ds.validate_dialogue_state(str(self.tmpdir), 5, 1)
        self.assertTrue(result["valid"])
        self.assertEqual(result["step"], 5)
        self.assertEqual(result["round"], 1)

    def test_result_has_required_fields(self):
        """Result must have standard fields."""
        self._write_fc(5, 1)
        self._write_rv(5, 1)
        result = ds.validate_dialogue_state(str(self.tmpdir), 5, 1)
        for field in ("valid", "step", "round", "domain", "checks", "warnings"):
            self.assertIn(field, result, f"Missing field: {field}")


if __name__ == "__main__":
    unittest.main()
