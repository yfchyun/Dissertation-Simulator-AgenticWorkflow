"""Centralized Claim patterns — single source of truth for all claim regex.

All scripts that need to find, count, validate, or analyze GroundedClaim data
MUST import from this module. Never define claim-related regex inline.

Claim ID formats:
  - Simple:      LS-001, GI-007, CMB-014
  - Multi-hyphen: EMP-NEURO-001, CR-LOGIC-001, MC-IV-002
  - Blockquote:   claim_id: PHIL-T001
  - YAML inline:  id: SYNTH-004
  - Quoted:       id: "LS-001", id: 'CMB-007'
  - Bold bracket: **[PHIL-T001]** claim_id: PHIL-T001

Claim metadata formats (three coexisting formats in thesis output):
  Format 1 (Blockquote — Wave 1):
    > **[PHIL-T001]** claim_id: PHIL-T001
    > claim_text: "..."
    > source: "..."
    > confidence: high
    > domain: philosophy

  Format 2 (YAML code block — Wave 2+):
    ```yaml
    - id: EMP-NEURO-001
      claim_type: EMPIRICAL
      confidence: 95
      claim: >
        ...
      source: "..."
    ```

  Format 3 (YAML inline — Wave 1 seminal-works):
    ```yaml
    - id: SWA-001
      claim_type: FACTUAL
      confidence: 92
      claim: "..."
    ```

Consumers: validate_grounded_claim.py, compute_srcs_scores.py,
  validate_criteria_evidence.py, compute_pccs_signals.py,
  generate_pccs_report.py, validate_pccs_output.py
"""

from __future__ import annotations

import re
from typing import Any

# =============================================================================
# §1 — Claim ID Patterns (existing, unchanged)
# =============================================================================

# --- Raw ID pattern (no context, with anchors) ---
# For validating a single extracted ID string.
# Allows: 1-6 uppercase letters per segment, 1+ segments separated by hyphens,
# optional hyphen before 2-4 trailing digits.
CLAIM_ID_VALIDATE_RE = re.compile(
    r"^[A-Z]{1,6}(?:-[A-Z]{1,6})*-?\d{2,4}$"
)

# --- Inline search pattern (no anchors, with context prefix) ---
# For finding claim IDs inside file content (markdown, YAML, blockquotes).
CLAIM_ID_INLINE_RE = re.compile(
    r'(?:id|claim_id):\s*["\']?(?:\*\*\[)?'
    r'([A-Z]{1,6}(?:-[A-Z]{1,6})*-?\d{2,4})'
    r'(?:\]\*\*)?["\']?'
)


def count_claims(content: str) -> int:
    """Count GroundedClaim entries in file content."""
    return len(CLAIM_ID_INLINE_RE.findall(content))


def extract_claim_ids(content: str) -> list[str]:
    """Extract all claim IDs from file content."""
    return CLAIM_ID_INLINE_RE.findall(content)


# =============================================================================
# §2 — Confidence Patterns (pCCS — P1 deterministic)
# =============================================================================

# String-to-numeric mapping for confidence values.
# Actual data: "high" (99 occurrences), "medium" (41), "high)" (31 — malformed).
# Numeric values: 78-97 in wave 2-4.
CONFIDENCE_STRING_TO_NUMERIC: dict[str, int] = {
    "high": 90,
    "medium": 70,
    "low": 50,
    "speculative": 40,
}

# Default confidence when field is missing entirely
CONFIDENCE_DEFAULT = 50

# Regex: captures numeric or string confidence values
# Handles: "confidence: 95", "confidence: high", "confidence: high)"
_CONFIDENCE_NUMERIC_RE = re.compile(r'confidence:\s*(\d+)')
_CONFIDENCE_STRING_RE = re.compile(
    r'confidence:\s*([a-zA-Z]+)\)?',  # trailing ) for malformed "high)"
    re.IGNORECASE,
)


def extract_confidence_numeric(text: str) -> int | None:
    """Extract confidence as a numeric value from a claim block.

    Handles both numeric (95) and string ("high") formats.
    Strips trailing parenthesis from malformed values like "high)".
    Returns None if no confidence field is found.
    """
    # Try numeric first (more precise)
    numeric = _CONFIDENCE_NUMERIC_RE.search(text)
    if numeric:
        return int(numeric.group(1))
    # Try string mapping
    string = _CONFIDENCE_STRING_RE.search(text)
    if string:
        key = string.group(1).lower().rstrip(")")
        return CONFIDENCE_STRING_TO_NUMERIC.get(key)
    return None


# =============================================================================
# §3 — Claim Type Patterns (pCCS — P1 deterministic)
# =============================================================================

# Canonical claim types used in pCCS weight/ceiling tables (7 types).
CANONICAL_CLAIM_TYPES = frozenset({
    "FACTUAL", "EMPIRICAL", "THEORETICAL",
    "METHODOLOGICAL", "INTERPRETIVE", "SPECULATIVE",
    "UNKNOWN",
})

