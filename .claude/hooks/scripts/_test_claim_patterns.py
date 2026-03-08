#!/usr/bin/env python3
"""Tests for _claim_patterns.py — centralized claim patterns."""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _claim_patterns import (
    BLOCKED_CLAIM_PATTERNS,
    CANONICAL_CLAIM_TYPES,
    CITATION_PAREN_RE,
    CITATION_INLINE_RE,
    CLAIM_ID_VALIDATE_RE,
    CLAIM_ID_INLINE_RE,
    CLAIM_TYPE_TO_CANONICAL,
    CONFIDENCE_DEFAULT,
    CONFIDENCE_STRING_TO_NUMERIC,
    REQUIRE_SOURCE_PATTERNS,
    TRACE_MARKER_RE,
    canonicalize_claim_type,
    count_claims,
    count_citations,
    extract_claim_ids,
    extract_claim_metadata,
    extract_claim_type,
    extract_confidence_numeric,
)


class TestClaimIdValidateRe(unittest.TestCase):
    """Test the validation regex (with anchors, for single ID strings)."""

    def test_simple_ids(self):
        for cid in ["LS-001", "GI-007", "CMB-014", "SWA-002", "TRA-003"]:
            self.assertRegex(cid, CLAIM_ID_VALIDATE_RE, f"{cid} should match")

    def test_multi_hyphen_ids(self):
        for cid in ["EMP-NEURO-001", "CR-LOGIC-001", "MC-IV-002"]:
            self.assertRegex(cid, CLAIM_ID_VALIDATE_RE, f"{cid} should match")

    def test_no_dash_before_digits(self):
        self.assertRegex("PHIL-T001", CLAIM_ID_VALIDATE_RE)

    def test_synth_ids(self):
        self.assertRegex("SYNTH-001", CLAIM_ID_VALIDATE_RE)
        self.assertRegex("SYNTH-009", CLAIM_ID_VALIDATE_RE)

    def test_rejects_lowercase(self):
        self.assertNotRegex("ls-001", CLAIM_ID_VALIDATE_RE)

    def test_rejects_single_digit(self):
        self.assertNotRegex("LS-1", CLAIM_ID_VALIDATE_RE)

    def test_rejects_no_digits(self):
        self.assertNotRegex("LS-ABC", CLAIM_ID_VALIDATE_RE)

    def test_rejects_too_long_prefix(self):
        self.assertNotRegex("ABCDEFG-001", CLAIM_ID_VALIDATE_RE)

    def test_four_digit_ids(self):
        self.assertRegex("LS-0001", CLAIM_ID_VALIDATE_RE)

    def test_rejects_five_digits(self):
        self.assertNotRegex("LS-00001", CLAIM_ID_VALIDATE_RE)


class TestCountClaims(unittest.TestCase):
    """Test count_claims function."""

    def test_no_claims(self):
        self.assertEqual(count_claims("No claims here"), 0)

    def test_simple_claims(self):
        self.assertEqual(count_claims("id: LS-001"), 1)
        self.assertEqual(count_claims("id: LS-001\nid: LS-002"), 2)

    def test_multi_hyphen(self):
        self.assertEqual(count_claims("id: EMP-NEURO-001"), 1)
        self.assertEqual(count_claims("id: CR-LOGIC-001\nid: MC-IV-002"), 2)

    def test_claim_id_prefix(self):
        self.assertEqual(count_claims("claim_id: PHIL-T001"), 1)

    def test_quoted(self):
        self.assertEqual(count_claims('id: "LS-001"'), 1)
        self.assertEqual(count_claims("id: 'LS-001'"), 1)

    def test_bold_bracket_not_double_counted(self):
        self.assertEqual(
            count_claims('**[PHIL-T001]** claim_id: PHIL-T001'), 1
        )

    def test_mixed_formats(self):
        content = """
id: LS-001
id: EMP-NEURO-002
claim_id: PHIL-T003
id: "SYNTH-004"
"""
        self.assertEqual(count_claims(content), 4)


class TestExtractClaimIds(unittest.TestCase):
    """Test extract_claim_ids function."""

    def test_simple(self):
        self.assertEqual(extract_claim_ids("id: LS-001"), ["LS-001"])

    def test_multi_hyphen(self):
        content = "id: EMP-NEURO-001\nid: CR-LOGIC-002"
        self.assertEqual(
            extract_claim_ids(content),
            ["EMP-NEURO-001", "CR-LOGIC-002"],
        )

    def test_claim_id_prefix(self):
        self.assertEqual(
            extract_claim_ids("claim_id: PHIL-T001"), ["PHIL-T001"]
        )

    def test_empty(self):
        self.assertEqual(extract_claim_ids(""), [])
        self.assertEqual(extract_claim_ids("no claims"), [])


