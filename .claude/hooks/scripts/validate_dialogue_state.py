#!/usr/bin/env python3
"""
Adversarial Dialogue State P1 Validation — validate_dialogue_state.py

Standalone script called by Orchestrator after each dialogue round completes.
NOT a Hook — manually invoked during workflow execution.

Usage:
    # Validate after Round K completes
    python3 .claude/hooks/scripts/validate_dialogue_state.py \
        --step 5 --round 2 --project-dir .

    # Validate final consensus state
    python3 .claude/hooks/scripts/validate_dialogue_state.py \
        --step 5 --round 2 --check-consensus --project-dir .

Output: JSON to stdout
    {"valid": true, "step": 5, "round": 2, "checks": {...}, "warnings": []}

Exit codes:
    0 — validation completed (check "valid" field for result)
    1 — argument error or fatal failure

Checks (DA1-DA5):
    DA1: Round files exist on disk for all rounds 1..K (domain-aware)
         Research: step-N-rK-fc.md + step-N-rK-rv.md (2 files/round)
         Development: step-N-rK-cr.md (1 file/round)
    DA2: For Research domain — draft-rK.md precedes critic-rK files (timestamp)
         Development domain: skipped (no draft files)
    DA3: If --check-consensus: final critic file verdict = PASS
    DA4: If SOT outcome == "escalated": final critic file verdict = FAIL
    DA5: rounds_used in SOT <= max_rounds (no counter overflow)

P1 Compliance: All checks are filesystem + regex + timestamp — zero LLM.
SOT Compliance: Read-only access to session.json and dialogue-logs/.
"""

import argparse
import json
import os
import re
import sys

# Add script directory to path for shared library import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Verdict extraction regex (same as validate_review.py)
_VERDICT_RE = re.compile(
    r"##\s*Verdict\s*[:\-]\s*(PASS|FAIL)", re.IGNORECASE
)
# Round outcome detection from SOT (checklist_manager dialogue_state)
_DIALOGUE_STATUS_RE = re.compile(r"dialogue_state", re.IGNORECASE)


