#!/usr/bin/env python3
"""Validate thesis output file structure — P1 structural validation.

Ensures output files follow naming conventions, are in correct directories,
and use proper claim prefixes.

Usage:
  python3 validate_thesis_output.py --project-dir <dir> --wave <N>
  python3 validate_thesis_output.py --project-dir <dir> --check-all
"""

import argparse
import json
import os
import sys
from pathlib import Path

from _claim_patterns import extract_claim_ids  # noqa: E402

# Expected output files per wave
WAVE_OUTPUTS = {
    1: [
        "01-literature-search-strategy.md",
        "02-seminal-works-analysis.md",
        "03-research-trend-analysis.md",
        "04-methodology-scan.md",
    ],
    2: [
        "05-theoretical-framework.md",
        "06-empirical-evidence-synthesis.md",
        "07-research-gap-analysis.md",
        "08-variable-relationship-analysis.md",
    ],
    3: [
        "09-critical-review.md",
        "10-methodology-critique.md",
        "11-limitation-analysis.md",
        "12-future-research-directions.md",
    ],
    4: [
        "13-literature-synthesis.md",
        "14-conceptual-model.md",
    ],
    5: [
        "15-plagiarism-report.md",
    ],
}

# Claim prefix per output file
FILE_CLAIM_PREFIXES = {
    "01-literature-search-strategy.md": "LS",
    "02-seminal-works-analysis.md": "SWA",
    "03-research-trend-analysis.md": "TRA",
    "04-methodology-scan.md": "MS",
    "05-theoretical-framework.md": "TFA",
    "06-empirical-evidence-synthesis.md": "EEA",
    "07-research-gap-analysis.md": "GI",
    "08-variable-relationship-analysis.md": "VRA",
    "09-critical-review.md": "CR",
    "10-methodology-critique.md": "MC",
    "11-limitation-analysis.md": "LA",
    "12-future-research-directions.md": "FDA",
    "13-literature-synthesis.md": "SA",
    "14-conceptual-model.md": "CMB",
    "15-plagiarism-report.md": "PC",
}

MIN_OUTPUT_SIZE = 100