# =============================================================================
# §2 — Confidence Extraction Tests
# =============================================================================


class TestExtractConfidenceNumeric(unittest.TestCase):
    """Test extract_confidence_numeric — dual format handling."""

    def test_numeric_value(self):
        self.assertEqual(extract_confidence_numeric("confidence: 95"), 95)
        self.assertEqual(extract_confidence_numeric("confidence: 0"), 0)

    def test_string_high(self):
        self.assertEqual(extract_confidence_numeric("confidence: high"), 90)

    def test_string_medium(self):
        self.assertEqual(extract_confidence_numeric("confidence: medium"), 70)

    def test_string_low(self):
        self.assertEqual(extract_confidence_numeric("confidence: low"), 50)

    def test_string_speculative(self):
        self.assertEqual(extract_confidence_numeric("confidence: speculative"), 40)

    def test_malformed_high_paren(self):
        """Handles malformed "high)" (31 occurrences in actual data)."""
        self.assertEqual(extract_confidence_numeric("confidence: high)"), 90)

    def test_case_insensitive(self):
        self.assertEqual(extract_confidence_numeric("confidence: HIGH"), 90)
        self.assertEqual(extract_confidence_numeric("confidence: Medium"), 70)

    def test_no_confidence_field(self):
        self.assertIsNone(extract_confidence_numeric("no confidence here"))
        self.assertIsNone(extract_confidence_numeric(""))

    def test_numeric_preferred_over_string(self):
        """When both formats appear, numeric is returned (searched first)."""
        text = "confidence: 85\nconfidence: high"
        self.assertEqual(extract_confidence_numeric(text), 85)

    def test_in_yaml_block(self):
        yaml = "- id: LS-001\n  claim_type: FACTUAL\n  confidence: 93\n  claim: >"
        self.assertEqual(extract_confidence_numeric(yaml), 93)

    def test_in_blockquote(self):
        bq = "> claim_id: PHIL-T001\n> confidence: high\n> domain: philosophy"
        self.assertEqual(extract_confidence_numeric(bq), 90)


# =============================================================================
# §3 — Claim Type Tests
# =============================================================================


class TestCanonicalizeClaimType(unittest.TestCase):
    """Test canonicalize_claim_type — 17+ types → 7 canonical."""

    def test_direct_mappings(self):
        for ct in ["FACTUAL", "EMPIRICAL", "THEORETICAL",
                    "METHODOLOGICAL", "INTERPRETIVE", "SPECULATIVE"]:
            self.assertEqual(canonicalize_claim_type(ct), ct)

    def test_analytical_to_interpretive(self):
        self.assertEqual(canonicalize_claim_type("ANALYTICAL"), "INTERPRETIVE")

    def test_methodological_critique(self):
        self.assertEqual(
            canonicalize_claim_type("METHODOLOGICAL_CRITIQUE"), "METHODOLOGICAL"
        )

    def test_theological_to_theoretical(self):
        self.assertEqual(canonicalize_claim_type("THEOLOGICAL"), "THEORETICAL")

    def test_definitional_to_factual(self):
        self.assertEqual(canonicalize_claim_type("DEFINITIONAL"), "FACTUAL")

    def test_historical_to_factual(self):
        self.assertEqual(canonicalize_claim_type("HISTORICAL"), "FACTUAL")

    def test_unknown_type(self):
        self.assertEqual(canonicalize_claim_type("MADE_UP_TYPE"), "UNKNOWN")
        self.assertEqual(canonicalize_claim_type(""), "UNKNOWN")

    def test_case_insensitive(self):
        self.assertEqual(canonicalize_claim_type("factual"), "FACTUAL")
        self.assertEqual(canonicalize_claim_type("Analytical"), "INTERPRETIVE")

    def test_all_mapped_types_are_canonical(self):
        """Every value in the mapping must be in CANONICAL_CLAIM_TYPES."""
        for raw, canonical in CLAIM_TYPE_TO_CANONICAL.items():
            self.assertIn(canonical, CANONICAL_CLAIM_TYPES,
                          f"{raw} → {canonical} is not canonical")


class TestExtractClaimType(unittest.TestCase):
    """Test extract_claim_type from text."""

    def test_yaml_format(self):
        self.assertEqual(extract_claim_type("claim_type: EMPIRICAL"), "EMPIRICAL")

    def test_quoted(self):
        self.assertEqual(extract_claim_type('claim_type: "FACTUAL"'), "FACTUAL")

    def test_no_type(self):
        self.assertIsNone(extract_claim_type("id: LS-001"))

    def test_analytical(self):
        self.assertEqual(extract_claim_type("claim_type: ANALYTICAL"), "ANALYTICAL")


