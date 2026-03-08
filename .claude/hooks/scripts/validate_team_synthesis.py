#!/usr/bin/env python3
"""
Agent Team Synthesis P1 Validation — validate_team_synthesis.py

Deterministic completeness check for Agent Team parallel execution.
Verifies that:
  - All expected agent output files were actually produced (TS1)
  - Synthesis file exists and is non-empty (TS2)
  - Synthesis is longer than the largest individual agent output (TS3)
  - Synthesis contains unique content tokens from each agent (TS4)
  - No agent output is an exact substring of the synthesis without integration (TS5)

This is the P1 layer preventing Orchestrator hallucinations where the synthesis
claims to incorporate N agents but actually uses only 1 (or invents content).

Usage:
    python3 validate_team_synthesis.py \\
      --synthesis-file thesis-output/proj/research/synthesis.md \\
      --agent-files agent1.md agent2.md agent3.md

    python3 validate_team_synthesis.py \\
      --synthesis-file synthesis.md \\
      --agent-files a1.md a2.md \\
      --expected-agents 3

Output: JSON to stdout
    {
      "expected_agents": 3,
      "found_agents": 2,
      "synthesis_size": 4500,
      "max_agent_size": 1800,
      "synthesis_larger_than_max": true,
      "results": [
        {"check": "TS1", "agent_file": "a1.md", "exists": true, "status": "PASS"},
        {"check": "TS3", "detail": "...", "status": "PASS"},
        {"check": "TS4", "agent_file": "a1.md", "overlap_bigrams": 7, "status": "PASS"},
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
    - P1 Compliance: zero heuristic inference, zero LLM
    - SOT Compliance: read-only (reads agent output files and synthesis file)
"""

import argparse
import json
import os
import re
import sys

# Minimum bigram overlap for TS4 to consider an agent "represented" in synthesis.
# Bigrams (word pairs) are far more distinctive than single words —
# common thesis vocabulary ("research", "analysis") no longer inflates the score.
TS4_MIN_BIGRAM_OVERLAP = 3

# Minimum synthesis-to-agent-max size ratio for TS3
TS3_MIN_RATIO = 1.1

# TS5 sliding window size (chars). Overlapping windows (stride = size // 2) are checked.
# 300 chars ≈ 50 words — substantial enough to distinguish copy-paste from coincidence,
# small enough that a typical synthesis (2000+ chars) contains 10+ windows for thorough coverage.
TS5_WINDOW_SIZE = 300
TS5_WINDOW_STRIDE = TS5_WINDOW_SIZE // 2  # 150-char stride — overlapping windows

# Thesis-domain stopwords: these single words appear in virtually every thesis
# document and carry no discriminative signal for synthesis coverage detection.
# P1 Compliance: static frozenset — deterministic filtering, no inference.
_THESIS_STOPWORDS: frozenset[str] = frozenset({
    # Generic academic verbs / connectives
    "also", "thus", "that", "this", "with", "from", "have", "been", "were",
    "more", "than", "both", "each", "such", "when", "then", "them", "they",
    "their", "these", "those", "while", "which", "would", "could", "should",
    "does", "done", "used", "uses", "make", "made", "over", "into", "upon",
    "even", "only", "very", "well", "just", "also", "here", "there", "where",
    # Thesis/academic domain common nouns — appear in ALL chapters
    "research", "study", "paper", "thesis", "chapter", "section", "analysis",
    "result", "results", "finding", "findings", "method", "methods", "approach",
    "framework", "theory", "model", "data", "work", "literature", "review",
    "discussion", "conclusion", "introduction", "abstract", "reference",
    "figure", "table", "source", "author", "note", "page", "text", "content",
    "information", "knowledge", "process", "system", "context", "example",
    "focus", "based", "provide", "present", "shows", "argue", "claim",
    "support", "suggest", "indicate", "propose", "define", "describe",
    "identify", "examine", "explore", "explain", "understand", "apply",
    "consider", "relate", "include", "involve", "require", "remain",
    "develop", "form", "structure", "function", "purpose", "role", "level",
    "point", "term", "area", "field", "case", "type", "kind", "form",
    "part", "aspect", "factor", "effect", "impact", "issue", "problem",
    "question", "answer", "response", "critique", "evidence", "basis",
    "concept", "idea", "view", "position", "argument", "claim",
    # Korean thesis stopwords (≥4 chars in Hangul)
    "연구", "분석", "논문", "방법", "결과", "고찰", "검토", "이론", "개념",
    "사례", "문헌", "검색", "정리", "기반", "중심", "관련", "통해", "위해",
})


# =============================================================================
# P1 Helpers: Deterministic Bigram Extraction
# =============================================================================

