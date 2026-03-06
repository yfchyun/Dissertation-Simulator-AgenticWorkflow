#!/usr/bin/env python3
"""Tests for verify_translation_terms.py — T10-T12 deterministic translation checks.

Run: python3 -m pytest _test_verify_translation_terms.py -v
  or: python3 _test_verify_translation_terms.py
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import verify_translation_terms as vt


class TestT10GlossaryAdherence(unittest.TestCase):
    """T10: Glossary term adherence check."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.glossary_path = str(self.tmpdir / "glossary.yaml")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_glossary(self, entries):
        with open(self.glossary_path, "w", encoding="utf-8") as f:
            for en, ko in entries.items():
                f.write(f'"{en}": "{ko}"\n')

    def test_all_terms_present_passes(self):
        """All glossary terms correctly mapped → PASS."""
        self._write_glossary({"Source of Truth": "진실의 원천", "Agent": "에이전트"})
        en = "The Source of Truth and Agent are critical."
        ko = "진실의 원천과 에이전트는 핵심입니다."
        result = vt.check_glossary_adherence(en, ko, self.glossary_path)
        self.assertTrue(result["passed"])
        self.assertEqual(result["terms_violated"], 0)

    def test_missing_term_fails(self):
        """Glossary term missing from Korean → FAIL."""
        self._write_glossary({"Source of Truth": "진실의 원천", "Agent": "에이전트"})
        en = "The Source of Truth and Agent are critical."
        ko = "진실의 원천은 핵심입니다."  # "에이전트" missing
        result = vt.check_glossary_adherence(en, ko, self.glossary_path)
        self.assertFalse(result["passed"])
        self.assertEqual(result["terms_violated"], 1)
        self.assertEqual(result["violations"][0]["term"], "Agent")

    def test_english_term_kept_passes(self):
        """Terms kept in English (e.g., SOT → SOT) should pass."""
        self._write_glossary({"SOT": "SOT"})
        en = "The SOT is the single source."
        ko = "SOT는 단일 소스입니다."
        result = vt.check_glossary_adherence(en, ko, self.glossary_path)
        self.assertTrue(result["passed"])

    def test_no_glossary_passes(self):
        """Missing glossary file → PASS (graceful)."""
        result = vt.check_glossary_adherence("text", "text", "/nonexistent/g.yaml")
        self.assertTrue(result["passed"])

    def test_term_not_in_source_skipped(self):
        """Glossary terms not in English source should not be checked."""
        self._write_glossary({"Agent": "에이전트", "Workflow": "워크플로우"})
        en = "Only the Agent matters."
        ko = "에이전트만 중요합니다."  # "워크플로우" not needed
        result = vt.check_glossary_adherence(en, ko, self.glossary_path)
        self.assertTrue(result["passed"])
        self.assertEqual(result["terms_checked"], 1)


class TestT11NumberPreservation(unittest.TestCase):
    """T11: Number and statistic preservation check."""

    def test_all_numbers_preserved_passes(self):
        en = "Results show 73.2% accuracy with p < 0.05 and n = 150."
        ko = "결과는 73.2% 정확도를 보였으며, p < 0.05, n = 150이다."
        result = vt.check_number_preservation(en, ko)
        self.assertTrue(result["passed"])

    def test_missing_number_fails(self):
        en = "The sample had n = 250 participants with 89.5% response rate."
        ko = "표본은 참여자 89.5% 응답률을 보였다."  # n=250 missing
        result = vt.check_number_preservation(en, ko)
        self.assertFalse(result["passed"])
        self.assertIn("n=250", result["missing"])

    def test_year_preserved(self):
        en = "Since 2024, the framework has been used."
        ko = "2024년 이후로 프레임워크가 사용되었다."
        result = vt.check_number_preservation(en, ko)
        self.assertTrue(result["passed"])

    def test_comma_numbers_normalized(self):
        en = "The dataset contains 10,000 entries."
        ko = "데이터셋에는 10000개의 항목이 있다."
        result = vt.check_number_preservation(en, ko)
        self.assertTrue(result["passed"])