# =============================================================================
# §4 — Citation Pattern Tests
# =============================================================================


class TestCitationPatterns(unittest.TestCase):
    """Test centralized citation regex patterns."""

    def test_paren_simple(self):
        self.assertEqual(len(CITATION_PAREN_RE.findall("(Smith, 2020)")), 1)

    def test_paren_et_al(self):
        self.assertEqual(len(CITATION_PAREN_RE.findall("(Smith et al., 2020)")), 1)

    def test_paren_ampersand(self):
        self.assertEqual(len(CITATION_PAREN_RE.findall("(Smith & Jones, 2020)")), 1)

    def test_inline_simple(self):
        self.assertEqual(len(CITATION_INLINE_RE.findall("Smith (2020)")), 1)

    def test_inline_et_al(self):
        self.assertEqual(len(CITATION_INLINE_RE.findall("Smith et al. (2020)")), 1)

    def test_count_citations(self):
        text = "(Smith, 2020) said X. Jones (2021) agreed."
        self.assertEqual(count_citations(text), 2)


# =============================================================================
# §5 — Hallucination Firewall Pattern Tests
# =============================================================================


class TestBlockedClaimPatterns(unittest.TestCase):
    """Test BLOCKED_CLAIM_PATTERNS — compiled regex list."""

    def test_all_studies_agree(self):
        matched = any(p.search("all studies agree") for p in BLOCKED_CLAIM_PATTERNS)
        self.assertTrue(matched)

    def test_100_percent(self):
        # \b100\s*%\b matches when % is immediately followed by a word char.
        # Pre-existing pattern limitation: "100% " (space after %) does not
        # match because \b requires word↔non-word boundary after %.
        matched = any(p.search("100%certain") for p in BLOCKED_CLAIM_PATTERNS)
        self.assertTrue(matched)
        # Verify the pattern does NOT match isolated "100%" (known limitation)
        matched_isolated = any(p.search("100% ") for p in BLOCKED_CLAIM_PATTERNS)
        self.assertFalse(matched_isolated)

    def test_no_exceptions(self):
        matched = any(p.search("no exception") for p in BLOCKED_CLAIM_PATTERNS)
        self.assertTrue(matched)

    def test_normal_text_not_blocked(self):
        matched = any(p.search("most studies suggest") for p in BLOCKED_CLAIM_PATTERNS)
        self.assertFalse(matched)


class TestRequireSourcePatterns(unittest.TestCase):
    """Test REQUIRE_SOURCE_PATTERNS — compiled regex list."""

    def test_p_value(self):
        matched = any(p.search("p < .05") for p in REQUIRE_SOURCE_PATTERNS)
        self.assertTrue(matched)

    def test_effect_size(self):
        matched = any(p.search("d = 0.8") for p in REQUIRE_SOURCE_PATTERNS)
        self.assertTrue(matched)

    def test_cohens_d(self):
        matched = any(p.search("Cohen's d") for p in REQUIRE_SOURCE_PATTERNS)
        self.assertTrue(matched)

    def test_normal_text_not_matched(self):
        matched = any(p.search("the results were significant") for p in REQUIRE_SOURCE_PATTERNS)
        self.assertFalse(matched)


# =============================================================================
# §6 — Trace Marker Tests
# =============================================================================


class TestTraceMarkerRe(unittest.TestCase):
    """Test TRACE_MARKER_RE."""

    def test_match(self):
        self.assertIsNotNone(TRACE_MARKER_RE.search("[trace:step-5"))

    def test_multi_digit(self):
        self.assertIsNotNone(TRACE_MARKER_RE.search("[trace:step-123"))

    def test_no_match(self):
        self.assertIsNone(TRACE_MARKER_RE.search("[trace:other-5"))


# =============================================================================
# §7 — Claim Metadata Extraction Tests
# =============================================================================


