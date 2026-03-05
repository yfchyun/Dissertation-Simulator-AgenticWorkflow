#!/usr/bin/env python3
"""Guard against unauthorized writes to thesis SOT (session.json).

PreToolUse Hook — blocks Write/Edit operations targeting the thesis SOT file
(session.json) when the caller is not the Orchestrator. This enforces
Absolute Criteria 2: single-writer pattern for SOT.

Exit codes:
  0 — allowed (not targeting SOT, or is Orchestrator)
  2 — BLOCKED (non-Orchestrator attempting SOT write)

This script is independent from _context_lib.py and context_guard.py
(ADR design decision — PreToolUse safety hooks run directly).

Environment variables read:
  CLAUDE_TOOL_NAME     — "Write" or "Edit"
  CLAUDE_TOOL_INPUT    — JSON with file_path
  CLAUDE_PROJECT_DIR   — project root
"""

import json
import os
import sys
from pathlib import Path

# The thesis SOT filename — must match checklist_manager.py
THESIS_SOT_FILENAME = "session.json"

# Directory pattern for thesis output
THESIS_OUTPUT_DIR = "thesis-output"


def is_thesis_sot_path(file_path: str, project_dir: str) -> bool:
    """Check if the target file is a thesis SOT file.

    Matches patterns:
      thesis-output/*/session.json
      thesis-output/**/session.json
    """
    try:
        rel = os.path.relpath(file_path, project_dir)
    except ValueError:
        return False

    parts = Path(rel).parts
    if len(parts) < 3:
        return False

    return (
        parts[0] == THESIS_OUTPUT_DIR
        and parts[-1] == THESIS_SOT_FILENAME
    )


def is_orchestrator_context() -> bool:
    """Determine if the current context is the Orchestrator.

    The Orchestrator is identified by:
    1. Being the main session (not a teammate)
    2. Having the THESIS_ORCHESTRATOR env var set

    For teammate sessions, CLAUDE_AGENT_TEAMS_TEAMMATE is set.
    """
    # Teammates have this env var set
    is_teammate = os.environ.get("CLAUDE_AGENT_TEAMS_TEAMMATE", "") != ""

    # Explicit orchestrator marker (set by thesis orchestrator during init)
    is_orchestrator = os.environ.get("THESIS_ORCHESTRATOR", "") == "1"

    # Also allow checklist_manager.py itself (called via Bash by orchestrator)
    # The guard is for direct Write/Edit tool calls
    return is_orchestrator or not is_teammate


def main():
    tool_name = os.environ.get("CLAUDE_TOOL_NAME", "")

    # Only guard Write and Edit operations
    if tool_name not in ("Write", "Edit"):
        return 0

    tool_input_raw = os.environ.get("CLAUDE_TOOL_INPUT", "{}")
    try:
        tool_input = json.loads(tool_input_raw)
    except json.JSONDecodeError:
        return 0  # Can't parse — allow and let other guards handle

    # Get the target file path
    file_path = tool_input.get("file_path", "")
    if not file_path:
        return 0

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if not project_dir:
        return 0

    # Check if targeting thesis SOT
    if not is_thesis_sot_path(file_path, project_dir):
        return 0  # Not thesis SOT — allow

    # Check authorization
    if is_orchestrator_context():
        return 0  # Orchestrator — allow

    # BLOCK: non-Orchestrator attempting to write thesis SOT
    print(
        f"BLOCKED: Unauthorized write to thesis SOT.\n"
        f"  File: {file_path}\n"
        f"  Rule: Only the Thesis Orchestrator may write to {THESIS_SOT_FILENAME}.\n"
        f"  Action: Use the Orchestrator to update SOT via checklist_manager.py.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
