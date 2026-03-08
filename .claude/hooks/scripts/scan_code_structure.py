#!/usr/bin/env python3
"""
scan_code_structure.py — Phase A: Code Structure Scanner for Predictive Debugging

Produces fp-code-map.json that grounds @failure-predictor against actual code facts.
Prevents LLM hallucinations by providing verified file paths, line numbers, and
pattern matches BEFORE the LLM reasons about failure risks.

P1 Compliance:
  - Pure stdlib, no LLM calls, deterministic output
  - Exit 0 always (non-blocking)
  - Output: JSON to .claude/context-snapshots/fp-code-map.json

CLI:
  python scan_code_structure.py [--project-dir PATH] [--output PATH]

Used by: /predict-failures slash command (Phase A)

Design:
  - Scans only production code (not tests, docs, translations)
  - Extracts F1-F7 failure taxonomy pattern matches with exact line numbers
  - Extracts Python symbol names (functions/classes) for navigation
  - Result feeds @failure-predictor as verified ground truth
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# === Scan Targets (relative to project root) ===
SCAN_TARGETS = [
    ".claude/hooks/scripts",  # Production hook scripts (exclude _test_*)
    ".claude/agents",         # Agent definitions
    ".claude/commands",       # Slash commands
    "tests/e2e",              # E2E integration tests
]

SCAN_EXTENSIONS = {".py", ".md"}

# Files to exclude by name pattern (applied to basename)
EXCLUDE_PATTERNS = [
    r"^_test_",       # Unit test files
    r"^context_guard",  # Auto-generated dispatcher
]


# === Failure Taxonomy Pattern Library (F1-F7) ===
# Each entry: id, desc, regex, severity_hint
# These are STRUCTURAL signals — LLM reasons about whether they are actual risks.
FAILURE_PATTERNS: Dict[str, List[Dict[str, str]]] = {
    "F1_concurrency": [
        {
            "id": "F1-01",
            "desc": "JSONL append-mode open — concurrent hook race condition",
            "regex": r'open\s*\([^)]+,\s*["\']a["\']\s*\)',
            "severity": "Critical",
        },
        {
            "id": "F1-02",
            "desc": "json.dump without atomic_write — partial write on process kill",
            "regex": r"json\.dump\s*\(",
            "severity": "Warning",
        },
        {
            "id": "F1-03",
            "desc": "Direct .write() to file — no atomicity guarantee",
            "regex": r"\bf\.write\s*\(",
            "severity": "Warning",
        },
    ],
    "F2_state_drift": [
        {
            "id": "F2-01",
            "desc": "Direct session.json reference — may bypass SOT guard",
            "regex": r'["\']session\.json["\']',
            "severity": "Warning",
        },
        {
            "id": "F2-02",
            "desc": "Direct state.yaml reference — SOT bypass risk",
            "regex": r'["\']state\.yaml["\']',
            "severity": "Warning",
        },
        {
            "id": "F2-03",
            "desc": "Hardcoded step number constant — state drift if SOT schema changes",
            "regex": r'\bstep[_\s]*=\s*\d{2,3}\b',
            "severity": "Info",
        },
    ],
    "F3_resource_leak": [
        {
            "id": "F3-01",
            "desc": "open() call — LLM verifies if properly wrapped in 'with' context manager",
            "regex": r'\bopen\s*\([^)]+\)',
            "severity": "Warning",
        },
        {
            "id": "F3-02",
            "desc": "subprocess without explicit timeout — potential hang",
            "regex": r'subprocess\.\w+\s*\([^)]*\)',
            "severity": "Warning",
        },
        {
            "id": "F3-03",
            "desc": "Unbounded append without pruning — memory growth risk",
            "regex": r'\b(?:output_lines|lines|results|sessions)\s*\.\s*append\s*\(',
            "severity": "Info",
        },
    ],
    "F4_regex_vulnerability": [
        {
            "id": "F4-01",
            "desc": "Nested quantifiers — catastrophic backtracking (ReDoS) risk",
            "regex": r're\.(?:compile|search|match|findall)\s*\([^)]*\([^)]*[+*]\)[+*]',
            "severity": "Critical",
        },
        {
            "id": "F4-02",
            "desc": "re.DOTALL usage — multiline matching may be unexpectedly broad",
            "regex": r're\.DOTALL|re\.S\b',
            "severity": "Info",
        },
        {
            "id": "F4-03",
            "desc": "re.compile/search/match without error handling — hangs on malformed input",
            "regex": r'\bre\.(compile|search|match|findall)\s*\(',
            "severity": "Info",
        },
    ],
    "F5_llm_specific": [
        {
            "id": "F5-01",
            "desc": "maxTurns value — verify sufficient depth for workflow",
            "regex": r'maxTurns:\s*\d+',
            "severity": "Info",
        },
        {
            "id": "F5-02",
            "desc": "json.loads without except — silent failure on LLM malformed output",
            "regex": r'\bjson\.loads\s*\(',
            "severity": "Warning",
        },
        {
            "id": "F5-03",
            "desc": "Agent tool invocation — verify error handling on agent failure",
            "regex": r'subagent_type|Agent\s+tool',
            "severity": "Info",
        },
    ],
    "F6_hook_system": [
        {
            "id": "F6-01",
            "desc": "sys.exit(2) — verify this hook is intended to be blocking",
            "regex": r'\bsys\.exit\s*\(\s*2\s*\)',
            "severity": "Warning",
        },
        {
            "id": "F6-02",
            "desc": "Broad except with pass/exit(0) — silent hook failure",
            "regex": r'except\s+Exception[^:]*:\s*\n\s*(?:pass\b|sys\.exit\(0\))',
            "severity": "Critical",
        },
        {
            "id": "F6-03",
            "desc": "stdin.read() without .strip() — empty/whitespace input handling",
            "regex": r'\bstdin\.read\(\s*\)\s*(?!\.strip)',
            "severity": "Info",
        },
    ],
    "F7_sot_integrity": [
        {
            "id": "F7-01",
            "desc": "JSON write without atomic_write — SOT corruption on process kill",
            "regex": r'json\.dump\s*\([^)]+\)\s*\n.*open\s*\(',
            "severity": "Warning",
        },
        {
            "id": "F7-02",
            "desc": "Direct open('w') on SOT file — bypasses guard_sot_write.py",
            "regex": r'open\s*\([^)]*["\'](?:session|state)[^"\']*\.(?:json|yaml)["\'][^)]*,\s*["\']w["\']',
            "severity": "Critical",
        },
        {
            "id": "F7-03",
            "desc": "_KI_REQUIRED_DEFAULTS reference — schema field may need SOT validation update",
            "regex": r'_KI_REQUIRED_DEFAULTS|_SOT_REQUIRED',
            "severity": "Info",
        },
    ],
}


def _should_exclude(filename: str) -> bool:
    """Return True if the file should be excluded from scanning."""
    for pat in EXCLUDE_PATTERNS:
        if re.search(pat, filename):
            return True
    return False


def _extract_python_symbols(content: str) -> List[str]:
    """Extract top-level function and class names from Python content."""
    symbols = []
    for m in re.finditer(r"^(?:def|class)\s+(\w+)", content, re.MULTILINE):
        symbols.append(m.group(1))
    return symbols[:60]  # Cap at 60 to keep map size reasonable


def _scan_file(filepath: str, project_dir: str) -> Dict[str, Any]:
    """Scan a single file for F1-F7 patterns. Returns structured result."""
    rel_path = os.path.relpath(filepath, project_dir)
    ext = os.path.splitext(filepath)[1]

    result: Dict[str, Any] = {
        "path": rel_path,
        "extension": ext,
        "line_count": 0,
        "symbols": [],
        "pattern_matches": {},
    }

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        content = "".join(lines)
        result["line_count"] = len(lines)

        # Python symbol extraction
        if ext == ".py":
            result["symbols"] = _extract_python_symbols(content)

        # F1-F7 pattern matching
        # .md files: only scan F5 (maxTurns, Agent invocations) — F1/F2/F3/F4/F6/F7
        # patterns in .md files are documentation examples, not executable code.
        scan_categories = (
            FAILURE_PATTERNS
            if ext == ".py"
            else {k: v for k, v in FAILURE_PATTERNS.items() if k == "F5_llm_specific"}
        )
        for category, patterns in scan_categories.items():
            matches = []
            for pdef in patterns:
                try:
                    for m in re.finditer(pdef["regex"], content, re.MULTILINE):
                        line_no = content[: m.start()].count("\n") + 1
                        snippet = lines[line_no - 1].rstrip() if line_no <= len(lines) else ""
                        matches.append(
                            {
                                "pattern_id": pdef["id"],
                                "desc": pdef["desc"],
                                "severity_hint": pdef["severity"],
                                "line": line_no,
                                "snippet": snippet[:120],  # Truncate long lines
                            }
                        )
                except re.error:
                    # Malformed regex — skip silently (P1: never crash)
                    continue

            if matches:
                result["pattern_matches"][category] = matches

    except (IOError, OSError) as e:
        result["error"] = str(e)

    return result


def _collect_files(project_dir: str) -> List[str]:
    """Collect all production files from SCAN_TARGETS."""
    collected = []
    for target_rel in SCAN_TARGETS:
        target_abs = os.path.join(project_dir, target_rel)
        if not os.path.isdir(target_abs):
            continue
        for fname in sorted(os.listdir(target_abs)):
            if os.path.splitext(fname)[1] not in SCAN_EXTENSIONS:
                continue
            if _should_exclude(fname):
                continue
            collected.append(os.path.join(target_abs, fname))
    return collected


def _build_category_summary(file_results: List[Dict]) -> Dict[str, int]:
    """Aggregate match counts per failure category across all files."""
    summary: Dict[str, int] = {}
    for fr in file_results:
        for cat, matches in fr.get("pattern_matches", {}).items():
            summary[cat] = summary.get(cat, 0) + len(matches)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan codebase for F1-F7 failure taxonomy patterns (Phase A)"
    )
    parser.add_argument(
        "--project-dir",
        default=os.environ.get("CLAUDE_PROJECT_DIR", "."),
        help="Project root directory",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON path (default: .claude/context-snapshots/fp-code-map.json)",
    )
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    output_path = args.output or os.path.join(
        project_dir, ".claude", "context-snapshots", "fp-code-map.json"
    )

    # Collect and scan files
    files = _collect_files(project_dir)
    file_results = [_scan_file(fp, project_dir) for fp in files]

    # Build output
    category_summary = _build_category_summary(file_results)
    code_map = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_dir": project_dir,
        "scan_targets": SCAN_TARGETS,
        "files_scanned": len(file_results),
        "category_summary": category_summary,
        "failure_taxonomy": {
            cat: [p["id"] for p in pats]
            for cat, pats in FAILURE_PATTERNS.items()
        },
        "files": file_results,
    }

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(code_map, f, indent=2, ensure_ascii=False)

    # Summary to stdout (for /predict-failures command to read)
    print(f"[scan_code_structure] Scanned {len(file_results)} files → {output_path}")
    categories_with_matches = [k for k, v in category_summary.items() if v > 0]
    print(f"  Categories with matches: {categories_with_matches}")
    critical_files = [
        fr["path"]
        for fr in file_results
        if any(
            m["severity_hint"] == "Critical"
            for matches in fr.get("pattern_matches", {}).values()
            for m in matches
        )
    ]
    if critical_files:
        print(f"  Files with Critical signals: {critical_files}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # P1: never block Claude on internal errors
        print(f"[scan_code_structure] ERROR: {e}", file=sys.stderr)
        sys.exit(0)
