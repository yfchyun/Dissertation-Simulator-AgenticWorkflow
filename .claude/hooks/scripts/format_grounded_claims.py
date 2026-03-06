#!/usr/bin/env python3
"""Format GroundedClaim entries — P1 deterministic claim formatting.

Takes LLM-identified claims (as JSON input) and formats them into
GroundedClaim YAML schema, ensuring:
  - Unique sequential IDs (PREFIX-NNN)
  - Correct prefix per file (from FILE_CLAIM_PREFIXES)
  - Valid claim_type values
  - Confidence within range
  - No duplicate IDs

This is a DETERMINISTIC bridge between LLM claim identification
(semantic) and structured claim formatting (deterministic).

Usage:
  python3 format_grounded_claims.py --file <wave-output.md> --claims <claims.json>
  python3 format_grounded_claims.py --file <wave-output.md> --claims <claims.json> --dry-run
  python3 format_grounded_claims.py --scan --project-dir <dir>
"""

import argparse
import json
import sys
from pathlib import Path

from _claim_patterns import CLAIM_ID_INLINE_RE, count_claims  # noqa: E402

# Valid claim types (from validate_grounded_claim.py — duplicated for independence)
VALID_CLAIM_TYPES = {
    "FACTUAL", "EMPIRICAL", "THEORETICAL",
    "METHODOLOGICAL", "INTERPRETIVE", "SPECULATIVE",
}

# Claim ID pattern — centralized from _claim_patterns
CLAIM_ID_RE = CLAIM_ID_INLINE_RE