def validate_wave(project_dir: str, wave: int) -> dict:
    """Validate all output files for a specific wave.

    Returns:
        dict with passed, errors, warnings
    """
    project = Path(project_dir)
    wave_dir = project / "wave-results" / f"wave-{wave}"
    errors = []
    warnings = []

    expected = WAVE_OUTPUTS.get(wave)
    if expected is None:
        return {"passed": False, "errors": [f"Unknown wave: {wave}"], "warnings": []}

    if not wave_dir.is_dir():
        return {"passed": False, "errors": [f"Wave directory missing: {wave_dir}"], "warnings": []}

    # Detect consolidated output mode: if consolidated files exist instead of
    # individual files, validate those. Consolidated filenames follow pattern:
    # step-NNN-to-NNN-{agent}.md (produced by query_step.py consolidation).
    # H-4: Strict regex — prevents false matches on arbitrary filenames.
    import re
    _CONSOLIDATED_RE = re.compile(r'^step-(\d{3})-to-(\d{3})-([a-z][-a-z]*[a-z])\.md$')
    consolidated_files = sorted(
        f for f in wave_dir.glob("step-*-to-*-*.md")
        if not f.name.endswith(".ko.md") and _CONSOLIDATED_RE.match(f.name)
    )
    if consolidated_files and len(consolidated_files) >= len(expected):
        # Consolidated mode: validate consolidated files instead of individual ones
        for cfile in consolidated_files:
            size = cfile.stat().st_size
            if size < MIN_OUTPUT_SIZE:
                errors.append(f"TO-L0: {cfile.name} too small ({size} bytes < {MIN_OUTPUT_SIZE})")
            else:
                try:
                    content = cfile.read_text(encoding="utf-8")
                    claim_ids = extract_claim_ids(content)
                    if not claim_ids:
                        warnings.append(f"TO3: {cfile.name} has no GroundedClaim IDs")
                    elif claim_ids:
                        # TO6: Prefix uniformity for consolidated output.
                        # Each consolidated file is produced by a SINGLE agent,
                        # so all claims should share one prefix. Mixed prefixes
                        # suggest claim contamination from a different step/agent.
                        prefixes = set()
                        for cid in claim_ids:
                            prefix = cid.rsplit("-", 1)[0]
                            prefixes.add(prefix)
                        if len(prefixes) > 1:
                            warnings.append(
                                f"TO6: {cfile.name} has {len(prefixes)} distinct "
                                f"claim prefixes {sorted(prefixes)} — expected 1 "
                                f"(single agent per consolidated file)"
                            )

                    # TO5: Per-step heading validation for consolidated output.
                    # generate_consolidated_prompt() requires "## Step N:" headings.
                    # Without them, per-step traceability is lost.
                    m = _CONSOLIDATED_RE.match(cfile.name)
                    if m:
                        first_s = int(m.group(1))
                        last_s = int(m.group(2))
                        for step_n in range(first_s, last_s + 1):
                            # Check for ## Step N (with optional colon and description)
                            heading_pattern = re.compile(
                                rf'^##\s+Step\s+{step_n}\b', re.MULTILINE,
                            )
                            if not heading_pattern.search(content):
                                warnings.append(
                                    f"TO5: {cfile.name} missing heading for Step {step_n} "
                                    f"(expected '## Step {step_n}: ...')"
                                )
                except Exception as exc:
                    warnings.append(f"TO-READ: Cannot read {cfile.name}: {exc}")
        return {"passed": len(errors) == 0, "errors": errors, "warnings": warnings}

    for filename in expected:
        filepath = wave_dir / filename
        # TO1: File exists with correct name
        if not filepath.exists():
            errors.append(f"TO1: Missing file: {filename}")
            continue

        # TO2: File in correct directory
        if filepath.parent.name != f"wave-{wave}":
            errors.append(f"TO2: {filename} in wrong directory: {filepath.parent}")

        # L0: Minimum size
        size = filepath.stat().st_size
        if size < MIN_OUTPUT_SIZE:
            errors.append(f"TO-L0: {filename} too small ({size} bytes < {MIN_OUTPUT_SIZE})")

        # TO3: Claim prefix consistency
        expected_prefix = FILE_CLAIM_PREFIXES.get(filename)
        if expected_prefix:
            try:
                content = filepath.read_text(encoding="utf-8")
                claim_ids = extract_claim_ids(content)
                for cid in claim_ids:
                    prefix = cid.rsplit("-", 1)[0]
                    if prefix != expected_prefix:
                        warnings.append(
                            f"TO3: {filename} has claim '{cid}' with prefix '{prefix}', "
                            f"expected '{expected_prefix}'"
                        )
            except Exception:
                pass

        # TO4: Check for Korean translation pair
        ko_file = wave_dir / filename.replace(".md", ".ko.md")
        if not ko_file.exists():
            warnings.append(f"TO4: Missing Korean translation: {ko_file.name}")

    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def validate_all(project_dir: str) -> int:
    """Validate all waves."""
    all_passed = True
    for wave in range(1, 6):
        result = validate_wave(project_dir, wave)
        status = "PASS" if result["passed"] else "FAIL"
        print(f"Wave {wave}: {status}")
        for err in result["errors"]:
            print(f"  ERROR: {err}")
        for warn in result["warnings"]:
            print(f"  WARN: {warn}")
        if not result["passed"]:
            all_passed = False

    return 0 if all_passed else 1


def main():
    parser = argparse.ArgumentParser(description="Thesis Output Structure Validator")
    parser.add_argument("--project-dir", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--wave", type=int, help="Validate specific wave (1-5)")
    group.add_argument("--check-all", action="store_true", help="Validate all waves")
    args = parser.parse_args()

    if args.check_all:
        return validate_all(args.project_dir)
    else:
        result = validate_wave(args.project_dir, args.wave)
        status = "PASS" if result["passed"] else "FAIL"
        print(f"Wave {args.wave}: {status}")
        for err in result["errors"]:
            print(f"  ERROR: {err}")
        for warn in result["warnings"]:
            print(f"  WARN: {warn}")
        return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
