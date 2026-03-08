#!/usr/bin/env python3
"""Tests for validate_sot_schema() S9 and S10 checks in _context_lib.py.

S9: output key language suffix must be 'en' or 'ko' (no arbitrary suffixes)
S10: pacs.history step numbers must not exceed current_step

Run: python3 -m pytest _test_validate_sot_schema.py -v
  or: python3 _test_validate_sot_schema.py
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _context_lib import validate_sot_schema


def _base_state(current_step: int = 3) -> dict:
    """Minimal valid SOT ap_state dict."""
    return {"current_step": current_step}


class TestS9OutputKeyLangSuffix(unittest.TestCase):
    """S9: output key suffix must be 'en' or 'ko' only."""

    def test_s9_valid_en_suffix(self) -> None:
        state = _base_state()
        state["outputs"] = {"step-1-en": "some output"}
        warnings = validate_sot_schema(state)
        s9_warns = [w for w in warnings if "unrecognized language suffix" in w]
        self.assertEqual(s9_warns, [], f"'en' suffix should be valid, got: {s9_warns}")

    def test_s9_valid_ko_suffix(self) -> None:
        state = _base_state()
        state["outputs"] = {"step-2-ko": "번역 결과"}
        warnings = validate_sot_schema(state)
        s9_warns = [w for w in warnings if "unrecognized language suffix" in w]
        self.assertEqual(s9_warns, [], f"'ko' suffix should be valid, got: {s9_warns}")

    def test_s9_valid_both_suffixes(self) -> None:
        state = _base_state()
        state["outputs"] = {"step-1-en": "english", "step-1-ko": "한국어"}
        warnings = validate_sot_schema(state)
        s9_warns = [w for w in warnings if "unrecognized language suffix" in w]
        self.assertEqual(s9_warns, [], f"Both 'en' and 'ko' should be valid: {s9_warns}")

    def test_s9_invalid_suffix_jp(self) -> None:
        state = _base_state()
        state["outputs"] = {"step-1-jp": "日本語"}
        warnings = validate_sot_schema(state)
        s9_warns = [w for w in warnings if "unrecognized language suffix" in w]
        self.assertEqual(len(s9_warns), 1, f"'jp' suffix should trigger S9 warning: {warnings}")
        self.assertIn("step-1-jp", s9_warns[0])
        self.assertIn("jp", s9_warns[0])

    def test_s9_invalid_suffix_zh(self) -> None:
        state = _base_state()
        state["outputs"] = {"step-2-zh": "中文"}
        warnings = validate_sot_schema(state)
        s9_warns = [w for w in warnings if "unrecognized language suffix" in w]
        self.assertEqual(len(s9_warns), 1, f"'zh' suffix should trigger S9 warning: {warnings}")

    def test_s9_invalid_suffix_hallucination_pattern(self) -> None:
        """Agent hallucination: writing 'step-3-draft' or 'step-3-final' as output key."""
        state = _base_state()
        state["outputs"] = {"step-3-draft": "some content", "step-3-final": "output"}
        warnings = validate_sot_schema(state)
        s9_warns = [w for w in warnings if "unrecognized language suffix" in w]
        self.assertEqual(len(s9_warns), 2, f"'draft' and 'final' suffixes should each warn: {warnings}")

    def test_s9_multiple_invalid_suffixes(self) -> None:
        state = _base_state()
        state["outputs"] = {
            "step-1-en": "valid",
            "step-1-ko": "valid",
            "step-2-fr": "français",
            "step-3-de": "Deutsch",
        }
        warnings = validate_sot_schema(state)
        s9_warns = [w for w in warnings if "unrecognized language suffix" in w]
        self.assertEqual(len(s9_warns), 2, f"'fr' and 'de' should each warn: {warnings}")

    def test_s9_no_outputs_key(self) -> None:
        """S9 should not crash when 'outputs' is absent."""
        state = _base_state()
        warnings = validate_sot_schema(state)
        s9_warns = [w for w in warnings if "unrecognized language suffix" in w]
        self.assertEqual(s9_warns, [], "No 'outputs' key → no S9 warnings")

    def test_s9_outputs_not_step_prefix_ignored(self) -> None:
        """Keys not starting with 'step-' are skipped by S9 (handled by S3)."""
        state = _base_state()
        state["outputs"] = {"meta-jp": "not a step key"}
        warnings = validate_sot_schema(state)
        s9_warns = [w for w in warnings if "unrecognized language suffix" in w]
        self.assertEqual(s9_warns, [], "Non-step keys should be ignored by S9")


class TestS10PacsHistoryFutureStep(unittest.TestCase):
    """S10: pacs.history step numbers must not exceed current_step."""

    def _make_pacs(self, history: dict) -> dict:
        return {
            "dimensions": {"F": 75, "C": 80, "L": 70},
            "current_step_score": 70,
            "history": history,
        }

    def test_s10_valid_history_at_current_step(self) -> None:
        state = _base_state(current_step=3)
        state["pacs"] = self._make_pacs({"step-3": {"score": 70, "weak": "F"}})
        warnings = validate_sot_schema(state)
        s10_warns = [w for w in warnings if "future step" in w]
        self.assertEqual(s10_warns, [], f"step-3 at current_step=3 should be valid: {warnings}")

    def test_s10_valid_history_past_steps(self) -> None:
        state = _base_state(current_step=5)
        state["pacs"] = self._make_pacs({
            "step-1": {"score": 65, "weak": "C"},
            "step-3": {"score": 72, "weak": "F"},
            "step-5": {"score": 78, "weak": "L"},
        })
        warnings = validate_sot_schema(state)
        s10_warns = [w for w in warnings if "future step" in w]
        self.assertEqual(s10_warns, [], f"Past steps should all be valid: {warnings}")

    def test_s10_future_step_detected(self) -> None:
        """Agent recorded pacs for step-5 when current_step=3 — hallucination."""
        state = _base_state(current_step=3)
        state["pacs"] = self._make_pacs({"step-5": {"score": 80, "weak": "L"}})
        warnings = validate_sot_schema(state)
        s10_warns = [w for w in warnings if "future step" in w]
        self.assertEqual(len(s10_warns), 1, f"step-5 at current_step=3 should trigger S10: {warnings}")
        self.assertIn("step-5", s10_warns[0])
        self.assertIn("current_step=3", s10_warns[0])

    def test_s10_multiple_future_steps(self) -> None:
        state = _base_state(current_step=2)
        state["pacs"] = self._make_pacs({
            "step-1": {"score": 70, "weak": "F"},
            "step-3": {"score": 75, "weak": "C"},  # future
            "step-10": {"score": 80, "weak": "L"},  # future
        })
        warnings = validate_sot_schema(state)
        s10_warns = [w for w in warnings if "future step" in w]
        self.assertEqual(len(s10_warns), 2, f"step-3 and step-10 should both warn: {warnings}")

    def test_s10_step_0_is_never_future(self) -> None:
        """step-0 is always <= any current_step >= 0."""
        state = _base_state(current_step=0)
        state["pacs"] = self._make_pacs({"step-0": {"score": 70, "weak": "F"}})
        warnings = validate_sot_schema(state)
        s10_warns = [w for w in warnings if "future step" in w]
        self.assertEqual(s10_warns, [], "step-0 at current_step=0 should be valid")

    def test_s10_no_history_key(self) -> None:
        """S10 should not crash when pacs.history is absent."""
        state = _base_state(current_step=3)
        state["pacs"] = {"dimensions": {"F": 75, "C": 80, "L": 70}, "current_step_score": 70}
        warnings = validate_sot_schema(state)
        s10_warns = [w for w in warnings if "future step" in w]
        self.assertEqual(s10_warns, [], "No history key → no S10 warnings")

    def test_s10_no_pacs_key(self) -> None:
        """S10 should not crash when pacs is absent entirely."""
        state = _base_state(current_step=3)
        warnings = validate_sot_schema(state)
        s10_warns = [w for w in warnings if "future step" in w]
        self.assertEqual(s10_warns, [], "No pacs key → no S10 warnings")

    def test_s10_no_current_step(self) -> None:
        """S10 requires current_step to be int — skips check if absent."""
        state = {"pacs": self._make_pacs({"step-99": {"score": 80, "weak": "F"}})}
        warnings = validate_sot_schema(state)
        s10_warns = [w for w in warnings if "future step" in w]
        self.assertEqual(s10_warns, [], "No current_step → S10 check skipped (no false positives)")


class TestS9S10Isolation(unittest.TestCase):
    """Confirm S9 and S10 are independent — one failing does not mask the other."""

    def test_s9_and_s10_can_both_fire(self) -> None:
        state = _base_state(current_step=2)
        state["outputs"] = {"step-1-jp": "invalid lang"}
        state["pacs"] = {
            "dimensions": {"F": 70, "C": 75, "L": 65},
            "current_step_score": 65,
            "history": {"step-5": {"score": 80, "weak": "L"}},  # future step
        }
        warnings = validate_sot_schema(state)
        s9_warns = [w for w in warnings if "unrecognized language suffix" in w]
        s10_warns = [w for w in warnings if "future step" in w]
        self.assertEqual(len(s9_warns), 1, f"S9 should fire: {warnings}")
        self.assertEqual(len(s10_warns), 1, f"S10 should fire: {warnings}")


if __name__ == "__main__":
    unittest.main()
