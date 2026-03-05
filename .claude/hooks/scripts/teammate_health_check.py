#!/usr/bin/env python3
"""Teammate health check for thesis Agent Teams.

Monitors teammate activity and detects unresponsive teammates.
Can be used as a TeammateIdle hook or called directly.

Usage:
  python3 teammate_health_check.py --project-dir <dir> --timeout <seconds>
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Default idle timeout (5 minutes)
DEFAULT_TIMEOUT_SECONDS = 300

# Health status
STATUS_HEALTHY = "healthy"
STATUS_IDLE = "idle"
STATUS_UNRESPONSIVE = "unresponsive"


def check_teammate_health(
    project_dir: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict:
    """Check health of teammates based on output activity.

    Returns:
        dict with overall_status, teammates list
    """
    project = Path(project_dir)
    sot_path = project / "session.json"

    if not sot_path.exists():
        return {"overall_status": "no_project", "teammates": []}

    with open(sot_path, "r", encoding="utf-8") as f:
        sot = json.load(f)

    active_team = sot.get("active_team")
    if not active_team:
        return {"overall_status": "no_active_team", "teammates": []}

    # Check wave result files for recent modifications
    now = time.time()
    teammates = []

    wave_dir = project / "wave-results"
    if wave_dir.is_dir():
        for wave_subdir in sorted(wave_dir.iterdir()):
            if not wave_subdir.is_dir():
                continue
            for output_file in wave_subdir.iterdir():
                if not output_file.is_file():
                    continue
                mtime = output_file.stat().st_mtime
                age = now - mtime
                status = STATUS_HEALTHY if age < timeout_seconds else STATUS_IDLE
                teammates.append({
                    "file": str(output_file.relative_to(project)),
                    "last_modified": mtime,
                    "age_seconds": round(age),
                    "status": status,
                })

    # Determine overall status
    if not teammates:
        overall = "no_outputs"
    elif all(t["status"] == STATUS_HEALTHY for t in teammates):
        overall = STATUS_HEALTHY
    elif any(t["status"] == STATUS_IDLE for t in teammates):
        overall = STATUS_IDLE
    else:
        overall = STATUS_HEALTHY

    return {
        "overall_status": overall,
        "active_team": active_team,
        "teammates": teammates,
        "timeout_seconds": timeout_seconds,
    }


def main():
    parser = argparse.ArgumentParser(description="Teammate Health Check")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS,
                        help=f"Idle timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS})")
    args = parser.parse_args()

    result = check_teammate_health(args.project_dir, args.timeout)

    print(f"Team status: {result['overall_status']}")
    if result.get("active_team"):
        print(f"Active team: {result['active_team']}")

    idle_count = sum(1 for t in result["teammates"] if t["status"] == STATUS_IDLE)
    if idle_count > 0:
        print(f"WARNING: {idle_count} idle output(s) detected")
        for t in result["teammates"]:
            if t["status"] == STATUS_IDLE:
                print(f"  IDLE: {t['file']} (age: {t['age_seconds']}s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
