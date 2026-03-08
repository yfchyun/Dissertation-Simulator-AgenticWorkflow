#!/usr/bin/env python3
"""
validate_failure_predictions.py — Phase C: Failure Prediction Validator (FP1-FP7)

Validates @failure-predictor and @failure-critic outputs against verified code facts.
Filters hallucinated file references, format violations, and out-of-range line numbers.

P1 Compliance:
  - Pure stdlib, deterministic, exit 0 always
  - Structural/format validation only — semantic correctness is @failure-critic's role
  - All violations logged; valid predictions passed through

CLI:
  # Validate predictor output (FP1-FP7):
  python validate_failure_predictions.py \\
    --input fp-draft.json \\
    --code-map fp-code-map.json \\
    --output fp-validated.json

  # Validate critic output (format check):
  python validate_failure_predictions.py \\
    --critic \\
    --input fp-critic.json \\
    --output fp-critic-validated.json

FP Check Definitions:
  FP1: Cited file exists in fp-code-map.json scanned files
  FP2: Cited line number within file range [1, line_count]
  FP3: File not fabricated (not in code map → removed)  [subset of FP1]
  FP4: severity field is one of {Critical, Warning, Info}
  FP5: All required fields present {id, category, severity, file, summary}
  FP6: category field is one of {F1, F2, F3, F4, F5, F6, F7}
  FP7: At least MIN_VALID_PREDICTIONS (3) valid predictions remain after all checks
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Tuple


# === Allowed values (P1 constants) ===
ALLOWED_SEVERITIES = {"Critical", "Warning", "Info"}
ALLOWED_CATEGORIES = {"F1", "F2", "F3", "F4", "F5", "F6", "F7"}
ALLOWED_VERDICTS = {"CONFIRM", "DISMISS", "ESCALATE"}

REQUIRED_PREDICTION_FIELDS = {"id", "category", "severity", "file", "summary"}
REQUIRED_JUDGMENT_FIELDS = {"id", "verdict"}

# FP7 threshold — aligned with @failure-predictor Absolute Rule 5
MIN_VALID_PREDICTIONS = 3


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_file_index(code_map: Dict) -> Dict[str, int]:
    """Build {rel_path: line_count} from code map. Used for FP1 + FP2."""
    index: Dict[str, int] = {}
    for fr in code_map.get("files", []):
        path = fr.get("path", "")
        if path:
            index[path] = fr.get("line_count", 0)
    return index


def _validate_predictor(
    draft: Dict,
    file_index: Dict[str, int],
) -> Tuple[List[Dict], List[str]]:
    """
    Apply FP1-FP7 structural checks to predictor output.

    Returns:
        (valid_predictions, violation_messages)
    """
    predictions = draft.get("predictions", [])
    if not isinstance(predictions, list):
        return [], ["FP5 FAIL: top-level 'predictions' key must be a list"]

    valid: List[Dict] = []
    violations: List[str] = []
    seen_ids: set = set()

    for i, pred in enumerate(predictions):
        if not isinstance(pred, dict):
            violations.append(f"FP5 FAIL [item {i}]: prediction must be a dict, got {type(pred)}")
            continue

        pred_id = pred.get("id", f"UNNAMED-{i}")
        item_violations: List[str] = []

        # FP5: Required fields
        missing = REQUIRED_PREDICTION_FIELDS - set(pred.keys())
        if missing:
            item_violations.append(
                f"FP5 FAIL [{pred_id}]: missing required fields: {sorted(missing)}"
            )

        # FP4: Severity
        severity = pred.get("severity", "")
        if severity not in ALLOWED_SEVERITIES:
            item_violations.append(
                f"FP4 FAIL [{pred_id}]: severity='{severity}' not in {sorted(ALLOWED_SEVERITIES)}"
            )

        # FP6: Category
        raw_category = pred.get("category", "")
        # Accept both "F1" and "F1_concurrency" style
        category = raw_category.split("_")[0] if "_" in raw_category else raw_category
        if category not in ALLOWED_CATEGORIES:
            item_violations.append(
                f"FP6 FAIL [{pred_id}]: category='{raw_category}' not in F1-F7"
            )

        # FP1 + FP3: File exists in code map
        file_path = pred.get("file", "")
        if file_path:
            if file_path not in file_index:
                item_violations.append(
                    f"FP1/FP3 FAIL [{pred_id}]: file '{file_path}' not found in scanned files "
                    f"— fabricated reference removed"
                )
        else:
            if "file" in REQUIRED_PREDICTION_FIELDS:
                item_violations.append(f"FP5 FAIL [{pred_id}]: 'file' field is empty")

        # FP2: Line number within range
        line = pred.get("line")
        if line is not None and file_path and file_path in file_index:
            max_line = file_index[file_path]
            if not isinstance(line, int) or line < 1 or line > max_line:
                item_violations.append(
                    f"FP2 FAIL [{pred_id}]: line={line} out of range [1, {max_line}] "
                    f"for '{file_path}'"
                )

        # Duplicate ID check
        if pred_id in seen_ids:
            item_violations.append(f"FP5 FAIL [{pred_id}]: duplicate prediction id")
        seen_ids.add(pred_id)

        if item_violations:
            violations.extend(item_violations)
            # Do not include this prediction in valid output
        else:
            # Normalize category to short form (F1, F2, etc.)
            pred_copy = dict(pred)
            pred_copy["category"] = category
            valid.append(pred_copy)

    # FP7: At least MIN_VALID_PREDICTIONS valid predictions
    if len(valid) < MIN_VALID_PREDICTIONS:
        violations.append(
            f"FP7 FAIL: {len(valid)} valid predictions remain after FP1-FP6 checks "
            f"(minimum {MIN_VALID_PREDICTIONS} required). "
            "Either predictions were fabricated or had format errors."
        )

    return valid, violations


def _validate_critic(draft: Dict) -> Tuple[Dict, List[str]]:
    """
    Validate critic review format.
    Checks: judgment structure, verdict values, addition format.
    """
    violations: List[str] = []

    judgments = draft.get("judgments", [])
    if not isinstance(judgments, list):
        violations.append("Critic FAIL: 'judgments' must be a list")
        return {"judgments": [], "additions": []}, violations

    valid_judgments: List[Dict] = []
    seen_judgment_ids: set = set()  # R-4: duplicate judgment ID check
    for i, j in enumerate(judgments):
        if not isinstance(j, dict):
            violations.append(f"Critic FAIL [item {i}]: judgment must be a dict")
            continue
        j_id = j.get("id", f"J-{i}")
        j_violations: List[str] = []

        missing = REQUIRED_JUDGMENT_FIELDS - set(j.keys())
        if missing:
            j_violations.append(f"Critic FP-J [{j_id}]: missing fields {sorted(missing)}")

        verdict = j.get("verdict", "")
        if verdict not in ALLOWED_VERDICTS:
            j_violations.append(
                f"Critic FP-J [{j_id}]: verdict='{verdict}' not in {sorted(ALLOWED_VERDICTS)}"
            )

        # R-4: Duplicate judgment ID check (consistent with predictor)
        if j_id in seen_judgment_ids:
            j_violations.append(f"Critic FP-J [{j_id}]: duplicate judgment id")
        seen_judgment_ids.add(j_id)

        if j_violations:
            violations.extend(j_violations)
        else:
            valid_judgments.append(j)

    # Validate additions (same structural requirements as predictions)
    additions = draft.get("additions", [])
    valid_additions: List[Dict] = []
    if isinstance(additions, list):
        for i, add in enumerate(additions):
            if not isinstance(add, dict):
                violations.append(f"Critic ADD [item {i}]: addition must be a dict")
                continue
            add_id = add.get("id", f"ADD-{i}")
            add_violations: List[str] = []

            missing = REQUIRED_PREDICTION_FIELDS - set(add.keys())
            if missing:
                add_violations.append(
                    f"Critic ADD [{add_id}]: missing required fields {sorted(missing)}"
                )

            # R-3: Empty file value check (consistent with predictor FP5)
            file_val = add.get("file", "")
            if not file_val:
                add_violations.append(
                    f"Critic ADD [{add_id}]: 'file' field is empty"
                )

            sev = add.get("severity", "")
            if sev not in ALLOWED_SEVERITIES:
                add_violations.append(
                    f"Critic ADD [{add_id}]: severity='{sev}' not in {sorted(ALLOWED_SEVERITIES)}"
                )

            cat = add.get("category", "").split("_")[0]
            if cat not in ALLOWED_CATEGORIES:
                add_violations.append(
                    f"Critic ADD [{add_id}]: category not in F1-F7"
                )

            if add_violations:
                violations.extend(add_violations)
            else:
                add_copy = dict(add)
                add_copy["category"] = cat
                valid_additions.append(add_copy)

    return {"judgments": valid_judgments, "additions": valid_additions}, violations


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate failure predictions (FP1-FP7) — Phase C"
    )
    parser.add_argument("--input", required=True, help="Input JSON file to validate")
    parser.add_argument(
        "--code-map",
        help="fp-code-map.json path (required for predictor mode, ignored for critic mode)",
    )
    parser.add_argument(
        "--critic",
        action="store_true",
        help="Validate critic output format (CONFIRM/DISMISS/ESCALATE/ADD)",
    )
    parser.add_argument("--output", required=True, help="Output validated JSON path")
    args = parser.parse_args()

    # Load input
    try:
        draft = _load_json(args.input)
    except Exception as e:
        print(
            f"[validate_failure_predictions] ERROR reading input '{args.input}': {e}",
            file=sys.stderr,
        )
        sys.exit(0)

    if args.critic:
        validated_data, violations = _validate_critic(draft)
        mode = "critic"
        valid_count = len(validated_data.get("judgments", []))
    else:
        if not args.code_map:
            print(
                "[validate_failure_predictions] ERROR: --code-map required for predictor mode",
                file=sys.stderr,
            )
            sys.exit(0)
        try:
            code_map = _load_json(args.code_map)
        except Exception as e:
            print(
                f"[validate_failure_predictions] ERROR reading code map: {e}",
                file=sys.stderr,
            )
            sys.exit(0)

        file_index = _build_file_index(code_map)
        valid_preds, violations = _validate_predictor(draft, file_index)
        validated_data = {"predictions": valid_preds}
        mode = "predictor"
        valid_count = len(valid_preds)

    # Build result
    result = {
        "mode": mode,
        "violation_count": len(violations),
        "violations": violations,
        **validated_data,
    }

    # Write output
    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # Summary
    print(
        f"[validate_failure_predictions] mode={mode} | valid={valid_count} | "
        f"violations={len(violations)} → {args.output}"
    )
    for v in violations:
        print(f"  {v}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[validate_failure_predictions] FATAL: {e}", file=sys.stderr)
        sys.exit(0)
