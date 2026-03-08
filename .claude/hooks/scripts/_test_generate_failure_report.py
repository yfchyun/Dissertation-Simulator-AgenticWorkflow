#!/usr/bin/env python3
"""Tests for generate_failure_report.py — Phase D Report Generator.

Run: python3 -m pytest _test_generate_failure_report.py -v
  or: python3 _test_generate_failure_report.py
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import generate_failure_report as gfr


# === Shared test fixtures ===

def _make_validated(predictions=None):
    if predictions is None:
        predictions = [
            {
                "id": "FP-001",
                "category": "F1",
                "severity": "Critical",
                "file": ".claude/hooks/scripts/restore_context.py",
                "line": 100,
                "summary": "JSONL race condition on concurrent hooks",
            },
            {
                "id": "FP-002",
                "category": "F3",
                "severity": "Warning",
                "file": ".claude/hooks/scripts/save_context.py",
                "line": 50,
                "summary": "open() without context manager",
            },
            {
                "id": "FP-003",
                "category": "F5",
                "severity": "Info",
                "file": ".claude/agents/reviewer.md",
                "summary": "maxTurns might be insufficient",
            },
        ]
    return {"predictions": predictions}


def _make_critic(judgments=None, additions=None):
    return {
        "judgments": judgments or [],
        "additions": additions or [],
    }


class TestSynthesize(unittest.TestCase):
    """Test _synthesize() — deterministic critic application."""

    def test_confirm_keeps_prediction(self):
        validated = _make_validated()
        critic = _make_critic([
            {"id": "FP-001", "verdict": "CONFIRM", "reason": "Verified"},
        ])
        result = gfr._synthesize(validated, critic)
        ids = {p["id"] for p in result}
        self.assertIn("FP-001", ids)

    def test_dismiss_removes_prediction(self):
        validated = _make_validated()
        critic = _make_critic([
            {"id": "FP-001", "verdict": "DISMISS", "reason": "Safeguard exists"},
        ])
        result = gfr._synthesize(validated, critic)
        ids = {p["id"] for p in result}
        self.assertNotIn("FP-001", ids)

    def test_escalate_promotes_severity(self):
        validated = _make_validated()
        critic = _make_critic([
            {"id": "FP-002", "verdict": "ESCALATE", "reason": "More severe"},
        ])
        result = gfr._synthesize(validated, critic)
        fp002 = next(p for p in result if p["id"] == "FP-002")
        # Warning → Critical
        self.assertEqual(fp002["severity"], "Critical")
        self.assertIn("ESCALATED", fp002.get("_critic_note", ""))

    def test_escalate_info_to_warning(self):
        validated = _make_validated()
        critic = _make_critic([
            {"id": "FP-003", "verdict": "ESCALATE", "reason": "Underrated"},
        ])
        result = gfr._synthesize(validated, critic)
        fp003 = next(p for p in result if p["id"] == "FP-003")
        self.assertEqual(fp003["severity"], "Warning")

    def test_escalate_critical_stays_critical(self):
        validated = _make_validated()
        critic = _make_critic([
            {"id": "FP-001", "verdict": "ESCALATE", "reason": "Already max"},
        ])
        result = gfr._synthesize(validated, critic)
        fp001 = next(p for p in result if p["id"] == "FP-001")
        self.assertEqual(fp001["severity"], "Critical")

    def test_no_judgment_defaults_to_confirm(self):
        """Predictions without a critic judgment are kept (CONFIRM default)."""
        validated = _make_validated()
        critic = _make_critic()  # No judgments
        result = gfr._synthesize(validated, critic)
        self.assertEqual(len(result), 3)

    def test_additions_included(self):
        validated = _make_validated()
        critic = _make_critic(additions=[
            {
                "id": "ADD-001",
                "category": "F6",
                "severity": "Warning",
                "file": "test.py",
                "summary": "Critic found new risk",
            },
        ])
        result = gfr._synthesize(validated, critic)
        ids = {p["id"] for p in result}
        self.assertIn("ADD-001", ids)
        add = next(p for p in result if p["id"] == "ADD-001")
        self.assertTrue(add.get("_critic_added"))

    def test_sorting_critical_first(self):
        validated = _make_validated()
        critic = _make_critic()
        result = gfr._synthesize(validated, critic)
        severities = [p["severity"] for p in result]
        # Critical should come before Warning, which comes before Info
        critical_idx = [i for i, s in enumerate(severities) if s == "Critical"]
        warning_idx = [i for i, s in enumerate(severities) if s == "Warning"]
        info_idx = [i for i, s in enumerate(severities) if s == "Info"]
        if critical_idx and warning_idx:
            self.assertLess(max(critical_idx), min(warning_idx))
        if warning_idx and info_idx:
            self.assertLess(max(warning_idx), min(info_idx))

    def test_confirm_with_reason_adds_critic_note(self):
        validated = _make_validated()
        critic = _make_critic([
            {"id": "FP-001", "verdict": "CONFIRM", "reason": "Detailed analysis"},
        ])
        result = gfr._synthesize(validated, critic)
        fp001 = next(p for p in result if p["id"] == "FP-001")
        self.assertIn("CONFIRMED", fp001.get("_critic_note", ""))


class TestSeverityIcon(unittest.TestCase):
    """Test _severity_icon() — icon string mapping."""

    def test_critical(self):
        self.assertEqual(gfr._severity_icon("Critical"), "[CRITICAL]")

    def test_warning(self):
        self.assertEqual(gfr._severity_icon("Warning"), "[WARNING]")

    def test_info(self):
        self.assertEqual(gfr._severity_icon("Info"), "[INFO]")

    def test_unknown(self):
        self.assertEqual(gfr._severity_icon("Unknown"), "[?]")


class TestSeverityEscalation(unittest.TestCase):
    """Test SEVERITY_ESCALATION constant — deterministic severity promotion."""

    def test_info_to_warning(self):
        self.assertEqual(gfr.SEVERITY_ESCALATION["Info"], "Warning")

    def test_warning_to_critical(self):
        self.assertEqual(gfr.SEVERITY_ESCALATION["Warning"], "Critical")

    def test_critical_stays_critical(self):
        self.assertEqual(gfr.SEVERITY_ESCALATION["Critical"], "Critical")


class TestGenerateMdReport(unittest.TestCase):
    """Test _generate_md_report() — human-readable report structure."""

    def test_report_contains_title(self):
        report = gfr._generate_md_report([], "fp-test", "2026-03-08T00:00:00Z", 0)
        self.assertIn("Predictive Failure Analysis", report)
        self.assertIn("2026-03-08", report)

    def test_report_contains_metadata_table(self):
        report = gfr._generate_md_report([], "fp-test", "2026-03-08T00:00:00Z", 0)
        self.assertIn("Run ID", report)
        self.assertIn("fp-test", report)

    def test_report_empty_predictions_message(self):
        report = gfr._generate_md_report([], "fp-test", "2026-03-08T00:00:00Z", 0)
        self.assertIn("No confirmed failure predictions", report)

    def test_report_with_predictions(self):
        predictions = [
            {
                "id": "FP-001",
                "category": "F1",
                "severity": "Critical",
                "file": "test.py",
                "line": 42,
                "summary": "Race condition detected",
            },
        ]
        report = gfr._generate_md_report(predictions, "fp-test", "2026-03-08T00:00:00Z", 0)
        self.assertIn("FP-001", report)
        self.assertIn("[CRITICAL]", report)
        self.assertIn("Race condition detected", report)
        self.assertIn("test.py", report)
        self.assertIn("line 42", report)

    def test_report_dismissed_count(self):
        report = gfr._generate_md_report([], "fp-test", "2026-03-08T00:00:00Z", 5)
        self.assertIn("5", report)

    def test_report_critic_added_tag(self):
        predictions = [
            {
                "id": "ADD-001",
                "category": "F3",
                "severity": "Warning",
                "file": "test.py",
                "summary": "Added by critic",
                "_critic_added": True,
            },
        ]
        report = gfr._generate_md_report(predictions, "fp-test", "2026-03-08T00:00:00Z", 0)
        self.assertIn("added by @failure-critic", report)

    def test_report_escalated_tag(self):
        predictions = [
            {
                "id": "FP-001",
                "category": "F1",
                "severity": "Critical",
                "file": "test.py",
                "summary": "Escalated risk",
                "_critic_note": "ESCALATED from Warning: more severe than rated",
            },
        ]
        report = gfr._generate_md_report(predictions, "fp-test", "2026-03-08T00:00:00Z", 0)
        self.assertIn("escalated by @failure-critic", report)

    def test_report_p1_attribution(self):
        """Report must state it's P1 deterministic synthesis."""
        report = gfr._generate_md_report([], "fp-test", "2026-03-08T00:00:00Z", 0)
        self.assertIn("P1 deterministic synthesis", report)


