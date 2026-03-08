#!/usr/bin/env python3
"""Tests for validate_claim_inheritance.py — Claim Inheritance validation (CI1-CI4).

Run: python3 -m pytest _test_validate_claim_inheritance.py -v
  or: python3 _test_validate_claim_inheritance.py
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import validate_claim_inheritance as ci


class TestClaimInheritanceBase(unittest.TestCase):
    """Base class with helper methods for claim inheritance tests."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.dlg_dir = self.tmpdir / "dialogue-logs"
        self.dlg_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_fc(self, step, round_num, content):
        path = self.dlg_dir / f"step-{step}-r{round_num}-fc.md"
        path.write_text(content, encoding="utf-8")
        return path

    def _write_draft(self, step, round_num, content):
        path = self.dlg_dir / f"step-{step}-draft-r{round_num}.md"
        path.write_text(content, encoding="utf-8")
        return path

    def _make_fc_content(self, claims):
        """Build a fact-check report with a claim verification table.

        claims: list of (claim_text, location, verdict, source, notes)
        """
        rows = "\n".join(
            f"| {i+1} | {c[0]} | {c[1]} | {c[2]} | {c[3]} | {c[4]} |"
            for i, c in enumerate(claims)
        )
        return (
            "# Fact-Check Report\n\n"
            "## Claim Verification Table\n\n"
            "| # | Claim (verbatim or paraphrased) | Location | Verdict | Source | Notes |\n"
            "|---|-------------------------------|----------|---------|--------|-------|\n"
            f"{rows}\n\n"
            "## Verdict: PASS\n"
        )


class TestDomainDetection(TestClaimInheritanceBase):
    """Test domain detection and skip logic."""

    def test_round_1_always_skipped(self):
        """Round 1 always returns skipped=True (full verification)."""
        result = ci.validate_claim_inheritance(str(self.tmpdir), 5, 1)
        self.assertTrue(result["skipped"])
        self.assertTrue(result["valid"])

    def test_development_domain_skipped(self):
        """Development domain (cr file, no fc file) → skipped."""
        cr_path = self.dlg_dir / "step-5-r2-cr.md"
        cr_path.write_text("# Code Review\n\n## Verdict: PASS\n")
        result = ci.validate_claim_inheritance(str(self.tmpdir), 5, 2)
        self.assertTrue(result["skipped"])
        self.assertTrue(result["valid"])
        self.assertIn("Development domain", result["reason"])

    def test_missing_fc_file_skipped(self):
        """No fc file for current round → skipped (not failed)."""
        result = ci.validate_claim_inheritance(str(self.tmpdir), 5, 2)
        self.assertTrue(result["skipped"])
        self.assertTrue(result["valid"])


class TestCI1ClaimExists(TestClaimInheritanceBase):
    """CI1: Inherited claims must exist in previous round."""

    def test_ci1_pass_exact_match(self):
        """Inherited claim text matches previous round exactly → CI1 PASS."""
        prev_content = self._make_fc_content([
            ("GPT-4 has 1.8T parameters", "Section 2.1", "Verified", "arxiv.org/1234", ""),
        ])
        curr_content = self._make_fc_content([
            ("GPT-4 has 1.8T parameters", "Section 2.1", "Verified", "arxiv.org/1234", "Inherited from Round 1"),
        ])
        self._write_fc(5, 1, prev_content)
        self._write_fc(5, 2, curr_content)

        result = ci.validate_claim_inheritance(str(self.tmpdir), 5, 2)
        inherited = [r for r in result["results"] if r.get("ci1", "").startswith("PASS")]
        self.assertTrue(len(inherited) > 0, f"CI1 should PASS: {result}")
        self.assertEqual(result["hallucinations_detected"], 0)

    def test_ci1_fail_claim_not_in_previous(self):
        """Inherited claim not in previous round → CI1 FAIL (hallucination)."""
        prev_content = self._make_fc_content([
            ("BERT was released in 2018", "Section 1.2", "Verified", "arxiv.org/5678", ""),
        ])
        curr_content = self._make_fc_content([
            ("GPT-4 has 1.8T parameters", "Section 2.1", "Verified", "arxiv.org/1234", "Inherited from Round 1"),
        ])
        self._write_fc(5, 1, prev_content)
        self._write_fc(5, 2, curr_content)

        result = ci.validate_claim_inheritance(str(self.tmpdir), 5, 2)
        self.assertGreater(result["hallucinations_detected"], 0)
        ci1_failures = [r for r in result["results"] if r.get("ci1") == "FAIL"]
        self.assertTrue(len(ci1_failures) > 0)

    def test_ci1_fuzzy_match_by_numbers(self):
        """Inherited claim matches previous by key numbers → CI1 fuzzy PASS."""
        prev_content = self._make_fc_content([
            ("The model achieves 92.7% accuracy on SQuAD", "Section 2", "Verified", "arxiv.org", ""),
        ])
        # Slightly different wording but same key number (no numeric tokens in non-claim parts)
        curr_content = self._make_fc_content([
            ("BERT scores 92.7% on SQuAD benchmark", "Section 2", "Verified", "arxiv.org", "Inherited from Round 1"),
        ])
        self._write_fc(5, 1, prev_content)
        self._write_fc(5, 2, curr_content)

        result = ci.validate_claim_inheritance(str(self.tmpdir), 5, 2)
        # Fuzzy match should not count as hallucination
        fuzzy_matches = [r for r in result["results"] if "fuzzy" in r.get("ci1", "").lower()]
        self.assertTrue(len(fuzzy_matches) > 0, f"Expected fuzzy match: {result['results']}")


