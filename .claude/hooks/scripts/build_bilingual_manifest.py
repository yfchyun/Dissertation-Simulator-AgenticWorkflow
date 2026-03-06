#!/usr/bin/env python3
"""Build bilingual manifest — P1 deterministic EN/KO pair verification.

Scans thesis output directory for English original files and their
Korean translation counterparts (.ko.md). Reports completeness,
size ratios, and missing translations.

Usage:
  python3 build_bilingual_manifest.py --project-dir <dir>
  python3 build_bilingual_manifest.py --project-dir <dir> --output manifest.md
  python3 build_bilingual_manifest.py --project-dir <dir> --format json
"""

import argparse
import json
import sys
from pathlib import Path


def scan_bilingual_pairs(project_dir: str) -> dict:
    """Scan for EN/KO file pairs across all output directories."""
    project = Path(project_dir)

    pairs = []
    missing_ko = []
    orphan_ko = []
    total_en_size = 0
    total_ko_size = 0

    # Directories to scan
    scan_dirs = [
        project / "phase-3",
        project / "phase-2",
        project / "phase-4",
    ]
    for wave_num in range(1, 6):
        scan_dirs.append(project / "wave-results" / f"wave-{wave_num}")

    # Also check phase-3/ko/ (legacy translation location)
    ko_subdir = project / "phase-3" / "ko"

    for scan_dir in scan_dirs:
        if not scan_dir.is_dir():
            continue

        en_files = sorted(
            f for f in scan_dir.glob("*.md")
            if not f.name.endswith(".ko.md")
        )

        ko_files = set(
            f.name for f in scan_dir.glob("*.ko.md")
        )

        for en_file in en_files:
            en_size = en_file.stat().st_size
            total_en_size += en_size

            # Check for .ko.md companion
            ko_name = en_file.stem + ".ko.md"
            ko_path = scan_dir / ko_name
            rel_path = str(en_file.relative_to(project))

            if ko_path.exists():
                ko_size = ko_path.stat().st_size
                total_ko_size += ko_size
                ratio = ko_size / max(en_size, 1)
                pairs.append({
                    "en_file": rel_path,
                    "ko_file": str(ko_path.relative_to(project)),
                    "en_size": en_size,
                    "ko_size": ko_size,
                    "ratio": round(ratio, 2),
                    "status": "paired",
                })
                ko_files.discard(ko_name)
            else:
                missing_ko.append({
                    "en_file": rel_path,
                    "en_size": en_size,
                    "expected_ko": str(
                        (scan_dir / ko_name).relative_to(project)
                    ),
                })

        # Any remaining .ko.md files without EN counterparts
        for ko_name in ko_files:
            orphan_ko.append({
                "ko_file": str(
                    (scan_dir / ko_name).relative_to(project)
                ),
            })

    # Check legacy ko/ subdirectory (files like ko/abstract.ko.md)
    if ko_subdir.is_dir():
        for ko_file in sorted(ko_subdir.glob("*.md")):
            ko_size = ko_file.stat().st_size
            total_ko_size += ko_size
            # Derive EN counterpart: ko/abstract.ko.md → abstract.md
            en_name = ko_file.name.replace(".ko.md", ".md")
            if en_name == ko_file.name:
                # No .ko.md suffix — use name as-is
                en_name = ko_file.name
            en_path = project / "phase-3" / en_name
            rel_ko = str(ko_file.relative_to(project))

            if en_path.exists():
                en_size = en_path.stat().st_size
                ratio = ko_size / max(en_size, 1)
                pairs.append({
                    "en_file": str(en_path.relative_to(project)),
                    "ko_file": rel_ko,
                    "en_size": en_size,
                    "ko_size": ko_size,
                    "ratio": round(ratio, 2),
                    "status": "paired (legacy ko/ dir)",
                })
            else:
                orphan_ko.append({"ko_file": rel_ko})

    # Remove missing_ko entries that were paired via legacy ko/ dir
    paired_en_files = {p["en_file"] for p in pairs}
    missing_ko = [
        m for m in missing_ko if m["en_file"] not in paired_en_files
    ]

    completeness = (
        len(pairs) / max(len(pairs) + len(missing_ko), 1) * 100
    )

    return {
        "pairs": pairs,
        "missing_ko": missing_ko,
        "orphan_ko": orphan_ko,
        "stats": {
            "paired_files": len(pairs),
            "missing_translations": len(missing_ko),
            "orphan_translations": len(orphan_ko),
            "total_en_bytes": total_en_size,
            "total_ko_bytes": total_ko_size,
            "completeness_pct": round(completeness, 1),
        },
    }


def format_as_markdown(data: dict) -> str:
    """Format manifest as markdown."""
    stats = data["stats"]
    lines = [
        "# Bilingual Thesis Package Manifest",
        "",
        f"> Completeness: **{stats['completeness_pct']}%** "
        f"({stats['paired_files']} paired, "
        f"{stats['missing_translations']} missing)",
        f"> Generated by build_bilingual_manifest.py (P1 deterministic)",
        "",
    ]

    # Paired files
    if data["pairs"]:
        lines.extend([
            "## Paired Files (EN + KO)",
            "",
            "| EN File | KO File | EN Size | KO Size | Ratio |",
            "|---------|---------|--------:|--------:|------:|",
        ])
        for p in data["pairs"]:
            lines.append(
                f"| {p['en_file']} | {p['ko_file']} | "
                f"{p['en_size']:,} | {p['ko_size']:,} | {p['ratio']} |"
            )
        lines.append("")

    # Missing translations
    if data["missing_ko"]:
        lines.extend([
            "## Missing Translations",
            "",
            "| EN File | Size | Expected KO |",
            "|---------|-----:|-------------|",
        ])
        for m in data["missing_ko"]:
            lines.append(
                f"| {m['en_file']} | {m['en_size']:,} | {m['expected_ko']} |"
            )
        lines.append("")

    # Orphan translations
    if data["orphan_ko"]:
        lines.extend([
            "## Orphan Translations (no EN counterpart)",
            "",
        ])
        for o in data["orphan_ko"]:
            lines.append(f"- {o['ko_file']}")
        lines.append("")

    # Statistics
    lines.extend([
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|------:|",
        f"| Paired files | {stats['paired_files']} |",
        f"| Missing translations | {stats['missing_translations']} |",
        f"| Orphan translations | {stats['orphan_translations']} |",
        f"| Total EN size | {stats['total_en_bytes']:,} bytes |",
        f"| Total KO size | {stats['total_ko_bytes']:,} bytes |",
        f"| Completeness | {stats['completeness_pct']}% |",
        "",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Build bilingual manifest (P1 deterministic)"
    )
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--output", default=None)
    parser.add_argument(
        "--format", choices=["markdown", "json"], default="markdown"
    )
    args = parser.parse_args()

    data = scan_bilingual_pairs(args.project_dir)

    if args.format == "json":
        output = json.dumps(data, indent=2, ensure_ascii=False)
    else:
        output = format_as_markdown(data)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Manifest written to {args.output}")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
