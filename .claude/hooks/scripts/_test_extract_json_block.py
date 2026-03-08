#!/usr/bin/env python3
"""Tests for extract_json_block.py — P1 JSON Block Extractor.

Run: python3 -m pytest _test_extract_json_block.py -v
  or: python3 _test_extract_json_block.py
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import extract_json_block as ejb


class TestExtractJsonBlock(unittest.TestCase):
    """Test extract_json_block() — regex-based JSON extraction."""

    def test_basic_extraction(self):
        text = (
            'Here is the analysis:\n\n'
            '```json\n{"predictions": [{"id": "FP-001"}]}\n```\n\n'
            'Done.'
        )
        result = ejb.extract_json_block(text)
        self.assertIsNotNone(result)
        self.assertIn("predictions", result)

    def test_multiline_json(self):
        text = '```json\n{\n  "predictions": [\n    {"id": "FP-001"}\n  ]\n}\n```'
        result = ejb.extract_json_block(text)
        self.assertIsNotNone(result)
        self.assertEqual(len(result["predictions"]), 1)

    def test_no_json_block_returns_none(self):
        text = "This text has no JSON blocks at all."
        result = ejb.extract_json_block(text)
        self.assertIsNone(result)

    def test_invalid_json_in_block_returns_none(self):
        text = '```json\n{invalid json here}\n```'
        result = ejb.extract_json_block(text)
        self.assertIsNone(result)

    def test_multiple_blocks_skips_invalid_takes_first_valid(self):
        text = (
            '```json\n{invalid}\n```\n'
            '```json\n{"valid": true}\n```\n'
            '```json\n{"also_valid": true}\n```'
        )
        result = ejb.extract_json_block(text)
        self.assertIsNotNone(result)
        self.assertEqual(result, {"valid": True})

    def test_json_with_nested_backtick_in_value(self):
        text = '```json\n{"key": "value with `backtick`"}\n```'
        result = ejb.extract_json_block(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["key"], "value with `backtick`")

    def test_empty_text_returns_none(self):
        result = ejb.extract_json_block("")
        self.assertIsNone(result)

    def test_code_block_without_json_label_ignored(self):
        """Only ```json blocks are extracted, not plain ``` blocks."""
        text = '```\n{"not_json_labeled": true}\n```'
        result = ejb.extract_json_block(text)
        self.assertIsNone(result)

    def test_preserves_all_json_types(self):
        text = '```json\n{"str": "a", "num": 42, "bool": true, "null": null, "arr": [1, 2]}\n```'
        result = ejb.extract_json_block(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["str"], "a")
        self.assertEqual(result["num"], 42)
        self.assertEqual(result["bool"], True)
        self.assertIsNone(result["null"])
        self.assertEqual(result["arr"], [1, 2])

    def test_surrounding_text_ignored(self):
        text = (
            "## Analysis\n\n"
            "I found several issues. Here are my predictions:\n\n"
            '```json\n{"predictions": [{"id": "FP-001", "category": "F1"}]}\n```\n\n'
            "Note: These predictions are based on cross-domain analysis.\n"
        )
        result = ejb.extract_json_block(text)
        self.assertIsNotNone(result)
        self.assertEqual(result["predictions"][0]["id"], "FP-001")

    def test_rejects_json_list_not_dict(self):
        """extract_json_block requires a dict, not a list."""
        text = '```json\n[1, 2, 3]\n```'
        result = ejb.extract_json_block(text)
        self.assertIsNone(result)

    def test_realistic_predictor_response(self):
        """Full realistic agent response with analysis text + JSON."""
        text = (
            "## Step 1: Code Map Survey\n\n"
            "I analyzed the code map and found 48 files scanned.\n\n"
            "## Step 2: Deep Dive\n\n"
            "File `restore_context.py` has 15 F1/F3 patterns.\n\n"
            "## Step 5: Predictions\n\n"
            '```json\n'
            '{\n'
            '  "predictions": [\n'
            '    {\n'
            '      "id": "FP-001",\n'
            '      "category": "F1",\n'
            '      "severity": "Critical",\n'
            '      "file": ".claude/hooks/scripts/restore_context.py",\n'
            '      "line": 100,\n'
            '      "summary": "JSONL race condition"\n'
            '    }\n'
            '  ]\n'
            '}\n'
            '```\n\n'
            "These predictions are based on my analysis.\n"
        )
        result = ejb.extract_json_block(text)
        self.assertIsNotNone(result)
        self.assertEqual(len(result["predictions"]), 1)
        self.assertEqual(result["predictions"][0]["id"], "FP-001")
        self.assertEqual(result["predictions"][0]["severity"], "Critical")

    def test_realistic_critic_response(self):
        """Full realistic critic response with judgments + additions."""
        text = (
            "## Verdict Analysis\n\n"
            '```json\n'
            '{\n'
            '  "judgments": [\n'
            '    {"id": "FP-001", "verdict": "CONFIRM", "reason": "Verified"}\n'
            '  ],\n'
            '  "additions": []\n'
            '}\n'
            '```\n'
        )
        result = ejb.extract_json_block(text)
        self.assertIsNotNone(result)
        self.assertEqual(len(result["judgments"]), 1)
        self.assertEqual(result["judgments"][0]["verdict"], "CONFIRM")


class TestCriticFallback(unittest.TestCase):
    """Test CRITIC_FALLBACK constant — deterministic, never LLM-typed."""

    def test_fallback_has_correct_keys(self):
        self.assertIn("judgments", ejb.CRITIC_FALLBACK)
        self.assertIn("additions", ejb.CRITIC_FALLBACK)

    def test_fallback_has_empty_lists(self):
        self.assertEqual(ejb.CRITIC_FALLBACK["judgments"], [])
        self.assertEqual(ejb.CRITIC_FALLBACK["additions"], [])

    def test_fallback_roundtrips_through_json(self):
        serialized = json.dumps(ejb.CRITIC_FALLBACK)
        deserialized = json.loads(serialized)
        self.assertEqual(deserialized, ejb.CRITIC_FALLBACK)

    def test_fallback_key_spelling(self):
        """Prevent British spelling 'judgements' — must be 'judgments'."""
        self.assertIn("judgments", ejb.CRITIC_FALLBACK)
        self.assertNotIn("judgements", ejb.CRITIC_FALLBACK)


class TestWriteOutput(unittest.TestCase):
    """Test _write_output() — file creation with parent directories."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_creates_directories(self):
        path = os.path.join(self.tmpdir, "nested", "dir", "output.json")
        ejb._write_output(path, {"test": True})
        self.assertTrue(os.path.exists(path))

    def test_writes_valid_json(self):
        path = os.path.join(self.tmpdir, "output.json")
        data = {"predictions": [{"id": "FP-001"}]}
        ejb._write_output(path, data)
        with open(path) as f:
            loaded = json.load(f)
        self.assertEqual(loaded, data)

    def test_writes_utf8(self):
        path = os.path.join(self.tmpdir, "output.json")
        data = {"summary": "한국어 테스트"}
        ejb._write_output(path, data)
        with open(path, encoding="utf-8") as f:
            loaded = json.load(f)
        self.assertEqual(loaded["summary"], "한국어 테스트")


