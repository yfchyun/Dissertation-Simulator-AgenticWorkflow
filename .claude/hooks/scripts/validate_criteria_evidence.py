#!/usr/bin/env python3
"""
Verification Evidence P1 Validation — validate_criteria_evidence.py

Deterministic cross-check of verification log claims against actual output files.
Detects hallucinated evidence by reading the output file and mechanically verifying
claims that CAN be verified by Python code (regex, counting, string matching).

This is the P1 hallucination prevention layer for the Verification Gate — it does
NOT trust the agent's self-reported evidence; it reads the actual output and checks.

Usage:
    python3 validate_criteria_evidence.py \
      --step 3 --project-dir . --output-file research/analysis.md

    python3 validate_criteria_evidence.py \
      --step 3 --project-dir . --auto-detect

Output: JSON to stdout
    {
      "step": 3,
      "total_criteria": 5,
      "verifiable_criteria": 3,
      "verified": 3,
      "results": [
        {"criterion": "...", "type": "VE1", "agent_result": "PASS",
         "p1_result": "PASS", "status": "CONFIRMED", "detail": "..."},
        ...
      ],
      "hallucinations_detected": 0,
      "passed": true,
      "warnings": []
    }

Exit codes:
    0 — always (non-blocking, P1 compliant)

Architecture:
    - Pure Python, stdlib only (no external dependencies)
    - Deterministic: same input → same output, every time
    - P1 Compliance: zero heuristic inference, zero LLM
    - SOT Compliance: read-only (reads verification-logs/ + output files)
    - Pattern: same as verify_translation_terms.py (T10-T12)
"""

import argparse
import json
import os
import re
import sys

# Add script directory to path for shared library import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _claim_patterns import TRACE_MARKER_RE  # noqa: E402


# =============================================================================
# Verifiable Criterion Patterns (VE1-VE5)
# =============================================================================

# VE1: Section/heading count — "N개 섹션", "≥ N sections", "N+ headings"
_VE1_HEADING_COUNT_RE = re.compile(
    r"(?:≥\s*|>=\s*|최소\s*|at\s+least\s+|min(?:imum)?\s+)?(\d+)\s*개?\s*"
    r"(?:이상\s*)?(?:섹션|section|heading|헤딩|장|chapter)",
    re.IGNORECASE,
)

# VE2: Placeholder/invalid URL absence — "placeholder 없음", "no placeholder"
_VE2_NO_PLACEHOLDER_RE = re.compile(
    r"(?:placeholder|example\.com|TODO|TBD|FIXME|Lorem\s+ipsum).*"
    r"(?:없음|없어야|no |absent|zero|forbidden)",
    re.IGNORECASE,
)
_VE2_NO_PLACEHOLDER_ALT_RE = re.compile(
    r"(?:no |없음|zero |without ).*"
    r"(?:placeholder|example\.com|TODO|TBD|FIXME)",
    re.IGNORECASE,
)
# Patterns to detect in output file (should NOT be present)
_VE2_PLACEHOLDER_PATTERNS = [
    re.compile(r"example\.com", re.IGNORECASE),
    re.compile(r"\bplaceholder\b", re.IGNORECASE),
    re.compile(r"\bTODO\b"),
    re.compile(r"\bTBD\b"),
    re.compile(r"\bFIXME\b"),
    re.compile(r"Lorem\s+ipsum", re.IGNORECASE),
]

# VE3: Item/row/element count — "≥ N 항목", "N+ items/rows"
_VE3_ITEM_COUNT_RE = re.compile(
    r"(?:≥\s*|>=\s*|최소\s*|at\s+least\s+|min(?:imum)?\s+)?(\d+)\s*개?\s*"
    r"(?:이상\s*)?(?:항목|item|행|row|요소|element|건|개|곳|데이터|data|"
    r"경쟁사|competitor|소스|source|출처|reference|인사이트|insight)",
    re.IGNORECASE,
)