# Mapping from actual thesis claim types (17+) to canonical 7 types.
# Unmapped types default to UNKNOWN.
CLAIM_TYPE_TO_CANONICAL: dict[str, str] = {
    # Direct 1:1 mappings (6 canonical types)
    "FACTUAL": "FACTUAL",
    "EMPIRICAL": "EMPIRICAL",
    "THEORETICAL": "THEORETICAL",
    "METHODOLOGICAL": "METHODOLOGICAL",
    "INTERPRETIVE": "INTERPRETIVE",
    "SPECULATIVE": "SPECULATIVE",
    # Extended types → canonical (sorted by frequency in actual data)
    "ANALYTICAL": "INTERPRETIVE",          # 110 — analysis involves interpretation
    "METHODOLOGICAL_CRITIQUE": "METHODOLOGICAL",  # 64 — critique of methodology
    "THEOLOGICAL": "THEORETICAL",          # 20 — theological reasoning
    "AUDIT": "METHODOLOGICAL",             # 14 — methodological assessment
    "COUNTERARGUMENT": "INTERPRETIVE",     # 14 — counter-arguments are interpretive
    "DEFINITIONAL": "FACTUAL",             # 12 — definitions are factual
    "ASSUMPTION_CRITIQUE": "INTERPRETIVE", # 12 — critique involves interpretation
    "HISTORICAL": "FACTUAL",               # 10 — historical claims are factual
    "STRUCTURAL": "METHODOLOGICAL",        # 8 — structural claims about methodology
    "SYNTHESIS": "INTERPRETIVE",           # 6 — synthesis involves interpretation
    "ARGUMENTATIVE": "INTERPRETIVE",       # 4 — arguments are interpretive
}

# Regex to extract claim_type from text
_CLAIM_TYPE_RE = re.compile(r'claim_type:\s*["\']?(\w+)["\']?')


def canonicalize_claim_type(raw_type: str) -> str:
    """Map a raw claim_type string to one of 7 canonical types.

    Returns UNKNOWN for unrecognized types.
    Note: .strip() applied defensively — extract_claim_type() regex
    guarantees no whitespace, but external callers may not.
    """
    return CLAIM_TYPE_TO_CANONICAL.get(raw_type.strip().upper(), "UNKNOWN")


def extract_claim_type(text: str) -> str | None:
    """Extract raw claim_type from a claim block.

    Returns the raw type string (e.g., "EMPIRICAL", "ANALYTICAL"),
    or None if no claim_type field is found.
    """
    match = _CLAIM_TYPE_RE.search(text)
    return match.group(1) if match else None


# =============================================================================
# §4 — Citation Patterns (shared by compute_srcs_scores.py, pCCS)
# =============================================================================

# (Author, Year) format: (Smith, 2020), (Smith et al., 2020), (Smith & Jones, 2020a)
CITATION_PAREN_RE = re.compile(
    r'\((?:[A-Z][a-z]+(?:\s+(?:et\s+al\.?|&\s+[A-Z][a-z]+))?'
    r',?\s*\d{4}[a-z]?)\)'
)

# Author (Year) format: Smith (2020), Smith et al. (2020)
CITATION_INLINE_RE = re.compile(
    r'[A-Z][a-z]+\s+(?:et\s+al\.?\s+)?\(\d{4}[a-z]?\)'
)

# Year references in general: (2020), (Year)
CITATION_YEAR_RE = re.compile(r'\(\d{4}\)')

# DOI pattern
CITATION_DOI_RE = re.compile(r'doi:\s*["\']?10\.\d{4,}/', re.IGNORECASE)


def count_citations(content: str) -> int:
    """Count total citations in content (parenthetical + inline formats)."""
    return len(CITATION_PAREN_RE.findall(content)) + len(CITATION_INLINE_RE.findall(content))


# =============================================================================
# §5 — Hallucination Firewall Patterns (shared by validate_grounded_claim.py, pCCS)
# =============================================================================

# Blocked absolute-claim patterns — must be softened or removed.
BLOCKED_CLAIM_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\ball\s+(?:studies|research|evidence)\s+(?:agree|confirm|show)\b",
        r"\b100\s*%\b",
        r"\bno\s+exceptions?\b",
        r"\buniversally\s+(?:accepted|agreed|true)\b",
        r"\bwithout\s+(?:any\s+)?exception\b",
        r"\bevery\s+single\b",
    ]
]

# Patterns requiring source citation (statistical claims).
REQUIRE_SOURCE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE) for p in [
        r"p\s*[<>=]\s*\.\d+",           # p-values
        r"[drgfF]\s*=\s*[\d.]+",        # effect sizes
        r"\beffect\s+size\b",
        r"\bcohen[''']?s\s+d\b",
        r"\br\s*=\s*[+-]?[\d.]+",       # correlations
        r"\bOR\s*=\s*[\d.]+",           # odds ratio
        r"\bRR\s*=\s*[\d.]+",           # risk ratio
    ]
]


