#!/usr/bin/env python3
"""Tests for scan_code_structure.py — Phase A Code Structure Scanner.

Run: python3 -m pytest _test_scan_code_structure.py -v
  or: python3 _test_scan_code_structure.py
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import scan_code_structure as scs


class TestShouldExclude(unittest.TestCase):
    """Test _should_exclude() — file exclusion logic."""

    def test_excludes_test_files(self):
        self.assertTrue(scs._should_exclude("_test_something.py"))

    def test_excludes_context_guard(self):
        self.assertTrue(scs._should_exclude("context_guard.py"))

    def test_allows_production_files(self):
        self.assertFalse(scs._should_exclude("validate_review.py"))

    def test_allows_non_test_underscore_files(self):
        self.assertFalse(scs._should_exclude("_context_lib.py"))

    def test_allows_md_files(self):
        self.assertFalse(scs._should_exclude("reviewer.md"))


class TestExtractPythonSymbols(unittest.TestCase):
    """Test _extract_python_symbols() — function/class name extraction."""

    def test_extracts_functions(self):
        content = "def foo():\n    pass\n\ndef bar():\n    pass\n"
        symbols = scs._extract_python_symbols(content)
        self.assertEqual(symbols, ["foo", "bar"])

    def test_extracts_classes(self):
        content = "class MyClass:\n    pass\n\nclass AnotherClass:\n    pass\n"
        symbols = scs._extract_python_symbols(content)
        self.assertEqual(symbols, ["MyClass", "AnotherClass"])

    def test_mixed_functions_and_classes(self):
        content = "class Foo:\n    pass\n\ndef bar():\n    pass\n"
        symbols = scs._extract_python_symbols(content)
        self.assertEqual(symbols, ["Foo", "bar"])

    def test_skips_nested_defs(self):
        # Only top-level (^) matches — indented defs are skipped
        content = "def outer():\n    def inner():\n        pass\n"
        symbols = scs._extract_python_symbols(content)
        self.assertEqual(symbols, ["outer"])

    def test_empty_content(self):
        symbols = scs._extract_python_symbols("")
        self.assertEqual(symbols, [])

    def test_caps_at_60(self):
        content = "\n".join(f"def func_{i}():\n    pass" for i in range(80))
        symbols = scs._extract_python_symbols(content)
        self.assertLessEqual(len(symbols), 60)


class TestScanFile(unittest.TestCase):
    """Test _scan_file() — single file F1-F7 pattern scanning."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_file(self, name, content, ext=".py"):
        path = os.path.join(self.tmpdir, name + ext)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_basic_structure(self):
        path = self._write_file("test", "x = 1\ny = 2\n")
        result = scs._scan_file(path, self.tmpdir)
        self.assertIn("path", result)
        self.assertEqual(result["extension"], ".py")
        self.assertEqual(result["line_count"], 2)
        self.assertIsInstance(result["symbols"], list)
        self.assertIsInstance(result["pattern_matches"], dict)

    def test_f1_concurrency_append_mode(self):
        """F1-01: open() with append mode detected."""
        path = self._write_file("test", "with open('log.jsonl', 'a') as f:\n    pass\n")
        result = scs._scan_file(path, self.tmpdir)
        matches = result["pattern_matches"].get("F1_concurrency", [])
        f1_01_matches = [m for m in matches if m["pattern_id"] == "F1-01"]
        self.assertGreaterEqual(len(f1_01_matches), 1)
        self.assertEqual(f1_01_matches[0]["severity_hint"], "Critical")

    def test_f1_json_dump(self):
        """F1-02: json.dump() without atomic_write detected."""
        path = self._write_file("test", "import json\njson.dump(data, f)\n")
        result = scs._scan_file(path, self.tmpdir)
        matches = result["pattern_matches"].get("F1_concurrency", [])
        f1_02_matches = [m for m in matches if m["pattern_id"] == "F1-02"]
        self.assertGreaterEqual(len(f1_02_matches), 1)

    def test_f3_open_call(self):
        """F3-01: open() call detected (fixed regex — no variable-width lookbehind)."""
        path = self._write_file("test", "f = open('data.txt', 'r')\n")
        result = scs._scan_file(path, self.tmpdir)
        matches = result["pattern_matches"].get("F3_resource_leak", [])
        f3_01_matches = [m for m in matches if m["pattern_id"] == "F3-01"]
        self.assertGreaterEqual(len(f3_01_matches), 1,
                                "F3-01 must detect open() calls after regex fix")

    def test_f6_blocking_exit(self):
        """F6-01: sys.exit(2) detected as blocking hook."""
        path = self._write_file("test", "import sys\nsys.exit(2)\n")
        result = scs._scan_file(path, self.tmpdir)
        matches = result["pattern_matches"].get("F6_hook_system", [])
        f6_01_matches = [m for m in matches if m["pattern_id"] == "F6-01"]
        self.assertGreaterEqual(len(f6_01_matches), 1)

    def test_md_files_only_get_f5(self):
        """Markdown files should only be scanned for F5 patterns, not F1-F4/F6/F7."""
        content = (
            "# Agent\n"
            "open('file.txt', 'a')\n"       # Would match F1 in .py
            "json.dump(data, f)\n"           # Would match F1 in .py
            "sys.exit(2)\n"                  # Would match F6 in .py
            "maxTurns: 30\n"                 # Should match F5 in .md
        )
        path = self._write_file("test", content, ext=".md")
        result = scs._scan_file(path, self.tmpdir)
        pm = result["pattern_matches"]
        # F5 should be present
        self.assertIn("F5_llm_specific", pm)
        # F1, F6 should NOT be present
        self.assertNotIn("F1_concurrency", pm)
        self.assertNotIn("F6_hook_system", pm)

    def test_line_numbers_are_accurate(self):
        """Pattern match line numbers should correspond to actual code lines."""
        content = "line1\nline2\njson.dump(data, f)\nline4\n"
        path = self._write_file("test", content)
        result = scs._scan_file(path, self.tmpdir)
        matches = result["pattern_matches"].get("F1_concurrency", [])
        json_dump_matches = [m for m in matches if m["pattern_id"] == "F1-02"]
        self.assertGreaterEqual(len(json_dump_matches), 1)
        self.assertEqual(json_dump_matches[0]["line"], 3)

    def test_snippet_truncation(self):
        """Snippets should be truncated to 120 characters."""
        long_line = "json.dump(" + "x" * 200 + ")\n"
        path = self._write_file("test", long_line)
        result = scs._scan_file(path, self.tmpdir)
        for cat_matches in result["pattern_matches"].values():
            for m in cat_matches:
                self.assertLessEqual(len(m["snippet"]), 120)

    def test_nonexistent_file_returns_error(self):
        result = scs._scan_file("/nonexistent/file.py", self.tmpdir)
        self.assertIn("error", result)

    def test_symbol_extraction_in_scan(self):
        content = "def my_func():\n    pass\n\nclass MyClass:\n    pass\n"
        path = self._write_file("test", content)
        result = scs._scan_file(path, self.tmpdir)
        self.assertIn("my_func", result["symbols"])
        self.assertIn("MyClass", result["symbols"])


