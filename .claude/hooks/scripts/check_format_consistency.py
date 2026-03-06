#!/usr/bin/env python3
"""Check format consistency across thesis chapters — P1 deterministic validation.

Validates:
  1. Citation format consistency (APA-style patterns)
  2. Heading hierarchy (no level skips)
  3. Terminology consistency (against glossary.yaml)
  4. Structural consistency (section numbering, markdown formatting)

Usage:
  python3 check_format_consistency.py --project-dir <dir>
  python3 check_format_consistency.py --project-dir <dir> --output report.md
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# APA citation patterns (deterministic checks)
APA_PATTERNS = {
    "single_author": re.compile(
        r'\([A-Z][a-z]+,?\s*\d{4}[a-z]?\)'
    ),
    "two_authors": re.compile(
        r'\([A-Z][a-z]+\s+(?:&|and)\s+[A-Z][a-z]+,?\s*\d{4}[a-z]?\)'
    ),
    "et_al": re.compile(
        r'\([A-Z][a-z]+\s+et\s+al\.?,?\s*\d{4}[a-z]?\)'
    ),
    "inline_single": re.compile(
        r'[A-Z][a-z]+\s+\(\d{4}[a-z]?\)'
    ),
    "inline_et_al": re.compile(
        r'[A-Z][a-z]+\s+et\s+al\.?\s+\(\d{4}[a-z]?\)'
    ),
}

# Inconsistency patterns to detect
INCONSISTENCY_CHECKS = {
    # "et al" should have period: "et al." not "et al"
    "et_al_no_period": re.compile(r'\bet al(?!\.)\b'),
    # Comma before year inconsistency: "(Author, 2020)" vs "(Author 2020)"
    "comma_before_year_yes": re.compile(r'\([A-Z][a-z]+,\s*\d{4}\)'),
    "comma_before_year_no": re.compile(r'\([A-Z][a-z]+\s+\d{4}\)'),
    # Ampersand vs "and" in parenthetical
    "ampersand_in_parens": re.compile(r'\([^)]*&[^)]*\d{4}[^)]*\)'),
    "and_in_parens": re.compile(r'\([^)]*\band\b[^)]*\d{4}[^)]*\)'),
}

# Heading pattern
HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)

# Latin/theological formatting — should be italic
LATIN_TERMS = [
    "voluntas", "liberum arbitrium", "servum arbitrium",
    "imago Dei", "anima rationalis", "prohairesis",
    "causa", "causae", "concursus", "natura",
    "motus animi", "De Libero Arbitrio", "Institutio",
    "De Gratia", "Summa Theologiae",
]


def check_citation_consistency(content: str, filename: str) -> list[dict]:
    """Check citation format consistency within a file."""
    issues = []

    # Check et al. period
    no_period = INCONSISTENCY_CHECKS["et_al_no_period"].findall(content)
    if no_period:
        issues.append({
            "type": "Warning",
            "rule": "APA-1",
            "file": filename,
            "message": f"'et al' without period found {len(no_period)} times. APA requires 'et al.'",
        })

    # Check comma consistency before year
    comma_yes = len(INCONSISTENCY_CHECKS["comma_before_year_yes"].findall(content))
    comma_no = len(INCONSISTENCY_CHECKS["comma_before_year_no"].findall(content))
    if comma_yes > 0 and comma_no > 0:
        issues.append({
            "type": "Warning",
            "rule": "APA-2",
            "file": filename,
            "message": (
                f"Inconsistent comma usage before year: "
                f"{comma_yes} with comma, {comma_no} without. "
                f"Choose one style consistently."
            ),
        })

    # Check ampersand vs "and" consistency in parenthetical citations
    amp = len(INCONSISTENCY_CHECKS["ampersand_in_parens"].findall(content))
    and_word = len(INCONSISTENCY_CHECKS["and_in_parens"].findall(content))
    if amp > 0 and and_word > 0:
        issues.append({
            "type": "Warning",
            "rule": "APA-3",
            "file": filename,
            "message": (
                f"Inconsistent use of '&' vs 'and' in parenthetical citations: "
                f"{amp} with '&', {and_word} with 'and'. "
                f"APA uses '&' in parenthetical, 'and' in narrative."
            ),
        })

    return issues


def check_heading_hierarchy(content: str, filename: str) -> list[dict]:
    """Check heading level hierarchy — no skips allowed."""
    issues = []
    headings = HEADING_PATTERN.findall(content)

    prev_level = 0
    for hashes, title in headings:
        level = len(hashes)
        if prev_level > 0 and level > prev_level + 1:
            issues.append({
                "type": "Warning",
                "rule": "STRUCT-1",
                "file": filename,
                "message": (
                    f"Heading level skip: '{hashes} {title}' "
                    f"(level {level}) follows level {prev_level}. "
                    f"Expected level {prev_level + 1} or less."
                ),
            })
        prev_level = level

    return issues


def check_glossary_consistency(
    content: str, filename: str, glossary: dict
) -> list[dict]:
    """Check terminology consistency against glossary."""
    issues = []

    for en_term, ko_term in glossary.items():
        if not isinstance(en_term, str) or not isinstance(ko_term, str):
            continue
        # Skip short terms (too many false positives)
        if len(en_term) < 4:
            continue
        # Check if English term appears in content
        # (glossary terms should be used consistently)
        count = content.lower().count(en_term.lower())
        if count > 0:
            # Check for variant spellings (case-insensitive)
            variants = set()
            for match in re.finditer(
                re.escape(en_term), content, re.IGNORECASE
            ):
                variants.add(match.group())
            if len(variants) > 1:
                issues.append({
                    "type": "Suggestion",
                    "rule": "TERM-1",
                    "file": filename,
                    "message": (
                        f"Term '{en_term}' appears in {len(variants)} "
                        f"variants: {sorted(variants)}. "
                        f"Use consistent capitalization."
                    ),
                })

    return issues


def check_latin_formatting(content: str, filename: str) -> list[dict]:
    """Check that Latin terms are properly italicized."""
    issues = []

    for term in LATIN_TERMS:
        # Find non-italicized occurrences (not preceded by * or _)
        pattern = re.compile(
            r'(?<!\*)'           # not preceded by *
            r'(?<!_)'            # not preceded by _
            + re.escape(term)
            + r'(?!\*)'          # not followed by *
            + r'(?!_)',          # not followed by _
            re.IGNORECASE,
        )
        matches = pattern.findall(content)
        if matches:
            # Verify it's not inside an already-italic block
            italic_pattern = re.compile(
                r'\*[^*]*' + re.escape(term) + r'[^*]*\*',
                re.IGNORECASE,
            )
            italic_count = len(italic_pattern.findall(content))
            non_italic = len(matches) - italic_count
            if non_italic > 0:
                issues.append({
                    "type": "Suggestion",
                    "rule": "LATIN-1",
                    "file": filename,
                    "message": (
                        f"Latin term '{term}' appears {non_italic} times "
                        f"without italics. Academic convention requires "
                        f"italicization of foreign terms."
                    ),
                })

    return issues


def run_all_checks(project_dir: str) -> dict:
    """Run all format consistency checks."""
    project = Path(project_dir)
    phase3_dir = project / "phase-3"
    glossary_path = project.parent.parent / "translations" / "glossary.yaml"

    # Try multiple glossary paths
    if not glossary_path.exists():
        glossary_path = Path(project_dir).parent / "translations" / "glossary.yaml"
    if not glossary_path.exists():
        # Search upward
        search = Path(project_dir)
        for _ in range(5):
            search = search.parent
            candidate = search / "translations" / "glossary.yaml"
            if candidate.exists():
                glossary_path = candidate
                break

    # Load glossary
    glossary = {}
    if glossary_path.exists() and HAS_YAML:
        with open(glossary_path, "r", encoding="utf-8") as f:
            glossary = yaml.safe_load(f) or {}
    elif glossary_path.exists():
        # Simple YAML parsing fallback (key: value pairs)
        with open(glossary_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if ":" in line and not line.startswith("#"):
                    parts = line.split(":", 1)
                    key = parts[0].strip().strip('"').strip("'")
                    val = parts[1].strip().strip('"').strip("'")
                    if key and val:
                        glossary[key] = val

    all_issues = []
    files_checked = 0

    if not phase3_dir.is_dir():
        return {
            "issues": [],
            "stats": {"files_checked": 0, "error": "phase-3 directory not found"},
        }

    for md_file in sorted(phase3_dir.glob("*.md")):
        if md_file.name.endswith(".ko.md"):
            continue
        content = md_file.read_text(encoding="utf-8")
        files_checked += 1

        all_issues.extend(check_citation_consistency(content, md_file.name))
        all_issues.extend(check_heading_hierarchy(content, md_file.name))
        all_issues.extend(check_latin_formatting(content, md_file.name))
        if glossary:
            all_issues.extend(
                check_glossary_consistency(content, md_file.name, glossary)
            )

    # Classify
    critical = [i for i in all_issues if i["type"] == "Critical"]
    warnings = [i for i in all_issues if i["type"] == "Warning"]
    suggestions = [i for i in all_issues if i["type"] == "Suggestion"]

    return {
        "issues": all_issues,
        "stats": {
            "files_checked": files_checked,
            "total_issues": len(all_issues),
            "critical": len(critical),
            "warnings": len(warnings),
            "suggestions": len(suggestions),
            "glossary_terms": len(glossary),
            "verdict": "FAIL" if critical else "PASS",
        },
    }


def format_report(data: dict) -> str:
    """Format consistency report as markdown."""
    stats = data["stats"]
    lines = [
        "# Format Consistency Report",
        "",
        f"> Checked {stats['files_checked']} files | "
        f"Glossary: {stats['glossary_terms']} terms | "
        f"Verdict: **{stats['verdict']}**",
        "",
        f"| Severity | Count |",
        f"|----------|-------|",
        f"| Critical | {stats['critical']} |",
        f"| Warning | {stats['warnings']} |",
        f"| Suggestion | {stats['suggestions']} |",
        "",
    ]

    if data["issues"]:
        lines.append("## Issues Found")
        lines.append("")
        lines.append("| # | Severity | Rule | File | Description |")
        lines.append("|---|----------|------|------|-------------|")
        for i, issue in enumerate(data["issues"], 1):
            lines.append(
                f"| {i} | {issue['type']} | {issue['rule']} | "
                f"{issue['file']} | {issue['message']} |"
            )
        lines.append("")

    lines.append(
        "> Generated by check_format_consistency.py (P1 deterministic)"
    )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Check format consistency (P1 deterministic)"
    )
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--output", default=None)
    parser.add_argument(
        "--format", choices=["markdown", "json"], default="markdown"
    )
    args = parser.parse_args()

    data = run_all_checks(args.project_dir)

    if args.format == "json":
        output = json.dumps(data, indent=2, ensure_ascii=False)
    else:
        output = format_report(data)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(output)

    return 0 if data["stats"]["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