# File-to-prefix mapping (from validate_grounded_claim.py)
FILE_CLAIM_PREFIXES = {
    "literature-search.md": "LS",
    "seminal-works.md": "SWA",
    "trend-analysis.md": "TRA",
    "methodology-survey.md": "MS",
    "theoretical-framework.md": "TFA",
    "empirical-evidence.md": "EEA",
    "gap-analysis.md": "GI",
    "variable-relationships.md": "VRA",
    "critical-review.md": "CR",
    "methodology-critique.md": "MC",
    "limitation-analysis.md": "LA",
    "future-directions.md": "FDA",
    "synthesis-and-literature-review.md": "SA",
    "conceptual-model.md": "CMB",
    "plagiarism-report.md": "PC",
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


def get_prefix_for_file(filename: str) -> str | None:
    """Get the correct claim ID prefix for a file."""
    # Try exact match
    if filename in FILE_CLAIM_PREFIXES:
        return FILE_CLAIM_PREFIXES[filename]
    # Try basename
    base = Path(filename).name
    if base in FILE_CLAIM_PREFIXES:
        return FILE_CLAIM_PREFIXES[base]
    return None


def get_existing_ids(content: str) -> list[str]:
    """Extract existing claim IDs from file content."""
    return CLAIM_ID_RE.findall(content)


def get_next_number(existing_ids: list[str], prefix: str) -> int:
    """Determine next sequential number for a prefix."""
    max_num = 0
    for cid in existing_ids:
        # Parse number from ID like "LS-001" or "TFA-012"
        match = re.search(r'(\d{3})$', cid)
        if match and cid.startswith(prefix):
            num = int(match.group(1))
            if num > max_num:
                max_num = num
    return max_num + 1


def format_claim_yaml(
    claim_id: str,
    claim_text: str,
    claim_type: str,
    confidence: int,
    source: str,
    domain: str = "",
) -> str:
    """Format a single claim as GroundedClaim YAML block."""
    # Validate claim_type
    if claim_type not in VALID_CLAIM_TYPES:
        claim_type = "INTERPRETIVE"  # Safe default

    # Validate confidence
    min_conf = MIN_CONFIDENCE.get(claim_type, 60)
    if confidence < min_conf:
        confidence = min_conf  # Floor to minimum for type

    lines = [
        f"- id: {claim_id}",
        f"  claim_text: \"{claim_text}\"",
        f"  claim_type: {claim_type}",
        f"  confidence: {confidence}",
        f"  source: \"{source}\"",
    ]
    if domain:
        lines.append(f"  domain: \"{domain}\"")

    return "\n".join(lines)


def format_claims_for_file(
    file_path: str,
    claims_json: list[dict],
    dry_run: bool = False,
) -> dict:
    """Format and optionally append GroundedClaim entries to a file.

    Args:
        file_path: Path to the wave output .md file
        claims_json: List of dicts with keys: text, type, confidence, source, domain
        dry_run: If True, don't modify file, just return formatted output

    Returns:
        dict with status, formatted_claims, claim_ids, errors
    """
    path = Path(file_path)
    if not path.exists():
        return {"status": "error", "errors": [f"File not found: {file_path}"]}

    content = path.read_text(encoding="utf-8")
    filename = path.name
    prefix = get_prefix_for_file(filename)

    if not prefix:
        return {
            "status": "error",
            "errors": [f"No prefix mapping for {filename}"],
        }

    # Get existing IDs
    existing_ids = get_existing_ids(content)
    next_num = get_next_number(existing_ids, prefix)

    # Format new claims
    formatted = []
    new_ids = []
    errors = []

    for i, claim in enumerate(claims_json):
        text = claim.get("text", "").strip()
        ctype = claim.get("type", "INTERPRETIVE").upper()
        conf = claim.get("confidence", 75)
        source = claim.get("source", "").strip()
        domain = claim.get("domain", "").strip()

        if not text:
            errors.append(f"Claim {i}: empty text")
            continue

        if ctype not in VALID_CLAIM_TYPES:
            errors.append(
                f"Claim {i}: invalid type '{ctype}', using INTERPRETIVE"
            )
            ctype = "INTERPRETIVE"

        claim_id = f"{prefix}-{next_num:03d}"
        next_num += 1
        new_ids.append(claim_id)

        yaml_block = format_claim_yaml(
            claim_id, text, ctype, conf, source, domain
        )
        formatted.append(yaml_block)

    if not formatted:
        return {
            "status": "no_claims",
            "errors": errors,
            "formatted_claims": [],
            "claim_ids": [],
        }

    # Build appendix section
    appendix = "\n\n---\n\n## GroundedClaim Registry\n\n"
    appendix += "```yaml\nclaims:\n"
    appendix += "\n\n".join(formatted)
    appendix += "\n```\n"

    if not dry_run:
        # Append to file
        with open(path, "a", encoding="utf-8") as f:
            f.write(appendix)

    return {
        "status": "success",
        "file": filename,
        "prefix": prefix,
        "existing_claims": len(existing_ids),
        "new_claims": len(new_ids),
        "claim_ids": new_ids,
        "formatted_claims": formatted,
        "errors": errors,
        "dry_run": dry_run,
    }


def scan_project(project_dir: str) -> dict:
    """Scan project for files missing GroundedClaim entries."""
    project = Path(project_dir)
    results = {"files_with_claims": [], "files_without_claims": [], "total_claims": 0}

    for wave_num in range(1, 6):
        wave_dir = project / "wave-results" / f"wave-{wave_num}"
        if not wave_dir.is_dir():
            continue
        for md_file in sorted(wave_dir.glob("*.md")):
            if md_file.name.endswith(".ko.md"):
                continue
            content = md_file.read_text(encoding="utf-8")
            ids = get_existing_ids(content)
            entry = {
                "file": str(md_file.relative_to(project)),
                "claim_count": len(ids),
                "prefix": get_prefix_for_file(md_file.name),
            }
            if len(ids) > 0:
                results["files_with_claims"].append(entry)
                results["total_claims"] += len(ids)
            else:
                results["files_without_claims"].append(entry)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Format GroundedClaim entries (P1 deterministic)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Wave output file to add claims to")
    group.add_argument(
        "--scan", action="store_true",
        help="Scan project for files missing claims"
    )
    parser.add_argument("--claims", help="JSON file with claims to format")
    parser.add_argument(
        "--project-dir", help="Project directory (for --scan)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Don't modify files, just show formatted output"
    )
    args = parser.parse_args()

    if args.scan:
        if not args.project_dir:
            print("ERROR: --scan requires --project-dir", file=sys.stderr)
            return 1
        results = scan_project(args.project_dir)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0

    if not args.claims:
        print("ERROR: --file requires --claims", file=sys.stderr)
        return 1

    # Load claims JSON
    claims_path = Path(args.claims)
    if claims_path.exists():
        with open(claims_path, "r", encoding="utf-8") as f:
            claims = json.load(f)
    else:
        # Try parsing as inline JSON
        try:
            claims = json.loads(args.claims)
        except json.JSONDecodeError:
            print(f"ERROR: Cannot parse claims: {args.claims}", file=sys.stderr)
            return 1

    if not isinstance(claims, list):
        claims = [claims]

    result = format_claims_for_file(args.file, claims, dry_run=args.dry_run)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
