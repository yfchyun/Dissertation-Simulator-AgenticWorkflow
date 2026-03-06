#!/usr/bin/env python3
"""Detect self-plagiarism via n-gram overlap — P1 deterministic detection.

Computes n-gram similarity between thesis chapters and wave outputs
to detect:
  1. Exact sentence duplication across chapters
  2. High n-gram overlap between sections
  3. Copy-paste from wave outputs into chapters without attribution

This is the DETERMINISTIC component of plagiarism detection.
Semantic similarity (paraphrase detection) requires LLM evaluation.

Usage:
  python3 detect_self_plagiarism.py --project-dir <dir>
  python3 detect_self_plagiarism.py --project-dir <dir> --threshold 0.3
  python3 detect_self_plagiarism.py --project-dir <dir> --output report.md
"""

import argparse
import json
import re
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path


# Default similarity threshold for flagging
DEFAULT_THRESHOLD = 0.30  # 30% n-gram overlap

# N-gram sizes to compute
NGRAM_SIZES = [3, 5]

# Minimum sentence length to consider (words)
MIN_SENTENCE_WORDS = 8

# Sentence splitter
SENTENCE_RE = re.compile(r'[.!?]+\s+|\n\n+')


def clean_text(content: str) -> str:
    """Remove markdown formatting, code blocks, YAML, and metadata."""
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', content)
    # Remove inline code
    text = re.sub(r'`[^`]+`', '', text)
    # Remove YAML front matter
    text = re.sub(r'^---[\s\S]*?---', '', text)
    # Remove markdown headings markers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove markdown formatting (* _ ~)
    text = re.sub(r'[*_~]{1,3}', '', text)
    # Remove links [text](url)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove tables
    text = re.sub(r'\|[^\n]+\|', '', text)
    # Remove blockquotes
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
    # Remove citation markers
    text = re.sub(r'\([^)]*\d{4}[^)]*\)', '', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def get_ngrams(text: str, n: int) -> list[tuple]:
    """Generate word-level n-grams from text."""
    words = text.lower().split()
    if len(words) < n:
        return []
    return [tuple(words[i:i + n]) for i in range(len(words) - n + 1)]


def compute_ngram_similarity(text_a: str, text_b: str, n: int) -> float:
    """Compute Jaccard similarity of n-grams between two texts."""
    ngrams_a = set(get_ngrams(text_a, n))
    ngrams_b = set(get_ngrams(text_b, n))

    if not ngrams_a or not ngrams_b:
        return 0.0

    intersection = ngrams_a & ngrams_b
    union = ngrams_a | ngrams_b

    return len(intersection) / len(union) if union else 0.0


def find_exact_sentence_matches(text_a: str, text_b: str) -> list[str]:
    """Find sentences that appear verbatim in both texts."""
    sentences_a = set()
    for sent in SENTENCE_RE.split(text_a):
        sent = sent.strip()
        words = sent.split()
        if len(words) >= MIN_SENTENCE_WORDS:
            sentences_a.add(sent.lower())

    matches = []
    for sent in SENTENCE_RE.split(text_b):
        sent = sent.strip()
        words = sent.split()
        if len(words) >= MIN_SENTENCE_WORDS:
            if sent.lower() in sentences_a:
                matches.append(sent[:100] + ("..." if len(sent) > 100 else ""))

    return matches


def detect_overlap(project_dir: str, threshold: float) -> dict:
    """Detect self-plagiarism across thesis files."""
    project = Path(project_dir)

    # Collect all relevant files
    files = {}

    # Phase 3 chapters
    phase3_dir = project / "phase-3"
    if phase3_dir.is_dir():
        for md_file in sorted(phase3_dir.glob("*.md")):
            if md_file.name.endswith(".ko.md"):
                continue
            content = clean_text(md_file.read_text(encoding="utf-8"))
            if len(content.split()) > 50:  # Skip very short files
                files[f"phase-3/{md_file.name}"] = content

    # Wave outputs
    for wave_num in range(1, 5):
        wave_dir = project / "wave-results" / f"wave-{wave_num}"
        if not wave_dir.is_dir():
            continue
        for md_file in sorted(wave_dir.glob("*.md")):
            if md_file.name.endswith(".ko.md"):
                continue
            content = clean_text(md_file.read_text(encoding="utf-8"))
            if len(content.split()) > 50:
                files[f"wave-{wave_num}/{md_file.name}"] = content

    # Compute pairwise similarities
    comparisons = []
    flagged = []

    file_names = sorted(files.keys())
    for name_a, name_b in combinations(file_names, 2):
        text_a = files[name_a]
        text_b = files[name_b]

        # Compute n-gram similarities
        similarities = {}
        for n in NGRAM_SIZES:
            sim = compute_ngram_similarity(text_a, text_b, n)
            similarities[f"{n}-gram"] = round(sim, 4)

        # Find exact sentence matches
        exact_matches = find_exact_sentence_matches(text_a, text_b)

        max_sim = max(similarities.values())
        is_flagged = max_sim >= threshold or len(exact_matches) >= 3

        comparison = {
            "file_a": name_a,
            "file_b": name_b,
            "similarities": similarities,
            "exact_sentence_matches": len(exact_matches),
            "flagged": is_flagged,
        }

        if exact_matches:
            comparison["sample_matches"] = exact_matches[:5]

        comparisons.append(comparison)
        if is_flagged:
            flagged.append(comparison)

    # Sort flagged by highest similarity
    flagged.sort(
        key=lambda x: max(x["similarities"].values()),
        reverse=True,
    )

    return {
        "comparisons": comparisons,
        "flagged": flagged,
        "stats": {
            "files_analyzed": len(files),
            "pairwise_comparisons": len(comparisons),
            "flagged_pairs": len(flagged),
            "threshold": threshold,
            "verdict": "REVIEW_NEEDED" if flagged else "CLEAN",
        },
    }


def format_report(data: dict) -> str:
    """Format plagiarism report as markdown."""
    stats = data["stats"]
    lines = [
        "# Self-Plagiarism Detection Report",
        "",
        f"> Analyzed {stats['files_analyzed']} files | "
        f"{stats['pairwise_comparisons']} comparisons | "
        f"Threshold: {stats['threshold']:.0%}",
        f"> Verdict: **{stats['verdict']}**",
        f"> Generated by detect_self_plagiarism.py (P1 deterministic — n-gram analysis)",
        "",
    ]

    if data["flagged"]:
        lines.extend([
            "## Flagged Pairs",
            "",
            "The following file pairs exceed the similarity threshold "
            "or have 3+ exact sentence matches:",
            "",
            "| File A | File B | 3-gram | 5-gram | Exact Matches |",
            "|--------|--------|-------:|-------:|--------------:|",
        ])
        for f in data["flagged"]:
            sim3 = f["similarities"].get("3-gram", 0)
            sim5 = f["similarities"].get("5-gram", 0)
            lines.append(
                f"| {f['file_a']} | {f['file_b']} | "
                f"{sim3:.1%} | {sim5:.1%} | "
                f"{f['exact_sentence_matches']} |"
            )
        lines.append("")

        # Show sample exact matches
        for f in data["flagged"]:
            if f.get("sample_matches"):
                lines.append(
                    f"### {f['file_a']} vs {f['file_b']}"
                )
                lines.append("")
                lines.append("Exact sentence matches (sample):")
                for m in f["sample_matches"]:
                    lines.append(f'- "{m}"')
                lines.append("")
    else:
        lines.extend([
            "## Result",
            "",
            "No file pairs exceed the similarity threshold. "
            "No exact sentence duplication detected.",
            "",
        ])

    lines.extend([
        "---",
        "",
        "> **Note**: This is deterministic n-gram analysis only. "
        "Semantic similarity (paraphrase detection) requires "
        "LLM-based review for comprehensive assessment.",
        "",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Detect self-plagiarism via n-gram overlap (P1 deterministic)"
    )
    parser.add_argument("--project-dir", required=True)
    parser.add_argument(
        "--threshold", type=float, default=DEFAULT_THRESHOLD,
        help=f"Similarity threshold for flagging (default: {DEFAULT_THRESHOLD})"
    )
    parser.add_argument("--output", default=None)
    parser.add_argument(
        "--format", choices=["markdown", "json"], default="markdown"
    )
    args = parser.parse_args()

    data = detect_overlap(args.project_dir, args.threshold)

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

    return 0 if data["stats"]["verdict"] == "CLEAN" else 1


if __name__ == "__main__":
    sys.exit(main())
