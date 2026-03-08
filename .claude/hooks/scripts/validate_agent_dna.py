#!/usr/bin/env python3
"""
Agent DNA P1 Validation — validate_agent_dna.py

Deterministic structural check for newly created agent .md files.
Verifies that all required AgenticWorkflow DNA sections are present.

Required DNA components (from soul.md §0 + AGENTS.md):
  - DA1: YAML frontmatter block (--- ... ---)
  - DA2: `name` field in frontmatter
  - DA3: `model` field in frontmatter (non-empty)
  - DA4: `maxTurns` field in frontmatter (integer value)
  - DA5: `tools` field in frontmatter (non-empty)
  - DA6: `## Inherited DNA` section present
  - DA7: English-First declaration in Inherited DNA section

Usage:
    python3 validate_agent_dna.py --agent-file .claude/agents/my-agent.md

    # Batch check all agents:
    python3 validate_agent_dna.py --agent-dir .claude/agents/

Output: JSON to stdout
    {
      "agent_file": ".claude/agents/my-agent.md",
      "checks": [
        {"check": "DA1", "status": "PASS", "detail": "Frontmatter block found"},
        {"check": "DA2", "status": "PASS", "detail": "name: my-agent"},
        ...
      ],
      "passed": true,
      "warnings": []
    }

Exit codes:
    0 — always (non-blocking, P1 compliant)

Architecture:
    - Pure Python, stdlib only (no external dependencies)
    - Deterministic: same input → same output, every time
    - P1 Compliance: zero heuristic inference, zero LLM — pure regex + string checks
    - SOT Compliance: read-only
"""

import argparse
import json
import os
import re
import sys

# Valid model values (Claude model identifiers)
_VALID_MODELS = {
    "opus", "sonnet", "haiku",
    "claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5",
    "claude-haiku-4-5-20251001",
    "claude-opus-4-5", "claude-sonnet-4-5",
    # Allow partial matches for future models (checked via prefix in DA3)
}

# Patterns for each DNA check
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_FIELD_RE = re.compile(r"^(\w[\w\-]*)\s*:\s*(.+)$", re.MULTILINE)
_MAX_TURNS_RE = re.compile(r"^maxTurns\s*:\s*(\d+)", re.MULTILINE | re.IGNORECASE)
_INHERITED_DNA_RE = re.compile(r"^##\s+Inherited DNA", re.MULTILINE | re.IGNORECASE)
_ENGLISH_FIRST_RE = re.compile(r"English[-\s]First", re.IGNORECASE)


# =============================================================================
# Individual DA Checks
# =============================================================================

def check_da1_frontmatter(content: str) -> dict:
    """DA1: YAML frontmatter block (--- ... ---) must be present."""
    match = _FRONTMATTER_RE.search(content)
    if match:
        return {
            "check": "DA1",
            "status": "PASS",
            "detail": "YAML frontmatter block found",
            "frontmatter": match.group(1),
        }
    return {
        "check": "DA1",
        "status": "FAIL",
        "detail": "No YAML frontmatter block (--- ... ---) found. Agent .md files must start with frontmatter.",
        "frontmatter": None,
    }


def check_da2_name(frontmatter: str | None) -> dict:
    """DA2: `name` field must be present in frontmatter."""
    if not frontmatter:
        return {"check": "DA2", "status": "SKIP", "detail": "DA1 failed — no frontmatter"}
    match = re.search(r"^name\s*:\s*(.+)$", frontmatter, re.MULTILINE)
    if match:
        name = match.group(1).strip()
        return {"check": "DA2", "status": "PASS", "detail": f"name: {name}", "value": name}
    return {
        "check": "DA2",
        "status": "FAIL",
        "detail": "No `name` field in frontmatter.",
    }


