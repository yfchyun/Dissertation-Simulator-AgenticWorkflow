#!/usr/bin/env python3
"""
Deterministic Translation Verification — verify_translation_terms.py

T10-T12: Hallucination-proof checks that produce identical results on every run.
These checks use pure Python (regex, string matching) with zero LLM inference.

Usage:
    python3 verify_translation_terms.py \
      --en-file path/to/english.md \
      --ko-file path/to/korean.ko.md \
      --glossary translations/glossary.yaml

Output: JSON to stdout
    {
      "passed": true/false,
      "checks": {
        "T10_glossary": {"passed": bool, "violations": [...]},
        "T11_numbers": {"passed": bool, "missing": [...], "extra": [...]},
        "T12_citations": {"passed": bool, "missing": [...]}
      },
      "summary": "T10: PASS, T11: PASS, T12: FAIL (2 missing citations)"
    }

Exit codes:
    0 — always (non-blocking, P1 compliant)

Architecture:
    - Pure Python, stdlib only (no external dependencies)
    - Deterministic: same input → same output, every time
    - P1 Compliance: zero heuristic inference
    - SOT Compliance: read-only (no file writes except stdout)
"""

import argparse
import json
import os
import re
import sys


# =============================================================================
# T10: Glossary Adherence Check
# =============================================================================

def check_glossary_adherence(en_content, ko_content, glossary_path):
    """Verify every glossary term in the English source has correct Korean mapping.

    Algorithm (deterministic):
      1. Load glossary (YAML-like key-value pairs)
      2. For each glossary English term found in en_content:
         a. Look up expected Korean translation
         b. Check if expected Korean appears in ko_content
      3. Report violations

    Tolerance: Terms kept in English (e.g., "SOT": "SOT") are checked
    for presence in ko_content as-is.
    """
    glossary = _load_glossary(glossary_path)
    if not glossary:
        return {"passed": True, "violations": [], "note": "No glossary found"}

    violations = []
    checked = 0

    for en_term, ko_term in glossary.items():
        # Only check terms that actually appear in the English source
        if en_term.lower() not in en_content.lower():
            continue

        checked += 1

        # Check if the expected Korean term appears in the Korean translation
        if ko_term.lower() not in ko_content.lower():
            # Also check if the English term itself appears (for terms kept in English)
            if en_term.lower() not in ko_content.lower():
                violations.append({
                    "term": en_term,
                    "expected_ko": ko_term,
                    "status": "missing",
                })

    return {
        "passed": len(violations) == 0,
        "violations": violations[:20],  # Cap at 20 to avoid huge output
        "terms_checked": checked,
        "terms_violated": len(violations),
    }


