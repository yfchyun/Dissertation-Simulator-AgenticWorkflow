#!/usr/bin/env python3
"""validate_pccs_assessment.py — Phase C: P1 Validation for LLM Assessments.

Validates LLM-produced assessment/critic JSON from Phase B-1/B-2.
Ensures claim IDs exist in claim-map, scores are in valid ranges,
and required fields are present.

Used at two handoff points:
  Phase B-1 → C-1: Validates @claim-quality-evaluator output
  Phase B-2 → C-2: Validates @claim-quality-critic output

Checks:
  CA1: All claim IDs in assessment exist in claim-map
  CA2: Quality scores in valid range [0, 100]
  CA3: Required fields present per assessment entry
  CA4: At least 1 assessment entry (non-empty output)
  CA5: No duplicate claim IDs in assessment
  CA6: (evaluator only) Sub-score fields present
  CA7: (evaluator only) Each sub-score in [0, 25]
  CA8: (evaluator only) quality_score == sum(sub-scores)

Usage:
  # Validate evaluator output (B-1 → C-1)
  python3 validate_pccs_assessment.py \\
    --assessment pccs-assessment.json \\
    --claim-map claim-map.json \\
    --mode evaluator

  # Validate critic output (B-2 → C-2)
  python3 validate_pccs_assessment.py \\
    --assessment pccs-critic.json \\
    --claim-map claim-map.json \\
    --mode critic

Exit codes:
  0 — always (P1 compliant, non-blocking)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any


# Required fields per mode
_EVALUATOR_REQUIRED = {"claim_id", "quality_score"}
_CRITIC_REQUIRED = {"claim_id", "adjusted_score"}

# Evaluator sub-score fields (each 0-25, sum = quality_score)
_EVALUATOR_SUB_SCORES = (
    "specificity", "evidence_alignment", "logical_soundness", "contribution"
)


def validate_assessment(
    assessment: dict[str, Any],
    claim_map: dict[str, Any],
    mode: str,
) -> dict[str, Any]:
    """Validate LLM assessment output against claim-map.

    Args:
        assessment: Parsed JSON from evaluator or critic.
        claim_map: Parsed claim-map.json from Phase A.
        mode: "evaluator" or "critic".

    Returns:
        {"passed": bool, "checks": [...], "errors": [...], "warnings": [...]}
    """
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []

    # Determine entry list and required fields
    if mode == "evaluator":
        entries = assessment.get("assessments", [])
        required = _EVALUATOR_REQUIRED
        score_field = "quality_score"
    else:
        entries = assessment.get("judgments", [])
        required = _CRITIC_REQUIRED
        score_field = "adjusted_score"

    # Build valid claim ID set from claim-map
    valid_ids = {c["claim_id"] for c in claim_map.get("claims", [])}

    # CA1: Claim ID existence
    ca1_pass = True
    for entry in entries:
        cid = entry.get("claim_id", "")
        if cid and cid not in valid_ids:
            errors.append(f"CA1: claim_id '{cid}' not found in claim-map")
            ca1_pass = False
    checks.append({"id": "CA1", "name": "Claim ID existence", "passed": ca1_pass})

    # CA2: Score range [0, 100]
    ca2_pass = True
    for entry in entries:
        score = entry.get(score_field)
        if score is not None and not (0 <= score <= 100):
            cid = entry.get("claim_id", "?")
            errors.append(f"CA2: {cid} {score_field}={score} out of [0,100]")
            ca2_pass = False
    checks.append({"id": "CA2", "name": "Score range", "passed": ca2_pass})

    # CA3: Required fields
    ca3_pass = True
    for i, entry in enumerate(entries):
        missing = required - set(entry.keys())
        if missing:
            errors.append(f"CA3: Entry {i} missing fields: {sorted(missing)}")
            ca3_pass = False
    checks.append({"id": "CA3", "name": "Required fields", "passed": ca3_pass})

    # CA4: Non-empty
    ca4_pass = len(entries) >= 1
    checks.append({"id": "CA4", "name": "Non-empty output", "passed": ca4_pass})
    if not ca4_pass:
        warnings.append(f"CA4: No {mode} entries found (degraded mode — P1-only scoring)")

    # CA5: No duplicate claim IDs
    ca5_pass = True
    seen: set[str] = set()
    for entry in entries:
        cid = entry.get("claim_id", "")
        if cid in seen:
            errors.append(f"CA5: Duplicate claim_id in assessment: {cid}")
            ca5_pass = False
        seen.add(cid)
    checks.append({"id": "CA5", "name": "Unique claim IDs", "passed": ca5_pass})

    # CA6-CA8: Evaluator sub-score validation (evaluator mode only)
    if mode == "evaluator":
        # CA6: Sub-score fields present
        ca6_pass = True
        for i, entry in enumerate(entries):
            for sf in _EVALUATOR_SUB_SCORES:
                if sf not in entry:
                    warnings.append(f"CA6: Entry {i} ({entry.get('claim_id', '?')}) "
                                    f"missing sub-score '{sf}'")
                    ca6_pass = False
        checks.append({"id": "CA6", "name": "Sub-score fields present", "passed": ca6_pass})

        # CA7: Each sub-score in [0, 25]
        ca7_pass = True
        for entry in entries:
            cid = entry.get("claim_id", "?")
            for sf in _EVALUATOR_SUB_SCORES:
                val = entry.get(sf)
                if val is not None and not (0 <= val <= 25):
                    errors.append(f"CA7: {cid} {sf}={val} out of [0,25]")
                    ca7_pass = False
        checks.append({"id": "CA7", "name": "Sub-score range [0,25]", "passed": ca7_pass})

        # CA8: quality_score == sum(sub-scores)
        ca8_pass = True
        for entry in entries:
            cid = entry.get("claim_id", "?")
            qs = entry.get("quality_score")
            sub_vals = [entry.get(sf) for sf in _EVALUATOR_SUB_SCORES]
            if qs is not None and all(v is not None for v in sub_vals):
                expected = sum(sub_vals)
                if qs != expected:
                    errors.append(
                        f"CA8: {cid} quality_score={qs} != sum(sub-scores)={expected}"
                    )
                    ca8_pass = False
        checks.append({"id": "CA8", "name": "Score sum consistency", "passed": ca8_pass})

    return {
        "passed": len(errors) == 0,
        "mode": mode,
        "entries_count": len(entries),
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="pCCS Phase C: P1 Validation for LLM Assessments"
    )
    parser.add_argument(
        "--assessment", required=True,
        help="Assessment/critic JSON file to validate"
    )
    parser.add_argument(
        "--claim-map", required=True,
        help="claim-map.json from Phase A"
    )
    parser.add_argument(
        "--mode", required=True, choices=["evaluator", "critic"],
        help="Validation mode: evaluator (B-1→C-1) or critic (B-2→C-2)"
    )
    parser.add_argument(
        "--output",
        help="Output validation JSON (default: stdout)"
    )
    args = parser.parse_args()

    # Load files
    try:
        with open(args.assessment, "r", encoding="utf-8") as f:
            assessment = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        assessment = {"assessments": [], "judgments": []}
        print(f"[validate_pccs_assessment] WARNING: Cannot load assessment: {e}",
              file=sys.stderr)

    try:
        with open(args.claim_map, "r", encoding="utf-8") as f:
            claim_map = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        claim_map = {"claims": []}
        print(f"[validate_pccs_assessment] WARNING: Cannot load claim-map: {e}",
              file=sys.stderr)

    result = validate_assessment(assessment, claim_map, args.mode)

    json_str = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        out_dir = os.path.dirname(os.path.abspath(args.output))
        os.makedirs(out_dir, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_str)

    status = "PASS" if result["passed"] else "FAIL"
    checks_str = ", ".join(
        f"{c['id']}:{'OK' if c['passed'] else 'FAIL'}" for c in result["checks"]
    )
    print(f"[validate_pccs_assessment] {status} ({args.mode}) — {checks_str}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[validate_pccs_assessment] FATAL: {e}", file=sys.stderr)
    sys.exit(0)  # P1: never block
