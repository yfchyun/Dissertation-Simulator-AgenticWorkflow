#!/usr/bin/env python3
"""Extract references from thesis chapters — P1 deterministic citation extraction.

Scans markdown chapter files for citation patterns, deduplicates, sorts
alphabetically, and produces a compiled references list. This is a
DETERMINISTIC operation — no LLM involvement, no hallucination possible.

Citation patterns recognized:
  - (Author, Year) — e.g., (Searle, 1980)
  - (Author & Author, Year) — e.g., (Fischer & Ravizza, 1998)
  - (Author et al., Year) — e.g., (Pereboom et al., 2014)
  - Author (Year) — e.g., Searle (1980)
  - Author et al. (Year) — e.g., Pereboom et al. (2014)
  - (Author Year; Author Year) — semicolon-separated groups
  - (Author Year, Year) — multi-year same author
  - Author, *Work Title* — classical/theological references

Usage:
  python3 extract_references.py --project-dir <dir>
  python3 extract_references.py --project-dir <dir> --output references.md
  python3 extract_references.py --project-dir <dir> --format json
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


# Citation patterns — deterministic regex extraction
# Pattern 1: (Author, Year) or (Author Year)
PAREN_SINGLE = re.compile(
    r'\(([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'     # Author name(s)
    r'(?:\s+(?:et\s+al\.?))?'                   # optional et al.
    r'(?:\s*&\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)?'  # optional & Second Author
    r',?\s*'
    r'(\d{4}[a-z]?)'                            # Year
    r'\)'
)

# Pattern 2: Author (Year) — inline
INLINE_AUTHOR_YEAR = re.compile(
    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'         # Author
    r'(?:\s+(?:et\s+al\.?))?'                    # optional et al.
    r'\s*\((\d{4}[a-z]?)\)'                      # (Year)
)

# Pattern 3: Semicolon-separated citations inside parens
# e.g., (Chisholm 1964; Kane 1996; O'Connor 2000)
PAREN_MULTI = re.compile(
    r'\(([^)]*\d{4}[^)]*;\s*[^)]*\d{4}[^)]*)\)'
)

# Pattern 4: Multi-year same author — (Author Year, Year)
MULTI_YEAR = re.compile(
    r'\(([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
    r'(?:\s+(?:et\s+al\.?))?'
    r',?\s*'
    r'(\d{4}[a-z]?(?:\s*,\s*\d{4}[a-z]?)+)'
    r'\)'
)

# Pattern 5: Classical/theological references — Author, *Title*
CLASSICAL_REF = re.compile(
    r'([A-Z][a-z]+(?:\s+(?:of\s+)?[A-Z][a-z]+)*)'  # Author (e.g., Augustine of Hippo)
    r',\s*\*([^*]+)\*'                               # *Title*
)

# Sub-pattern for splitting semicolon groups
SEMI_SPLIT = re.compile(
    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
    r'(?:\s+(?:et\s+al\.?))?'
    r'(?:\s*(?:&|and)\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)?'
    r',?\s*'
    r'(\d{4}[a-z]?)'
)

# Known non-author words to filter out false positives
NON_AUTHOR_WORDS = {
    "The", "This", "That", "These", "Those", "However", "Moreover",
    "Furthermore", "Nevertheless", "Although", "Because", "Since",
    "While", "When", "Where", "What", "Which", "Who", "How",
    "Book", "Chapter", "Section", "Part", "Table", "Figure",
    "See", "Also", "Note", "For", "From", "With", "Into",
    "Step", "Phase", "Wave", "Gate", "Mode", "Type",
    "PRIMARY", "SECONDARY", "TERTIARY", "NOT", "AND", "BUT",
}


def extract_citations_from_text(content: str) -> list[dict]:
    """Extract all citations from markdown text content.

    Returns list of dicts: {author, year, context, pattern_type}
    """
    citations = []
    seen = set()

    def _add(author: str, year: str, ptype: str):
        author = author.strip()
        if author in NON_AUTHOR_WORDS:
            return
        if len(author) < 2:
            return
        key = f"{author}|{year}"
        if key not in seen:
            seen.add(key)
            citations.append({
                "author": author,
                "year": year,
                "pattern_type": ptype,
            })

    # Pattern 3: Multi-citation parenthetical (highest priority — parse first)
    for match in PAREN_MULTI.finditer(content):
        group = match.group(1)
        for sub in SEMI_SPLIT.finditer(group):
            _add(sub.group(1), sub.group(2), "paren_multi")

    # Pattern 4: Multi-year same author
    for match in MULTI_YEAR.finditer(content):
        author = match.group(1)
        years_str = match.group(2)
        for year in re.findall(r'\d{4}[a-z]?', years_str):
            _add(author, year, "multi_year")

    # Pattern 1: Single parenthetical
    for match in PAREN_SINGLE.finditer(content):
        _add(match.group(1), match.group(2), "paren_single")

    # Pattern 2: Inline author (year)
    for match in INLINE_AUTHOR_YEAR.finditer(content):
        _add(match.group(1), match.group(2), "inline")

    # Pattern 5: Classical references
    for match in CLASSICAL_REF.finditer(content):
        author = match.group(1)
        title = match.group(2)
        _add(author, "classical", f"classical:{title}")

    return citations


def extract_from_file(file_path: Path) -> list[dict]:
    """Extract citations from a single markdown file."""
    content = file_path.read_text(encoding="utf-8")
    citations = extract_citations_from_text(content)
    for c in citations:
        c["source_file"] = file_path.name
    return citations


def compile_references(project_dir: str) -> dict:
    """Compile all references from thesis chapter files.

    Returns dict with:
      - citations: deduplicated list sorted by author
      - by_author: grouped by author name
      - stats: counts and coverage metrics
    """
    project = Path(project_dir)
    phase3_dir = project / "phase-3"

    all_citations = []
    file_count = 0

    # Scan chapter files
    if phase3_dir.is_dir():
        for md_file in sorted(phase3_dir.glob("chapter-*.md")):
            citations = extract_from_file(md_file)
            all_citations.extend(citations)
            file_count += 1

        # Also scan abstract
        abstract = phase3_dir / "abstract.md"
        if abstract.exists():
            all_citations.extend(extract_from_file(abstract))
            file_count += 1

    # Deduplicate by author+year
    unique = {}
    for c in all_citations:
        key = f"{c['author']}|{c['year']}"
        if key not in unique:
            unique[key] = {
                "author": c["author"],
                "year": c["year"],
                "source_files": [c["source_file"]],
                "pattern_type": c["pattern_type"],
            }
        else:
            if c["source_file"] not in unique[key]["source_files"]:
                unique[key]["source_files"].append(c["source_file"])

    # Sort by author name, then year
    sorted_refs = sorted(
        unique.values(),
        key=lambda x: (x["author"].lower(), x["year"]),
    )

    # Group by author
    by_author = defaultdict(list)
    for ref in sorted_refs:
        by_author[ref["author"]].append(ref)

    # Filter out classical references for separate section
    modern_refs = [r for r in sorted_refs if r["year"] != "classical"]
    classical_refs = [r for r in sorted_refs if r["year"] == "classical"]

    stats = {
        "total_citations_found": len(all_citations),
        "unique_references": len(sorted_refs),
        "unique_authors": len(by_author),
        "modern_references": len(modern_refs),
        "classical_references": len(classical_refs),
        "files_scanned": file_count,
    }

    return {
        "references": sorted_refs,
        "modern": modern_refs,
        "classical": classical_refs,
        "by_author": dict(by_author),
        "stats": stats,
    }


def format_as_markdown(data: dict) -> str:
    """Format compiled references as markdown bibliography."""
    lines = [
        "# References",
        "",
        f"> Compiled from {data['stats']['files_scanned']} thesis files.",
        f"> {data['stats']['unique_references']} unique references "
        f"({data['stats']['modern_references']} modern, "
        f"{data['stats']['classical_references']} classical).",
        f"> Extracted deterministically by extract_references.py (P1).",
        "",
    ]

    # Modern references
    if data["modern"]:
        lines.append("## Modern References")
        lines.append("")
        for ref in data["modern"]:
            author = ref["author"]
            year = ref["year"]
            files = ", ".join(ref["source_files"])
            # APA-style stub: Author (Year). [cited in: files]
            if "et al" in ref.get("pattern_type", ""):
                lines.append(f"- {author} et al. ({year}). [cited in: {files}]")
            else:
                lines.append(f"- {author} ({year}). [cited in: {files}]")
        lines.append("")

    # Classical/theological references
    if data["classical"]:
        lines.append("## Classical and Theological References")
        lines.append("")
        for ref in data["classical"]:
            author = ref["author"]
            ptype = ref.get("pattern_type", "")
            title = ptype.replace("classical:", "") if ptype.startswith("classical:") else ""
            files = ", ".join(ref["source_files"])
            if title:
                lines.append(f"- {author}, *{title}*. [cited in: {files}]")
            else:
                lines.append(f"- {author}. [cited in: {files}]")
        lines.append("")

    # Statistics
    lines.extend([
        "## Extraction Statistics",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total citation instances | {data['stats']['total_citations_found']} |",
        f"| Unique references | {data['stats']['unique_references']} |",
        f"| Unique authors | {data['stats']['unique_authors']} |",
        f"| Files scanned | {data['stats']['files_scanned']} |",
        "",
        "> **Note**: This is a deterministic extraction. Full bibliographic details "
        "(publisher, journal, DOI) require fact-checker verification.",
        "",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Extract references from thesis chapters (P1 deterministic)"
    )
    parser.add_argument(
        "--project-dir", required=True,
        help="Thesis project directory"
    )
    parser.add_argument(
        "--output", default=None,
        help="Output file path (default: stdout)"
    )
    parser.add_argument(
        "--format", choices=["markdown", "json"], default="markdown",
        help="Output format (default: markdown)"
    )
    args = parser.parse_args()

    data = compile_references(args.project_dir)

    if args.format == "json":
        output = json.dumps(data, indent=2, ensure_ascii=False)
    else:
        output = format_as_markdown(data)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"References written to {args.output}")
        print(f"Stats: {json.dumps(data['stats'])}")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