# =============================================================================
# §6 — Trace Marker Patterns (shared by validate_criteria_evidence.py, pCCS)
# =============================================================================

# [trace:step-N] marker pattern
TRACE_MARKER_RE = re.compile(r"\[trace:step-\d+")


# =============================================================================
# §7 — Claim Metadata Extraction (pCCS Phase A — P1 deterministic)
# =============================================================================

# Regex patterns for extracting claim blocks
# Format 2/3: YAML code block (```yaml ... ```)
_YAML_BLOCK_RE = re.compile(r'```yaml\s*\n(.*?)```', re.DOTALL)

# Format 1: Blockquote claim (> **[ID]** claim_id: ...)
_BLOCKQUOTE_CLAIM_RE = re.compile(
    r'(?:^|\n)(?:>\s*.*\n)*'  # consecutive blockquote lines
    r'(?=.*(?:id|claim_id):\s*)',  # must contain id field
    re.MULTILINE,
)

# Source field extraction
_SOURCE_RE = re.compile(r'source:\s*["\']?(.*?)(?:["\']?\s*$)', re.MULTILINE)

# Claim text extraction
_CLAIM_TEXT_RE = re.compile(
    r'(?:claim_text|claim):\s*[>|]?\s*\n?\s*["\']?(.*?)(?:["\']?\s*(?:\n\s*\w+:|$))',
    re.DOTALL,
)


def extract_claim_metadata(content: str) -> list[dict[str, Any]]:
    """Extract structured claim metadata from file content.

    Handles all three coexisting formats in thesis output:
      Format 1: Blockquote with claim_id/confidence/source (Wave 1 trend/lit)
      Format 2: YAML code block with id/claim_type/confidence (Wave 2+)
      Format 3: YAML inline with id/claim_type/confidence (Wave 1 seminal)

    Returns list of dicts, each with:
      - claim_id: str (e.g., "EMP-NEURO-001")
      - claim_type: str | None (raw type, e.g., "EMPIRICAL", "ANALYTICAL")
      - canonical_type: str (one of 7 canonical types)
      - confidence_raw: str | None (raw value, e.g., "95", "high")
      - confidence_numeric: int (mapped numeric, e.g., 95, 90)
      - has_source: bool
      - has_citation: bool (source contains year reference)
      - source_text: str (first 200 chars of source, for debugging)
    """
    claims: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    # --- Strategy 1: YAML code blocks (Format 2, 3) ---
    for yaml_match in _YAML_BLOCK_RE.finditer(content):
        yaml_block = yaml_match.group(1)
        # Split into individual claim entries (start with "- id:")
        entries = re.split(r'(?=^-\s+id:)', yaml_block, flags=re.MULTILINE)
        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue
            ids = CLAIM_ID_INLINE_RE.findall(entry)
            if not ids:
                continue
            claim_id = ids[0]
            if claim_id in seen_ids:
                continue
            seen_ids.add(claim_id)

            raw_type = extract_claim_type(entry)
            conf = extract_confidence_numeric(entry)
            source_match = _SOURCE_RE.search(entry)
            source_text = source_match.group(1).strip()[:200] if source_match else ""
            has_citation = bool(CITATION_YEAR_RE.search(source_text)) if source_text else False

            claims.append({
                "claim_id": claim_id,
                "claim_type": raw_type,
                "canonical_type": canonicalize_claim_type(raw_type) if raw_type else "UNKNOWN",
                "confidence_raw": str(conf) if conf is not None else None,
                "confidence_numeric": conf if conf is not None else CONFIDENCE_DEFAULT,
                "has_source": bool(source_text),
                "has_citation": has_citation,
                "source_text": source_text,
            })

    # --- Strategy 2: Blockquote claims (Format 1) ---
    # Split by blockquote claim markers: > **[ID]** claim_id: ID
    bq_pattern = re.compile(
        r'(?:^>.*\n)+',  # consecutive blockquote lines
        re.MULTILINE,
    )
    for bq_match in bq_pattern.finditer(content):
        block = bq_match.group(0)
        ids = CLAIM_ID_INLINE_RE.findall(block)
        if not ids:
            continue
        claim_id = ids[0]
        if claim_id in seen_ids:
            continue
        seen_ids.add(claim_id)

        raw_type = extract_claim_type(block)
        conf = extract_confidence_numeric(block)
        source_match = _SOURCE_RE.search(block)
        source_text = source_match.group(1).strip()[:200] if source_match else ""
        has_citation = bool(CITATION_YEAR_RE.search(source_text)) if source_text else False

        claims.append({
            "claim_id": claim_id,
            "claim_type": raw_type,
            "canonical_type": canonicalize_claim_type(raw_type) if raw_type else "UNKNOWN",
            "confidence_raw": str(conf) if conf is not None else None,
            "confidence_numeric": conf if conf is not None else CONFIDENCE_DEFAULT,
            "has_source": bool(source_text),
            "has_citation": has_citation,
            "source_text": source_text,
        })

    return claims
