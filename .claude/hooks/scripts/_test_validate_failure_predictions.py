#!/usr/bin/env python3
"""Tests for validate_failure_predictions.py — FP1-FP7 Validation (Phase C).

Run: python3 -m pytest _test_validate_failure_predictions.py -v
  or: python3 _test_validate_failure_predictions.py
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import validate_failure_predictions as vfp


# === Shared test fixtures ===

def _make_code_map(files=None):
    """Build a minimal code map fixture."""
    if files is None:
        files = [
            {"path": ".claude/hooks/scripts/restore_context.py", "line_count": 950},
            {"path": ".claude/hooks/scripts/save_context.py", "line_count": 200},
            {"path": ".claude/agents/reviewer.md", "line_count": 80},
        ]
    return {"files": files}


def _make_prediction(
    pred_id="FP-001",
    category="F1",
    severity="Warning",
    file=".claude/hooks/scripts/restore_context.py",
    line=100,
    summary="Test prediction",
    **extra,
):
    pred = {
        "id": pred_id,
        "category": category,
        "severity": severity,
        "file": file,
        "summary": summary,
    }
    if line is not None:
        pred["line"] = line
    pred.update(extra)
    return pred


class TestBuildFileIndex(unittest.TestCase):
    """Test _build_file_index() — code map to {path: line_count} index."""

    def test_basic_indexing(self):
        code_map = _make_code_map()
        index = vfp._build_file_index(code_map)
        self.assertEqual(
            index[".claude/hooks/scripts/restore_context.py"], 950
        )
        self.assertEqual(len(index), 3)

    def test_empty_code_map(self):
        index = vfp._build_file_index({"files": []})
        self.assertEqual(index, {})

    def test_missing_files_key(self):
        index = vfp._build_file_index({})
        self.assertEqual(index, {})

    def test_skips_empty_paths(self):
        code_map = _make_code_map([{"path": "", "line_count": 10}])
        index = vfp._build_file_index(code_map)
        self.assertEqual(index, {})


class TestValidatePredictor(unittest.TestCase):
    """Test _validate_predictor() — FP1-FP7 structural checks."""

    def setUp(self):
        self.file_index = vfp._build_file_index(_make_code_map())

    def test_valid_prediction_passes(self):
        draft = {"predictions": [
            _make_prediction(pred_id="FP-001", line=10),
            _make_prediction(pred_id="FP-002", line=20),
            _make_prediction(pred_id="FP-003", line=30),
        ]}
        valid, violations = vfp._validate_predictor(draft, self.file_index)
        self.assertEqual(len(valid), 3)
        self.assertEqual(len(violations), 0)

    def test_fp1_file_not_in_code_map(self):
        """FP1/FP3: File not found in scanned files → removed."""
        draft = {"predictions": [
            _make_prediction(file="nonexistent/file.py")
        ]}
        valid, violations = vfp._validate_predictor(draft, self.file_index)
        self.assertEqual(len(valid), 0)
        self.assertTrue(any("FP1/FP3" in v for v in violations))

    def test_fp2_line_out_of_range(self):
        """FP2: Line number beyond file line_count → removed."""
        draft = {"predictions": [
            _make_prediction(line=9999)  # restore_context.py has 950 lines
        ]}
        valid, violations = vfp._validate_predictor(draft, self.file_index)
        self.assertEqual(len(valid), 0)
        self.assertTrue(any("FP2" in v for v in violations))

    def test_fp2_line_zero(self):
        """FP2: Line 0 is invalid (lines start at 1)."""
        draft = {"predictions": [
            _make_prediction(line=0)
        ]}
        valid, violations = vfp._validate_predictor(draft, self.file_index)
        self.assertEqual(len(valid), 0)
        self.assertTrue(any("FP2" in v for v in violations))

    def test_fp2_line_negative(self):
        """FP2: Negative line number → removed."""
        draft = {"predictions": [
            _make_prediction(line=-5)
        ]}
        valid, violations = vfp._validate_predictor(draft, self.file_index)
        self.assertEqual(len(valid), 0)

    def test_fp2_line_exactly_at_max(self):
        """FP2: Line exactly at line_count is valid."""
        draft = {"predictions": [
            _make_prediction(pred_id="FP-001", line=950),
            _make_prediction(pred_id="FP-002", line=10),
            _make_prediction(pred_id="FP-003", line=20),
        ]}
        valid, violations = vfp._validate_predictor(draft, self.file_index)
        self.assertEqual(len(valid), 3)
        self.assertEqual(len(violations), 0)

    def test_fp4_invalid_severity(self):
        """FP4: Invalid severity value → removed."""
        draft = {"predictions": [
            _make_prediction(severity="High")
        ]}
        valid, violations = vfp._validate_predictor(draft, self.file_index)
        self.assertEqual(len(valid), 0)
        self.assertTrue(any("FP4" in v for v in violations))

    def test_fp4_all_valid_severities(self):
        """FP4: All three valid severity values accepted."""
        for sev in ("Critical", "Warning", "Info"):
            draft = {"predictions": [
                _make_prediction(pred_id=f"FP-{sev}", severity=sev)
            ]}
            valid, violations = vfp._validate_predictor(draft, self.file_index)
            self.assertEqual(len(valid), 1, f"Severity '{sev}' should be valid")

    def test_fp5_missing_required_fields(self):
        """FP5: Missing required fields → removed."""
        draft = {"predictions": [{"id": "FP-001", "category": "F1"}]}
        valid, violations = vfp._validate_predictor(draft, self.file_index)
        self.assertEqual(len(valid), 0)
        self.assertTrue(any("FP5" in v for v in violations))

    def test_fp5_empty_file_field(self):
        """FP5: Empty string for 'file' field → violation."""
        draft = {"predictions": [
            _make_prediction(file="")
        ]}
        valid, violations = vfp._validate_predictor(draft, self.file_index)
        self.assertEqual(len(valid), 0)
        self.assertTrue(any("FP5" in v for v in violations))

    def test_fp6_invalid_category(self):
        """FP6: Category not in F1-F7 → removed."""
        draft = {"predictions": [
            _make_prediction(category="F99")
        ]}
        valid, violations = vfp._validate_predictor(draft, self.file_index)
        self.assertEqual(len(valid), 0)
        self.assertTrue(any("FP6" in v for v in violations))

    def test_fp6_full_category_name_accepted(self):
        """FP6: 'F1_concurrency' style should be accepted (split on _)."""
        draft = {"predictions": [
            _make_prediction(category="F1_concurrency")
        ]}
        valid, violations = vfp._validate_predictor(draft, self.file_index)
        self.assertEqual(len(valid), 1)
        # Verify category was normalized
        self.assertEqual(valid[0]["category"], "F1")

    def test_fp7_zero_valid_predictions(self):
        """FP7: 0 valid predictions after all checks → violation."""
        draft = {"predictions": [
            _make_prediction(file="nonexistent.py")  # FP1 fail
        ]}
        valid, violations = vfp._validate_predictor(draft, self.file_index)
        self.assertEqual(len(valid), 0)
        self.assertTrue(any("FP7" in v for v in violations))

    def test_fp7_below_minimum_threshold(self):
        """FP7: 1-2 valid predictions below MIN_VALID_PREDICTIONS (3) → violation."""
        draft = {"predictions": [
            _make_prediction(pred_id="FP-001", line=10),
            _make_prediction(pred_id="FP-002", line=20),
        ]}
        valid, violations = vfp._validate_predictor(draft, self.file_index)
        self.assertEqual(len(valid), 2)
        # Should have FP7 violation because 2 < MIN_VALID_PREDICTIONS (3)
        self.assertTrue(any("FP7" in v for v in violations),
                        "2 valid predictions should trigger FP7 (minimum is 3)")

    def test_fp7_at_minimum_passes(self):
        """FP7: Exactly MIN_VALID_PREDICTIONS (3) → no FP7 violation."""
        draft = {"predictions": [
            _make_prediction(pred_id="FP-001", line=10),
            _make_prediction(pred_id="FP-002", line=20),
            _make_prediction(pred_id="FP-003", line=30),
        ]}
        valid, violations = vfp._validate_predictor(draft, self.file_index)
        self.assertEqual(len(valid), 3)
        self.assertFalse(any("FP7" in v for v in violations),
                         "3 valid predictions should not trigger FP7")

    def test_fp7_above_minimum_passes(self):
        """FP7: Above MIN_VALID_PREDICTIONS → no FP7 violation."""
        draft = {"predictions": [
            _make_prediction(pred_id=f"FP-{i:03d}", line=i*10)
            for i in range(1, 6)  # 5 predictions
        ]}
        valid, violations = vfp._validate_predictor(draft, self.file_index)
        self.assertEqual(len(valid), 5)
        self.assertFalse(any("FP7" in v for v in violations))

    def test_duplicate_id_rejected(self):
        """Duplicate prediction IDs → second one removed."""
        draft = {"predictions": [
            _make_prediction(pred_id="FP-001", line=10),
            _make_prediction(pred_id="FP-001", line=20),
        ]}
        valid, violations = vfp._validate_predictor(draft, self.file_index)
        self.assertEqual(len(valid), 1)
        self.assertTrue(any("duplicate" in v for v in violations))

    def test_predictions_not_a_list(self):
        """predictions key is not a list → violation."""
        draft = {"predictions": "not a list"}
        valid, violations = vfp._validate_predictor(draft, self.file_index)
        self.assertEqual(len(valid), 0)
        self.assertTrue(any("FP5" in v for v in violations))

    def test_prediction_not_a_dict(self):
        """Individual prediction is not a dict → violation."""
        draft = {"predictions": ["string item"]}
        valid, violations = vfp._validate_predictor(draft, self.file_index)
        self.assertEqual(len(valid), 0)

    def test_multiple_valid_and_invalid(self):
        """Mix of valid and invalid predictions — only valid pass through."""
        draft = {"predictions": [
            _make_prediction(pred_id="FP-001", line=10),   # valid
            _make_prediction(pred_id="FP-002", file="bad.py"),  # FP1 fail
            _make_prediction(pred_id="FP-003", line=20),   # valid
        ]}
        valid, violations = vfp._validate_predictor(draft, self.file_index)
        self.assertEqual(len(valid), 2)
        valid_ids = {p["id"] for p in valid}
        self.assertEqual(valid_ids, {"FP-001", "FP-003"})

    def test_line_none_accepted(self):
        """Prediction without 'line' field (None) is valid — line is optional."""
        draft = {"predictions": [
            _make_prediction(line=None)
        ]}
        valid, violations = vfp._validate_predictor(draft, self.file_index)
        self.assertEqual(len(valid), 1)


class TestValidateCritic(unittest.TestCase):
    """Test _validate_critic() — critic format validation."""

    def test_valid_judgments(self):
        draft = {
            "judgments": [
                {"id": "FP-001", "verdict": "CONFIRM", "reason": "Verified"},
                {"id": "FP-002", "verdict": "DISMISS", "reason": "Safeguard exists"},
            ],
            "additions": [],
        }
        result, violations = vfp._validate_critic(draft)
        self.assertEqual(len(result["judgments"]), 2)
        self.assertEqual(len(violations), 0)

    def test_invalid_verdict(self):
        draft = {
            "judgments": [
                {"id": "FP-001", "verdict": "MAYBE"},
            ],
            "additions": [],
        }
        result, violations = vfp._validate_critic(draft)
        self.assertEqual(len(result["judgments"]), 0)
        self.assertTrue(any("verdict" in v for v in violations))

    def test_all_valid_verdicts(self):
        for verdict in ("CONFIRM", "DISMISS", "ESCALATE"):
            draft = {
                "judgments": [{"id": f"FP-{verdict}", "verdict": verdict}],
                "additions": [],
            }
            result, violations = vfp._validate_critic(draft)
            self.assertEqual(len(result["judgments"]), 1,
                             f"Verdict '{verdict}' should be valid")

    def test_missing_judgment_fields(self):
        draft = {
            "judgments": [{"verdict": "CONFIRM"}],  # missing id
            "additions": [],
        }
        result, violations = vfp._validate_critic(draft)
        self.assertEqual(len(result["judgments"]), 0)
        self.assertTrue(any("missing fields" in v for v in violations))

    def test_valid_addition(self):
        draft = {
            "judgments": [],
            "additions": [
                {
                    "id": "ADD-001",
                    "category": "F3",
                    "severity": "Warning",
                    "file": "test.py",
                    "summary": "Missed risk",
                },
            ],
        }
        result, violations = vfp._validate_critic(draft)
        self.assertEqual(len(result["additions"]), 1)
        self.assertEqual(result["additions"][0]["category"], "F3")

    def test_invalid_addition_severity(self):
        draft = {
            "judgments": [],
            "additions": [
                {
                    "id": "ADD-001",
                    "category": "F3",
                    "severity": "Extreme",
                    "file": "test.py",
                    "summary": "Bad severity",
                },
            ],
        }
        result, violations = vfp._validate_critic(draft)
        self.assertEqual(len(result["additions"]), 0)

    def test_invalid_addition_category(self):
        draft = {
            "judgments": [],
            "additions": [
                {
                    "id": "ADD-001",
                    "category": "F99",
                    "severity": "Warning",
                    "file": "test.py",
                    "summary": "Bad category",
                },
            ],
        }
        result, violations = vfp._validate_critic(draft)
        self.assertEqual(len(result["additions"]), 0)

    def test_judgments_not_a_list(self):
        draft = {"judgments": "not a list", "additions": []}
        result, violations = vfp._validate_critic(draft)
        self.assertEqual(len(result["judgments"]), 0)
        self.assertTrue(any("must be a list" in v for v in violations))

    def test_addition_category_normalization(self):
        """Addition with 'F3_resource_leak' should normalize to 'F3'."""
        draft = {
            "judgments": [],
            "additions": [
                {
                    "id": "ADD-001",
                    "category": "F3_resource_leak",
                    "severity": "Warning",
                    "file": "test.py",
                    "summary": "Resource leak",
                },
            ],
        }
        result, violations = vfp._validate_critic(draft)
        self.assertEqual(len(result["additions"]), 1)
        self.assertEqual(result["additions"][0]["category"], "F3")

    def test_r3_addition_empty_file_rejected(self):
        """R-3: Critic addition with empty file field should be rejected."""
        draft = {
            "judgments": [],
            "additions": [
                {
                    "id": "ADD-001",
                    "category": "F3",
                    "severity": "Warning",
                    "file": "",
                    "summary": "Empty file",
                },
            ],
        }
        result, violations = vfp._validate_critic(draft)
        self.assertEqual(len(result["additions"]), 0)
        self.assertTrue(any("empty" in v for v in violations))

    def test_r4_duplicate_judgment_id_rejected(self):
        """R-4: Duplicate judgment IDs should be rejected."""
        draft = {
            "judgments": [
                {"id": "FP-001", "verdict": "CONFIRM", "reason": "First"},
                {"id": "FP-001", "verdict": "DISMISS", "reason": "Second"},
            ],
            "additions": [],
        }
        result, violations = vfp._validate_critic(draft)
        self.assertEqual(len(result["judgments"]), 1)
        self.assertTrue(any("duplicate" in v for v in violations))

    def test_r4_unique_judgment_ids_pass(self):
        """R-4: Unique judgment IDs should all pass."""
        draft = {
            "judgments": [
                {"id": "FP-001", "verdict": "CONFIRM"},
                {"id": "FP-002", "verdict": "DISMISS"},
                {"id": "FP-003", "verdict": "ESCALATE"},
            ],
            "additions": [],
        }
        result, violations = vfp._validate_critic(draft)
        self.assertEqual(len(result["judgments"]), 3)
        self.assertFalse(any("duplicate" in v for v in violations))


class TestMinValidPredictions(unittest.TestCase):
    """Verify MIN_VALID_PREDICTIONS constant alignment."""

    def test_min_valid_predictions_is_3(self):
        """Must match @failure-predictor Absolute Rule 5."""
        self.assertEqual(vfp.MIN_VALID_PREDICTIONS, 3)


class TestConstants(unittest.TestCase):
    """Verify P1 constants are complete and correct."""

    def test_allowed_severities_complete(self):
        self.assertEqual(vfp.ALLOWED_SEVERITIES, {"Critical", "Warning", "Info"})

    def test_allowed_categories_complete(self):
        self.assertEqual(
            vfp.ALLOWED_CATEGORIES,
            {"F1", "F2", "F3", "F4", "F5", "F6", "F7"},
        )

    def test_allowed_verdicts_complete(self):
        self.assertEqual(
            vfp.ALLOWED_VERDICTS,
            {"CONFIRM", "DISMISS", "ESCALATE"},
        )

    def test_required_prediction_fields(self):
        self.assertEqual(
            vfp.REQUIRED_PREDICTION_FIELDS,
            {"id", "category", "severity", "file", "summary"},
        )


class TestNoSystemSOTReference(unittest.TestCase):
    def test_no_state_yaml_reference(self):
        src = Path(__file__).parent / "validate_failure_predictions.py"
        content = src.read_text(encoding="utf-8")
        self.assertNotIn("state.yaml", content,
                         "validate_failure_predictions.py must not reference system SOT")


if __name__ == "__main__":
    unittest.main()