class TestCI2VerifiableVerdicts(TestClaimInheritanceBase):
    """CI2: Inherited claims must have had Verified/Partially Verified in previous round."""

    def test_ci2_pass_for_verified(self):
        """Previous verdict=Verified → CI2 PASS."""
        prev_content = self._make_fc_content([
            ("Claim A", "Section 1", "Verified", "source.com", ""),
        ])
        curr_content = self._make_fc_content([
            ("Claim A", "Section 1", "Verified", "source.com", "Inherited from Round 1"),
        ])
        self._write_fc(5, 1, prev_content)
        self._write_fc(5, 2, curr_content)

        result = ci.validate_claim_inheritance(str(self.tmpdir), 5, 2)
        ci2_passes = [r for r in result["results"] if r.get("ci2") == "PASS"]
        self.assertTrue(len(ci2_passes) > 0, f"CI2 should PASS: {result}")

    def test_ci2_pass_for_partially_verified(self):
        """Previous verdict=Partially Verified → CI2 PASS."""
        prev_content = self._make_fc_content([
            ("Claim B", "Section 2", "Partially Verified", "source.org", ""),
        ])
        curr_content = self._make_fc_content([
            ("Claim B", "Section 2", "Verified", "source.org", "Inherited from Round 1"),
        ])
        self._write_fc(5, 1, prev_content)
        self._write_fc(5, 2, curr_content)

        result = ci.validate_claim_inheritance(str(self.tmpdir), 5, 2)
        self.assertEqual(result["hallucinations_detected"], 0, f"No hallucinations expected: {result}")

    def test_ci2_fail_for_false_verdict(self):
        """Previous verdict=False → CI2 FAIL (cannot inherit False verdict as Verified)."""
        prev_content = self._make_fc_content([
            ("Claim C — incorrect fact", "Section 3", "False", "debunking.org", ""),
        ])
        curr_content = self._make_fc_content([
            ("Claim C — incorrect fact", "Section 3", "Verified", "source.com", "Inherited from Round 1"),
        ])
        self._write_fc(5, 1, prev_content)
        self._write_fc(5, 2, curr_content)

        result = ci.validate_claim_inheritance(str(self.tmpdir), 5, 2)
        self.assertGreater(result["hallucinations_detected"], 0)
        ci2_fails = [r for r in result["results"] if r.get("ci2") == "FAIL"]
        self.assertTrue(len(ci2_fails) > 0, f"CI2 should FAIL: {result}")

    def test_ci2_fail_for_unable_to_verify(self):
        """Previous verdict=Unable to Verify → CI2 FAIL (cannot inherit as Verified)."""
        prev_content = self._make_fc_content([
            ("Claim D", "Section 4", "Unable to Verify", "n/a", ""),
        ])
        curr_content = self._make_fc_content([
            ("Claim D", "Section 4", "Verified", "source.com", "Inherited from Round 1"),
        ])
        self._write_fc(5, 1, prev_content)
        self._write_fc(5, 2, curr_content)

        result = ci.validate_claim_inheritance(str(self.tmpdir), 5, 2)
        self.assertGreater(result["hallucinations_detected"], 0)