# VE4: Trace marker count — "[trace:step-N] ≥ 3"
_VE4_TRACE_COUNT_RE = re.compile(
    r"\[trace:step-(?:\d+|N)\].*(?:≥\s*|>=\s*|최소\s*|at\s+least\s+)(\d+)",
    re.IGNORECASE,
)
_VE4_TRACE_COUNT_ALT_RE = re.compile(
    r"(?:≥\s*|>=\s*|최소\s*|at\s+least\s+)(\d+)\s*개?\s*"
    r"(?:이상\s*)?.*\[?trace",
    re.IGNORECASE,
)
# Also match "마커 ≥ N개" after trace reference
_VE4_TRACE_MARKER_COUNT_RE = re.compile(
    r"trace.*마커\s*(?:≥\s*|>=\s*)?(\d+)\s*개",
    re.IGNORECASE,
)
_VE4_TRACE_MARKER_RE = TRACE_MARKER_RE  # centralized from _claim_patterns

# VE5: Specific field/keyword presence — "필드 포함", "contains fields (x, y)"
_VE5_FIELD_PRESENCE_RE = re.compile(
    r"(?:포함|contains?|includes?|존재|present|있어야)\s+"
    r"(?:fields?\s+)?[\(（]\s*([a-zA-Z_][a-zA-Z0-9_, ]+)\s*[\)）]",
    re.IGNORECASE,
)
_VE5_FIELD_LIST_RE = re.compile(
    r"(?:필드|fields?|키워드|keyword)\s*[\(（]\s*"
    r"([a-zA-Z_][a-zA-Z0-9_,\s]+)\s*[\)）].*(?:포함|contain|include|present)",
    re.IGNORECASE,
)
# Alt: "포함" or "contains" BEFORE the field list
_VE5_FIELD_PRESENCE_ALT_RE = re.compile(
    r"[\(（]\s*([a-zA-Z_][a-zA-Z0-9_, ]+)\s*[\)）]\s*"
    r"(?:포함|contain|include|present|존재)",
    re.IGNORECASE,
)


# =============================================================================
# Verification Log Parsing
# =============================================================================

# Same regex as _context_lib.py — parse criterion + result + evidence from table
_CRITERION_TABLE_RE = re.compile(
    r"^\|\s*([^|]+?)\s*\|\s*(PASS|FAIL)[^|]*\|\s*([^|]*?)\s*\|",
    re.MULTILINE | re.IGNORECASE,
)

_TABLE_HEADER_WORDS = frozenset({
    "criterion", "criteria", "check", "기준", "항목",
    "dimension", "result", "evidence", "#", "---", "status",
    "retries", "no", "no.",
})