class TestStaleOutputDeletion(unittest.TestCase):
    """Test R-1: stale output file is deleted on extraction failure."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_stale_output_deleted_on_failure(self):
        """If output file exists from previous run and extraction fails, delete it."""
        output_path = os.path.join(self.tmpdir, "fp-draft.json")
        # Simulate stale file from previous run
        with open(output_path, "w") as f:
            json.dump({"stale": True}, f)
        self.assertTrue(os.path.exists(output_path))

        # Write input with no JSON block
        input_path = os.path.join(self.tmpdir, "response.txt")
        with open(input_path, "w") as f:
            f.write("No JSON here at all.")

        # Run main() via subprocess to test CLI behavior
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "extract_json_block",
             "--input", input_path, "--output", output_path],
            capture_output=True, text=True,
            cwd=str(Path(__file__).parent),
        )
        # Stale output should be deleted
        self.assertFalse(os.path.exists(output_path),
                         "Stale output file should be deleted on extraction failure")

    def test_no_error_when_no_stale_output(self):
        """Extraction failure with no pre-existing output file should not error."""
        output_path = os.path.join(self.tmpdir, "nonexistent.json")
        input_path = os.path.join(self.tmpdir, "response.txt")
        with open(input_path, "w") as f:
            f.write("No JSON here.")

        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "extract_json_block",
             "--input", input_path, "--output", output_path],
            capture_output=True, text=True,
            cwd=str(Path(__file__).parent),
        )
        self.assertEqual(result.returncode, 0)
        self.assertFalse(os.path.exists(output_path))

    def test_s1_stale_output_deleted_on_input_read_error(self):
        """S-1: Stale output deleted even when input file read fails."""
        output_path = os.path.join(self.tmpdir, "fp-draft.json")
        # Simulate stale file from previous run
        with open(output_path, "w") as f:
            json.dump({"stale": True}, f)
        self.assertTrue(os.path.exists(output_path))

        # Input file does not exist — triggers IOError path
        input_path = os.path.join(self.tmpdir, "does_not_exist.txt")

        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "extract_json_block",
             "--input", input_path, "--output", output_path],
            capture_output=True, text=True,
            cwd=str(Path(__file__).parent),
        )
        self.assertEqual(result.returncode, 0)
        self.assertFalse(os.path.exists(output_path),
                         "S-1: Stale output should be deleted on input read error")


class TestNoSystemSOTReference(unittest.TestCase):
    def test_no_sot_references(self):
        src = Path(__file__).parent / "extract_json_block.py"
        content = src.read_text(encoding="utf-8")
        self.assertNotIn("state.yaml", content)
        self.assertNotIn("session.json", content)


if __name__ == "__main__":
    unittest.main()