def check_da3_model(frontmatter: str | None) -> dict:
    """DA3: `model` field must be present and non-empty."""
    if not frontmatter:
        return {"check": "DA3", "status": "SKIP", "detail": "DA1 failed — no frontmatter"}
    match = re.search(r"^model\s*:\s*(.+)$", frontmatter, re.MULTILINE)
    if not match:
        return {
            "check": "DA3",
            "status": "FAIL",
            "detail": "No `model` field in frontmatter. Must specify model (e.g., opus, sonnet, haiku).",
        }
    model = match.group(1).strip().lower()
    # Accept exact match or known claude- prefix
    is_valid = (
        model in _VALID_MODELS
        or model.startswith("claude-")
        or any(v in model for v in ("opus", "sonnet", "haiku"))
    )
    if is_valid:
        return {"check": "DA3", "status": "PASS", "detail": f"model: {model}", "value": model}
    return {
        "check": "DA3",
        "status": "WARN",
        "detail": f"Unknown model value `{model}`. Expected one of: opus, sonnet, haiku (or claude-* variant).",
        "value": model,
    }


def check_da4_max_turns(frontmatter: str | None) -> dict:
    """DA4: `maxTurns` field must be present and be a positive integer."""
    if not frontmatter:
        return {"check": "DA4", "status": "SKIP", "detail": "DA1 failed — no frontmatter"}
    match = _MAX_TURNS_RE.search(frontmatter)
    if not match:
        return {
            "check": "DA4",
            "status": "FAIL",
            "detail": "No `maxTurns` field in frontmatter. All agents must declare maxTurns to prevent runaway loops.",
        }
    turns = int(match.group(1))
    if turns < 1:
        return {
            "check": "DA4",
            "status": "FAIL",
            "detail": f"maxTurns={turns} is invalid (must be ≥ 1).",
            "value": turns,
        }
    if turns > 500:
        return {
            "check": "DA4",
            "status": "WARN",
            "detail": f"maxTurns={turns} is unusually high (> 500). Verify this is intentional.",
            "value": turns,
        }
    return {
        "check": "DA4",
        "status": "PASS",
        "detail": f"maxTurns: {turns}",
        "value": turns,
    }


def check_da5_tools(frontmatter: str | None) -> dict:
    """DA5: `tools` field must be present and non-empty."""
    if not frontmatter:
        return {"check": "DA5", "status": "SKIP", "detail": "DA1 failed — no frontmatter"}
    match = re.search(r"^tools\s*:\s*(.+)$", frontmatter, re.MULTILINE)
    if not match:
        return {
            "check": "DA5",
            "status": "FAIL",
            "detail": "No `tools` field in frontmatter. Agent must declare tool access.",
        }
    tools = match.group(1).strip()
    if not tools:
        return {
            "check": "DA5",
            "status": "FAIL",
            "detail": "`tools` field is empty.",
        }
    return {"check": "DA5", "status": "PASS", "detail": f"tools: {tools}", "value": tools}


def check_da6_inherited_dna(content: str) -> dict:
    """DA6: `## Inherited DNA` section must be present in agent body."""
    if _INHERITED_DNA_RE.search(content):
        return {
            "check": "DA6",
            "status": "PASS",
            "detail": "## Inherited DNA section found",
        }
    return {
        "check": "DA6",
        "status": "FAIL",
        "detail": (
            "Missing `## Inherited DNA` section. All agents must express the "
            "AgenticWorkflow genome (soul.md §0). Add: "
            "`## Inherited DNA\\n| DNA Component | Expression |\\n| Absolute Criteria 1 | ... |`"
        ),
    }


