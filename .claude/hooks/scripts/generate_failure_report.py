#!/usr/bin/env python3
"""
generate_failure_report.py — Phase D: Failure Report Generator

Synthesizes @failure-predictor + @failure-critic outputs into three artifacts:
  1. failure-predictions/YYYY-MM-DD.md       (human-readable report — archived)
  2. failure-predictions/active-risks.md     (RLM IMMORTAL surface — always replaced)
  3. failure-predictions/index.jsonl         (SOT — append-only, machine-readable)

P1 Compliance:
  - Pure stdlib, deterministic synthesis rules, exit 0 always
  - Single writer: only /predict-failures calls this (no concurrent writes)
  - active-risks.md is always REPLACED (not appended) — stale-safe

CLI:
  python generate_failure_report.py \\
    --validated fp-validated.json \\
    --critic fp-critic-validated.json \\
    --project-dir PATH \\
    [--cleanup file1 file2 ...]

Synthesis rules (deterministic):
  CONFIRM   → prediction included as-is
  DISMISS   → prediction removed from final report
  ESCALATE  → severity promoted one level (Info→Warning→Critical)
  ADD       → critic addition included in final report
  No judgment → CONFIRM by default (critic silence = agreement)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# Severity ordering for sorting (Critical first)
SEVERITY_ORDER = {"Critical": 0, "Warning": 1, "Info": 2}

SEVERITY_ESCALATION = {"Info": "Warning", "Warning": "Critical", "Critical": "Critical"}

CATEGORY_NAMES = {
    "F1": "Concurrency / Race Conditions",
    "F2": "State Machine Drift",
    "F3": "Resource Leaks",
    "F4": "Regex / Parser Vulnerabilities",
    "F5": "LLM-Specific Failures",
    "F6": "Hook System Failures",
    "F7": "SOT Integrity",
}


def _load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _filter_critic_additions(critic: Dict, project_dir: str) -> None:
    """Remove critic additions referencing non-existent files (H-3 hallucination check).

    Unlike predictor predictions (checked against code map by FP1), critic additions
    can reference files outside SCAN_TARGETS. We verify disk existence instead.
    Modifies critic dict in-place.
    """
    additions = critic.get("additions", [])
    if not additions:
        return

    valid: List[Dict] = []
    for add in additions:
        file_path = add.get("file", "")
        if not file_path:
            valid.append(add)  # Missing file — format validator should have caught this
            continue
        abs_path = os.path.join(project_dir, file_path)
        if os.path.exists(abs_path):
            valid.append(add)
        else:
            print(
                f"[generate_failure_report] H-3 FILTER: critic addition '{add.get('id', '?')}' "
                f"references non-existent file '{file_path}' — removed",
                file=sys.stderr,
            )

    if len(valid) != len(additions):
        print(
            f"[generate_failure_report] H-3: {len(additions) - len(valid)} additions removed "
            f"(non-existent files), {len(valid)} retained"
        )
    critic["additions"] = valid


def _synthesize(validated: Dict, critic: Dict) -> List[Dict]:
    """
    Apply critic judgments to validated predictions.
    Returns sorted final prediction list.
    """
    # Index predictions by id
    predictions: Dict[str, Dict] = {
        p["id"]: dict(p) for p in validated.get("predictions", [])
    }

    # Build judgment index
    judgment_map: Dict[str, str] = {}
    judgment_reasons: Dict[str, str] = {}
    for j in critic.get("judgments", []):
        pid = j.get("id", "")
        if pid:
            judgment_map[pid] = j.get("verdict", "CONFIRM")
            judgment_reasons[pid] = j.get("reason", "")

    # Apply judgments
    dismissed_ids = set()
    for pid, pred in list(predictions.items()):
        verdict = judgment_map.get(pid, "CONFIRM")  # Default: CONFIRM

        if verdict == "DISMISS":
            dismissed_ids.add(pid)
            del predictions[pid]

        elif verdict == "ESCALATE":
            old_sev = pred["severity"]
            pred["severity"] = SEVERITY_ESCALATION[old_sev]
            pred["_critic_note"] = f"ESCALATED from {old_sev}: {judgment_reasons.get(pid, '')}"

        elif verdict == "CONFIRM":
            if pid in judgment_reasons and judgment_reasons[pid]:
                pred["_critic_note"] = f"CONFIRMED: {judgment_reasons[pid]}"

    # Add critic additions
    for add in critic.get("additions", []):
        add_copy = dict(add)
        add_copy["_critic_added"] = True
        add_id = add_copy.get("id", f"ADD-{len(predictions)}")
        add_copy["id"] = add_id
        predictions[add_id] = add_copy

    # Sort: Critical first, then by category, then by id
    result = sorted(
        predictions.values(),
        key=lambda p: (
            SEVERITY_ORDER.get(p.get("severity", "Info"), 3),
            p.get("category", "F9"),
            p.get("id", ""),
        ),
    )
    return result


def _severity_icon(severity: str) -> str:
    return {"Critical": "[CRITICAL]", "Warning": "[WARNING]", "Info": "[INFO]"}.get(
        severity, "[?]"
    )


def _generate_md_report(
    final: List[Dict], run_id: str, timestamp: str, dismissed_count: int
) -> str:
    """Generate human-readable markdown report."""
    date = timestamp[:10]
    critical = [p for p in final if p.get("severity") == "Critical"]
    warning = [p for p in final if p.get("severity") == "Warning"]
    info = [p for p in final if p.get("severity") == "Info"]

    lines = [
        f"# Predictive Failure Analysis — {date}",
        f"",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Run ID | `{run_id}` |",
        f"| Timestamp | {timestamp} |",
        f"| Total Predictions | {len(final)} |",
        f"| Critical | {len(critical)} |",
        f"| Warning | {len(warning)} |",
        f"| Info | {len(info)} |",
        f"| Dismissed by @failure-critic | {dismissed_count} |",
        f"",
        f"> Generated by `generate_failure_report.py` (P1 deterministic synthesis).",
        f"> Predictor: @failure-predictor | Critic: @failure-critic",
        f"",
        f"---",
        f"",
        f"## Failure Predictions",
        f"",
    ]

    if not final:
        lines.append("_No confirmed failure predictions after critic review._")
        return "\n".join(lines)

    for pred in final:
        pred_id = pred.get("id", "?")
        cat = pred.get("category", "?")
        cat_name = CATEGORY_NAMES.get(cat, cat)
        severity = pred.get("severity", "Info")
        sev_icon = _severity_icon(severity)

        meta_tags = []
        if pred.get("_critic_added"):
            meta_tags.append("added by @failure-critic")
        if "_critic_note" in pred and "ESCALATED" in pred["_critic_note"]:
            meta_tags.append("escalated by @failure-critic")
        meta_str = f" _({', '.join(meta_tags)})_" if meta_tags else ""

        lines += [
            f"### {pred_id} — {sev_icon} {severity} [{cat}: {cat_name}]{meta_str}",
            f"",
            f"**File**: `{pred.get('file', 'N/A')}`"
            + (f" line {pred['line']}" if pred.get("line") else ""),
            f"",
        ]

        if pred.get("pattern"):
            lines += [f"**Pattern**: {pred['pattern']}", f""]

        lines += [f"**Analysis**: {pred.get('summary', '—')}", f""]

        if pred.get("cross_domain_pattern"):
            lines += [f"**Cross-Domain Evidence**: {pred['cross_domain_pattern']}", f""]

        if pred.get("mitigation"):
            lines += [f"**Mitigation**: {pred['mitigation']}", f""]

        if pred.get("_critic_note"):
            lines += [f"_Critic note: {pred['_critic_note']}_", f""]

        lines += ["---", ""]

    return "\n".join(lines)


def _generate_active_risks(
    final: List[Dict], run_id: str, timestamp: str
) -> str:
    """
    Generate active-risks.md for RLM IMMORTAL surfacing.
    This file is ALWAYS replaced on each /predict-failures run.
    """
    date = timestamp[:10]
    critical = [p for p in final if p.get("severity") == "Critical"]
    warning = [p for p in final if p.get("severity") == "Warning"]
    top_risks = (critical + warning)[:5]

    lines = [
        f"<!-- IMMORTAL: failure-predictor active risks -->",
        f"<!-- run_id: {run_id} | generated: {timestamp} -->",
        f"<!-- Replace on each /predict-failures run — do not edit manually -->",
        f"",
        f"## Active Failure Predictions (scan: {date})",
        f"",
        f"Total: {len(final)} | Critical: {len(critical)} | Warning: {len(warning)}",
        f"",
    ]

    if not top_risks:
        lines.append("  No Critical or Warning predictions in last scan.")
    else:
        for pred in top_risks:
            sev = pred.get("severity", "Info")
            icon = "[CRITICAL]" if sev == "Critical" else "[WARNING]"
            cat = pred.get("category", "?")
            summary = pred.get("summary", pred.get("pattern", "?"))[:90]
            file_short = os.path.basename(pred.get("file", "?"))
            lines.append(
                f"  - [{pred['id']}] {icon} [{cat}] `{file_short}` — {summary}"
            )

        remaining = len(final) - len(top_risks)
        if remaining > 0:
            lines.append(
                f"  - ... +{remaining} more — see failure-predictions/{date}.md"
            )

    lines += [
        f"",
        f"  Run /predict-failures to refresh predictions.",
        f"  Full report: failure-predictions/{date}.md",
    ]

    return "\n".join(lines)


def _append_index(index_path: str, entry: Dict) -> None:
    """Append one entry to index.jsonl (SOT — append-only)."""
    os.makedirs(os.path.dirname(os.path.abspath(index_path)), exist_ok=True)
    with open(index_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate failure predictions report (Phase D)"
    )
    parser.add_argument(
        "--validated", required=True,
        help="fp-validated.json (predictor output, FP1-FP7 validated)"
    )
    parser.add_argument(
        "--critic", required=True,
        help="fp-critic-validated.json (critic output, format validated)"
    )
    parser.add_argument(
        "--project-dir",
        default=os.environ.get("CLAUDE_PROJECT_DIR", "."),
        help="Project root directory",
    )
    parser.add_argument(
        "--cleanup", nargs="*", default=[],
        help="Temp files to delete after successful generation",
    )
    args = parser.parse_args()

    project_dir = os.path.abspath(args.project_dir)
    output_dir = os.path.join(project_dir, "failure-predictions")
    os.makedirs(output_dir, exist_ok=True)

    # Load inputs
    try:
        validated = _load_json(args.validated)
        critic = _load_json(args.critic)
    except Exception as e:
        print(f"[generate_failure_report] ERROR loading inputs: {e}", file=sys.stderr)
        sys.exit(0)

    # H-3: Filter critic additions referencing non-existent files
    _filter_critic_additions(critic, project_dir)

    # Count dismissed (for report metadata)
    original_ids = {p["id"] for p in validated.get("predictions", [])}
    confirmed_verdicts = {
        j["id"] for j in critic.get("judgments", []) if j.get("verdict") == "DISMISS"
    }
    dismissed_count = len(original_ids & confirmed_verdicts)

    # Synthesize
    final_predictions = _synthesize(validated, critic)

    # Timestamps
    now = datetime.now(timezone.utc)
    timestamp = now.isoformat()
    date_str = now.strftime("%Y-%m-%d")
    run_id = f"fp-{now.strftime('%Y%m%d-%H%M%S')}"

    # 1. Human-readable archived report
    report_path = os.path.join(output_dir, f"{date_str}.md")
    report_content = _generate_md_report(final_predictions, run_id, timestamp, dismissed_count)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    print(f"[generate_failure_report] Report: {report_path}")

    # 2. active-risks.md — REPLACE (always fresh)
    active_risks_path = os.path.join(output_dir, "active-risks.md")
    active_content = _generate_active_risks(final_predictions, run_id, timestamp)
    with open(active_risks_path, "w", encoding="utf-8") as f:
        f.write(active_content)
    print(f"[generate_failure_report] Active risks updated: {active_risks_path}")

    # 3. index.jsonl — APPEND (SOT)
    index_path = os.path.join(output_dir, "index.jsonl")
    critical_list = [p for p in final_predictions if p.get("severity") == "Critical"]
    warning_list = [p for p in final_predictions if p.get("severity") == "Warning"]

    top_risks_entry = [
        {
            "id": p["id"],
            "category": p.get("category", "?"),
            "severity": p["severity"],
            "file": p.get("file", "?"),
            "line": p.get("line"),
            "summary": (p.get("summary") or p.get("pattern") or "")[:120],
        }
        for p in (critical_list + warning_list)[:10]
    ]

    index_entry: Dict[str, Any] = {
        "run_id": run_id,
        "timestamp": timestamp,
        "scope": "full",
        "total_predictions": len(final_predictions),
        "severity_counts": {
            "Critical": len(critical_list),
            "Warning": len(warning_list),
            "Info": sum(1 for p in final_predictions if p.get("severity") == "Info"),
        },
        "dismissed_count": dismissed_count,
        "top_risks": top_risks_entry,
        "report_path": f"failure-predictions/{date_str}.md",
        "active_risks_updated": True,
    }

    _append_index(index_path, index_entry)
    print(f"[generate_failure_report] SOT index updated: {index_path}")

    # Cleanup temp files
    for tmp in args.cleanup:
        try:
            if tmp and os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass

    # Final summary
    print(
        f"[generate_failure_report] Done — {len(final_predictions)} predictions "
        f"({len(critical_list)} Critical, {len(warning_list)} Warning, "
        f"{dismissed_count} dismissed)"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[generate_failure_report] FATAL: {e}", file=sys.stderr)
        sys.exit(0)
