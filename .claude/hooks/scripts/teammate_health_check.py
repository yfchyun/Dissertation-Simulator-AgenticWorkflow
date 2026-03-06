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
from datetime import datetime, timezone
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

    # Check task timestamps from active_team (preferred source)
    now = time.time()
    task_status_list = []
    if isinstance(active_team, dict):
        for task in active_team.get("tasks_pending", []):
            if isinstance(task, dict) and task.get("created_at"):
                try:
                    created = datetime.fromisoformat(task["created_at"])
                    age = now - created.timestamp()
                    t_status = STATUS_HEALTHY if age < timeout_seconds else STATUS_IDLE
                    task_status_list.append({
                        "task_id": task.get("task_id", "unknown"),
                        "agent": task.get("agent"),
                        "created_at": task["created_at"],
                        "age_seconds": round(age),
                        "status": t_status,
                    })
                except (ValueError, OSError):
                    pass
        for task in active_team.get("tasks_completed", []):
            tid = task.get("task_id", task) if isinstance(task, dict) else task
            task_status_list.append({
                "task_id": tid,
                "agent": task.get("agent") if isinstance(task, dict) else None,
                "status": "completed",
                "age_seconds": 0,
            })

    # FALLBACK: Check wave result files for recent modifications
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

    # Determine overall status — prefer task_status if available
    all_items = task_status_list if task_status_list else teammates
    if not all_items:
        overall = "no_outputs"
    elif all(t["status"] in (STATUS_HEALTHY, "completed") for t in all_items):
        overall = STATUS_HEALTHY
    elif any(t["status"] == STATUS_IDLE for t in all_items):
        overall = STATUS_IDLE
    else:
        overall = STATUS_HEALTHY

    return {
        "overall_status": overall,
        "active_team": active_team,
        "task_status": task_status_list,
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
        team = result["active_team"]
        team_name = team.get("name", team) if isinstance(team, dict) else team
        print(f"Active team: {team_name}")

    # Show per-task status if available
    task_status = result.get("task_status", [])
    if task_status:
        print(f"\nTask status ({len(task_status)} tasks):")
        for ts in task_status:
            age_str = f"age: {ts['age_seconds']}s" if ts.get("age_seconds") else ""
            agent_str = f" [{ts['agent']}]" if ts.get("agent") else ""
            print(f"  {ts['status'].upper()}: {ts['task_id']}{agent_str} ({age_str})")

    idle_count = sum(1 for t in result["teammates"] if t["status"] == STATUS_IDLE)
    if idle_count > 0:
        print(f"WARNING: {idle_count} idle output(s) detected")
        for t in result["teammates"]:
            if t["status"] == STATUS_IDLE:
                print(f"  IDLE: {t['file']} (age: {t['age_seconds']}s)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
