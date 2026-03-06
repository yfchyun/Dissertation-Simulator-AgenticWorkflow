#!/usr/bin/env python3
"""Step Sequence Validator — P1 deterministic dependency enforcement.

Validates that step prerequisites are met before allowing advancement.
Imports PHASE_RANGES, STEP_DEPENDENCIES from checklist_manager.py (single source).

Usage:
  python3 validate_step_sequence.py --project-dir <dir> --step <N>
  python3 validate_step_sequence.py --project-dir <dir> --check-all
"""

import argparse
import json
import sys
from pathlib import Path

# Import from checklist_manager — the single source of truth for thesis constants.
# NOTE: This is a thesis-internal import, NOT a system SOT reference.
# R6 prohibits referencing system SOT filenames (state.yaml/state.yml),
# NOT thesis-internal constant sharing.
from checklist_manager import (
    PHASE_RANGES,
    STEP_DEPENDENCIES,
    THESIS_SOT_FILENAME,
)

# Derived: first step of each phase
PHASE_ENTRY_STEPS = {start: name for name, (start, _) in PHASE_RANGES.items()}


def load_thesis_sot(project_dir: str) -> dict | None:
    """Load thesis session.json SOT."""
    sot_path = Path(project_dir) / THESIS_SOT_FILENAME
    if not sot_path.exists():
        return None
    with open(sot_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_completed_steps(sot: dict) -> set[int]:
    """Extract set of completed step numbers from SOT."""
    completed = set()
    outputs = sot.get("outputs", {})
    for key in outputs:
        if key.startswith("step-") and not key.endswith("-ko"):
            try:
                step_num = int(key.split("-")[1])
                completed.add(step_num)
            except (IndexError, ValueError):
                pass
    return completed


def get_gate_results(sot: dict) -> dict[str, str]:
    """Extract gate results from SOT. Returns gate_name → status."""
    gates = {}
    for key, val in sot.get("gates", {}).items():
        if isinstance(val, dict):
            gates[key] = val.get("status", "unknown")
        else:
            gates[key] = str(val)
    return gates


def get_hitl_results(sot: dict) -> dict[str, str]:
    """Extract HITL results from SOT. Returns hitl_name → status.

    Reads from 'hitl_checkpoints' key (the actual SOT schema),
    NOT from a non-existent 'hitl' key.
    """
    hitls = {}
    for key, val in sot.get("hitl_checkpoints", {}).items():
        if isinstance(val, dict):
            hitls[key] = val.get("status", "unknown")
        else:
            hitls[key] = str(val)
    return hitls


def _get_gate_for_step(step: int) -> str | None:
    """Get required gate name for a step, if any.

    Derives from STEP_DEPENDENCIES: if a phase requires a gate,
    its first step inherits that requirement.
    """
    for phase_name, (start, _end) in PHASE_RANGES.items():
        if step == start:
            deps = STEP_DEPENDENCIES.get(phase_name, {})
            return deps.get("gate")
    return None


def _get_hitl_for_step(step: int) -> str | None:
    """Get required HITL checkpoint for a step, if any.

    Derives from STEP_DEPENDENCIES: if a phase requires a HITL,
    its first step inherits that requirement.
    """
    for phase_name, (start, _end) in PHASE_RANGES.items():
        if step == start:
            deps = STEP_DEPENDENCIES.get(phase_name, {})
            return deps.get("hitl")
    return None


def validate_step(project_dir: str, step: int) -> dict:
    """Validate whether a step can be executed.

    Returns:
        dict with can_proceed, errors, warnings
    """
    sot = load_thesis_sot(project_dir)
    errors = []
    warnings = []

    if sot is None:
        return {
            "step": step,
            "can_proceed": False,
            "errors": [f"Thesis SOT ({THESIS_SOT_FILENAME}) not found"],
            "warnings": [],
        }

    completed = get_completed_steps(sot)
    gates = get_gate_results(sot)
    hitls = get_hitl_results(sot)

    # Check 1: Previous step must be completed (unless step 1)
    if step > 1 and (step - 1) not in completed:
        errors.append(f"Previous step {step - 1} not completed")

    # Check 2: Gate prerequisites (derived from STEP_DEPENDENCIES)
    required_gate = _get_gate_for_step(step)
    if required_gate:
        gate_status = gates.get(required_gate)
        if gate_status != "pass":
            errors.append(
                f"Gate '{required_gate}' not passed (status: {gate_status or 'not run'})"
            )

    # Check 3: HITL prerequisites (derived from STEP_DEPENDENCIES)
    required_hitl = _get_hitl_for_step(step)
    if required_hitl:
        hitl_status = hitls.get(required_hitl)
        if hitl_status != "completed":
            errors.append(
                f"HITL '{required_hitl}' not completed (status: {hitl_status or 'not run'})"
            )

    # Check 4: Phase boundary — warn about entering new phase
    if step in PHASE_ENTRY_STEPS:
        phase_name = PHASE_ENTRY_STEPS[step]
        warnings.append(f"Entering new phase: {phase_name}")

    # Check 5: Current step not already completed
    if step in completed:
        warnings.append(f"Step {step} already completed — re-execution will overwrite")

    return {
        "step": step,
        "can_proceed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def validate_all_steps(project_dir: str) -> list[dict]:
    """Validate sequence integrity for all steps."""
    sot = load_thesis_sot(project_dir)
    if sot is None:
        return [{"error": "Thesis SOT not found"}]

    completed = get_completed_steps(sot)
    if not completed:
        return [{"info": "No steps completed yet. Step 1 is ready."}]

    results = []
    max_step = max(completed)

    # Check for gaps
    for step in range(1, max_step + 1):
        if step not in completed:
            results.append({
                "step": step,
                "issue": "gap",
                "message": f"Step {step} missing — gap in sequence",
            })

    # Check gate/HITL prerequisites for completed steps
    gates = get_gate_results(sot)
    hitls = get_hitl_results(sot)

    for step in sorted(completed):
        gate = _get_gate_for_step(step)
        if gate and gates.get(gate) != "pass":
            results.append({
                "step": step,
                "issue": "gate_bypass",
                "message": f"Step {step} completed without gate '{gate}' pass",
            })
        hitl = _get_hitl_for_step(step)
        if hitl and hitls.get(hitl) != "completed":
            results.append({
                "step": step,
                "issue": "hitl_bypass",
                "message": f"Step {step} completed without HITL '{hitl}' completion",
            })

    if not results:
        results.append({
            "info": f"Sequence valid. {len(completed)} steps completed, max step: {max_step}",
        })

    return results


def main():
    parser = argparse.ArgumentParser(description="Step Sequence Validator")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--json", action="store_true",
                        help="Output JSON (for orchestrator consumption)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--step", type=int, help="Validate specific step")
    group.add_argument("--check-all", action="store_true",
                       help="Validate entire sequence")
    args = parser.parse_args()

    if args.check_all:
        results = validate_all_steps(args.project_dir)
        if args.json:
            print(json.dumps(results, ensure_ascii=False))
            return 1 if any("issue" in r for r in results) else 0
        for r in results:
            if "error" in r:
                print(f"ERROR: {r['error']}")
            elif "info" in r:
                print(f"OK: {r['info']}")
            else:
                print(f"ISSUE [{r.get('issue')}]: {r.get('message')}")
        has_issues = any("issue" in r for r in results)
        return 1 if has_issues else 0

    result = validate_step(args.project_dir, args.step)
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["can_proceed"] else 1
    status = "OK" if result["can_proceed"] else "BLOCKED"
    print(f"Step {args.step}: {status}")
    for err in result["errors"]:
        print(f"  ERROR: {err}")
    for warn in result["warnings"]:
        print(f"  WARN: {warn}")
    return 0 if result["can_proceed"] else 1


if __name__ == "__main__":
    sys.exit(main())