def _read_sot(project_dir: str) -> dict[str, object] | None:
    """Read session.json (thesis SOT). Returns dict or None."""
    sot_path = os.path.join(project_dir, "session.json")
    if not os.path.exists(sot_path):
        # Try nested — thesis-output/*/session.json
        for root, dirs, files in os.walk(project_dir):
            for fname in files:
                if fname == "session.json":
                    candidate = os.path.join(root, fname)
                    try:
                        with open(candidate, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        if "dialogue_state" in data or "current_step" in data:
                            return dict(data)
                    except (json.JSONDecodeError, IOError):
                        continue
        return None
    try:
        with open(sot_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            return dict(loaded) if isinstance(loaded, dict) else None
    except (json.JSONDecodeError, IOError):
        return None


def _dialogue_logs_dir(project_dir: str) -> str:
    return os.path.join(project_dir, "dialogue-logs")


def _critic_files_for_round(project_dir: str, step: int, round_num: int, domain: str) -> list[str]:
    """Return expected critic file paths for a given round.

    Research: [step-N-rK-fc.md, step-N-rK-rv.md]
    Development: [step-N-rK-cr.md]
    """
    dlg_dir = _dialogue_logs_dir(project_dir)
    if domain == "development":
        return [os.path.join(dlg_dir, f"step-{step}-r{round_num}-cr.md")]
    else:  # research (default)
        return [
            os.path.join(dlg_dir, f"step-{step}-r{round_num}-fc.md"),
            os.path.join(dlg_dir, f"step-{step}-r{round_num}-rv.md"),
        ]


def _draft_file_for_round(project_dir: str, step: int, round_num: int) -> str:
    """Return expected draft file path for research domain round."""
    return os.path.join(
        _dialogue_logs_dir(project_dir),
        f"step-{step}-draft-r{round_num}.md",
    )


def _extract_verdict(file_path: str) -> str | None:
    """Extract PASS/FAIL verdict from a critic report file.

    P1: regex match on file content — deterministic.
    Returns "PASS", "FAIL", or None if not extractable.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        match = _VERDICT_RE.search(content)
        return match.group(1).upper() if match else None
    except (IOError, UnicodeDecodeError):
        return None


def validate_dialogue_state(project_dir: str, step: int, current_round: int, check_consensus: bool = False) -> dict[str, object]:
    """Core DA1-DA5 validation.

    Args:
        project_dir: Project root directory
        step: Step number (int)
        current_round: Current round number to validate up to (int)
        check_consensus: If True, also validate DA3/DA4 consensus state

    Returns:
        dict with validation results
    """
    warnings = []
    checks = {}

    # Determine domain from SOT (if available)
    sot = _read_sot(project_dir)
    domain = "research"  # safe default
    sot_rounds_used = None
    sot_max_rounds = None
    sot_outcome = None

    if sot:
        ds = sot.get("dialogue_state", {})
        if isinstance(ds, dict):
            domain = ds.get("domain", "research")
            sot_rounds_used = ds.get("rounds_used")
            sot_max_rounds = ds.get("max_rounds")
            sot_outcome = ds.get("outcome") or ds.get("status")

    # -----------------------------------------------------------------------
    # DA1: All round files exist for rounds 1..current_round
    # -----------------------------------------------------------------------
    da1_pass = True
    missing_files = []
    for r in range(1, current_round + 1):
        expected = _critic_files_for_round(project_dir, step, r, domain)
        for fpath in expected:
            if not os.path.exists(fpath):
                missing_files.append(os.path.basename(fpath))
                da1_pass = False

    checks["DA1"] = "PASS" if da1_pass else "FAIL"
    if not da1_pass:
        warnings.append(
            f"DA1 FAIL: Missing critic files for step {step} rounds 1..{current_round}: "
            f"{', '.join(missing_files)}"
        )

    # -----------------------------------------------------------------------
    # DA2: Research domain — draft-rK precedes critic-rK (timestamp)
    #      Development domain — skipped
    # -----------------------------------------------------------------------
    if domain == "research":
        da2_pass = True
        for r in range(1, current_round + 1):
            draft_path = _draft_file_for_round(project_dir, step, r)
            if not os.path.exists(draft_path):
                # draft file missing — DA2 cannot verify; record as warning not fail
                warnings.append(
                    f"DA2 WARNING: draft file missing for research round {r}: "
                    f"{os.path.basename(draft_path)} — timestamp check skipped"
                )
                continue
            critic_files = _critic_files_for_round(project_dir, step, r, domain)
            try:
                draft_mtime = os.path.getmtime(draft_path)
            except OSError:
                warnings.append(f"DA2 WARNING: Cannot read draft mtime for round {r}")
                continue
            for cf in critic_files:
                if not os.path.exists(cf):
                    continue
                try:
                    critic_mtime = os.path.getmtime(cf)
                    if critic_mtime < draft_mtime:
                        da2_pass = False
                        warnings.append(
                            f"DA2 FAIL: {os.path.basename(cf)} (mtime {critic_mtime:.0f}) "
                            f"precedes draft-r{r}.md (mtime {draft_mtime:.0f}) — "
                            f"critic ran before generator"
                        )
                except OSError:
                    continue
        checks["DA2"] = "PASS" if da2_pass else "FAIL"
    else:
        checks["DA2"] = "SKIP (development domain)"

    # -----------------------------------------------------------------------
    # DA3: If check_consensus — final critic file(s) verdict = PASS
    # -----------------------------------------------------------------------
    if check_consensus:
        da3_pass = True
        final_critic_files = _critic_files_for_round(project_dir, step, current_round, domain)
        for cf in final_critic_files:
            if not os.path.exists(cf):
                da3_pass = False
                warnings.append(
                    f"DA3 FAIL: Final critic file missing: {os.path.basename(cf)}"
                )
                continue
            verdict = _extract_verdict(cf)
            if verdict != "PASS":
                da3_pass = False
                warnings.append(
                    f"DA3 FAIL: {os.path.basename(cf)} verdict is '{verdict}', "
                    f"expected PASS for consensus"
                )
        checks["DA3"] = "PASS" if da3_pass else "FAIL"
    else:
        checks["DA3"] = "SKIP (--check-consensus not set)"

    # -----------------------------------------------------------------------
    # DA4: SOT outcome consistency
    #      If SOT outcome == "escalated", final critic file(s) must have FAIL
    #      If SOT outcome == "consensus", final critic file(s) must have PASS
    # -----------------------------------------------------------------------
    if sot_outcome in ("consensus", "escalated"):
        da4_pass = True
        expected_verdict = "PASS" if sot_outcome == "consensus" else "FAIL"
        final_critic_files = _critic_files_for_round(project_dir, step, current_round, domain)
        for cf in final_critic_files:
            if not os.path.exists(cf):
                da4_pass = False
                warnings.append(
                    f"DA4 FAIL: SOT outcome='{sot_outcome}' but final critic file missing: "
                    f"{os.path.basename(cf)}"
                )
                continue
            verdict = _extract_verdict(cf)
            if verdict != expected_verdict:
                da4_pass = False
                warnings.append(
                    f"DA4 FAIL: SOT outcome='{sot_outcome}' expects verdict='{expected_verdict}' "
                    f"but {os.path.basename(cf)} verdict='{verdict}'"
                )
        checks["DA4"] = "PASS" if da4_pass else "FAIL"
    else:
        checks["DA4"] = f"SKIP (SOT outcome='{sot_outcome}')"

    # -----------------------------------------------------------------------
    # DA5: rounds_used in SOT <= max_rounds (no counter overflow)
    # -----------------------------------------------------------------------
    if sot_rounds_used is not None and sot_max_rounds is not None:
        da5_pass = sot_rounds_used <= sot_max_rounds
        checks["DA5"] = "PASS" if da5_pass else "FAIL"
        if not da5_pass:
            warnings.append(
                f"DA5 FAIL: SOT rounds_used={sot_rounds_used} exceeds "
                f"max_rounds={sot_max_rounds}"
            )
    else:
        checks["DA5"] = "SKIP (SOT dialogue_state not found or incomplete)"

    is_valid = all(v in ("PASS", "SKIP (development domain)", "SKIP (--check-consensus not set)")
                   or v.startswith("SKIP")
                   for v in checks.values())
    # Explicit: any FAIL → invalid
    is_valid = not any(v == "FAIL" for v in checks.values())

    return {
        "valid": is_valid,
        "step": step,
        "round": current_round,
        "domain": domain,
        "checks": checks,
        "warnings": warnings,
        "sot_rounds_used": sot_rounds_used,
        "sot_max_rounds": sot_max_rounds,
        "sot_outcome": sot_outcome,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="P1 Validation for Adversarial Dialogue state integrity (DA1-DA5)"
    )
    parser.add_argument("--step", type=int, required=True, help="Step number")
    parser.add_argument("--round", type=int, required=True, help="Current round number")
    parser.add_argument(
        "--project-dir", type=str, default=".",
        help="Project root directory (default: current directory)"
    )
    parser.add_argument(
        "--check-consensus", action="store_true",
        help="Also validate DA3: final critic verdict = PASS (for consensus check)"
    )
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    result = validate_dialogue_state(
        project_dir, args.step, args.round, args.check_consensus
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except Exception as e:
        error_output = {
            "valid": False,
            "error": str(e),
            "warnings": [f"Fatal error: {e}"],
        }
        print(json.dumps(error_output, indent=2, ensure_ascii=False))
        sys.exit(1)