class TestGenerateActiveRisks(unittest.TestCase):
    """Test _generate_active_risks() — RLM IMMORTAL surface."""

    def test_immortal_comment(self):
        content = gfr._generate_active_risks([], "fp-test", "2026-03-08T00:00:00Z")
        self.assertIn("IMMORTAL", content)

    def test_run_id_embedded(self):
        content = gfr._generate_active_risks([], "fp-test", "2026-03-08T00:00:00Z")
        self.assertIn("fp-test", content)

    def test_no_risks_message(self):
        content = gfr._generate_active_risks([], "fp-test", "2026-03-08T00:00:00Z")
        self.assertIn("No Critical or Warning", content)

    def test_top_risks_listed(self):
        predictions = [
            {"id": "FP-001", "category": "F1", "severity": "Critical",
             "file": "test.py", "summary": "Race condition"},
            {"id": "FP-002", "category": "F3", "severity": "Warning",
             "file": "other.py", "summary": "Resource leak"},
        ]
        content = gfr._generate_active_risks(predictions, "fp-test", "2026-03-08T00:00:00Z")
        self.assertIn("FP-001", content)
        self.assertIn("[CRITICAL]", content)
        self.assertIn("FP-002", content)
        self.assertIn("[WARNING]", content)

    def test_caps_at_5_top_risks(self):
        predictions = [
            {"id": f"FP-{i:03d}", "category": "F1", "severity": "Critical",
             "file": f"file{i}.py", "summary": f"Risk {i}"}
            for i in range(10)
        ]
        content = gfr._generate_active_risks(predictions, "fp-test", "2026-03-08T00:00:00Z")
        # Should show 5 risks + "... +5 more" line
        self.assertIn("+5 more", content)

    def test_refresh_instruction(self):
        content = gfr._generate_active_risks([], "fp-test", "2026-03-08T00:00:00Z")
        self.assertIn("/predict-failures", content)


