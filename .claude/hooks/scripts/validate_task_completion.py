#!/usr/bin/env python3
"""Validate thesis task completion — L0 Anti-Skip Guard for thesis outputs.

Verifies that a task's output file exists, is non-empty, and meets
minimum size requirements before allowing step advancement.

Usage:
  python3 validate_task_completion.py --file <output-file> [--min-size 100]
"""

import argparse
import os
import sys
from pathlib import Path

# Default minimum output size (aligned with _context_lib.py MIN_OUTPUT_SIZE)
DEFAULT_MIN_SIZE = 100


def validate_output(file_path: str, min_size: int = DEFAULT_MIN_SIZE) -> dict:
    """Validate a thesis output file.

    Returns dict with:
      - exists: bool
      - size: int (bytes)
      - non_empty: bool (has non-whitespace content)
      - meets_min_size: bool
      - passed: bool (all checks pass)
      - errors: list of error strings
    """
    path = Path(file_path)
    errors = []

    exists = path.exists()
    if not exists:
        return {
            "exists": False,
            "size": 0,
            "non_empty": False,
            "meets_min_size": False,
            "passed": False,
            "errors": [f"File does not exist: {file_path}"],
        }

    size = path.stat().st_size

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        return {
            "exists": True,
            "size": size,
            "non_empty": False,
            "meets_min_size": False,
            "passed": False,
            "errors": [f"Cannot read file: {e}"],
        }

    non_empty = len(content.strip()) > 0
    meets_min = size >= min_size

    if not non_empty:
        errors.append("File is empty or contains only whitespace")
    if not meets_min:
        errors.append(f"File size ({size} bytes) below minimum ({min_size} bytes)")

    return {
        "exists": True,
        "size": size,
        "non_empty": non_empty,
        "meets_min_size": meets_min,
        "passed": non_empty and meets_min,
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(description="Thesis Task Completion Validator")
    parser.add_argument("--file", required=True, help="Output file to validate")
    parser.add_argument("--min-size", type=int, default=DEFAULT_MIN_SIZE,
                        help=f"Minimum file size in bytes (default: {DEFAULT_MIN_SIZE})")
    args = parser.parse_args()

    result = validate_output(args.file, args.min_size)

    if result["passed"]:
        print(f"PASS: {args.file} ({result['size']} bytes)")
        return 0
    else:
        print(f"FAIL: {args.file}")
        for err in result["errors"]:
            print(f"  - {err}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
