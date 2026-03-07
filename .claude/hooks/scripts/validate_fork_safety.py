#!/usr/bin/env python3
"""Validate fork safety for skills and commands with `context: fork`.

P1 Deterministic Validator — eliminates LLM hallucination in fork decisions.

This is a standalone CLI tool (NOT a Hook). Intended usage:
  1. Manual validation after editing skill/command files
  2. Called by skill-creator / subagent-creator as post-generation check
  3. Project-wide audit via --all flag

When a skill (.claude/skills/*/SKILL.md) or command (.claude/commands/*.md)
declares `context: fork` in its frontmatter, this script verifies that the
fork is safe by checking 5 deterministic rules:

  FS-1: Detect `context: fork` in frontmatter
  FS-2: No SOT write patterns in body (session.json, state.yaml, checklist_manager)
  FS-3: No Bash dependency without compatible agent
  FS-4: No HITL patterns (AskUserQuestion, human approval)
  FS-5: If `agent:` specified, validate agent exists and has required tools

Usage:
  # Direct CLI validation
  python3 validate_fork_safety.py --file path/to/command.md --project-dir /path/to/project

  # Validate all skills and commands in project
  python3 validate_fork_safety.py --all --project-dir /path/to/project

Exit codes:
  0 — PASS (no fork, or fork is safe)
  1 — FAIL (fork safety violation detected)

SOT Compliance: READ-ONLY. Never modifies any files.

ADR: Fork safety P1 enforcement — prevents SOT corruption from unsafe forks.
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# FS-2: SOT Write Patterns (deterministic string matching)
#
# These patterns indicate the skill/command writes to SOT files.
# Any match in the body means fork is UNSAFE (Absolute Criteria 2 violation).
# ---------------------------------------------------------------------------
SOT_WRITE_PATTERNS = [
    # Direct SOT file references (write context)
    r"session\.json",
    r"state\.yaml",
    r"state\.yml",
    # checklist_manager write operations
    r"checklist_manager\.py\s+.*--advance",
    r"checklist_manager\.py\s+.*--gate",
    r"checklist_manager\.py\s+.*--hitl",
    r"checklist_manager\.py\s+.*--init",
    r"checklist_manager\.py\s+.*--checkpoint",
    # Generic SOT write indicators
    r"(?i)update\s+(?:the\s+)?SOT",
    r"(?i)write\s+(?:to\s+)?SOT",
    r"(?i)record\s+.*\s+in\s+SOT",
    r"(?i)save\s+.*\s+to\s+SOT",
    r"(?i)Track\s+Progress\s+in\s+SOT",
]

# Patterns that are READ-ONLY SOT access (safe — not flagged)
SOT_READ_PATTERNS = [
    r"checklist_manager\.py\s+.*--status",
    r"checklist_manager\.py\s+.*--translation-progress",
    r"(?i)read\s+(?:the\s+)?SOT",
    r"(?i)check\s+(?:the\s+)?SOT",
]

# ---------------------------------------------------------------------------
# FS-3: Bash Dependency Patterns
#
# These patterns indicate the command needs Bash tool access.
# If an agent is specified that lacks Bash, fork will break.
# ---------------------------------------------------------------------------
BASH_DEPENDENCY_PATTERNS = [
    r"python3\s+",
    r"\bpython\s+",
    r"```bash",
    r"```sh",
    r"validate_\w+\.py",
    r"verify_\w+\.py",
    r"compute_\w+\.py",
    r"checklist_manager\.py",
    r"fallback_controller\.py",
    r"teammate_health_check\.py",
]

# ---------------------------------------------------------------------------
# FS-4: HITL (Human-in-the-Loop) Patterns
#
# Commands with HITL steps require main context for user interaction.
# Fork isolates the context, making HITL unreliable.
# ---------------------------------------------------------------------------
HITL_PATTERNS = [
    r"AskUserQuestion",
    r"(?i)HITL[-\s]?\d+",
    r"(?i)human.?in.?the.?loop",
    r"(?i)human\s+approval",
    r"(?i)user\s+approval",
    r"(?i)ask\s+(?:the\s+)?user",
    r"(?i)wait\s+for\s+(?:user|human)",
    r"(?i)present\s+.*\s+for\s+(?:user|human)\s+review",
]


def parse_frontmatter(content: str) -> Tuple[Dict[str, str], str]:
    """Parse YAML frontmatter from a markdown file.

    Returns:
        Tuple of (frontmatter_dict, body_text).
        If no frontmatter, returns ({}, full_content).
    """
    if not content.startswith("---"):
        return {}, content

    end_match = re.search(r"\n---\s*\n", content[3:])
    if not end_match:
        return {}, content

    fm_text = content[3:end_match.start() + 3]
    body = content[end_match.end() + 3:]

    # Simple YAML-like parsing (no external dependency)
    fm = {}
    for line in fm_text.strip().split("\n"):
        line = line.strip()
        if ":" in line and not line.startswith("#"):
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value:
                fm[key] = value

    return fm, body


def parse_agent_tools(agent_path: str) -> Optional[List[str]]:
    """Parse the tools list from an agent .md file's frontmatter.

    Returns:
        List of tool names, or None if agent file not found.
    """
    if not os.path.isfile(agent_path):
        return None

    try:
        with open(agent_path, "r", encoding="utf-8") as f:
            content = f.read()
    except IOError:
        return None

    fm, _ = parse_frontmatter(content)
    tools_str = fm.get("tools", "")
    if not tools_str:
        return []

    return [t.strip() for t in tools_str.split(",")]


def check_patterns(text: str, patterns: List[str]) -> List[str]:
    """Check text against a list of regex patterns.

    Returns list of matched pattern descriptions.
    """
    matches = []
    for pattern in patterns:
        found = re.search(pattern, text)
        if found:
            matches.append(f"  matched: /{pattern}/ => \"{found.group()}\"")
    return matches


def is_sot_read_only(match_line: str, body: str) -> bool:
    """Check if a SOT pattern match is actually read-only access."""
    for read_pattern in SOT_READ_PATTERNS:
        if re.search(read_pattern, match_line):
            return True
    return False


def validate_file(file_path: str, project_dir: str) -> Tuple[bool, List[str]]:
    """Validate fork safety for a single skill/command file.

    Returns:
        Tuple of (is_pass, list_of_messages).
    """
    messages = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except IOError as e:
        return False, [f"FAIL: Cannot read file: {e}"]

    fm, body = parse_frontmatter(content)

    # FS-1: Check if context: fork is declared
    context_value = fm.get("context", "")
    if context_value != "fork":
        return True, []  # No fork — nothing to validate

    rel_path = os.path.relpath(file_path, project_dir) if project_dir else file_path
    messages.append(f"FORK SAFETY CHECK: {rel_path}")
    messages.append(f"  context: fork detected in frontmatter")

    violations = []

    # FS-2: SOT write patterns
    for pattern in SOT_WRITE_PATTERNS:
        found = re.search(pattern, body)
        if found:
            # Check if this is actually a read-only reference
            # Get the line containing the match
            line_start = body.rfind("\n", 0, found.start()) + 1
            line_end = body.find("\n", found.end())
            if line_end == -1:
                line_end = len(body)
            match_line = body[line_start:line_end]

            if not is_sot_read_only(match_line, body):
                violations.append(
                    f"[FS-2] SOT write pattern found — fork must not write to SOT\n"
                    f"  matched: /{pattern}/ => \"{found.group()}\"\n"
                    f"  line: {match_line.strip()}"
                )

    # FS-3: Bash dependency check
    bash_matches = check_patterns(body, BASH_DEPENDENCY_PATTERNS)
    if bash_matches:
        agent_name = fm.get("agent", "")
        has_bash = True  # Default: no agent specified → general-purpose (has Bash)

        if agent_name and agent_name not in ("general-purpose", "Explore", "Plan"):
            # Check if specified agent has Bash
            agent_path = os.path.join(
                project_dir, ".claude", "agents", f"{agent_name}.md"
            )
            agent_tools = parse_agent_tools(agent_path)

            if agent_tools is None:
                violations.append(
                    f"[FS-5] Agent '{agent_name}' not found at {agent_path}"
                )
                has_bash = False
            elif "Bash" not in agent_tools:
                has_bash = False

        if not has_bash:
            violations.append(
                f"[FS-3] Bash dependency detected but agent '{agent_name}' "
                f"lacks Bash tool\n" +
                "\n".join(bash_matches)
            )

    # FS-4: HITL patterns
    hitl_matches = check_patterns(body, HITL_PATTERNS)
    if hitl_matches:
        violations.append(
            f"[FS-4] HITL pattern found — fork isolates context from user\n" +
            "\n".join(hitl_matches)
        )

    # FS-5: Agent existence (if specified and not already checked in FS-3)
    agent_name = fm.get("agent", "")
    if agent_name and agent_name not in ("general-purpose", "Explore", "Plan"):
        agent_path = os.path.join(
            project_dir, ".claude", "agents", f"{agent_name}.md"
        )
        if not os.path.isfile(agent_path):
            # Only add if not already reported in FS-3
            fs5_msg = f"[FS-5] Agent '{agent_name}' not found at {agent_path}"
            if not any("[FS-5]" in v for v in violations):
                violations.append(fs5_msg)

    # Result
    if violations:
        messages.append(f"  FAIL — {len(violations)} violation(s):")
        for v in violations:
            messages.append(f"  {v}")
        return False, messages
    else:
        messages.append("  PASS — fork is safe")
        return True, messages


def find_all_targets(project_dir: str) -> List[str]:
    """Find all skill and command files in the project."""
    targets = []

    # Skills
    skills_dir = os.path.join(project_dir, ".claude", "skills")
    if os.path.isdir(skills_dir):
        for root, _, files in os.walk(skills_dir):
            for f in files:
                if f.endswith(".md"):
                    targets.append(os.path.join(root, f))

    # Commands
    commands_dir = os.path.join(project_dir, ".claude", "commands")
    if os.path.isdir(commands_dir):
        for f in os.listdir(commands_dir):
            if f.endswith(".md"):
                targets.append(os.path.join(commands_dir, f))

    return sorted(targets)


def main():
    parser = argparse.ArgumentParser(
        description="Validate fork safety for skills/commands (P1 deterministic)"
    )
    parser.add_argument(
        "--file", type=str,
        help="Path to a single skill/command .md file to validate"
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Validate all skills and commands in the project"
    )
    parser.add_argument(
        "--project-dir", type=str,
        default=os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()),
        help="Project root directory (default: CLAUDE_PROJECT_DIR or cwd)"
    )
    args = parser.parse_args()

    if not args.file and not args.all:
        parser.print_help()
        return 0

    project_dir = os.path.abspath(args.project_dir)
    all_pass = True

    if args.file:
        targets = [os.path.abspath(args.file)]
    else:
        targets = find_all_targets(project_dir)

    checked = 0
    failed = 0

    for target in targets:
        is_pass, messages = validate_file(target, project_dir)
        if messages:  # Only print if there's a fork to validate
            for msg in messages:
                print(msg, file=sys.stderr)
            print("", file=sys.stderr)
            checked += 1
            if not is_pass:
                failed += 1
                all_pass = False

    if checked > 0:
        print(
            f"Fork safety: {checked} file(s) checked, "
            f"{checked - failed} passed, {failed} failed",
            file=sys.stderr,
        )

    return 0 if all_pass else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"FAIL: Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
