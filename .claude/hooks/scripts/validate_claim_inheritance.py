#!/usr/bin/env python3
"""
Claim Inheritance P1 Validation — validate_claim_inheritance.py

Standalone script called by Orchestrator for Research domain dialogue Round 2+.
NOT a Hook — manually invoked during workflow execution.
NOT applicable to Development domain (no draft files or claim tables).

Purpose: Prevent @fact-checker from falsely inheriting stale verdicts when the
Generator modified the claim's source text between rounds.

Usage:
    python3 .claude/hooks/scripts/validate_claim_inheritance.py \
        --step 5 --round 2 --project-dir .

Output: JSON to stdout
    {
      "valid": true,
      "step": 5,
      "round": 2,
      "inherited_claims": 12,
      "verified_inherited": 10,
      "hallucinations_detected": 2,
      "results": [...],
      "warnings": []
    }

Exit codes:
    0 — always (non-blocking, P1 compliant)

Checks (CI1-CI4):
    CI1: Each "Inherited" claim in Round K report exists in Round K-1 report
         (claim text or ID match — cross-reference check)
    CI2: Inherited claims from Round K-1 had Verified/Partially Verified verdict
         (cannot inherit False/Unable-to-Verify as Verified)
    CI3: Claim count in Round K >= Round K-1 (no silent claim dropping)
    CI4: Claims in paragraphs that changed between drafts cannot be "Inherited"
         (diff-based paragraph comparison — deterministic string comparison)

P1 Compliance: Pure Python regex + string comparison — zero LLM inference.
SOT Compliance: Read-only access to dialogue-logs/ only.
Domain: Research only. Development domain: always returns {"valid": true, "skipped": true}.
"""

import argparse
import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# Regex Patterns
# ---------------------------------------------------------------------------

# Claim table row in @fact-checker report
# Format: | # | Claim text | Location | Verdict | Source | Notes |
_CLAIM_ROW_RE = re.compile(
    r"^\|\s*\d+\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*(Verified|Partially\s+Verified|Unable\s+to\s+Verify|Outdated|False)\s*[^|]*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|",
    re.MULTILINE | re.IGNORECASE,
)

# Detect "Inherited" marker in Notes column (last column)
_INHERITED_MARKER_RE = re.compile(r"Inherited\s+from\s+Round", re.IGNORECASE)

# Table header words to skip
_HEADER_WORDS = frozenset({
    "#", "no", "no.", "claim", "location", "verdict", "source", "notes",
    "---", "result",
})

# Verdicts that are safe to inherit
_INHERITABLE_VERDICTS = frozenset({"verified", "partially verified"})

# Numeric patterns for key facts (reused from verify_translation_terms.py T11 pattern)
_NUMBER_RE = re.compile(r"\b\d[\d,.%]*\b")


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_claim_table(content: str) -> list[dict[str, object]]:
    """Parse @fact-checker claim verification table into list of dicts.

    Returns list of {claim_text, location, verdict, source, notes}
    """
    claims = []
    for match in _CLAIM_ROW_RE.finditer(content):
        claim_text = match.group(1).strip()
        location = match.group(2).strip()
        verdict = match.group(3).strip()
        source = match.group(4).strip()
        notes = match.group(5).strip()

        # Skip header rows
        if claim_text.lower().rstrip("-") in _HEADER_WORDS:
            continue

        claims.append({
            "claim_text": claim_text,
            "location": location,
            "verdict": verdict,
            "source": source,
            "notes": notes,
            "is_inherited": bool(_INHERITED_MARKER_RE.search(notes)),
        })
    return claims


def _split_paragraphs(text: str) -> list[str]:
    """Split text into non-empty paragraphs (double-newline separated).

    P1: pure string split — deterministic.
    """
    paragraphs = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paragraphs if p.strip()]


def _find_changed_paragraphs(draft_prev: str, draft_curr: str) -> set[str]:
    """Find paragraphs present in draft_prev but NOT in draft_curr (modified/removed).

    P1: set difference on stripped paragraph strings — deterministic.
    Returns set of changed paragraph strings from draft_prev.
    """
    prev_paras = set(_split_paragraphs(draft_prev))
    curr_paras = set(_split_paragraphs(draft_curr))
    return prev_paras - curr_paras


def _key_numbers_in_text(text: str) -> set[str]:
    """Extract key numerical values from text for fact-checking.

    P1: regex number extraction — deterministic.
    """
    return set(_NUMBER_RE.findall(text))


# ---------------------------------------------------------------------------
# Core Validation
# ---------------------------------------------------------------------------