class TestCI2FuzzyMatchBug(TestClaimInheritanceBase):
    """Regression tests: CI2 must run even when CI1 matched via fuzzy (not exact) match.

    Bug: Previously CI2 was only in the `else:` (exact match) path.
    Fix: CI2 now runs for both exact and fuzzy matches.
    """

    def test_ci2_checked_when_fuzzy_match_false_verdict(self):
        """Fuzzy match found + prev verdict=False → CI2 FAIL (not skipped)."""
        prev_content = self._make_fc_content([
            ("The study reported 42% accuracy on the benchmark", "Section 3", "False", "debunk.org", ""),
        ])
        # Same key number (42), different wording → fuzzy match
        curr_content = self._make_fc_content([
            ("Researchers achieved 42% accuracy on the benchmark", "Section 3", "Verified", "src.com", "Inherited from Round 1"),
        ])
        self._write_fc(5, 1, prev_content)
        self._write_fc(5, 2, curr_content)

        result = ci.validate_claim_inheritance(str(self.tmpdir), 5, 2)
        # CI1 should be fuzzy PASS, CI2 should be FAIL (False verdict)
        self.assertGreater(result["hallucinations_detected"], 0,
                           "CI2 must detect False verdict even on fuzzy-matched claims")
        ci2_fails = [r for r in result["results"] if r.get("ci2") == "FAIL"]
        self.assertTrue(len(ci2_fails) > 0, f"CI2 FAIL expected for fuzzy match with False verdict: {result['results']}")

    def test_ci2_checked_when_fuzzy_match_unable_to_verify(self):
        """Fuzzy match found + prev verdict=Unable to Verify → CI2 FAIL."""
        prev_content = self._make_fc_content([
            ("BERT achieves 92.7% on SQuAD dataset", "Section 2", "Unable to Verify", "n/a", ""),
        ])
        curr_content = self._make_fc_content([
            ("BERT model scores 92.7% on SQuAD benchmark", "Section 2", "Verified", "arxiv", "Inherited from Round 1"),
        ])
        self._write_fc(5, 1, prev_content)
        self._write_fc(5, 2, curr_content)

        result = ci.validate_claim_inheritance(str(self.tmpdir), 5, 2)
        self.assertGreater(result["hallucinations_detected"], 0)

    def test_ci2_passes_when_fuzzy_match_verified_verdict(self):
        """Fuzzy match found + prev verdict=Verified → CI2 PASS."""
        prev_content = self._make_fc_content([
            ("The paper cites 300 references in total", "Section 5", "Verified", "openreview.net", ""),
        ])
        curr_content = self._make_fc_content([
            ("Authors included 300 references in the bibliography", "Section 5", "Verified", "openreview.net", "Inherited from Round 1"),
        ])
        self._write_fc(5, 1, prev_content)
        self._write_fc(5, 2, curr_content)

        result = ci.validate_claim_inheritance(str(self.tmpdir), 5, 2)
        self.assertEqual(result["hallucinations_detected"], 0,
                         f"No hallucinations when fuzzy match has Verified verdict: {result}")
        ci2_passes = [r for r in result["results"] if r.get("ci2") == "PASS"]
        self.assertTrue(len(ci2_passes) > 0)


class TestDegenerateCaseNoDoubleCount(TestClaimInheritanceBase):
    """Regression test: degenerate case must not double-count hallucinations."""

    def test_degenerate_no_double_count(self):
        """When prev_verified_count==0, hallucinations_detected == len(inherited_claims), not 2x."""
        # One inherited claim from a round with 0 verified claims (all "Unable to Verify")
        prev_content = self._make_fc_content([
            ("Claim A with uncertain data", "S1", "Unable to Verify", "n/a", ""),
        ])
        curr_content = self._make_fc_content([
            ("Claim A with uncertain data", "S1", "Verified", "src", "Inherited from Round 1"),
        ])
        self._write_fc(5, 1, prev_content)
        self._write_fc(5, 2, curr_content)

        result = ci.validate_claim_inheritance(str(self.tmpdir), 5, 2)
        # CI2 FAIL for 1 claim → hallucinations = 1
        # Degenerate case MUST NOT add another +1 → total should stay at 1
        self.assertEqual(result["hallucinations_detected"], 1,
                         f"Expected 1 hallucination (CI2 only), not double: {result}")