class TestT12CitationPreservation(unittest.TestCase):
    """T12: Citation reference preservation check."""

    def test_author_year_preserved_passes(self):
        en = "As shown by Searle (1980) and (Chalmers, 2001), consciousness is complex."
        ko = "Searle (1980)과 (Chalmers, 2001)이 보여주듯이, 의식은 복잡하다."
        result = vt.check_citation_preservation(en, ko)
        self.assertTrue(result["passed"])

    def test_missing_citation_fails(self):
        en = "According to (Searle, 1980) and (Chalmers, 2001), the argument holds."
        ko = "Searle (1980)에 따르면, 논증이 성립한다."  # Chalmers, 2001 missing
        result = vt.check_citation_preservation(en, ko)
        self.assertFalse(result["passed"])
        self.assertTrue(any("Chalmers" in m for m in result["missing"]))

    def test_bracketed_references_preserved(self):
        en = "Prior work [1] and [23] support this claim."
        ko = "선행 연구 [1]과 [23]이 이 주장을 뒷받침한다."
        result = vt.check_citation_preservation(en, ko)
        self.assertTrue(result["passed"])

    def test_et_al_citation(self):
        en = "(Smith et al., 2020) found significant results."
        ko = "(Smith et al., 2020)은 유의미한 결과를 발견했다."
        result = vt.check_citation_preservation(en, ko)
        self.assertTrue(result["passed"])


class TestVerifyAll(unittest.TestCase):
    """Integration test for verify_all()."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.en_path = str(self.tmpdir / "step-1.md")
        self.ko_path = str(self.tmpdir / "step-1.ko.md")
        self.glossary_path = str(self.tmpdir / "glossary.yaml")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_full_pass(self):
        """All checks pass → overall passed = True."""
        with open(self.glossary_path, "w") as f:
            f.write('"Agent": "에이전트"\n')
        with open(self.en_path, "w") as f:
            f.write("The Agent scored 95.5% in (Smith, 2020).")
        with open(self.ko_path, "w") as f:
            f.write("에이전트는 (Smith, 2020)에서 95.5%를 기록했다.")

        result = vt.verify_all(self.en_path, self.ko_path, self.glossary_path)
        self.assertTrue(result["passed"])
        self.assertIn("T10: PASS", result["summary"])
        self.assertIn("T11: PASS", result["summary"])
        self.assertIn("T12: PASS", result["summary"])

    def test_missing_en_file_fails(self):
        """Non-existent English file → passed = False with error."""
        result = vt.verify_all("/nonexistent/en.md", self.ko_path)
        self.assertFalse(result["passed"])
        self.assertIn("error", result)

    def test_json_output_format(self):
        """Output should be valid JSON with required keys."""
        with open(self.en_path, "w") as f:
            f.write("Simple text.")
        with open(self.ko_path, "w") as f:
            f.write("간단한 텍스트.")

        result = vt.verify_all(self.en_path, self.ko_path)
        self.assertIn("passed", result)
        self.assertIn("checks", result)
        self.assertIn("summary", result)
        self.assertIn("T10_glossary", result["checks"])
        self.assertIn("T11_numbers", result["checks"])
        self.assertIn("T12_citations", result["checks"])


class TestLoadGlossary(unittest.TestCase):
    """Test glossary YAML loading (stdlib regex parser)."""

    def test_parses_double_quoted(self):
        tmpdir = Path(tempfile.mkdtemp())
        try:
            g = tmpdir / "g.yaml"
            g.write_text('"SOT": "SOT"\n"Agent": "에이전트"\n', encoding="utf-8")
            result = vt._load_glossary(str(g))
            self.assertEqual(result["SOT"], "SOT")
            self.assertEqual(result["Agent"], "에이전트")
        finally:
            shutil.rmtree(tmpdir)

    def test_skips_comments_and_blanks(self):
        tmpdir = Path(tempfile.mkdtemp())
        try:
            g = tmpdir / "g.yaml"
            g.write_text('# Comment\n\n"Key": "Value"\n', encoding="utf-8")
            result = vt._load_glossary(str(g))
            self.assertEqual(len(result), 1)
        finally:
            shutil.rmtree(tmpdir)

    def test_nonexistent_returns_empty(self):
        result = vt._load_glossary("/nonexistent/g.yaml")
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