def check_da7_english_first(content: str, dna_start: int | None) -> dict:
    """DA7: English-First declaration must appear in the Inherited DNA section."""
    if dna_start is None:
        return {"check": "DA7", "status": "SKIP", "detail": "DA6 failed — no Inherited DNA section"}
    # Extract from DNA section to next ## heading
    dna_section = content[dna_start:]
    # Find next heading after ## Inherited DNA
    next_heading = re.search(r"\n##\s+", dna_section[10:])
    if next_heading:
        dna_section = dna_section[: next_heading.start() + 10]
    if _ENGLISH_FIRST_RE.search(dna_section):
        return {
            "check": "DA7",
            "status": "PASS",
            "detail": "English-First declaration found in Inherited DNA section",
        }
    return {
        "check": "DA7",
        "status": "WARN",
        "detail": (
            "No `English-First` reference found in Inherited DNA section. "
            "All agents must declare English-First compliance (CLAUDE.md §언어 규칙)."
        ),
    }


# =============================================================================
# Main Validation Function
# =============================================================================

def validate_agent_dna(agent_file: str) -> dict:
    """Run DA1–DA7 checks on a single agent .md file.

    P1 Compliance: Deterministic regex checks, no LLM.
    SOT Compliance: Read-only.
    Non-blocking: returns result dict.
    Returns: dict with checks, passed, warnings.
    """
    warnings: list[str] = []

    if not os.path.isfile(agent_file):
        return {
            "agent_file": agent_file,
            "checks": [],
            "passed": False,
            "warnings": [f"File not found: {agent_file}"],
        }

    try:
        content = open(agent_file, "r", encoding="utf-8").read()
    except Exception as e:
        return {
            "agent_file": agent_file,
            "checks": [],
            "passed": False,
            "warnings": [f"Cannot read file: {e}"],
        }

    checks: list[dict] = []

    # DA1: Frontmatter
    da1 = check_da1_frontmatter(content)
    checks.append(da1)
    frontmatter = da1.get("frontmatter")  # None if DA1 failed

    # DA2–DA5: Frontmatter fields
    checks.append(check_da2_name(frontmatter))
    checks.append(check_da3_model(frontmatter))
    checks.append(check_da4_max_turns(frontmatter))
    checks.append(check_da5_tools(frontmatter))

    # DA6: Inherited DNA section
    da6 = check_da6_inherited_dna(content)
    checks.append(da6)
    dna_match = _INHERITED_DNA_RE.search(content)
    dna_start = dna_match.start() if dna_match else None

    # DA7: English-First in DNA section
    checks.append(check_da7_english_first(content, dna_start))

    # Overall: FAIL = hard failure; WARN = soft warning only
    hard_fails = [c for c in checks if c.get("status") == "FAIL"]
    soft_warns = [c for c in checks if c.get("status") == "WARN"]
    for w in soft_warns:
        warnings.append(f"{w['check']}: {w.get('detail', '')}")

    passed = len(hard_fails) == 0

    return {
        "agent_file": agent_file,
        "checks": checks,
        "hard_fails": len(hard_fails),
        "soft_warns": len(soft_warns),
        "passed": passed,
        "warnings": warnings,
    }


# =============================================================================
# CLI Entry Point
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agent DNA Structural Validator (DA1-DA7)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--agent-file",
        help="Path to a single agent .md file to validate",
    )
    group.add_argument(
        "--agent-dir",
        help="Directory containing agent .md files (validates all *.md files)",
    )
    args = parser.parse_args()

    if args.agent_file:
        result = validate_agent_dna(args.agent_file)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)

    # Batch mode: validate all .md files in directory
    if not os.path.isdir(args.agent_dir):
        print(json.dumps({"error": f"Directory not found: {args.agent_dir}"}))
        sys.exit(0)

    agent_files = sorted(
        os.path.join(args.agent_dir, f)
        for f in os.listdir(args.agent_dir)
        if f.endswith(".md")
    )

    if not agent_files:
        print(json.dumps({"error": f"No .md files found in {args.agent_dir}"}))
        sys.exit(0)

    results = [validate_agent_dna(af) for af in agent_files]
    failed = [r for r in results if not r["passed"]]

    batch_result = {
        "total": len(results),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "results": results,
        "all_passed": len(failed) == 0,
    }
    print(json.dumps(batch_result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