class TestCI3ClaimCount(TestClaimInheritanceBase):
    """CI3: Claim count must be non-decreasing."""

    def test_ci3_pass_count_same(self):
        """Round K has same count as Round K-1 → CI3 PASS."""
        prev_content = self._make_fc_content([
            ("Claim A", "S1", "Verified", "src", ""),
            ("Claim B", "S2", "Verified", "src", ""),
        ])
        curr_content = self._make_fc_content([
            ("Claim A", "S1", "Verified", "src", "Inherited from Round 1"),
            ("Claim B", "S2", "Verified", "src", "Inherited from Round 1"),
        ])
        self._write_fc(5, 1, prev_content)
        self._write_fc(5, 2, curr_content)

        result = ci.validate_claim_inheritance(str(self.tmpdir), 5, 2)
        self.assertTrue(result["ci3_pass"], f"CI3 should PASS: {result}")

    def test_ci3_pass_count_increased(self):
        """Round K has more claims than Round K-1 → CI3 PASS."""
        prev_content = self._make_fc_content([
            ("Claim A", "S1", "Verified", "src", ""),
        ])
        curr_content = self._make_fc_content([
            ("Claim A", "S1", "Verified", "src", "Inherited from Round 1"),
            ("Claim B", "S2", "Verified", "src", ""),  # new claim
        ])
        self._write_fc(5, 1, prev_content)
        self._write_fc(5, 2, curr_content)

        result = ci.validate_claim_inheritance(str(self.tmpdir), 5, 2)
        self.assertTrue(result["ci3_pass"])

    def test_ci3_fail_count_decreased(self):
        """Round K has fewer claims than Round K-1 → CI3 FAIL."""
        prev_content = self._make_fc_content([
            ("Claim A", "S1", "Verified", "src", ""),
            ("Claim B", "S2", "Verified", "src", ""),
            ("Claim C", "S3", "Verified", "src", ""),
        ])
        curr_content = self._make_fc_content([
            ("Claim A", "S1", "Verified", "src", "Inherited from Round 1"),
        ])
        self._write_fc(5, 1, prev_content)
        self._write_fc(5, 2, curr_content)

        result = ci.validate_claim_inheritance(str(self.tmpdir), 5, 2)
        self.assertFalse(result["ci3_pass"])
        self.assertFalse(result["valid"])


class TestCI4ChangedParagraph(TestClaimInheritanceBase):
    """CI4: Inherited claims must not be in paragraphs that changed between drafts."""

    def test_ci4_pass_claim_in_unchanged_paragraph(self):
        """Claim in unchanged paragraph → CI4 PASS."""
        para_unchanged = "This paragraph discusses GPT-4 capabilities and parameters."
        para_other = "Introduction paragraph that is different.\n\nSecond paragraph."

        prev_draft = para_unchanged + "\n\n" + para_other
        curr_draft = para_unchanged + "\n\n" + "New introduction paragraph.\n\nSecond paragraph."

        self._write_draft(5, 1, prev_draft)
        self._write_draft(5, 2, curr_draft)

        prev_content = self._make_fc_content([
            ("GPT-4 capabilities", "Para 1", "Verified", "openai.com", ""),
        ])
        curr_content = self._make_fc_content([
            ("GPT-4 capabilities", "Para 1", "Verified", "openai.com", "Inherited from Round 1"),
        ])
        self._write_fc(5, 1, prev_content)
        self._write_fc(5, 2, curr_content)

        result = ci.validate_claim_inheritance(str(self.tmpdir), 5, 2)
        ci4_fails = [r for r in result["results"] if r.get("ci4") == "FAIL"]
        self.assertEqual(len(ci4_fails), 0, f"CI4 should PASS: {result}")

    def test_ci4_fail_claim_in_changed_paragraph(self):
        """Claim's location found in a changed paragraph → CI4 FAIL."""
        # The location "Section 2.1" is in the changed paragraph
        changed_para = "Section 2.1 discusses the transformer architecture changes."
        prev_draft = "Introduction.\n\n" + changed_para + "\n\nConclusion."
        curr_draft = "Introduction.\n\n" + "Section 2.1 discusses revised transformer architecture." + "\n\nConclusion."

        self._write_draft(5, 1, prev_draft)
        self._write_draft(5, 2, curr_draft)

        prev_content = self._make_fc_content([
            ("Transformers use attention", "Section 2.1", "Verified", "vaswani2017", ""),
        ])
        curr_content = self._make_fc_content([
            ("Transformers use attention", "Section 2.1", "Verified", "vaswani2017", "Inherited from Round 1"),
        ])
        self._write_fc(5, 1, prev_content)
        self._write_fc(5, 2, curr_content)

        result = ci.validate_claim_inheritance(str(self.tmpdir), 5, 2)
        ci4_fails = [r for r in result["results"] if r.get("ci4") == "FAIL"]
        self.assertTrue(len(ci4_fails) > 0, f"CI4 should FAIL: {result}")


