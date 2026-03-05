#!/usr/bin/env python3
"""Validate SRCS scores against threshold.

Checks that SRCS (Source-Rigor-Confidence-Specificity) 4-axis scores
meet the minimum threshold of 75 for thesis quality assurance.

Usage:
  python3 validate_srcs_threshold.py --report <srcs-report.json>
  python3 validate_srcs_threshold.py --claim-file <claim-file.md>
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Import from checklist_manager — single source of truth for thesis constants.
# NOTE: This is a thesis-internal import, NOT a system SOT reference (R6 safe).
from checklist_manager import SRCS_WEIGHTS, SRCS_THRESHOLD


def compute_weighted_srcs(scores: dict, claim_type: str = "EMPIRICAL") -> float:
    """Compute weighted SRCS score.

    Args:
        scores: dict with CS, GS, US, VS keys (each 0-100)
        claim_type: claim type for weight selection

    Returns:
        Weighted SRCS score (0-100)
    """
    weights = SRCS_WEIGHTS.get(claim_type, SRCS_WEIGHTS["EMPIRICAL"])

    total = 0.0
    for axis in ("CS", "GS", "US", "VS"):
        score = scores.get(axis, 0)
        if not isinstance(score, (int, float)) or score < 0 or score > 100:
            raise ValueError(f"Invalid {axis} score: {score} (must be 0-100)")
        total += score * weights[axis]

    return round(total, 2)


def validate_scores(scores: dict, claim_type: str = "EMPIRICAL") -> dict:
    """Validate SRCS scores against threshold.

    Returns dict with:
      - weighted_score: computed weighted SRCS
      - threshold: the threshold value
      - passed: bool
      - below_threshold_axes: list of axes below individual threshold
    """
    weighted = compute_weighted_srcs(scores, claim_type)

    below = []
    for axis in ("CS", "GS", "US", "VS"):
        if scores.get(axis, 0) < 50:  # Individual axis minimum
            below.append(axis)

    return {
        "weighted_score": weighted,
        "threshold": SRCS_THRESHOLD,
        "passed": weighted >= SRCS_THRESHOLD,
        "below_threshold_axes": below,
        "claim_type": claim_type,
    }


def validate_report(report_path: str) -> int:
    """Validate an SRCS report JSON file."""
    path = Path(report_path)
    if not path.exists():
        print(f"ERROR: Report not found: {report_path}", file=sys.stderr)
        return 1

    with open(path, "r", encoding="utf-8") as f:
        report = json.load(f)

    claims = report.get("claims", [])
    if not claims:
        print("WARNING: No claims found in report")
        return 0

    failed = []
    for claim in claims:
        claim_id = claim.get("id", "unknown")
        claim_type = claim.get("claim_type", "EMPIRICAL")
        scores = claim.get("srcs_scores", {})

        try:
            result = validate_scores(scores, claim_type)
        except ValueError as e:
            print(f"ERROR: Claim {claim_id}: {e}", file=sys.stderr)
            failed.append(claim_id)
            continue

        if not result["passed"]:
            failed.append(claim_id)
            print(
                f"BELOW THRESHOLD: Claim {claim_id} "
                f"(type={claim_type}, score={result['weighted_score']}, "
                f"threshold={SRCS_THRESHOLD})"
            )

    if failed:
        print(f"\n{len(failed)} claim(s) below SRCS threshold of {SRCS_THRESHOLD}")
        return 1

    print(f"All {len(claims)} claim(s) meet SRCS threshold of {SRCS_THRESHOLD}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="SRCS Threshold Validator")
    parser.add_argument("--report", help="Path to SRCS report JSON")
    args = parser.parse_args()

    if args.report:
        return validate_report(args.report)

    print("Usage: validate_srcs_threshold.py --report <srcs-report.json>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