def _load_glossary(glossary_path):
    """Load glossary.yaml as a dict. Handles the simple key-value YAML format.

    Format: "English term": "Korean translation"
    Uses regex parsing instead of PyYAML to avoid external dependency.
    """
    if not glossary_path or not os.path.exists(glossary_path):
        return {}

    glossary = {}
    # Pattern: "key": "value" or 'key': 'value'
    pattern = re.compile(r'^["\'](.+?)["\']\s*:\s*["\'](.+?)["\']')

    try:
        with open(glossary_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                m = pattern.match(stripped)
                if m:
                    glossary[m.group(1)] = m.group(2)
    except Exception:
        pass

    return glossary


# =============================================================================
# T11: Number/Statistic Preservation
# =============================================================================

# Patterns for numbers and statistics (compiled once)
_NUMBER_PATTERNS = re.compile(
    r'(?:'
    r'\d+\.\d+%'          # 73.2%
    r'|\d+%'              # 73%
    r'|p\s*[<>=≤≥]\s*\d+\.?\d*'  # p < 0.05, p = 0.001
    r'|n\s*=\s*\d+'       # n = 150
    r'|N\s*=\s*\d+'       # N = 150
    r'|\d{1,3}(?:,\d{3})+' # 1,000 or 10,000
    r'|\d+\.\d+'          # 3.14 (decimal numbers)
    r'|(?<!\d)\d{4,}(?!\d)' # 4+ digit numbers (years, large numbers) — non-digit boundary
    r')',
    re.IGNORECASE
)

# Numbers to exclude (too common, cause false positives)
_EXCLUDED_NUMBERS = frozenset({
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
    "0.0", "1.0", "2.0",
})


def check_number_preservation(en_content, ko_content):
    """Verify all significant numbers in English source appear in Korean translation.

    Algorithm (deterministic):
      1. Extract all number patterns from English content
      2. Extract all number patterns from Korean content
      3. Find numbers in English but not in Korean (missing)
      4. Report missing numbers (potential translation omissions)
    """
    en_numbers = _extract_numbers(en_content)
    ko_numbers = _extract_numbers(ko_content)

    # Normalize: strip whitespace from patterns for comparison
    en_set = {_normalize_number(n) for n in en_numbers}
    ko_set = {_normalize_number(n) for n in ko_numbers}

    # Remove trivially common numbers
    en_set -= _EXCLUDED_NUMBERS
    ko_set -= _EXCLUDED_NUMBERS

    missing = sorted(en_set - ko_set)
    extra = sorted(ko_set - en_set)

    return {
        "passed": len(missing) == 0,
        "en_count": len(en_set),
        "ko_count": len(ko_set),
        "missing": missing[:20],
        "extra": extra[:10],
    }


def _extract_numbers(text):
    """Extract all number patterns from text."""
    return _NUMBER_PATTERNS.findall(text)


def _normalize_number(n):
    """Normalize a number string for comparison."""
    # Remove spaces around operators
    n = re.sub(r'\s+', '', n)
    # Remove commas in numbers
    n = n.replace(',', '')
    return n


# =============================================================================
# T12: Citation Preservation
# =============================================================================

# Citation patterns (compiled once)
_CITATION_PATTERNS = [
    # (Author, Year) — e.g., (Searle, 1980), (Chalmers & Jackson, 2001)
    re.compile(r'\(([A-Z][a-z]+(?:\s+(?:&|and)\s+[A-Z][a-z]+)*(?:\s+et\s+al\.?)?),?\s*(\d{4}[a-z]?)\)'),
    # Author (Year) — e.g., Searle (1980), Chalmers and Jackson (2001)
    re.compile(r'([A-Z][a-z]+(?:\s+(?:&|and)\s+[A-Z][a-z]+)*(?:\s+et\s+al\.?)?)\s*\((\d{4}[a-z]?)\)'),
    # [N] bracketed references — e.g., [1], [23], [145]
    re.compile(r'\[(\d{1,3})\]'),
]


def check_citation_preservation(en_content, ko_content):
    """Verify all citations in English source appear in Korean translation.

    Algorithm (deterministic):
      1. Extract citation patterns from English content
      2. Extract citation patterns from Korean content
      3. For author-year citations: check if (Author, Year) pair exists in Korean
      4. For bracketed citations: check if [N] exists in Korean
    """
    en_citations = _extract_citations(en_content)
    ko_citations = _extract_citations(ko_content)

    # Compare normalized citation sets
    en_set = set(en_citations)
    ko_set = set(ko_citations)

    missing = sorted(en_set - ko_set)

    return {
        "passed": len(missing) == 0,
        "en_count": len(en_set),
        "ko_count": len(ko_set),
        "missing": list(missing)[:20],
    }


def _extract_citations(text):
    """Extract all citation references from text as normalized strings."""
    citations = []

    for pattern in _CITATION_PATTERNS[:2]:  # Author-year patterns
        for match in pattern.finditer(text):
            author = match.group(1).strip()
            year = match.group(2).strip()
            # Normalize: "Author, Year"
            citations.append(f"{author}, {year}")

    # Bracketed references [N]
    for match in _CITATION_PATTERNS[2].finditer(text):
        citations.append(f"[{match.group(1)}]")

    return citations


# =============================================================================
# Main
# =============================================================================

def verify_all(en_path, ko_path, glossary_path=None):
    """Run all deterministic translation checks.

    Returns: dict with overall passed status and per-check results.
    """
    # Read files
    try:
        with open(en_path, "r", encoding="utf-8") as f:
            en_content = f.read()
    except Exception as e:
        return {"passed": False, "error": f"Cannot read English file: {e}"}

    try:
        with open(ko_path, "r", encoding="utf-8") as f:
            ko_content = f.read()
    except Exception as e:
        return {"passed": False, "error": f"Cannot read Korean file: {e}"}

    # Run checks
    t10 = check_glossary_adherence(en_content, ko_content, glossary_path)
    t11 = check_number_preservation(en_content, ko_content)
    t12 = check_citation_preservation(en_content, ko_content)

    overall = t10["passed"] and t11["passed"] and t12["passed"]

    # Build summary string
    parts = []
    for name, result in [("T10", t10), ("T11", t11), ("T12", t12)]:
        if result["passed"]:
            parts.append(f"{name}: PASS")
        else:
            detail = ""
            if name == "T10":
                detail = f" ({result.get('terms_violated', 0)} glossary violations)"
            elif name == "T11":
                detail = f" ({len(result.get('missing', []))} missing numbers)"
            elif name == "T12":
                detail = f" ({len(result.get('missing', []))} missing citations)"
            parts.append(f"{name}: FAIL{detail}")

    return {
        "passed": overall,
        "en_file": en_path,
        "ko_file": ko_path,
        "checks": {
            "T10_glossary": t10,
            "T11_numbers": t11,
            "T12_citations": t12,
        },
        "summary": ", ".join(parts),
    }


def main():
    parser = argparse.ArgumentParser(
        description="T10-T12: Deterministic translation term verification (P1 compliant)"
    )
    parser.add_argument(
        "--en-file", required=True,
        help="Path to English source file"
    )
    parser.add_argument(
        "--ko-file", required=True,
        help="Path to Korean translation file"
    )
    parser.add_argument(
        "--glossary", default="translations/glossary.yaml",
        help="Path to glossary YAML (default: translations/glossary.yaml)"
    )
    args = parser.parse_args()

    result = verify_all(args.en_file, args.ko_file, args.glossary)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        error_output = {
            "passed": False,
            "error": str(e),
        }
        print(json.dumps(error_output, indent=2, ensure_ascii=False))
    sys.exit(0)  # Always exit 0 (non-blocking, P1 compliant)