class TestDegenerateCase(TestClaimInheritanceBase):
    """Test degenerate case: previous round had 0 verified claims."""

    def test_degenerate_zero_verified_previous(self):
        """Prev round had 0 verified claims + inherited claims → hallucination detected."""
        prev_content = self._make_fc_content([
            ("All claims are unverified", "Section 1", "Unable to Verify", "n/a", ""),
        ])
        curr_content = self._make_fc_content([
            ("All claims are unverified", "Section 1", "Verified", "n/a", "Inherited from Round 1"),
        ])
        self._write_fc(5, 1, prev_content)
        self._write_fc(5, 2, curr_content)

        result = ci.validate_claim_inheritance(str(self.tmpdir), 5, 2)
        # Should detect the problem
        self.assertGreater(result["hallucinations_detected"], 0)


class TestParseClaimTable(unittest.TestCase):
    """Test the claim table parser directly."""

    def test_parse_inherited_marker(self):
        """Claims with 'Inherited from Round' in notes → is_inherited=True."""
        content = (
            "| # | Claim | Location | Verdict | Source | Notes |\n"
            "|---|-------|----------|---------|--------|-------|\n"
            "| 1 | Some claim text | Section 1 | Verified | src | Inherited from Round 1 |\n"
            "| 2 | Another claim | Section 2 | Verified | src | New claim |\n"
        )
        claims = ci._parse_claim_table(content)
        self.assertEqual(len(claims), 2)
        self.assertTrue(claims[0]["is_inherited"])
        self.assertFalse(claims[1]["is_inherited"])

    def test_parse_empty_content(self):
        """Empty content → empty list."""
        claims = ci._parse_claim_table("")
        self.assertEqual(claims, [])

    def test_parse_header_row_skipped(self):
        """Header row (Claim, Verdict, etc.) should be skipped."""
        content = (
            "| # | Claim | Location | Verdict | Source | Notes |\n"
            "|---|-------|----------|---------|--------|-------|\n"
            "| 1 | Real claim here about something | Section 1 | Verified | src | |\n"
        )
        claims = ci._parse_claim_table(content)
        self.assertEqual(len(claims), 1)
        self.assertNotIn(claims[0]["claim_text"].lower(), ("claim", "#", "verdict"))


class TestChangedParagraphs(unittest.TestCase):
    """Test paragraph diff detection."""

    def test_identical_drafts_no_changes(self):
        """Identical drafts → no changed paragraphs."""
        text = "Para 1\n\nPara 2\n\nPara 3"
        changed = ci._find_changed_paragraphs(text, text)
        self.assertEqual(len(changed), 0)

    def test_modified_paragraph_detected(self):
        """Modified paragraph appears in changed set."""
        prev = "Unchanged para.\n\nThis will change.\n\nAlso unchanged."
        curr = "Unchanged para.\n\nThis has changed now.\n\nAlso unchanged."
        changed = ci._find_changed_paragraphs(prev, curr)
        self.assertIn("This will change.", changed)
        self.assertNotIn("Unchanged para.", changed)

    def test_removed_paragraph_detected(self):
        """Removed paragraph appears in changed set."""
        prev = "Para A.\n\nPara B.\n\nPara C."
        curr = "Para A.\n\nPara C."
        changed = ci._find_changed_paragraphs(prev, curr)
        self.assertIn("Para B.", changed)


if __name__ == "__main__":
    unittest.main()