class TestCollectFiles(unittest.TestCase):
    """Test _collect_files() — file collection from SCAN_TARGETS."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Create scan target directories
        for target in scs.SCAN_TARGETS:
            os.makedirs(os.path.join(self.tmpdir, target), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_collects_py_files(self):
        scripts_dir = os.path.join(self.tmpdir, ".claude", "hooks", "scripts")
        Path(os.path.join(scripts_dir, "validate_review.py")).write_text("pass")
        files = scs._collect_files(self.tmpdir)
        basenames = [os.path.basename(f) for f in files]
        self.assertIn("validate_review.py", basenames)

    def test_collects_md_files(self):
        agents_dir = os.path.join(self.tmpdir, ".claude", "agents")
        Path(os.path.join(agents_dir, "reviewer.md")).write_text("# Reviewer")
        files = scs._collect_files(self.tmpdir)
        basenames = [os.path.basename(f) for f in files]
        self.assertIn("reviewer.md", basenames)

    def test_excludes_test_files(self):
        scripts_dir = os.path.join(self.tmpdir, ".claude", "hooks", "scripts")
        Path(os.path.join(scripts_dir, "_test_review.py")).write_text("pass")
        Path(os.path.join(scripts_dir, "validate_review.py")).write_text("pass")
        files = scs._collect_files(self.tmpdir)
        basenames = [os.path.basename(f) for f in files]
        self.assertNotIn("_test_review.py", basenames)
        self.assertIn("validate_review.py", basenames)

    def test_excludes_non_scan_extensions(self):
        scripts_dir = os.path.join(self.tmpdir, ".claude", "hooks", "scripts")
        Path(os.path.join(scripts_dir, "data.json")).write_text("{}")
        files = scs._collect_files(self.tmpdir)
        basenames = [os.path.basename(f) for f in files]
        self.assertNotIn("data.json", basenames)

    def test_missing_target_dir_skipped(self):
        """If a SCAN_TARGET directory doesn't exist, it's silently skipped."""
        empty_dir = tempfile.mkdtemp()
        try:
            files = scs._collect_files(empty_dir)
            self.assertEqual(files, [])
        finally:
            shutil.rmtree(empty_dir)


class TestBuildCategorySummary(unittest.TestCase):
    """Test _build_category_summary() — per-category match aggregation."""

    def test_aggregates_across_files(self):
        results = [
            {"pattern_matches": {"F1_concurrency": [{"id": "F1-01"}]}},
            {"pattern_matches": {"F1_concurrency": [{"id": "F1-02"}], "F3_resource_leak": [{"id": "F3-01"}]}},
        ]
        summary = scs._build_category_summary(results)
        self.assertEqual(summary["F1_concurrency"], 2)
        self.assertEqual(summary["F3_resource_leak"], 1)

    def test_empty_results(self):
        summary = scs._build_category_summary([])
        self.assertEqual(summary, {})

    def test_no_matches(self):
        results = [{"pattern_matches": {}}]
        summary = scs._build_category_summary(results)
        self.assertEqual(summary, {})


class TestNoSystemSOTReference(unittest.TestCase):
    """Ensure scan_code_structure.py does not import or open system SOT files.

    Note: state.yaml and session.json appear in F2_state_drift FAILURE_PATTERNS
    as detection regexes — that's intentional (scanning for SOT bypass patterns
    in other files). We check that no open/read calls reference SOT files.
    """

    def test_no_sot_open_calls(self):
        """No open() calls targeting SOT files (only regex pattern strings allowed)."""
        import re as re_mod
        src = Path(__file__).parent / "scan_code_structure.py"
        content = src.read_text(encoding="utf-8")
        # Match open("state.yaml"...) or open("session.json"...) patterns
        sot_open = re_mod.findall(
            r'open\s*\([^)]*(?:state\.yaml|session\.json)', content
        )
        self.assertEqual(sot_open, [],
                         "scan_code_structure.py must not open SOT files")


class TestAllF1F7PatternsCompile(unittest.TestCase):
    """Verify all F1-F7 regex patterns compile without errors (regression guard)."""

    def test_all_patterns_compile(self):
        import re
        for category, patterns in scs.FAILURE_PATTERNS.items():
            for pdef in patterns:
                try:
                    re.compile(pdef["regex"])
                except re.error as e:
                    self.fail(
                        f"Pattern {pdef['id']} ({category}) failed to compile: {e}"
                    )

    def test_all_patterns_have_required_fields(self):
        for category, patterns in scs.FAILURE_PATTERNS.items():
            for pdef in patterns:
                self.assertIn("id", pdef, f"Missing 'id' in {category}")
                self.assertIn("desc", pdef, f"Missing 'desc' in {category}")
                self.assertIn("regex", pdef, f"Missing 'regex' in {category}")
                self.assertIn("severity", pdef, f"Missing 'severity' in {category}")
                self.assertIn(
                    pdef["severity"], {"Critical", "Warning", "Info"},
                    f"Invalid severity '{pdef['severity']}' in {pdef['id']}"
                )


if __name__ == "__main__":
    unittest.main()
