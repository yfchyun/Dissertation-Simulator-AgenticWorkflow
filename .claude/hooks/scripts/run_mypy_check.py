#!/usr/bin/env python3
"""
mypy Type Check Hook — run_mypy_check.py

PostToolUse hook: runs mypy after Python file edits.
Enforces strict type checking on annotated Phase 1 files.
Warns (exit 0) on all other .py files.

Purpose: Prevent type regressions in annotated scripts.
         Implements "실제 작동" for the strict typing system.

Hook event: PostToolUse (Edit|Write)
SOT Compliance: Read-only, no file writes.
P1 Compliance: Deterministic — mypy output is reproducible.

Exit codes:
    0 — always (PostToolUse hooks cannot block after-the-fact)
"""

import json
import os
import re
import subprocess
import sys

# Scripts directory (relative to project root)
_SCRIPTS_SUBPATH = os.path.join(".claude", "hooks", "scripts")

# Regex to extract module names from [[tool.mypy.overrides]] section
_MYPY_MODULE_RE = re.compile(r'"([\w]+)"', re.MULTILINE)


def _get_project_dir() -> str:
    return os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())


def _find_pyproject_toml(project_dir: str) -> str | None:
    candidate = os.path.join(project_dir, "pyproject.toml")
    return candidate if os.path.exists(candidate) else None


def _load_strict_files(pyproject_path: str | None) -> frozenset[str]:
    """Read strict module list from pyproject.toml — single source of truth.

    Parses [[tool.mypy.overrides]] module list and converts to .py filenames.
    Falls back to empty frozenset if pyproject.toml is absent or unparseable.
    P1: pure regex string matching — deterministic, zero LLM.
    """
    if not pyproject_path or not os.path.exists(pyproject_path):
        return frozenset()
    try:
        content = open(pyproject_path, encoding="utf-8").read()
    except (IOError, UnicodeDecodeError):
        return frozenset()

    # Find [[tool.mypy.overrides]] section and extract module list
    overrides_match = re.search(
        r"\[\[tool\.mypy\.overrides\]\]\s*\nmodule\s*=\s*\[(.*?)\]",
        content,
        re.DOTALL,
    )
    if not overrides_match:
        return frozenset()

    modules_block = overrides_match.group(1)
    modules = _MYPY_MODULE_RE.findall(modules_block)
    return frozenset(f"{m}.py" for m in modules if m)


def main() -> int:
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return 0

    tool_name = hook_input.get("tool_name", "")
    if tool_name not in ("Edit", "Write"):
        return 0

    tool_input = hook_input.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path or not file_path.endswith(".py"):
        return 0

    filename = os.path.basename(file_path)
    project_dir = _get_project_dir()

    # Only check files in the hooks/scripts directory
    scripts_dir = os.path.join(project_dir, _SCRIPTS_SUBPATH)
    abs_file = os.path.abspath(file_path)
    if not abs_file.startswith(os.path.abspath(scripts_dir)):
        return 0

    if not os.path.exists(abs_file):
        return 0

    pyproject = _find_pyproject_toml(project_dir)
    strict_files = _load_strict_files(pyproject)
    is_strict = filename in strict_files

    # Build mypy command
    cmd = [sys.executable, "-m", "mypy", "--no-error-summary",
           "--ignore-missing-imports"]

    if pyproject:
        cmd.extend(["--config-file", pyproject])

    if is_strict:
        cmd.extend(["--disallow-untyped-defs", "--disallow-incomplete-defs",
                    "--strict-optional", "--warn-return-any"])
    else:
        # Lenient: only check for obvious errors, don't require annotations
        cmd.extend(["--no-strict-optional"])

    cmd.append(abs_file)

    result = subprocess.run(
        cmd, capture_output=True, text=True,
        cwd=os.path.join(project_dir, _SCRIPTS_SUBPATH),
    )

    if result.returncode != 0:
        prefix = "[mypy STRICT]" if is_strict else "[mypy WARN]"
        print(f"{prefix} {filename}:", file=sys.stderr)
        output = result.stdout.strip()
        if output:
            # Trim to avoid flooding output
            lines = output.splitlines()[:20]
            print("\n".join(lines), file=sys.stderr)
            if len(output.splitlines()) > 20:
                print(f"  ... ({len(output.splitlines()) - 20} more lines)", file=sys.stderr)
    else:
        if is_strict:
            print(f"[mypy OK] {filename} — strict check passed", file=sys.stderr)

    return 0  # PostToolUse: always exit 0 (cannot block after-the-fact)


if __name__ == "__main__":
    sys.exit(main())