def _words(text: str) -> list[str]:
    """Extract non-stopword words (≥4 chars) from text — deterministic, P1.

    Stopword filtering removes thesis-domain common words that appear in all
    documents and would otherwise create false overlap between any two thesis files.
    """
    raw = re.findall(r"[A-Za-z]{4,}|[가-힣]{2,}", text)
    return [w.lower() for w in raw if w.lower() not in _THESIS_STOPWORDS]


def _bigrams(text: str) -> set[tuple[str, str]]:
    """Extract consecutive word-pair bigrams after stopword filtering.

    Bigrams are far stronger evidence of shared content than single words.
    Two random thesis texts will share many single words but few specific bigrams.
    P1 Compliance: Deterministic, no NLP library, no inference.
    """
    ws = _words(text)
    return set(zip(ws, ws[1:]))


def _read_file(path: str) -> tuple[bool, str, int]:
    """Read file safely. Returns (exists, content, size)."""
    if not os.path.isfile(path):
        return False, "", 0
    try:
        content = open(path, "r", encoding="utf-8").read()
        return True, content, len(content.encode("utf-8"))
    except Exception:
        return True, "", 0  # exists but unreadable


# =============================================================================
# TS1–TS5 Check Functions
# =============================================================================

def check_ts1_agent_files_exist(agent_files: list[str]) -> list[dict]:
    """TS1: All expected agent output files must exist and be non-empty."""
    results = []
    for af in agent_files:
        exists, content, size = _read_file(af)
        non_empty = len(content.strip()) > 0 if content else False
        if not exists:
            status = "FAIL"
            detail = f"Agent output file not found: {af}"
        elif not non_empty:
            status = "FAIL"
            detail = f"Agent output file is empty: {af}"
        else:
            status = "PASS"
            detail = f"Found {size} bytes"
        results.append({
            "check": "TS1",
            "agent_file": os.path.basename(af),
            "exists": exists,
            "non_empty": non_empty,
            "size": size,
            "status": status,
            "detail": detail,
        })
    return results


def check_ts2_synthesis_exists(synthesis_file: str) -> dict:
    """TS2: Synthesis file must exist and be non-empty."""
    exists, content, size = _read_file(synthesis_file)
    non_empty = len(content.strip()) > 0 if content else False
    if not exists:
        return {
            "check": "TS2",
            "status": "FAIL",
            "detail": f"Synthesis file not found: {synthesis_file}",
            "size": 0,
        }
    if not non_empty:
        return {
            "check": "TS2",
            "status": "FAIL",
            "detail": "Synthesis file is empty",
            "size": 0,
        }
    return {
        "check": "TS2",
        "status": "PASS",
        "detail": f"Synthesis exists with {size} bytes",
        "size": size,
    }


def check_ts3_synthesis_size(synthesis_content: str, agent_contents: list[str]) -> dict:
    """TS3: Synthesis must be longer than the largest individual agent output.

    Rationale: A true synthesis of N agents should be longer than any single agent.
    If synthesis ≤ max(agent_sizes), the Orchestrator likely used only one agent.
    """
    synth_size = len(synthesis_content.encode("utf-8"))
    agent_sizes = [len(c.encode("utf-8")) for c in agent_contents if c.strip()]
    if not agent_sizes:
        return {
            "check": "TS3",
            "status": "SKIP",
            "detail": "No readable agent outputs to compare",
            "synthesis_size": synth_size,
            "max_agent_size": 0,
            "ratio": None,
        }
    max_agent = max(agent_sizes)
    ratio = synth_size / max_agent if max_agent > 0 else 0.0
    if ratio < TS3_MIN_RATIO:
        status = "WARN"
        detail = (
            f"Synthesis ({synth_size}B) is not significantly larger than "
            f"largest agent output ({max_agent}B), ratio={ratio:.2f} < {TS3_MIN_RATIO}. "
            "Possible single-agent synthesis."
        )
    else:
        status = "PASS"
        detail = (
            f"Synthesis ({synth_size}B) > max agent ({max_agent}B), ratio={ratio:.2f}"
        )
    return {
        "check": "TS3",
        "status": status,
        "detail": detail,
        "synthesis_size": synth_size,
        "max_agent_size": max_agent,
        "ratio": round(ratio, 3),
    }