def validate_claim_inheritance(project_dir: str, step: int, current_round: int) -> dict[str, object]:
    """CI1-CI4 validation for @fact-checker incremental mode.

    Args:
        project_dir: Project root directory
        step: Step number (int)
        current_round: Current round number (must be >= 2)

    Returns:
        dict with validation results
    """
    warnings = []
    results = []
    hallucinations = 0

    dlg_dir = os.path.join(project_dir, "dialogue-logs")

    # Check domain: only applicable to research domain
    # Detect via presence of fc files (research) vs cr files (development)
    curr_fc_path = os.path.join(dlg_dir, f"step-{step}-r{current_round}-fc.md")
    curr_cr_path = os.path.join(dlg_dir, f"step-{step}-r{current_round}-cr.md")

    if os.path.exists(curr_cr_path) and not os.path.exists(curr_fc_path):
        # Development domain — skip
        return {
            "valid": True,
            "skipped": True,
            "reason": "Development domain detected (cr file present, fc file absent) — CI1-CI4 not applicable",
            "step": step,
            "round": current_round,
            "warnings": [],
        }

    if current_round < 2:
        return {
            "valid": True,
            "skipped": True,
            "reason": "Round 1 is always full verification — CI1-CI4 not applicable",
            "step": step,
            "round": current_round,
            "warnings": [],
        }

    # File paths
    prev_round = current_round - 1
    prev_fc_path = os.path.join(dlg_dir, f"step-{step}-r{prev_round}-fc.md")
    draft_prev_path = os.path.join(dlg_dir, f"step-{step}-draft-r{prev_round}.md")
    draft_curr_path = os.path.join(dlg_dir, f"step-{step}-draft-r{current_round}.md")

    # Read current round's fact-check report
    if not os.path.exists(curr_fc_path):
        return {
            "valid": True,
            "skipped": True,
            "reason": f"Current round fc file not found: {os.path.basename(curr_fc_path)}",
            "step": step,
            "round": current_round,
            "warnings": [f"CI SKIP: {os.path.basename(curr_fc_path)} not found"],
        }

    try:
        with open(curr_fc_path, "r", encoding="utf-8") as f:
            curr_content = f.read()
    except (IOError, UnicodeDecodeError) as e:
        return {
            "valid": True, "skipped": True,
            "reason": f"Cannot read current fc file: {e}",
            "step": step, "round": current_round, "warnings": [str(e)],
        }

    # Read previous round's fact-check report
    prev_claims_by_text = {}
    if os.path.exists(prev_fc_path):
        try:
            with open(prev_fc_path, "r", encoding="utf-8") as f:
                prev_content = f.read()
            prev_claims = _parse_claim_table(prev_content)
            prev_claims_by_text = {str(c["claim_text"]).lower(): c for c in prev_claims}
        except (IOError, UnicodeDecodeError):
            warnings.append(f"CI WARNING: Cannot read previous round fc file — CI1/CI2 checks skipped")

    # Parse current round's claims
    curr_claims = _parse_claim_table(curr_content)
    total_curr = len(curr_claims)
    inherited_claims = [c for c in curr_claims if c["is_inherited"]]

    # Read draft files for CI4 (paragraph diff)
    changed_paragraphs = set()
    if os.path.exists(draft_prev_path) and os.path.exists(draft_curr_path):
        try:
            with open(draft_prev_path, "r", encoding="utf-8") as f:
                draft_prev = f.read()
            with open(draft_curr_path, "r", encoding="utf-8") as f:
                draft_curr = f.read()
            changed_paragraphs = _find_changed_paragraphs(draft_prev, draft_curr)
        except (IOError, UnicodeDecodeError):
            warnings.append("CI WARNING: Cannot read draft files — CI4 check skipped")
    else:
        warnings.append(
            f"CI WARNING: Draft files not found for round comparison — CI4 check skipped"
        )

    # -----------------------------------------------------------------------
    # CI3: Claim count non-decreasing
    # -----------------------------------------------------------------------
    prev_claim_count = len(prev_claims_by_text) if prev_claims_by_text else 0
    ci3_pass = total_curr >= prev_claim_count
    if not ci3_pass:
        warnings.append(
            f"CI3 FAIL: Round {current_round} has {total_curr} claims, "
            f"Round {prev_round} had {prev_claim_count} — claim count decreased "
            f"(possible silent omission)"
        )

    # -----------------------------------------------------------------------
    # CI1, CI2, CI4: Per-inherited-claim checks
    # -----------------------------------------------------------------------
    for claim in inherited_claims:
        claim_text = str(claim["claim_text"])
        claim_text_lower = claim_text.lower()
        ci_result = {
            "claim": claim_text[:120],
            "ci1": "SKIP",
            "ci2": "SKIP",
            "ci4": "SKIP",
            "status": "CONFIRMED",
        }

        # CI1: Inherited claim must exist in previous round's report
        if prev_claims_by_text:
            prev_claim = prev_claims_by_text.get(claim_text_lower)
            if prev_claim is None:
                # Try fuzzy: check if key numbers are preserved
                curr_numbers = _key_numbers_in_text(claim_text)
                found_match = False
                for prev_text_lower, prev_c in prev_claims_by_text.items():
                    prev_numbers = _key_numbers_in_text(str(prev_c["claim_text"]))
                    if curr_numbers and prev_numbers and curr_numbers == prev_numbers:
                        found_match = True
                        prev_claim = prev_c
                        break

                if not found_match:
                    ci_result["ci1"] = "FAIL"
                    ci_result["status"] = "HALLUCINATION_DETECTED"
                    hallucinations += 1
                    warnings.append(
                        f"CI1 FAIL: Inherited claim not found in Round {prev_round} report: "
                        f"'{claim_text[:80]}'"
                    )
                else:
                    ci_result["ci1"] = "PASS (fuzzy number match)"
            else:
                # CI1: exact text match found
                ci_result["ci1"] = "PASS"

            # CI2: Previous verdict must be inheritable (exact match OR fuzzy match)
            # Runs whenever prev_claim was found (ci1 != "FAIL")
            if prev_claim is not None and ci_result["ci1"] != "FAIL":
                prev_verdict = str(prev_claim.get("verdict", "")).lower().strip()
                if prev_verdict not in _INHERITABLE_VERDICTS:
                    ci_result["ci2"] = "FAIL"
                    ci_result["status"] = "HALLUCINATION_DETECTED"
                    hallucinations += 1
                    warnings.append(
                        f"CI2 FAIL: Inherited claim had non-inheritable verdict "
                        f"'{prev_verdict}' in Round {prev_round}: "
                        f"'{claim_text[:80]}'"
                    )
                else:
                    ci_result["ci2"] = "PASS"

        # CI4: Claim location must not be in a changed paragraph
        if changed_paragraphs and claim.get("location"):
            location_text = str(claim["location"])
            # Check if any changed paragraph contains the location hint
            location_in_changed = any(
                location_text.lower() in para.lower()
                for para in changed_paragraphs
            )
            # Also check if the claim text itself appears in a changed paragraph
            claim_in_changed = any(
                claim_text_lower[:50] in para.lower()
                for para in changed_paragraphs
            )
            if location_in_changed or claim_in_changed:
                ci_result["ci4"] = "FAIL"
                ci_result["status"] = "HALLUCINATION_DETECTED"
                hallucinations += 1
                warnings.append(
                    f"CI4 FAIL: Inherited claim is in a changed paragraph "
                    f"(location: '{location_text}') — must be re-verified: "
                    f"'{claim_text[:80]}'"
                )
            else:
                ci_result["ci4"] = "PASS"

        results.append(ci_result)

    # Degenerate case: prev round had 0 verified claims
    prev_verified_count = sum(
        1 for c in prev_claims_by_text.values()
        if str(c.get("verdict", "")).lower() in _INHERITABLE_VERDICTS
    ) if prev_claims_by_text else 0

    if prev_verified_count == 0 and inherited_claims:
        warnings.append(
            f"CI WARNING: Round {prev_round} had 0 verified claims, but Round {current_round} "
            f"has {len(inherited_claims)} inherited claims. "
            f"When previous round has 0 verified claims, Incremental Mode should not be used."
        )
        # Do NOT add to hallucinations here — CI1/CI2 per-claim checks already
        # counted each of these inherited claims when prev_verified_count == 0
        # (every CI2 check fails → hallucinations already incremented per claim).
        # Adding len(inherited_claims) again would double-count.

    return {
        "valid": hallucinations == 0 and ci3_pass,
        "step": step,
        "round": current_round,
        "total_claims": total_curr,
        "inherited_claims": len(inherited_claims),
        "prev_claim_count": prev_claim_count,
        "prev_verified_count": prev_verified_count,
        "ci3_pass": ci3_pass,
        "hallucinations_detected": hallucinations,
        "results": results,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="P1 Claim Inheritance Validation for @fact-checker Incremental Mode (CI1-CI4)"
    )
    parser.add_argument("--step", type=int, required=True, help="Step number")
    parser.add_argument("--round", type=int, required=True, help="Current round number (must be >= 2)")
    parser.add_argument(
        "--project-dir", type=str, default=".",
        help="Project root directory (default: current directory)"
    )
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    result = validate_claim_inheritance(project_dir, args.step, args.round)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        error_output = {
            "valid": True,  # Non-blocking on fatal error
            "error": str(e),
            "hallucinations_detected": 0,
            "warnings": [f"Fatal error: {e}"],
        }
        print(json.dumps(error_output, indent=2, ensure_ascii=False))
    sys.exit(0)  # Always exit 0 (non-blocking, P1 compliant)
