#!/usr/bin/env python3
"""Tests for validate_task_completion.py — L0 Anti-Skip Guard."""

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from validate_task_completion import validate_output, DEFAULT_MIN_SIZE


class TestValidateOutput(unittest.TestCase):
    """Test output file validation."""

    def test_nonexistent_file(self):
        result = validate_output("/nonexistent/path/file.md")
        self.assertFalse(result["passed"])
        self.assertFalse(result["exists"])
        self.assertEqual(len(result["errors"]), 1)

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("")
            path = f.name
        try:
            result = validate_output(path)
            self.assertFalse(result["passed"])
            self.assertFalse(result["non_empty"])
        finally:
            Path(path).unlink()

    def test_whitespace_only_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("   \n\n  \t  \n")
            path = f.name
        try:
            result = validate_output(path)
            self.assertFalse(result["passed"])
            self.assertFalse(result["non_empty"])
        finally:
            Path(path).unlink()

    def test_too_small_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("short")
            path = f.name
        try:
            result = validate_output(path)
            self.assertFalse(result["passed"])
            self.assertFalse(result["meets_min_size"])
        finally:
            Path(path).unlink()

    def test_valid_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Valid Output\n\n" + "Content " * 50)
            path = f.name
        try:
            result = validate_output(path)
            self.assertTrue(result["passed"])
            self.assertTrue(result["exists"])
            self.assertTrue(result["non_empty"])
            self.assertTrue(result["meets_min_size"])
            self.assertEqual(len(result["errors"]), 0)
        finally:
            Path(path).unlink()

    def test_custom_min_size(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("Small content")
            path = f.name
        try:
            result = validate_output(path, min_size=10)
            self.assertTrue(result["passed"])
        finally:
            Path(path).unlink()

    def test_exact_min_size(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            content = "x" * DEFAULT_MIN_SIZE
            f.write(content)
            path = f.name
        try:
            result = validate_output(path)
            self.assertTrue(result["passed"])
            self.assertTrue(result["meets_min_size"])
        finally:
            Path(path).unlink()

    def test_size_field_accurate(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Test\n" + "x" * 200)
            path = f.name
        try:
            result = validate_output(path)
            expected_size = Path(path).stat().st_size
            self.assertEqual(result["size"], expected_size)
        finally:
            Path(path).unlink()


class TestDefaultMinSize(unittest.TestCase):
    def test_default_is_100(self):
        self.assertEqual(DEFAULT_MIN_SIZE, 100)


class TestNoSystemSOTReference(unittest.TestCase):
    def test_no_state_yaml_reference(self):
        content = (SCRIPT_DIR / "validate_task_completion.py").read_text(encoding="utf-8")
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            self.assertNotIn("state.yaml", line, f"Line {i}")
            self.assertNotIn("state.yml", line, f"Line {i}")


if __name__ == "__main__":
    unittest.main()