def check_ts4_bigram_overlap(
    synthesis_content: str,
    agent_files: list[str],
    agent_contents: list[str],
) -> list[dict]:
    """TS4: Synthesis must contain bigram overlap from each agent's distinctive content.

    Uses consecutive word-pair (bigram) matching after thesis-domain stopword filtering.
    This is a far stronger signal than single-word overlap:
      - Common thesis words ("research analysis", "data results") filtered as stopwords
      - Only domain-specific consecutive word pairs register as overlap
      - A hallucinated synthesis that never incorporated an agent's specific findings
        will have near-zero bigram overlap with that agent

    Threshold: TS4_MIN_BIGRAM_OVERLAP=3 bigrams is a conservative but meaningful bar.
    P1 Compliance: Deterministic — same files always produce same bigram sets.
    """
    synth_bigrams = _bigrams(synthesis_content)
    results = []
    for af, content in zip(agent_files, agent_contents):
        if not content.strip():
            results.append({
                "check": "TS4",
                "agent_file": os.path.basename(af),
                "overlap_bigrams": 0,
                "status": "SKIP",
                "detail": "Agent file unreadable — skip",
            })
            continue
        agent_bigrams = _bigrams(content)
        if not agent_bigrams:
            # WARN, not SKIP: inability to verify ≠ verified absence of problem.
            # If agent uses only stopwords, we cannot confirm synthesis coverage.
            # This warrants human review — silent SKIP could mask dropped agents.
            results.append({
                "check": "TS4",
                "agent_file": os.path.basename(af),
                "overlap_bigrams": 0,
                "status": "WARN",
                "detail": (
                    f"No distinctive bigrams in {os.path.basename(af)} after stopword "
                    "filtering. Cannot verify synthesis coverage — agent may use only "
                    "common vocabulary, or agent content was not incorporated. "
                    "Manual review required."
                ),
            })
            continue
        overlap = synth_bigrams & agent_bigrams
        count = len(overlap)
        # Surface up to 3 example bigrams for diagnostics
        examples = [f'"{a} {b}"' for a, b in list(overlap)[:3]]
        example_str = ", ".join(examples) if examples else "(none)"
        if count < TS4_MIN_BIGRAM_OVERLAP:
            status = "WARN"
            detail = (
                f"Only {count} distinctive bigrams shared between synthesis and "
                f"{os.path.basename(af)} (threshold={TS4_MIN_BIGRAM_OVERLAP}). "
                "Agent-specific content may be missing from synthesis."
            )
        else:
            status = "PASS"
            detail = f"{count} distinctive bigrams confirmed (e.g. {example_str})"
        results.append({
            "check": "TS4",
            "agent_file": os.path.basename(af),
            "overlap_bigrams": count,
            "agent_total_bigrams": len(agent_bigrams),
            "status": status,
            "detail": detail,
        })
    return results


def check_ts5_no_verbatim_copy(
    synthesis_content: str,
    agent_files: list[str],
    agent_contents: list[str],
) -> list[dict]:
    """TS5: Synthesis must not contain verbatim blocks copied from any agent output.

    Correct scanning direction: slide through the SYNTHESIS (not the agent) and
    check each synthesis window against all agent outputs. This guarantees detection
    regardless of WHERE in the agent output the Orchestrator copied from.

    Why synthesis-side scanning is correct:
      - We want to know: "Does the synthesis contain a verbatim chunk from agent X?"
      - Checking agent windows in synthesis is fragile — agent's prefix/suffix content
        dilutes windows that straddle the verbatim boundary (false negatives).
      - Checking synthesis windows in agents is correct — any 500-char synthesis block
        that came verbatim from an agent will be found in that agent's content.

    Each non-overlapping 500-char window of the synthesis is checked against all
    agent contents. A match means that chunk of synthesis is verbatim from an agent.

    P1 Compliance: Deterministic substring search (`in` operator), no heuristics.
    SOT Compliance: Read-only.
    """
    synth_stripped = synthesis_content.strip()
    if len(synth_stripped) < TS5_WINDOW_SIZE:
        # Synthesis too short — skip for all agents
        return [
            {
                "check": "TS5",
                "agent_file": os.path.basename(af),
                "status": "SKIP",
                "detail": f"Synthesis too short for verbatim check (<{TS5_WINDOW_SIZE} chars)",
                "windows_checked": 0,
            }
            for af in agent_files
        ]

    # Pre-strip all agent contents for O(1) repeated lookup
    agent_stripped = [c.strip() for c in agent_contents]

    # Slide through SYNTHESIS in overlapping windows (stride = WINDOW_SIZE // 2).
    # Overlapping ensures any verbatim block ≥ TS5_WINDOW_SIZE chars is fully contained
    # in at least one window — eliminates false negatives from boundary misalignment.
    synthesis_windows: list[str] = []
    for start in range(0, len(synth_stripped) - TS5_WINDOW_SIZE + 1, TS5_WINDOW_STRIDE):
        synthesis_windows.append(synth_stripped[start : start + TS5_WINDOW_SIZE])
    total_synth_windows = len(synthesis_windows)

    results = []
    for af, ac in zip(agent_files, agent_stripped):
        if len(ac) < TS5_WINDOW_SIZE:
            results.append({
                "check": "TS5",
                "agent_file": os.path.basename(af),
                "status": "SKIP",
                "detail": (
                    f"Agent output too short to contain a verbatim block "
                    f"(<{TS5_WINDOW_SIZE} chars)"
                ),
                "synth_windows_checked": total_synth_windows,
            })
            continue

        verbatim_found = False
        hit_synth_offset = -1
        for i, window in enumerate(synthesis_windows):
            if window in ac:
                verbatim_found = True
                hit_synth_offset = i * TS5_WINDOW_SIZE
                break

        if verbatim_found:
            status = "WARN"
            detail = (
                f"Synthesis window at offset ~{hit_synth_offset} is verbatim from "
                f"{os.path.basename(af)}. "
                "Orchestrator may have copy-pasted rather than synthesized."
            )
        else:
            status = "PASS"
            detail = (
                f"No verbatim block detected "
                f"({total_synth_windows} synthesis windows × {os.path.basename(af)})"
            )
        results.append({
            "check": "TS5",
            "agent_file": os.path.basename(af),
            "verbatim_found": verbatim_found,
            "synth_windows_checked": total_synth_windows,
            "hit_synth_offset": hit_synth_offset if verbatim_found else None,
            "status": status,
            "detail": detail,
        })
    return results