def parse_verification_log(verify_path: str) -> list[dict[str, str]]:
    """Parse verification log to extract criteria with results and evidence.

    Returns list of dicts: [{"name": str, "result": str, "evidence": str}]
    """
    if not os.path.exists(verify_path):
        return []

    try:
        with open(verify_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (IOError, UnicodeDecodeError):
        return []

    criteria = []
    for match in _CRITERION_TABLE_RE.finditer(content):
        name = match.group(1).strip()
        if name.lower().rstrip("-") in _TABLE_HEADER_WORDS:
            continue
        if name.startswith("-"):
            continue
        result = match.group(2).upper()
        evidence = match.group(3).strip().replace("\\|", "|")
        criteria.append({
            "name": name,
            "result": result,
            "evidence": evidence,
        })
    return criteria


# =============================================================================
# VE1-VE5 Verification Functions
# =============================================================================

def check_ve1_heading_count(criterion_text: str, output_content: str) -> dict[str, str] | None:
    """VE1: Verify heading/section count in output file.

    P1: regex counting — deterministic.
    """
    match = _VE1_HEADING_COUNT_RE.search(criterion_text)
    if not match:
        return None  # Not a VE1-type criterion

    expected_min = int(match.group(1))
    # Count markdown headings (## level and above)
    headings = re.findall(r"^#{1,6}\s+.+$", output_content, re.MULTILINE)
    actual_count = len(headings)

    passed = actual_count >= expected_min
    return {
        "type": "VE1",
        "detail": f"headings found: {actual_count}, required: >= {expected_min}",
        "p1_result": "PASS" if passed else "FAIL",
    }


def check_ve2_no_placeholder(criterion_text: str, output_content: str) -> dict[str, str] | None:
    """VE2: Verify absence of placeholder/invalid URLs in output file.

    P1: regex search — deterministic.
    """
    if not (_VE2_NO_PLACEHOLDER_RE.search(criterion_text)
            or _VE2_NO_PLACEHOLDER_ALT_RE.search(criterion_text)):
        return None  # Not a VE2-type criterion

    found_placeholders = []
    for pattern in _VE2_PLACEHOLDER_PATTERNS:
        matches = pattern.findall(output_content)
        if matches:
            found_placeholders.extend(matches[:3])  # Limit to 3 per pattern

    passed = len(found_placeholders) == 0
    detail = "no placeholders found" if passed else (
        f"placeholders found: {', '.join(found_placeholders[:5])}"
    )
    return {
        "type": "VE2",
        "detail": detail,
        "p1_result": "PASS" if passed else "FAIL",
    }


def check_ve3_item_count(criterion_text: str, output_content: str) -> dict[str, str] | None:
    """VE3: Verify item/row/element count in output file.

    P1: regex counting of list items + table rows — deterministic.
    """
    match = _VE3_ITEM_COUNT_RE.search(criterion_text)
    if not match:
        return None  # Not a VE3-type criterion

    expected_min = int(match.group(1))

    # Count items: markdown list items + table data rows
    list_items = re.findall(r"^[-*+]\s+.+$", output_content, re.MULTILINE)
    # Table rows: lines starting with | that are not headers/separators
    table_rows = [
        line for line in output_content.split("\n")
        if line.strip().startswith("|")
        and not re.match(r"^\|\s*[-:]+", line.strip())  # Skip separator
        and not re.match(r"^\|\s*#", line.strip())  # Skip header-like
    ]
    # Exclude likely header row (first table row)
    if len(table_rows) > 1:
        table_data_rows = table_rows[1:]  # Skip header
    else:
        table_data_rows = table_rows

    # Use whichever count is higher (document may use either format)
    actual_count = max(len(list_items), len(table_data_rows))

    passed = actual_count >= expected_min
    return {
        "type": "VE3",
        "detail": (f"items found: {actual_count} "
                   f"(list: {len(list_items)}, table: {len(table_data_rows)}), "
                   f"required: >= {expected_min}"),
        "p1_result": "PASS" if passed else "FAIL",
    }


def check_ve4_trace_markers(criterion_text: str, output_content: str) -> dict[str, str] | None:
    """VE4: Verify [trace:step-N] marker count in output file.

    P1: regex counting — deterministic.
    """
    match = _VE4_TRACE_COUNT_RE.search(criterion_text)
    if not match:
        match = _VE4_TRACE_COUNT_ALT_RE.search(criterion_text)
    if not match:
        match = _VE4_TRACE_MARKER_COUNT_RE.search(criterion_text)
    if not match:
        return None  # Not a VE4-type criterion

    expected_min = int(match.group(1))
    markers = _VE4_TRACE_MARKER_RE.findall(output_content)
    actual_count = len(markers)

    passed = actual_count >= expected_min
    return {
        "type": "VE4",
        "detail": f"trace markers found: {actual_count}, required: >= {expected_min}",
        "p1_result": "PASS" if passed else "FAIL",
    }


def check_ve5_field_presence(criterion_text: str, output_content: str) -> dict[str, str] | None:
    """VE5: Verify specific field/keyword presence in output file.

    P1: string search — deterministic.
    """
    match = _VE5_FIELD_LIST_RE.search(criterion_text)
    if not match:
        match = _VE5_FIELD_PRESENCE_RE.search(criterion_text)
    if not match:
        match = _VE5_FIELD_PRESENCE_ALT_RE.search(criterion_text)
    if not match:
        return None  # Not a VE5-type criterion

    raw_fields = match.group(1).strip()
    # Split by comma or whitespace to get individual field names
    fields = [f.strip() for f in re.split(r"[,\s]+", raw_fields) if f.strip()]
    # Filter out common words that aren't field names
    _SKIP_WORDS = {"the", "a", "an", "all", "each", "every", "and", "or",
                   "are", "is", "be", "has", "have", "포함", "모두", "각"}
    fields = [f for f in fields if f.lower() not in _SKIP_WORDS and len(f) > 1]

    if not fields:
        return None

    output_lower = output_content.lower()
    missing = [f for f in fields if f.lower() not in output_lower]
    found = [f for f in fields if f.lower() in output_lower]

    passed = len(missing) == 0
    detail = (
        f"fields found: {', '.join(found)}"
        + (f"; missing: {', '.join(missing)}" if missing else "")
    )
    return {
        "type": "VE5",
        "detail": detail,
        "p1_result": "PASS" if passed else "FAIL",
    }


# All VE checkers in order
_VE_CHECKERS = [
    check_ve1_heading_count,
    check_ve2_no_placeholder,
    check_ve3_item_count,
    check_ve4_trace_markers,
    check_ve5_field_presence,
]


# =============================================================================
# SOT Output Path Detection
# =============================================================================

def detect_output_path(project_dir: str, step_number: int) -> str | None:
    """Auto-detect output file path from SOT (state.yaml) for the given step.

    Reads SOT read-only to find outputs.step-N path.
    Returns absolute path or None.
    """
    sot_candidates = [
        os.path.join(project_dir, ".claude", "state.yaml"),
        os.path.join(project_dir, "state.yaml"),
    ]

    for sot_path in sot_candidates:
        if not os.path.exists(sot_path):
            continue
        try:
            with open(sot_path, "r", encoding="utf-8") as f:
                content = f.read()
        except (IOError, UnicodeDecodeError):
            continue

        # Simple regex extraction — avoid YAML dependency
        # Look for "step-N: path/to/file" or "step-N-en: path/to/file"
        pattern = re.compile(
            rf"step-{step_number}(?:-en)?:\s*['\"]?([^\s'\"#]+)",
            re.MULTILINE,
        )
        match = pattern.search(content)
        if match:
            rel_path = match.group(1).strip()
            abs_path = os.path.join(project_dir, rel_path)
            if os.path.exists(abs_path):
                return abs_path

    return None


# =============================================================================
# Main Validation
# =============================================================================

def validate_criteria_evidence(project_dir: str, step_number: int, output_file: str | None = None) -> dict[str, object]:
    """Cross-check verification log evidence against actual output file.

    P1 Compliance: All checks are regex/string — zero LLM.
    SOT Compliance: Read-only access to verification-logs/, output files, SOT.

    Args:
        project_dir: Project root directory
        step_number: Step number to validate
        output_file: Path to output file (if None, auto-detect from SOT)

    Returns:
        dict with validation results
    """
    warnings = []
    results = []

    # 1. Parse verification log
    verify_path = os.path.join(
        project_dir, "verification-logs", f"step-{step_number}-verify.md"
    )
    criteria = parse_verification_log(verify_path)
    if not criteria:
        return {
            "step": step_number,
            "total_criteria": 0,
            "verifiable_criteria": 0,
            "verified": 0,
            "results": [],
            "hallucinations_detected": 0,
            "passed": True,
            "warnings": ["No criteria found in verification log"],
        }

    # 2. Resolve output file
    abs_output: str | None
    if output_file:
        abs_output = (
            output_file if os.path.isabs(output_file)
            else os.path.join(project_dir, output_file)
        )
    else:
        abs_output = detect_output_path(project_dir, step_number)

    if not abs_output or not os.path.exists(abs_output):
        return {
            "step": step_number,
            "total_criteria": len(criteria),
            "verifiable_criteria": 0,
            "verified": 0,
            "results": [],
            "hallucinations_detected": 0,
            "passed": True,
            "warnings": [
                f"Output file not found"
                + (f": {abs_output}" if abs_output else " (auto-detect failed)")
                + " — skipping evidence cross-check"
            ],
        }

    # 3. Read output file
    try:
        with open(abs_output, "r", encoding="utf-8") as f:
            output_content = f.read()
    except (IOError, UnicodeDecodeError) as e:
        return {
            "step": step_number,
            "total_criteria": len(criteria),
            "verifiable_criteria": 0,
            "verified": 0,
            "results": [],
            "hallucinations_detected": 0,
            "passed": True,
            "warnings": [f"Cannot read output file: {e}"],
        }

    # 4. Run VE1-VE5 checks for each criterion
    hallucinations = 0
    verifiable_count = 0
    skipped_criteria = []  # H6: track non-verifiable criteria

    for c in criteria:
        criterion_text = c["name"]
        agent_result = c["result"]

        # Try each VE checker
        ve_result = None
        for checker in _VE_CHECKERS:
            ve_result = checker(criterion_text, output_content)
            if ve_result is not None:
                break

        if ve_result is None:
            # H6: Track non-verifiable criteria for transparency
            skipped_criteria.append(criterion_text[:80])
            continue

        verifiable_count += 1
        p1_result = ve_result["p1_result"]

        # Cross-check agent claim vs P1 result
        if agent_result == "PASS" and p1_result == "FAIL":
            status = "HALLUCINATION_DETECTED"
            hallucinations += 1
            warnings.append(
                f"{ve_result['type']} FAIL: Agent claimed PASS but P1 check "
                f"shows FAIL for criterion '{criterion_text}' — {ve_result['detail']}"
            )
        elif agent_result == "FAIL" and p1_result == "PASS":
            status = "OVER_CAUTIOUS"
            warnings.append(
                f"{ve_result['type']} INFO: Agent claimed FAIL but P1 check "
                f"shows PASS for criterion '{criterion_text}' — {ve_result['detail']}"
            )
        else:
            status = "CONFIRMED"

        results.append({
            "criterion": criterion_text,
            "type": ve_result["type"],
            "agent_result": agent_result,
            "p1_result": p1_result,
            "status": status,
            "detail": ve_result["detail"],
        })

    # H6: Report verification coverage transparently
    skipped_count = len(skipped_criteria)
    total = len(criteria)
    coverage = f"{verifiable_count}/{total}"

    return {
        "step": step_number,
        "total_criteria": total,
        "verifiable_criteria": verifiable_count,
        "verified": len(results),
        "skipped_count": skipped_count,
        "skipped_criteria": skipped_criteria,
        "verification_coverage": coverage,
        "results": results,
        "hallucinations_detected": hallucinations,
        "passed": hallucinations == 0,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="P1 Evidence Cross-Check for Verification Gate outputs"
    )
    parser.add_argument(
        "--step", type=int, required=True,
        help="Step number to validate"
    )
    parser.add_argument(
        "--project-dir", type=str, default=".",
        help="Project root directory"
    )
    parser.add_argument(
        "--output-file", type=str, default=None,
        help="Path to output file to verify against (relative or absolute)"
    )
    parser.add_argument(
        "--auto-detect", action="store_true",
        help="Auto-detect output file from SOT"
    )
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)

    output_file = args.output_file
    if args.auto_detect and not output_file:
        output_file = None  # Will trigger auto-detect in validate function

    result = validate_criteria_evidence(project_dir, args.step, output_file)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        error_output = {
            "step": -1,
            "total_criteria": 0,
            "verifiable_criteria": 0,
            "verified": 0,
            "results": [],
            "hallucinations_detected": 0,
            "passed": True,
            "warnings": [f"Fatal error: {e}"],
        }
        print(json.dumps(error_output, indent=2, ensure_ascii=False))
    sys.exit(0)  # Always exit 0 (non-blocking, P1 compliant)