class TestAppendIndex(unittest.TestCase):
    """Test _append_index() — SOT append-only JSONL."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.index_path = os.path.join(self.tmpdir, "failure-predictions", "index.jsonl")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_creates_directory_and_file(self):
        entry = {"run_id": "fp-test", "total": 3}
        gfr._append_index(self.index_path, entry)
        self.assertTrue(os.path.exists(self.index_path))

    def test_appends_valid_jsonl(self):
        entry1 = {"run_id": "fp-001", "total": 3}
        entry2 = {"run_id": "fp-002", "total": 5}
        gfr._append_index(self.index_path, entry1)
        gfr._append_index(self.index_path, entry2)

        with open(self.index_path, "r") as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 2)
        # Each line should be valid JSON
        obj1 = json.loads(lines[0])
        obj2 = json.loads(lines[1])
        self.assertEqual(obj1["run_id"], "fp-001")
        self.assertEqual(obj2["run_id"], "fp-002")

    def test_each_line_ends_with_newline(self):
        entry = {"run_id": "fp-test"}
        gfr._append_index(self.index_path, entry)
        with open(self.index_path, "r") as f:
            content = f.read()
        self.assertTrue(content.endswith("\n"))


class TestFilterCriticAdditions(unittest.TestCase):
    """Test _filter_critic_additions() — H-3 file existence check."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Create a file that "exists" in the project
        os.makedirs(os.path.join(self.tmpdir, ".claude", "hooks", "scripts"), exist_ok=True)
        Path(os.path.join(self.tmpdir, ".claude", "hooks", "scripts", "real.py")).write_text("pass")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_keeps_existing_file(self):
        critic = {
            "judgments": [],
            "additions": [
                {"id": "ADD-001", "category": "F3", "severity": "Warning",
                 "file": ".claude/hooks/scripts/real.py", "summary": "Real risk"},
            ],
        }
        gfr._filter_critic_additions(critic, self.tmpdir)
        self.assertEqual(len(critic["additions"]), 1)

    def test_removes_nonexistent_file(self):
        critic = {
            "judgments": [],
            "additions": [
                {"id": "ADD-001", "category": "F3", "severity": "Warning",
                 "file": "fabricated/path/hallucinated.py", "summary": "Fake"},
            ],
        }
        gfr._filter_critic_additions(critic, self.tmpdir)
        self.assertEqual(len(critic["additions"]), 0)

    def test_mixed_real_and_fabricated(self):
        critic = {
            "judgments": [],
            "additions": [
                {"id": "ADD-001", "category": "F3", "severity": "Warning",
                 "file": ".claude/hooks/scripts/real.py", "summary": "Real"},
                {"id": "ADD-002", "category": "F1", "severity": "Critical",
                 "file": "does/not/exist.py", "summary": "Fake"},
            ],
        }
        gfr._filter_critic_additions(critic, self.tmpdir)
        self.assertEqual(len(critic["additions"]), 1)
        self.assertEqual(critic["additions"][0]["id"], "ADD-001")

    def test_empty_additions_no_error(self):
        critic = {"judgments": [], "additions": []}
        gfr._filter_critic_additions(critic, self.tmpdir)
        self.assertEqual(len(critic["additions"]), 0)

    def test_no_additions_key_no_error(self):
        critic = {"judgments": []}
        gfr._filter_critic_additions(critic, self.tmpdir)

    def test_modifies_critic_in_place(self):
        """_filter_critic_additions modifies the dict in-place."""
        original_additions = [
            {"id": "ADD-001", "category": "F3", "severity": "Warning",
             "file": "nonexistent.py", "summary": "Fake"},
        ]
        critic = {"judgments": [], "additions": original_additions}
        gfr._filter_critic_additions(critic, self.tmpdir)
        self.assertEqual(len(critic["additions"]), 0)


class TestCategoryNames(unittest.TestCase):
    """Test CATEGORY_NAMES constant completeness."""

    def test_all_f1_f7_covered(self):
        for cat in ("F1", "F2", "F3", "F4", "F5", "F6", "F7"):
            self.assertIn(cat, gfr.CATEGORY_NAMES,
                          f"Category {cat} missing from CATEGORY_NAMES")


class TestSeverityOrder(unittest.TestCase):
    """Test SEVERITY_ORDER constant — Critical first sorting."""

    def test_critical_lowest_order(self):
        self.assertEqual(gfr.SEVERITY_ORDER["Critical"], 0)

    def test_warning_middle(self):
        self.assertEqual(gfr.SEVERITY_ORDER["Warning"], 1)

    def test_info_highest_order(self):
        self.assertEqual(gfr.SEVERITY_ORDER["Info"], 2)


class TestNoSystemSOTReference(unittest.TestCase):
    def test_no_state_yaml_reference(self):
        src = Path(__file__).parent / "generate_failure_report.py"
        content = src.read_text(encoding="utf-8")
        self.assertNotIn("state.yaml", content,
                         "generate_failure_report.py must not reference system SOT")


if __name__ == "__main__":
    unittest.main()
