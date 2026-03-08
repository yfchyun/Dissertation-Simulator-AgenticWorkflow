#!/usr/bin/env python3
"""
extract_json_block.py — P1 JSON Block Extractor for Agent Responses

Deterministically extracts the first valid ```json ... ``` code block from text.
Prevents hallucination at LLM→P1 handoff points by removing LLM from JSON extraction.

P1 Compliance:
  - Pure stdlib, deterministic regex extraction, exit 0 always
  - Single responsibility: text → JSON extraction
  - No LLM calls, no heuristics

CLI:
  # Extract JSON from agent response text:
  python extract_json_block.py \\
    --input agent-response.txt \\
    --output fp-draft.json

  # With critic fallback (if extraction fails, generate empty critic):
  python extract_json_block.py \\
    --input agent-response.txt \\
    --output fp-critic.json \\
    --fallback-critic

Used by: /predict-failures slash command (Phase B-1→C-1 and B-2→C-2 handoffs)

Design:
  - Regex-based extraction: ```json\\n ... ``` pattern
  - First valid JSON block wins: skips malformed blocks, tries next
  - Fallback mode: --fallback-critic generates {"judgments":[],"additions":[]}
    deterministically (never typed by LLM — prevents spelling errors)
  - Full agent response preserved in input file for debugging

ADR: H-1/H-2 hallucination fix — removes LLM from data handoff path
"""

import argparse
import json
import os
import re
import sys
from typing import Any, Optional


# Deterministic fallback for critic failure — NEVER LLM-typed
CRITIC_FALLBACK: dict[str, list[Any]] = {"judgments": [], "additions": []}


def extract_json_block(text: str) -> Optional[dict[str, Any]]:
    """Extract the first valid ```json ... ``` code block from text.

    Scans for all ```json ... ``` blocks in order. For each block,
    attempts json.loads(). Returns the first successfully parsed dict.
    Returns None if no valid JSON block is found.

    Args:
        text: Full agent response text containing one or more JSON code blocks.

    Returns:
        Parsed dict from the first valid JSON block, or None.
    """
    # Match ```json ... ``` blocks — non-greedy content capture
    pattern = r"```json\s*\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)

    for match in matches:
        try:
            parsed = json.loads(match.strip())
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            continue

    return None


def _write_output(path: str, data: dict[str, Any]) -> None:
    """Write JSON to file, creating parent directories as needed."""
    out_dir = os.path.dirname(os.path.abspath(path))
    os.makedirs(out_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract JSON block from agent response text (P1 deterministic)"
    )
    parser.add_argument(
        "--input", required=True,
        help="Input text file (agent response saved by Write tool)"
    )
    parser.add_argument(
        "--output", required=True,
        help="Output JSON file path"
    )
    parser.add_argument(
        "--fallback-critic",
        action="store_true",
        help="If extraction fails, generate empty critic JSON instead of reporting failure"
    )
    args = parser.parse_args()

    # Read input text
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            text = f.read()
    except (IOError, OSError) as e:
        print(
            f"[extract_json_block] ERROR reading input '{args.input}': {e}",
            file=sys.stderr,
        )
        if args.fallback_critic:
            _write_output(args.output, CRITIC_FALLBACK)
            print(
                f"[extract_json_block] Fallback critic JSON written (read error) → {args.output}"
            )
        else:
            # R-1/S-1: consistent stale output cleanup on all failure paths
            if os.path.exists(args.output):
                os.remove(args.output)
        sys.exit(0)

    # Extract JSON block
    result = extract_json_block(text)

    if result is not None:
        _write_output(args.output, result)
        # Count top-level keys for diagnostic
        keys = sorted(result.keys())[:5]
        print(f"[extract_json_block] Extracted JSON block (keys: {keys}) → {args.output}")
    elif args.fallback_critic:
        _write_output(args.output, CRITIC_FALLBACK)
        print(
            "[extract_json_block] No valid ```json``` block found — "
            f"fallback critic JSON written → {args.output}"
        )
    else:
        # R-1: Prevent stale output from previous runs masking this failure
        if os.path.exists(args.output):
            os.remove(args.output)
        print(
            "[extract_json_block] FAIL: No valid ```json``` block found in input "
            f"({len(text)} chars, {text.count(chr(10))} lines)",
            file=sys.stderr,
        )
        # Exit 0 — P1 never blocks. Caller checks output file existence.
        sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # P1: never block Claude on internal errors
        print(f"[extract_json_block] FATAL: {e}", file=sys.stderr)
        sys.exit(0)