class TestExtractClaimMetadata(unittest.TestCase):
    """Test extract_claim_metadata — all three thesis output formats."""

    def test_format2_yaml_block(self):
        """Format 2: YAML code block (Wave 2+)."""
        content = """```yaml
- id: EMP-NEURO-001
  claim_type: EMPIRICAL
  confidence: 95
  claim: >
    Libet's experiments demonstrated something.
  source: "Libet, B. (1985). Behavioral and Brain Sciences."
```"""
        claims = extract_claim_metadata(content)
        self.assertEqual(len(claims), 1)
        c = claims[0]
        self.assertEqual(c["claim_id"], "EMP-NEURO-001")
        self.assertEqual(c["claim_type"], "EMPIRICAL")
        self.assertEqual(c["canonical_type"], "EMPIRICAL")
        self.assertEqual(c["confidence_numeric"], 95)
        self.assertTrue(c["has_source"])
        self.assertTrue(c["has_citation"])

    def test_format1_blockquote(self):
        """Format 1: Blockquote (Wave 1 trend/lit)."""
        content = """> **[PHIL-T001]** claim_id: PHIL-T001
> claim_text: "Turing reframed the question."
> source: "Turing, A. M. (1950). Mind, 59(236), 433-460."
> confidence: high
> domain: philosophy
> verified: true
"""
        claims = extract_claim_metadata(content)
        self.assertEqual(len(claims), 1)
        c = claims[0]
        self.assertEqual(c["claim_id"], "PHIL-T001")
        self.assertIsNone(c["claim_type"])  # Format 1 has no claim_type
        self.assertEqual(c["canonical_type"], "UNKNOWN")
        self.assertEqual(c["confidence_numeric"], 90)  # "high" → 90
        self.assertTrue(c["has_source"])

    def test_format3_yaml_inline(self):
        """Format 3: YAML inline with claim_type (Wave 1 seminal-works)."""
        content = """```yaml
- id: SWA-001
  claim_type: FACTUAL
  confidence: 92
  claim: "Turing published his landmark paper in 1950."
  source: "Turing (1950)"
```"""
        claims = extract_claim_metadata(content)
        self.assertEqual(len(claims), 1)
        c = claims[0]
        self.assertEqual(c["claim_id"], "SWA-001")
        self.assertEqual(c["claim_type"], "FACTUAL")
        self.assertEqual(c["canonical_type"], "FACTUAL")
        self.assertEqual(c["confidence_numeric"], 92)

    def test_multiple_claims_in_yaml(self):
        """Multiple claims in a single YAML block."""
        content = """```yaml
- id: EMP-001
  claim_type: EMPIRICAL
  confidence: 93
  claim: "First claim."
  source: "Author (2020)"
- id: EMP-002
  claim_type: ANALYTICAL
  confidence: 88
  claim: "Second claim."
  source: "Another (2021)"
```"""
        claims = extract_claim_metadata(content)
        self.assertEqual(len(claims), 2)
        self.assertEqual(claims[0]["claim_id"], "EMP-001")
        self.assertEqual(claims[1]["claim_id"], "EMP-002")
        self.assertEqual(claims[1]["canonical_type"], "INTERPRETIVE")  # ANALYTICAL → INTERPRETIVE

    def test_mixed_formats(self):
        """File with both blockquote and YAML block formats."""
        content = """> **[PHIL-T001]** claim_id: PHIL-T001
> claim_text: "Something."
> confidence: medium

Some text here.

```yaml
- id: EMP-001
  claim_type: EMPIRICAL
  confidence: 90
  claim: "Another thing."
  source: "Author (2020)"
```"""
        claims = extract_claim_metadata(content)
        self.assertEqual(len(claims), 2)
        ids = {c["claim_id"] for c in claims}
        self.assertIn("PHIL-T001", ids)
        self.assertIn("EMP-001", ids)

    def test_no_duplicate_ids(self):
        """Same claim ID in both YAML and blockquote should not be double-counted."""
        content = """```yaml
- id: LS-001
  claim_type: FACTUAL
  confidence: 92
  claim: "Something."
```

> claim_id: LS-001
> confidence: high
"""
        claims = extract_claim_metadata(content)
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["claim_id"], "LS-001")

    def test_missing_confidence_uses_default(self):
        """Missing confidence field → CONFIDENCE_DEFAULT (50)."""
        content = """```yaml
- id: LS-001
  claim_type: FACTUAL
  claim: "No confidence here."
```"""
        claims = extract_claim_metadata(content)
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["confidence_numeric"], CONFIDENCE_DEFAULT)
        self.assertIsNone(claims[0]["confidence_raw"])

    def test_empty_content(self):
        self.assertEqual(extract_claim_metadata(""), [])
        self.assertEqual(extract_claim_metadata("no claims at all"), [])

    def test_malformed_confidence_high_paren(self):
        """Handles "high)" malformed value (31 occurrences in actual data)."""
        content = """> claim_id: PHIL-T001
> confidence: high)
> source: "Author (2020)"
"""
        claims = extract_claim_metadata(content)
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["confidence_numeric"], 90)


if __name__ == "__main__":
    unittest.main()
