#!/usr/bin/env python3
"""Validate GroundedClaim schema compliance in thesis output files.

PostToolUse Hook — validates that Write operations targeting thesis wave-results
produce output conforming to the GroundedClaim schema (GRA Layer 1).

Environment variables:
  CLAUDE_TOOL_NAME     — "Write"
  CLAUDE_TOOL_INPUT    — JSON with file_path and content
  CLAUDE_PROJECT_DIR   — project root
"""

import json
import os
import re
import sys
from pathlib import Path

from _claim_patterns import (  # noqa: E402
    BLOCKED_CLAIM_PATTERNS,
    CLAIM_ID_VALIDATE_RE,
    REQUIRE_SOURCE_PATTERNS,
    extract_claim_ids,
)

# Thesis output directory pattern
THESIS_OUTPUT_DIR = "thesis-output"
WAVE_RESULTS_DIR = "wave-results"

# Valid claim types for GRA authoring validation (workflow.md GRA spec).
# Note: This is DIFFERENT from _claim_patterns.CANONICAL_CLAIM_TYPES (7 types
# including UNKNOWN). VALID_CLAIM_TYPES defines what types agents SHOULD write.
# CANONICAL_CLAIM_TYPES defines what types exist in the pCCS scoring system
# (includes UNKNOWN as a fallback for unmapped types like ANALYTICAL, THEOLOGICAL).
VALID_CLAIM_TYPES = {
    "FACTUAL", "EMPIRICAL", "THEORETICAL",
    "METHODOLOGICAL", "INTERPRETIVE", "SPECULATIVE",
}

# Minimum confidence by claim type
MIN_CONFIDENCE = {
    "FACTUAL": 95,
    "EMPIRICAL": 85,
    "THEORETICAL": 75,
    "METHODOLOGICAL": 80,
    "INTERPRETIVE": 70,
    "SPECULATIVE": 60,
}

# Claim ID validation — imported from _claim_patterns (centralized)
CLAIM_ID_PATTERN = CLAIM_ID_VALIDATE_RE


def is_wave_result_file(file_path: str, project_dir: str) -> bool:
    """Check if the file is a thesis wave result."""
    try:
        rel = os.path.relpath(file_path, project_dir)
    except ValueError:
        return False
    parts = Path(rel).parts
    return (
        len(parts) >= 4
        and parts[0] == THESIS_OUTPUT_DIR
        and WAVE_RESULTS_DIR in parts
        and parts[-1].endswith(".md")
    )


def validate_claim_block(text: str) -> list[str]:
    """Validate GroundedClaim YAML blocks in the document.
    Returns list of warnings (not errors — informational).
    """
    warnings = []

    # Check for Hallucination Firewall violations (centralized patterns)
    for compiled_re in BLOCKED_CLAIM_PATTERNS:
        matches = compiled_re.findall(text)
        if matches:
            warnings.append(
                f"FIREWALL BLOCK: Pattern '{matches[0]}' detected. "
                f"Absolute claims must be softened or removed."
            )

    # Check for statistical claims without sources (centralized patterns)
    for compiled_re in REQUIRE_SOURCE_PATTERNS:
        matches = compiled_re.finditer(text)
        for match in matches:
            # Look for a source reference nearby (within 200 chars)
            start = max(0, match.start() - 200)
            end = min(len(text), match.end() + 200)
            context = text[start:end]
            if not re.search(r"\(\d{4}\)|doi:|DOI:", context):
                warnings.append(
                    f"REQUIRE_SOURCE: Statistical claim '{match.group()}' "
                    f"found without nearby citation."
                )

    # Check for claim ID format in YAML blocks (centralized pattern)
    claim_ids = extract_claim_ids(text)
    for cid in claim_ids:
        if not CLAIM_ID_PATTERN.match(cid):
            warnings.append(
                f"CLAIM_ID: '{cid}' does not match format PREFIX-NNN "
                f"(e.g., LS-001, TFA-012)"
            )

    # Check for claim type validity
    claim_types = re.findall(r'claim_type:\s*["\']?(\w+)["\']?', text)
    for ct in claim_types:
        if ct not in VALID_CLAIM_TYPES:
            warnings.append(
                f"CLAIM_TYPE: '{ct}' is not a valid claim type. "
                f"Valid: {sorted(VALID_CLAIM_TYPES)}"
            )

    # Check confidence values
    confidences = re.findall(r'confidence:\s*(\d+)', text)
    for conf_str in confidences:
        conf = int(conf_str)
        if conf < 0 or conf > 100:
            warnings.append(f"CONFIDENCE: Value {conf} out of range [0, 100]")

    # H2: Cross-validate claim_type vs confidence (P1 deterministic)
    # SPECULATIVE claims should not have high confidence; each type has a ceiling.
    # Match claim_type and confidence within 4 lines (same YAML block, no DOTALL)
    ct_conf_pairs = re.findall(
        r'claim_type:\s*["\']?(\w+)["\']?[^\n]*\n(?:[^\n]*\n){0,3}[^\n]*confidence:\s*(\d+)',
        text,
    )
    for ct, conf_str in ct_conf_pairs:
        conf = int(conf_str)
        max_conf = MIN_CONFIDENCE.get(ct)
        if max_conf is not None and conf > max_conf:
            warnings.append(
                f"CONFIDENCE_CEILING: {ct} claim has confidence={conf}, "
                f"max allowed for {ct}={max_conf}. "
                f"Reduce confidence or change claim_type."
            )

    return warnings


def main():
    tool_name = os.environ.get("CLAUDE_TOOL_NAME", "")
    if tool_name != "Write":
        return 0

    tool_input_raw = os.environ.get("CLAUDE_TOOL_INPUT", "{}")
    try:
        tool_input = json.loads(tool_input_raw)
    except json.JSONDecodeError:
        return 0

    file_path = tool_input.get("file_path", "")
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")

    if not file_path or not project_dir:
        return 0

    if not is_wave_result_file(file_path, project_dir):
        return 0  # Not a wave result file — skip

    # Read the content that was written
    content = tool_input.get("content", "")
    if not content:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except (FileNotFoundError, OSError):
            return 0

    warnings = validate_claim_block(content)

    if warnings:
        print("GRA VALIDATION WARNINGS:")
        for w in warnings:
            print(f"  - {w}")
        # Warnings only — do not block (exit 0)

    return 0


if __name__ == "__main__":
    sys.exit(main())
