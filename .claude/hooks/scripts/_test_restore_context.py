#!/usr/bin/env python3
"""Tests for restore_context.py — SessionStart recovery + Active Knowledge Retrieval.

Run: python3 -m pytest _test_restore_context.py -v
  or: python3 _test_restore_context.py
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import restore_context as rc


class TestRetrieveRelevantSessions(unittest.TestCase):
    """Test P0-RLM: Active Knowledge Retrieval scoring."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.ki_path = str(self.tmpdir / "knowledge-index.jsonl")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_ki(self, entries):
        with open(self.ki_path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def test_empty_ki_returns_empty(self):
        result = rc._retrieve_relevant_sessions(self.ki_path, "test task", [])
        self.assertEqual(result, [])

    def test_nonexistent_ki_returns_empty(self):
        result = rc._retrieve_relevant_sessions("/nonexistent/path.jsonl", "task", [])
        self.assertEqual(result, [])

    def test_keyword_matching(self):
        """Sessions with overlapping task keywords should score higher."""
        self._write_ki([
            {"session_id": "aaa", "user_task": "implement hook scripts validation", "modified_files": [], "tags": []},
            {"session_id": "bbb", "user_task": "write documentation for API", "modified_files": [], "tags": []},
            {"session_id": "ccc", "user_task": "fix hook scripts error handling", "modified_files": [], "tags": []},
        ])
        result = rc._retrieve_relevant_sessions(self.ki_path, "hook scripts testing", [])
        self.assertTrue(len(result) > 0)
        # Sessions with "hook" and "scripts" should rank higher
        top_session_id = result[0][1]["session_id"]
        self.assertIn(top_session_id, ["aaa", "ccc"])

    def test_file_path_matching(self):
        """Sessions with matching modified files should score high."""
        self._write_ki([
            {"session_id": "aaa", "user_task": "unrelated task", "modified_files": ["/path/to/restore_context.py"], "tags": []},
            {"session_id": "bbb", "user_task": "another task", "modified_files": ["/path/to/other.py"], "tags": []},
        ])
        result = rc._retrieve_relevant_sessions(
            self.ki_path, "some task", ["/path/to/restore_context.py"]
        )
        self.assertTrue(len(result) > 0)
        self.assertEqual(result[0][1]["session_id"], "aaa")

    def test_tag_matching(self):
        """Sessions with matching tags should get bonus score."""
        self._write_ki([
            {"session_id": "aaa", "user_task": "work on hooks", "modified_files": [], "tags": ["hooks", "context"]},
            {"session_id": "bbb", "user_task": "work on docs", "modified_files": [], "tags": ["docs", "readme"]},
        ])
        result = rc._retrieve_relevant_sessions(
            self.ki_path, "context preservation hooks",
            ["/project/.claude/hooks/scripts/save_context.py"]
        )
        self.assertTrue(len(result) > 0)
        # "aaa" has tag "hooks" which should match path tag extraction
        top_id = result[0][1]["session_id"]
        self.assertEqual(top_id, "aaa")

    def test_max_results_limit(self):
        """Should return at most max_results entries."""
        entries = [
            {"session_id": f"s{i}", "user_task": "hook script work", "modified_files": [], "tags": []}
            for i in range(20)
        ]
        self._write_ki(entries)
        result = rc._retrieve_relevant_sessions(self.ki_path, "hook script", [], max_results=3)
        self.assertLessEqual(len(result), 3)

    def test_zero_score_sessions_excluded(self):
        """Sessions with no relevance should not appear."""
        self._write_ki([
            {"session_id": "aaa", "user_task": "xyz abc def", "modified_files": ["/foo/bar.py"], "tags": ["unrelated"]},
        ])
        result = rc._retrieve_relevant_sessions(self.ki_path, "hook scripts", ["/other/path.py"])
        self.assertEqual(len(result), 0)

    def test_error_patterns_bonus(self):
        """Sessions with error patterns get a small bonus."""
        self._write_ki([
            {"session_id": "aaa", "user_task": "hook work", "modified_files": [], "tags": [],
             "error_patterns": [{"type": "syntax", "tool": "Edit"}]},
            {"session_id": "bbb", "user_task": "hook work", "modified_files": [], "tags": [],
             "error_patterns": []},
        ])
        result = rc._retrieve_relevant_sessions(self.ki_path, "hook work", [])
        self.assertTrue(len(result) >= 2)
        # "aaa" should score higher due to error_patterns bonus
        self.assertEqual(result[0][1]["session_id"], "aaa")


class TestParseSnapshotSections(unittest.TestCase):
    """Test P1-RLM: Selective Peek — section boundary parsing."""

    def test_parses_marked_snapshot(self):
        md = (
            "<!-- SECTION:header -->\n"
            "# Context Recovery — Session abc123\n"
            "> Saved: 2026-03-06\n"
            "\n"
            "<!-- SECTION:task -->\n"
            "## Current Task\n"
            "Implement RLM features\n"
            "\n"
            "<!-- SECTION:sot -->\n"
            "## SOT State\n"
            "state.yaml content\n"
        )
        sections = rc.parse_snapshot_sections(md)
        self.assertIn("header", sections)
        self.assertIn("task", sections)
        self.assertIn("sot", sections)
        self.assertIn("Context Recovery", sections["header"])
        self.assertIn("Implement RLM", sections["task"])

    def test_unmarked_snapshot_returns_full(self):
        """Pre-P1 snapshots without markers return _full key."""
        md = "# Context Recovery\nSome content\n"
        sections = rc.parse_snapshot_sections(md)
        self.assertIn("_full", sections)
        self.assertEqual(sections["_full"], md)

    def test_empty_sections_handled(self):
        md = (
            "<!-- SECTION:header -->\n"
            "<!-- SECTION:task -->\n"
            "## Task content\n"
        )
        sections = rc.parse_snapshot_sections(md)
        self.assertIn("header", sections)
        self.assertEqual(sections["header"].strip(), "")
        self.assertIn("task", sections)

    def test_immortal_sections_constant(self):
        """IMMORTAL_SECTIONS should contain all critical section keys."""
        from _context_lib import SNAPSHOT_SECTION_MARKERS
        # All immortal sections must exist in the marker dict
        for key in rc.IMMORTAL_SECTIONS:
            self.assertIn(key, SNAPSHOT_SECTION_MARKERS,
                          f"IMMORTAL section '{key}' missing from SNAPSHOT_SECTION_MARKERS")

    def test_marker_constant_sync(self):
        """SNAPSHOT_SECTION_MARKERS values must match the format used in parsing."""
        from _context_lib import SNAPSHOT_SECTION_MARKERS
        import re
        pattern = re.compile(r'<!-- SECTION:(\w+) -->')
        for key, marker in SNAPSHOT_SECTION_MARKERS.items():
            match = pattern.match(marker)
            self.assertIsNotNone(match, f"Marker '{marker}' doesn't match expected format")
            self.assertEqual(match.group(1), key,
                             f"Marker key mismatch: dict key='{key}', marker name='{match.group(1)}'")


class TestSelectivePeekIntegration(unittest.TestCase):
    """Test P1-RLM: Selective Peek integration in _extract_brief_summary."""

    def test_section_based_extraction(self):
        """P1 snapshots with markers should use section-based extraction."""
        md = (
            "<!-- SECTION:header -->\n"
            "# Context Recovery — Session test123\n"
            "> Saved: 2026-03-06 | Trigger: stop\n"
            "\n"
            "<!-- SECTION:task -->\n"
            "## 현재 작업 (Current Task)\n"
            "<!-- IMMORTAL: 사용자 작업 지시 -->\n"
            "Implement RLM features for memory system\n"
            "\n"
            "**최근 지시 (Latest Instruction):** Fix the consolidation bug\n"
            "\n"
            "<!-- SECTION:completion -->\n"
            "## 결정론적 완료 상태 (Deterministic Completion State)\n"
            "### 도구 호출 결과\n"
            "- Edit: 5회 호출 → 5 성공, 0 실패\n"
            "\n"
            "<!-- SECTION:modified_files -->\n"
            "## 수정된 파일 (Modified Files)\n"
            "### `/path/to/restore_context.py` (Edit, 3회 수정)\n"
            "\n"
            "<!-- SECTION:statistics -->\n"
            "## 대화 통계\n"
            "- 총 메시지: 10개\n"
            "- 도구 사용: 15회\n"
        )
        summary = rc._extract_brief_summary(md)
        labels = [l for l, _ in summary]

        # Should extract task
        self.assertIn("현재 작업", labels)
        task_content = next(c for l, c in summary if l == "현재 작업")
        self.assertIn("Implement RLM", task_content)

        # Should extract latest instruction
        self.assertIn("최근 지시", labels)

        # Should extract completion state
        self.assertIn("완료상태", labels)

        # Should extract file paths
        self.assertIn("수정_파일_경로", labels)

        # Should extract statistics
        self.assertIn("통계", labels)

    def test_legacy_fallback(self):
        """Pre-P1 snapshots without markers should use legacy extraction."""
        md = (
            "# Context Recovery — Session test123\n"
            "\n"
            "## 현재 작업 (Current Task)\n"
            "Legacy task description\n"
            "\n"
            "## 대화 통계\n"
            "- 총 메시지: 5개\n"
        )
        summary = rc._extract_brief_summary(md)
        labels = [l for l, _ in summary]
        self.assertIn("현재 작업", labels)
        self.assertIn("통계", labels)


class TestOrphanMarkerRemoval(unittest.TestCase):
    """Test Phase 2 fix: _remove_section() cleans up SECTION markers."""

    def test_remove_section_drops_preceding_marker(self):
        """When a section is removed, its preceding SECTION marker should also be removed."""
        from _context_lib import _remove_section
        sections = [
            "## Some Section",
            "content line",
            "",
            "<!-- SECTION:statistics -->",
            "## 대화 통계",
            "- 총 메시지: 10개",
            "",
            "<!-- SECTION:commands -->",
            "## 실행된 명령 (Commands Executed)",
            "- `git status`",
        ]
        result = _remove_section(sections, "## 대화 통계")
        result_text = "\n".join(result)

        # Statistics section and its marker should be gone
        self.assertNotIn("대화 통계", result_text)
        self.assertNotIn("SECTION:statistics", result_text)

        # Commands section should remain
        self.assertIn("실행된 명령", result_text)
        self.assertIn("SECTION:commands", result_text)


class TestBuildRecoveryOutput(unittest.TestCase):
    """Test _build_recovery_output includes active retrieval block."""

    def test_active_retrieval_block_present(self):
        """When relevant sessions exist, ACTIVE RETRIEVAL block should appear."""
        tmpdir = Path(tempfile.mkdtemp())
        try:
            # Place ki at the path get_snapshot_dir() expects
            snapshot_dir = tmpdir / ".claude" / "context-snapshots"
            snapshot_dir.mkdir(parents=True)
            ki_path = snapshot_dir / "knowledge-index.jsonl"
            with open(ki_path, "w") as f:
                f.write(json.dumps({
                    "session_id": "test123",
                    "user_task": "hook scripts work",
                    "modified_files": ["/path/restore_context.py"],
                    "tags": ["hooks"],
                    "timestamp": "2026-03-06T12:00:00",
                }) + "\n")

            summary = [
                ("현재 작업", "hook scripts enhancement"),
                ("수정_파일_경로", "/path/restore_context.py"),
            ]

            output = rc._build_recovery_output(
                source="compact",
                latest_path=str(snapshot_dir / "latest.md"),
                summary=summary,
                sot_warning=None,
                snapshot_age=60,
                project_dir=str(tmpdir),
            )

            self.assertIn("ACTIVE RETRIEVAL", output)
            self.assertIn("test123", output)
        finally:
            shutil.rmtree(tmpdir)


class TestExtractRecentErrorResolutions(unittest.TestCase):
    """Test P1-1: Error resolution extraction."""

    def test_extracts_resolved_errors(self):
        sessions = [{
            "error_patterns": [{
                "type": "syntax",
                "tool": "Edit",
                "file": "foo.py",
                "resolution": {"tool": "Edit", "file": "foo.py"},
            }]
        }]
        result = rc._extract_recent_error_resolutions(sessions)
        self.assertEqual(len(result), 1)
        self.assertIn("syntax", result[0])

    def test_empty_sessions(self):
        result = rc._extract_recent_error_resolutions([])
        self.assertEqual(result, [])

    def test_max_three_results(self):
        sessions = [{
            "error_patterns": [
                {"type": f"err{i}", "tool": "Bash", "file": f"f{i}.py",
                 "resolution": {"tool": "Edit", "file": f"f{i}.py"}}
                for i in range(10)
            ]
        }]
        result = rc._extract_recent_error_resolutions(sessions)
        self.assertLessEqual(len(result), 3)


class TestExtractQuarterlyInsights(unittest.TestCase):
    """Test P3-RLM: Quarterly archive active consumption."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.qa_path = str(self.tmpdir / "knowledge-archive-quarterly.jsonl")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_qa(self, entries):
        with open(self.qa_path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def test_empty_file_returns_empty(self):
        result = rc._extract_quarterly_insights(self.qa_path)
        self.assertEqual(result, [])

    def test_nonexistent_returns_empty(self):
        result = rc._extract_quarterly_insights("/nonexistent/path.jsonl")
        self.assertEqual(result, [])

    def test_extracts_error_patterns(self):
        self._write_qa([{
            "quarter": "2026-Q1",
            "session_count": 15,
            "error_patterns_aggregated": {"syntax": 10, "type_error": 5},
            "design_decisions": [],
            "top_modified_files": {},
        }])
        result = rc._extract_quarterly_insights(self.qa_path)
        self.assertTrue(any("syntax" in r for r in result))

    def test_extracts_top_files(self):
        self._write_qa([{
            "quarter": "2026-Q1",
            "session_count": 10,
            "error_patterns_aggregated": {},
            "design_decisions": [],
            "top_modified_files": {"/path/to/important.py": 25},
        }])
        result = rc._extract_quarterly_insights(self.qa_path)
        self.assertTrue(any("important.py" in r for r in result))

    def test_extracts_design_decision_count(self):
        self._write_qa([{
            "quarter": "2026-Q1",
            "session_count": 10,
            "error_patterns_aggregated": {},
            "design_decisions": ["Decision A", "Decision B"],
            "top_modified_files": {},
        }])
        result = rc._extract_quarterly_insights(self.qa_path)
        self.assertTrue(any("설계 결정" in r for r in result))

    def test_aggregates_across_quarters(self):
        self._write_qa([
            {
                "quarter": "2025-Q4",
                "session_count": 5,
                "error_patterns_aggregated": {"syntax": 3},
                "design_decisions": ["D1"],
                "top_modified_files": {},
            },
            {
                "quarter": "2026-Q1",
                "session_count": 10,
                "error_patterns_aggregated": {"syntax": 7},
                "design_decisions": ["D2"],
                "top_modified_files": {},
            },
        ])
        result = rc._extract_quarterly_insights(self.qa_path)
        # Should show aggregated count of 10 syntax errors
        self.assertTrue(any("syntax(10)" in r for r in result))


if __name__ == "__main__":
    unittest.main()