# =============================================================================
# Main Validation
# =============================================================================

def validate_team_synthesis(
    synthesis_file: str,
    agent_files: list[str],
    expected_agents: int | None = None,
) -> dict:
    """Run TS1–TS5 checks. Returns structured result dict.

    P1 Compliance: All checks deterministic, no LLM inference.
    SOT Compliance: Read-only access to output files.
    Non-blocking: returns result dict (caller handles exit code).
    """
    warnings: list[str] = []
    all_results: list[dict] = []

    # Expected vs found agent count
    found_agents = len(agent_files)
    expected = expected_agents if expected_agents is not None else found_agents
    if expected_agents is not None and found_agents < expected_agents:
        warnings.append(
            f"Expected {expected_agents} agent files, got {found_agents}. "
            "Missing agent outputs."
        )

    # Read all agent contents up front
    agent_contents: list[str] = []
    for af in agent_files:
        _, content, _ = _read_file(af)
        agent_contents.append(content)

    # Read synthesis content
    _, synth_content, synth_size = _read_file(synthesis_file)

    # TS1: All agent files exist
    ts1 = check_ts1_agent_files_exist(agent_files)
    all_results.extend(ts1)

    # TS2: Synthesis exists and non-empty
    ts2 = check_ts2_synthesis_exists(synthesis_file)
    all_results.append(ts2)

    # Only run TS3-TS5 if synthesis is readable
    if synth_content.strip():
        # TS3: Synthesis larger than max agent
        ts3 = check_ts3_synthesis_size(synth_content, agent_contents)
        all_results.append(ts3)

        # TS4: Bigram overlap per agent (stopword-filtered, stronger than unigram)
        ts4 = check_ts4_bigram_overlap(synth_content, agent_files, agent_contents)
        all_results.extend(ts4)

        # TS5: No verbatim copy-paste
        ts5 = check_ts5_no_verbatim_copy(synth_content, agent_files, agent_contents)
        all_results.extend(ts5)
    else:
        warnings.append("Synthesis file unreadable — skipping TS3/TS4/TS5")

    # Overall pass: TS1 all pass, TS2 pass; TS3/TS4/TS5 WARN are not hard failures
    hard_fails = [
        r for r in all_results
        if r.get("status") == "FAIL"
    ]
    passed = len(hard_fails) == 0

    return {
        "expected_agents": expected,
        "found_agents": found_agents,
        "synthesis_file": synthesis_file,
        "synthesis_size": synth_size,
        "results": all_results,
        "hard_fails": len(hard_fails),
        "warnings": warnings,
        "passed": passed,
    }


# =============================================================================
# CLI Entry Point
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agent Team Synthesis Completeness Validator (TS1-TS5)"
    )
    parser.add_argument(
        "--synthesis-file",
        required=True,
        help="Path to the synthesized/merged output file",
    )
    parser.add_argument(
        "--agent-files",
        nargs="+",
        default=[],
        help="Paths to individual agent output files",
    )
    parser.add_argument(
        "--expected-agents",
        type=int,
        default=None,
        help="Expected number of agents (optional cross-check)",
    )
    args = parser.parse_args()

    result = validate_team_synthesis(
        synthesis_file=args.synthesis_file,
        agent_files=args.agent_files,
        expected_agents=args.expected_agents,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
