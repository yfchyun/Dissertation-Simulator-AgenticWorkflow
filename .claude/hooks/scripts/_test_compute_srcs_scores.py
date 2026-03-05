#!/usr/bin/env python3
"""Tests for compute_srcs_scores.py — Deterministic SRCS axes (CS, VS)."""

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from compute_srcs_scores import (
    compute_citation_score,
    compute_verifiability_score,
    compute_file_scores,
    MAX_CS_SCORE,
    MAX_VS_SCORE,
)


class TestCitationScore(unittest.TestCase):
    """Test CS (Citation Score) computation."""

    def test_zero_claims(self):
        self.assertEqual(compute_citation_score("any content", 0), 0)

    def test_no_citations(self):
        score = compute_citation_score("No citations here", 5)
        self.assertLess(score, MAX_CS_SCORE)

    def test_parenthetical_citations(self):
        content = "(Smith, 2023) (Jones, 2022) (Lee et al., 2021)"
        score = compute_citation_score(content, 2)
        self.assertGreater(score, 0)

    def test_narrative_citations(self):
        content = "Smith (2023) and Jones et al. (2022) found..."
        score = compute_citation_score(content, 2)
        self.assertGreater(score, 0)

    def test_doi_presence_boosts_score(self):
        content_no_doi = "(Smith, 2023)"
        content_with_doi = '(Smith, 2023)\ndoi: 10.1234/test'
        score_no_doi = compute_citation_score(content_no_doi, 1)
        score_with_doi = compute_citation_score(content_with_doi, 1)
        self.assertGreaterEqual(score_with_doi, score_no_doi)

    def test_source_diversity(self):
        content = "type: PRIMARY\ntype: SECONDARY\n(Smith, 2023)"
        score = compute_citation_score(content, 1)
        content_no_div = "(Smith, 2023)"
        score_no_div = compute_citation_score(content_no_div, 1)
        self.assertGreaterEqual(score, score_no_div)

    def test_max_score_cap(self):
        # Even with excessive citations, shouldn't exceed MAX
        content = "\n".join([f"(Author{i}, 2023)" for i in range(100)])
        content += "\n" + "\n".join([f"doi: 10.1234/test{i}" for i in range(100)])
        content += "\ntype: PRIMARY\ntype: SECONDARY"
        score = compute_citation_score(content, 1)
        self.assertLessEqual(score, MAX_CS_SCORE)


class TestVerifiabilityScore(unittest.TestCase):
    """Test VS (Verifiability Score) computation."""

    def test_zero_claims(self):
        self.assertEqual(compute_verifiability_score("any content", 0), 0)

    def test_doi_boosts_score(self):
        content = 'doi: 10.1234/test'
        score = compute_verifiability_score(content, 1)
        self.assertGreater(score, 0)

    def test_url_boosts_score(self):
        content = 'https://example.com/paper'
        score = compute_verifiability_score(content, 1)
        self.assertGreater(score, 0)

    def test_verified_markers(self):
        content = 'verified: true'
        score = compute_verifiability_score(content, 1)
        self.assertGreater(score, 0)

    def test_page_references(self):
        content = 'p. 42\npp. 100-105\nchapter 3'
        score = compute_verifiability_score(content, 1)
        self.assertGreater(score, 0)

    def test_max_score_cap(self):
        content = "\n".join([
            "doi: 10.1234/test",
            "https://example.com",
            "verified: true",
            "p. 42",
        ] * 50)
        score = compute_verifiability_score(content, 1)
        self.assertLessEqual(score, MAX_VS_SCORE)


class TestComputeFileScores(unittest.TestCase):
    """Test file-level scoring."""

    def test_nonexistent_file(self):
        result = compute_file_scores("/nonexistent/file.md")
        self.assertIn("error", result)

    def test_valid_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("""# Test
id: LS-001
id: LS-002
(Smith, 2023)
doi: 10.1234/test
type: PRIMARY
https://example.com
verified: true
""")
            path = f.name
        try:
            result = compute_file_scores(path)
            self.assertNotIn("error", result)
            self.assertEqual(result["claim_count"], 2)
            self.assertIsInstance(result["CS"], int)
            self.assertIsInstance(result["VS"], int)
            self.assertIsNone(result["GS"])
            self.assertIsNone(result["US"])
        finally:
            Path(path).unlink()

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("")
            path = f.name
        try:
            result = compute_file_scores(path)
            self.assertEqual(result["claim_count"], 0)
            self.assertEqual(result["CS"], 0)
            self.assertEqual(result["VS"], 0)
        finally:
            Path(path).unlink()


class TestScoreConstants(unittest.TestCase):
    def test_max_scores(self):
        self.assertEqual(MAX_CS_SCORE, 100)
        self.assertEqual(MAX_VS_SCORE, 100)


class TestNoSystemSOTReference(unittest.TestCase):
    def test_no_state_yaml_reference(self):
        content = (SCRIPT_DIR / "compute_srcs_scores.py").read_text(encoding="utf-8")
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            self.assertNotIn("state.yaml", line, f"Line {i}")
            self.assertNotIn("state.yml", line, f"Line {i}")


if __name__ == "__main__":
    unittest.main()
