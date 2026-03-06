"""Centralized Claim ID patterns — single source of truth for all claim regex.

All scripts that need to find, count, or validate GroundedClaim IDs
MUST import from this module. Never define claim ID regex inline.

Supported formats:
  - Simple:      LS-001, GI-007, CMB-014
  - Multi-hyphen: EMP-NEURO-001, CR-LOGIC-001, MC-IV-002
  - Blockquote:   claim_id: PHIL-T001
  - YAML inline:  id: SYNTH-004
  - Quoted:       id: "LS-001", id: 'CMB-007'
  - Bold bracket: **[PHIL-T001]** claim_id: PHIL-T001
"""

import re

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
