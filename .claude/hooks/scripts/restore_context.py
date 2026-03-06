#!/usr/bin/env python3
"""
Context Preservation System — restore_context.py

Triggered by: SessionStart (all sources: clear, compact, resume, startup)

RLM Pattern Implementation:
  - Outputs a POINTER to the full snapshot file + brief summary
  - Does NOT inject the full snapshot content into stdout
  - Claude uses Read tool to load the external file when needed
  - This treats the snapshot as an "external environment object" (RLM)
  - Knowledge Archive: includes pointers to knowledge-index.jsonl and sessions/
  - Claude can Grep knowledge-index.jsonl for programmatic probing (RLM pattern)

Output (stdout, exit 0):
  [CONTEXT RECOVERY]
  pointer to .claude/context-snapshots/latest.md
  + brief summary (≤500 chars)
  + knowledge archive pointers (if available)

SOT Compliance:
  - Read-only: reads latest.md and state.yaml, never modifies
  - Verifies SOT consistency between snapshot and current state
"""

import os
import re
import sys
import json
import time
from datetime import datetime

# Add script directory to path for shared library import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _context_lib import (
    read_stdin_json, get_snapshot_dir, read_autopilot_state,
    validate_step_output, validate_sot_schema, sot_paths,
    extract_path_tags, aggregate_risk_scores, atomic_write,
    SNAPSHOT_SECTION_MARKERS,
    _extract_thesis_continuity,  # Phase 1-A: reuse from shared lib (no duplication)
)


# Module-level compiled regex (process-level singleton)
_SECTION_MARKER_RE = re.compile(r'<!-- SECTION:(\w+) -->')
_TOKENIZE_SPLIT_RE = re.compile(r'[^a-zA-Z0-9가-힣_\-./]+')


_ENGLISH_STOP_WORDS = frozenset({
    "is", "to", "do", "an", "if", "or", "in", "on", "at", "as",
    "be", "by", "no", "so", "up", "we", "it", "of", "am", "he",
    "me", "my", "us", "vs",
})


def _tokenize(text):
    """Split text into keyword tokens for relevance scoring.

    P1 Compliance: Deterministic — regex split + filter.
    Preserves Korean characters, file path segments, and identifiers.
    M10: Minimum length reduced from 3 to 2; uppercase acronyms (2+ chars) preserved.
    Stop words filtered to prevent English 2-char noise from inflating scores.
    """
    if not text:
        return set()
    # M10: Extract uppercase acronyms (2+ chars) before lowercasing
    acronyms = {t for t in _TOKENIZE_SPLIT_RE.split(text) if len(t) >= 2 and t.isupper()}
    tokens = _TOKENIZE_SPLIT_RE.split(text.lower())
    # M10: Changed minimum token length from 3 to 2
    result = {t for t in tokens if len(t) > 1 and t not in _ENGLISH_STOP_WORDS}
    # M10: Merge back lowercase versions of acronyms (already included) + original case
    result.update(a.lower() for a in acronyms)
    return result


# Maximum age (seconds) for snapshot restoration per source type
RESTORE_THRESHOLDS = {
    "clear": float("inf"),    # Always restore after /clear
    "compact": float("inf"),  # Always restore after compression
    "resume": 3600,           # 1 hour for resume
    "startup": 1800,          # 30 minutes for fresh startup
}


def main():
    input_data = read_stdin_json()

    # Determine source type
    source = input_data.get("source", "startup")

    # Determine project directory
    project_dir = os.environ.get(
        "CLAUDE_PROJECT_DIR",
        input_data.get("cwd", os.getcwd()),
    )

    snapshot_dir = get_snapshot_dir(project_dir)
    latest_path = os.path.join(snapshot_dir, "latest.md")

    # Check if snapshot exists
    if not os.path.exists(latest_path):
        sys.exit(0)  # No snapshot to restore — silent exit

    # Check age threshold
    snapshot_age = time.time() - os.path.getmtime(latest_path)
    max_age = RESTORE_THRESHOLDS.get(source, 1800)
    if snapshot_age > max_age:
        sys.exit(0)  # Snapshot too old for this source type

    # E6: Find best available snapshot (fallback if latest.md is inadequate)
    best_path, best_size = _find_best_snapshot(snapshot_dir, latest_path)
    fallback_note = ""
    if best_path != latest_path:
        latest_size = 0
        try:
            latest_size = os.path.getsize(latest_path)
        except OSError:
            pass
        fallback_note = (
            f"⚠️ latest.md ({latest_size}B)가 빈약하여 "
            f"더 풍부한 아카이브({best_size}B)를 참조합니다."
        )

    # Read snapshot for summary extraction
    try:
        with open(best_path, "r", encoding="utf-8") as f:
            snapshot_content = f.read()
    except Exception:
        sys.exit(0)

    if not snapshot_content.strip():
        sys.exit(0)

    # Extract brief summary from snapshot
    summary = _extract_brief_summary(snapshot_content)

    # Verify SOT consistency
    sot_warning = _verify_sot_consistency(snapshot_content, project_dir)

    # Predictive Debugging: Aggregate risk scores from Knowledge Archive
    # Runs once per SessionStart — writes cache for PreToolUse hook
    risk_data = _generate_risk_scores_cache(project_dir, snapshot_dir)

    # Build RLM-style recovery output (pointer + summary)
    recovery_output = _build_recovery_output(
        source=source,
        latest_path=best_path,  # E6: point to best available snapshot
        summary=summary,
        sot_warning=sot_warning,
        snapshot_age=snapshot_age,
        fallback_note=fallback_note,
        project_dir=project_dir,
        snapshot_content=snapshot_content,
        risk_data=risk_data,
    )

    # Output to stdout — Claude receives this as session context
    print(recovery_output)
    sys.exit(0)


def _extract_brief_summary(content):
    """Extract key information from snapshot for brief summary.

    P1-RLM Selective Peek: Uses SECTION markers for precise section extraction
    when available. Falls back to legacy line-by-line parsing for pre-P1 snapshots.

    Deterministic extraction from snapshot structure:
      - 현재 작업 (Current Task): first content line
      - 수정된 파일 (Modified Files): count of table rows
      - 참조된 파일 (Referenced Files): count of table rows
      - 대화 통계: numeric stats lines
    """
    # P1-RLM: Try section-marker-based extraction first
    sections = parse_snapshot_sections(content)
    if "_full" not in sections:
        return _extract_summary_from_sections(sections, content)

    # Fallback: legacy line-by-line parsing (pre-P1 snapshots without markers)
    return _extract_summary_legacy(content)


def _extract_summary_from_sections(sections, full_content):
    """P1-RLM: Extract summary using parsed SECTION markers.

    Direct section access eliminates line-by-line scanning.
    Each section's content is parsed independently, reducing
    cross-section interference and improving extraction accuracy.
    """
    summary_parts = []

    # Task section
    task_text = sections.get("task", "")
    if task_text:
        for line in task_text.split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith(">") or line.startswith("<!--"):
                continue
            if line.startswith("**최근 지시") or line.startswith("**Latest Instruction"):
                instruction = line.split(":**", 1)[-1].strip() if ":**" in line else line
                summary_parts.append(("최근 지시", instruction[:200]))
            elif not any(l == "현재 작업" for l, _ in summary_parts):
                summary_parts.append(("현재 작업", line[:200]))

    # Completion state section
    completion_text = sections.get("completion", "")
    if completion_text:
        for line in completion_text.split("\n"):
            line = line.strip()
            if line.startswith("- ") and ("실패" in line or "성공" in line):
                summary_parts.append(("완료상태", line[:150]))
            elif "ERROR" in line:
                summary_parts.append(("에러", line[:200]))

    # Git section
    git_text = sections.get("git", "")
    if git_text:
        in_code_block = False
        for line in git_text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block and (stripped.startswith("M ") or stripped.startswith(" M") or
                                  stripped.startswith("A ") or stripped.startswith("??")):
                summary_parts.append(("git", stripped[:100]))

    # Modified files section
    files_count = 0
    files_text = sections.get("modified_files", "")
    if files_text:
        for line in files_text.split("\n"):
            line = line.strip()
            if line.startswith("| `") or line.startswith("### `"):
                files_count += 1
                if '`' in line:
                    backtick_parts = line.split('`')
                    if len(backtick_parts) >= 2 and backtick_parts[1]:
                        summary_parts.append(("수정_파일_경로", backtick_parts[1]))

    # Referenced files section
    read_count = 0
    refs_text = sections.get("referenced_files", "")
    if refs_text:
        for line in refs_text.split("\n"):
            if line.strip().startswith("| `"):
                read_count += 1

    # Statistics section
    stats_text = sections.get("statistics", "")
    if stats_text:
        for line in stats_text.split("\n"):
            line = line.strip()
            if line.startswith("- "):
                summary_parts.append(("통계", line[:100]))

    # Error detection from recent tool activity (in completion or resume sections)
    for section_key in ("completion", "resume"):
        sec_text = sections.get(section_key, "")
        if "← ERROR" in sec_text:
            for line in sec_text.split("\n"):
                if "← ERROR" in line:
                    summary_parts.append(("에러", line.strip()[:200]))

    # Autopilot section (direct — no full-content scan needed)
    autopilot_text = sections.get("autopilot", "")
    if autopilot_text:
        for line in autopilot_text.split("\n"):
            if "현재 단계:" in line:
                summary_parts.append(("autopilot", line.strip()[:100]))
                break

    # ULW section (direct — no full-content scan needed)
    ulw_text = sections.get("ulw", "")
    if ulw_text:
        summary_parts.append(("ulw", "ULW (Ultrawork) Mode Active"))

    # Team section (direct)
    team_text = sections.get("team", "")
    if team_text:
        for line in team_text.split("\n"):
            if "tasks_pending" in line.lower() or "tasks_completed" in line.lower():
                summary_parts.append(("team", line.strip()[:100]))
                break

    # File counts
    if files_count > 0:
        summary_parts.append(("수정 파일", f"{files_count}개 파일 수정됨"))
    if read_count > 0:
        summary_parts.append(("참조 파일", f"{read_count}개 파일 참조됨"))

    return summary_parts


def _extract_summary_legacy(content):
    """Legacy line-by-line summary extraction for pre-P1 snapshots.

    Preserved for backward compatibility with snapshots that lack
    <!-- SECTION: --> markers.
    """
    summary_parts = []

    lines = content.split("\n")
    current_section = ""
    files_count = 0
    read_count = 0

    for line in lines:
        # Section header detection
        if line.startswith("## 현재 작업"):
            current_section = "task"
            continue
        elif line.startswith("## 결정론적 완료 상태"):
            current_section = "completion"
            continue
        elif line.startswith("## Git 변경 상태"):
            current_section = "git"
            continue
        elif line.startswith("## 수정된 파일"):
            current_section = "files"
            continue
        elif line.startswith("## 참조된 파일"):
            current_section = "reads"
            continue
        elif line.startswith("## 대화 통계"):
            current_section = "stats"
            continue
        elif line.startswith("## "):
            current_section = ""
            continue

        line = line.strip()
        if not line or line.startswith(">"):
            continue

        if current_section == "task":
            if line.startswith("**마지막 사용자 지시:**"):
                instruction = line.replace("**마지막 사용자 지시:**", "").strip()
                summary_parts.append(("최근 지시", instruction[:200]))
            elif len(summary_parts) < 1:
                summary_parts.append(("현재 작업", line[:200]))
        elif current_section == "completion" and line.startswith("- "):
            # "- Edit: 18회 호출 → 18 성공, 0 실패" 형태
            if "실패" in line or "성공" in line:
                summary_parts.append(("완료상태", line[:150]))
        elif current_section == "git" and line.startswith("```"):
            pass  # skip code block markers
        elif current_section == "git" and (line.startswith("M ") or line.startswith(" M") or line.startswith("A ") or line.startswith("??")):
            summary_parts.append(("git", line[:100]))
        elif current_section == "files" and (line.startswith("| `") or line.startswith("### `")):
            files_count += 1
            # C1: Extract file path for dynamic RLM hints
            if '`' in line:
                backtick_parts = line.split('`')
                if len(backtick_parts) >= 2 and backtick_parts[1]:
                    summary_parts.append(("수정_파일_경로", backtick_parts[1]))
        elif current_section == "reads" and line.startswith("| `"):
            read_count += 1
        elif current_section == "stats" and line.startswith("- "):
            summary_parts.append(("통계", line[:100]))
        # C1: Detect recent errors from completion state
        elif current_section == "completion" and "ERROR" in line:
            summary_parts.append(("에러", line[:200]))
        # C1: Detect recent tool errors from 최근 도구 활동 section
        elif "← ERROR" in line:
            summary_parts.append(("에러", line.strip()[:200]))

    # C1: Extract Autopilot section presence
    if "AUTOPILOT MODE ACTIVE" in content or "autopilot" in content.lower():
        for line in lines:
            if "현재 단계:" in line:
                summary_parts.append(("autopilot", line.strip()[:100]))
                break

    # C1: Extract ULW mode presence
    # D-7: ULW detection pattern must match _context_lib.py + validate_retry_budget.py
    if "ULW 상태" in content or "Ultrawork Mode State" in content:
        summary_parts.append(("ulw", "ULW (Ultrawork) Mode Active"))

    # C1: Extract active team info
    if "Agent Team" in content or "active_team" in content:
        for line in lines:
            if "tasks_pending" in line.lower() or "tasks_completed" in line.lower():
                summary_parts.append(("team", line.strip()[:100]))
                break

    # Add file counts as summary entries
    if files_count > 0:
        summary_parts.append(("수정 파일", f"{files_count}개 파일 수정됨"))
    if read_count > 0:
        summary_parts.append(("참조 파일", f"{read_count}개 파일 참조됨"))

    return summary_parts


def _verify_sot_consistency(snapshot_content, project_dir):
    """Check if current SOT matches snapshot's recorded SOT."""
    paths = sot_paths(project_dir)
    current_sot_exists = any(os.path.exists(p) for p in paths)

    if "SOT 파일 없음" in snapshot_content and not current_sot_exists:
        return None  # Consistent: both have no SOT

    if current_sot_exists:
        # Read current SOT modification time
        for sot_path in paths:
            if os.path.exists(sot_path):
                sot_mtime = datetime.fromtimestamp(
                    os.path.getmtime(sot_path)
                ).isoformat()

                # Check if snapshot recorded an older mtime
                if "수정 시각:" in snapshot_content:
                    for line in snapshot_content.split("\n"):
                        if "수정 시각:" in line:
                            recorded_time = line.split("수정 시각:")[1].strip()
                            if recorded_time != sot_mtime:
                                return (
                                    f"SOT가 snapshot 저장 이후 변경되었습니다. "
                                    f"기록: {recorded_time} → 현재: {sot_mtime}"
                                )
                break

    return None


# =============================================================================
# MEMORY.md Health Check (Improvement A — deterministic, P1 compliant)
# =============================================================================

# Pre-compiled regex for duplicate header detection
_MEMORY_HEADER_RE = re.compile(r'^(#{1,3})\s+(.+)$', re.MULTILINE)


def _check_memory_health(project_dir):
    """Deterministic health check for MEMORY.md (auto memory file).

    P1 Compliance: All checks are string/regex operations — zero LLM inference.
    Returns: list of warning strings (empty if healthy).

    Checks:
      MH-1: Line count > 200 (system truncation threshold)
      MH-2: Duplicate ## headers (same header text appears 2+ times)
      MH-3: Empty sections (## header followed immediately by another ## header)
      MH-4: Nearly empty file (< 3 content lines)
    """
    warnings = []

    # Locate MEMORY.md — Claude's auto memory directory
    # Convention: ~/.claude-*/projects/{project-hash}/memory/MEMORY.md
    memory_path = _find_memory_md(project_dir)
    if not memory_path or not os.path.exists(memory_path):
        return warnings  # No MEMORY.md — not an error, just nothing to check

    try:
        with open(memory_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return warnings

    lines = content.split("\n")
    total_lines = len(lines)
    content_lines = [l for l in lines if l.strip() and not l.strip().startswith("#")]

    # MH-1: Line count > 200
    if total_lines > 200:
        warnings.append(
            f"MEMORY.md가 200줄을 초과 ({total_lines}줄). "
            "200줄 이후는 truncate됩니다. 정리를 권장합니다."
        )

    # MH-2: Duplicate headers
    headers = _MEMORY_HEADER_RE.findall(content)
    header_texts = [text.strip() for _, text in headers]
    seen = {}
    for ht in header_texts:
        seen[ht] = seen.get(ht, 0) + 1
    duplicates = [ht for ht, count in seen.items() if count > 1]
    if duplicates:
        warnings.append(
            f"중복 섹션 감지: {', '.join(duplicates[:3])}. 통합을 권장합니다."
        )

    # MH-3: Empty sections (## followed by ## with no content between)
    empty_sections = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("## "):
            # Look ahead for next non-empty line
            for j in range(i + 1, min(i + 5, len(lines))):
                next_stripped = lines[j].strip()
                if not next_stripped:
                    continue
                if next_stripped.startswith("## ") or next_stripped.startswith("# "):
                    empty_sections.append(stripped)
                break
    if empty_sections:
        warnings.append(
            f"빈 섹션: {', '.join(s[:40] for s in empty_sections[:3])}. "
            "내용 추가 또는 섹션 삭제를 권장합니다."
        )

    # MH-4: Nearly empty file
    if len(content_lines) < 3 and total_lines > 0:
        warnings.append(
            "MEMORY.md가 거의 비어 있습니다. "
            "핵심 사실과 사용자 선호도를 기록하세요."
        )

    return warnings


def _find_memory_md(project_dir):
    """Locate the auto memory MEMORY.md file for this project.

    Convention: ~/.claude-*/projects/{project-hash}/memory/MEMORY.md
    The project hash is derived from the absolute project path.
    """
    if not project_dir:
        return None

    home = os.path.expanduser("~")
    abs_project = os.path.abspath(project_dir)

    # Search for claude insight directories
    try:
        for entry in os.listdir(home):
            if entry.startswith(".claude-") and os.path.isdir(os.path.join(home, entry)):
                projects_dir = os.path.join(home, entry, "projects")
                if not os.path.isdir(projects_dir):
                    continue
                # Project hash: path with / replaced by -
                project_hash = abs_project.replace("/", "-")
                memory_path = os.path.join(
                    projects_dir, project_hash, "memory", "MEMORY.md"
                )
                if os.path.exists(memory_path):
                    return memory_path
    except Exception:
        pass

    return None


# =============================================================================
# Today/Yesterday Session Summary (Improvement B — deterministic, P1 compliant)
# =============================================================================

def _get_today_yesterday_summary(ki_path):
    """Aggregate today's and yesterday's sessions from knowledge-index.jsonl.

    P1 Compliance: All operations are deterministic (timestamp string comparison,
    counting, set operations). Zero LLM inference.

    Returns: list of summary strings (empty if no sessions today/yesterday).
    """
    if not ki_path or not os.path.exists(ki_path):
        return []

    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = datetime.fromtimestamp(
        datetime.now().timestamp() - 86400
    ).strftime("%Y-%m-%d")

    today_sessions = []
    yesterday_sessions = []

    try:
        with open(ki_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    entry = json.loads(stripped)
                except (json.JSONDecodeError, ValueError):
                    continue
                ts = entry.get("timestamp", "")
                if ts.startswith(today):
                    today_sessions.append(entry)
                elif ts.startswith(yesterday):
                    yesterday_sessions.append(entry)
    except Exception:
        return []

    summaries = []

    if today_sessions:
        n_sessions = len(today_sessions)
        all_files = set()
        for s in today_sessions:
            for f in s.get("modified_files", []):
                all_files.add(os.path.basename(f) if f else "")
        all_files.discard("")
        n_files = len(all_files)
        first_task = (today_sessions[0].get("user_task", "") or "")[:80]
        summaries.append(
            f"오늘 작업: {n_sessions}개 세션, {n_files}개 파일 수정"
            + (f" | 첫 작업: {first_task}" if first_task else "")
        )

    if yesterday_sessions:
        n_sessions = len(yesterday_sessions)
        all_files = set()
        for s in yesterday_sessions:
            for f in s.get("modified_files", []):
                all_files.add(os.path.basename(f) if f else "")
        all_files.discard("")
        n_files = len(all_files)
        summaries.append(
            f"어제 작업: {n_sessions}개 세션, {n_files}개 파일 수정"
        )

    return summaries


# =============================================================================
# Phase 1-A: Thesis Continuity Markers
# =============================================================================
# Uses _extract_thesis_continuity() imported from _context_lib.py (DRY — no duplication).
# Both SessionStart (live display) and save_context (KI archival) use the same function.


# =============================================================================
# Phase 1-C: Quality Gate Trend (pass/fail history from knowledge-index)
# =============================================================================

def _get_quality_gate_trend(ki_path, max_sessions=10):
    """Extract quality gate pass/fail trend from recent knowledge-index sessions.

    Scans thesis_continuity.pending_gates across recent sessions to detect
    patterns like repeated gate failures (indicates systematic quality issues).

    P1 Compliance: Deterministic JSON extraction + counting.
    Returns: summary string or empty string.
    """
    if not ki_path or not os.path.exists(ki_path):
        return ""
    try:
        entries = []
        with open(ki_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        # Scan recent sessions with thesis_continuity data
        gate_history = {}  # gate_name → list of statuses ("pending" or "pass")
        recent = entries[-max_sessions:] if entries else []
        sessions_with_data = 0
        for sess in recent:
            tc = sess.get("thesis_continuity", {})
            if not tc:
                continue
            sessions_with_data += 1
            pending = set(tc.get("pending_gates", []))
            # Any gate mentioned as pending is "fail/pending" in that session
            for g in pending:
                gate_history.setdefault(g, []).append("pending")

        if sessions_with_data < 2:
            return ""

        # Detect repeated failures (same gate pending in 3+ consecutive sessions)
        repeated_failures = []
        for gate, statuses in gate_history.items():
            if len(statuses) >= 3:
                repeated_failures.append(f"{gate} ({len(statuses)}x pending)")

        if repeated_failures:
            return f"Repeated gate failures: {', '.join(repeated_failures)} — consider root cause analysis"
        elif gate_history:
            total_pending = sum(len(v) for v in gate_history.values())
            return f"{total_pending} gate-pending events across {sessions_with_data} sessions"
        return ""
    except Exception:
        return ""


def _build_recovery_output(source, latest_path, summary, sot_warning, snapshot_age, fallback_note="", project_dir=None, snapshot_content="", risk_data=None):
    """Build the RLM-style recovery output for SessionStart injection."""
    age_str = _format_age(snapshot_age)

    # Build header
    output_lines = [
        "[CONTEXT RECOVERY]",
        f"이전 세션이 {'clear' if source == 'clear' else 'compact' if source == 'compact' else source}되었습니다.",
        f"전체 복원 파일: {latest_path}",
        "",
    ]

    # Brief summary
    task_info = ""
    latest_instruction = ""
    files_info = ""
    reads_info = ""
    stats_info = []
    completion_info = []
    git_info = []
    error_info = []
    autopilot_info = ""
    team_info = ""
    ulw_info = ""

    for label, content in summary:
        if label == "현재 작업":
            task_info = content
        elif label == "최근 지시":
            latest_instruction = content
        elif label == "수정 파일":
            files_info = content
        elif label == "참조 파일":
            reads_info = content
        elif label == "통계":
            stats_info.append(content)
        elif label == "완료상태":
            completion_info.append(content)
        elif label == "git":
            git_info.append(content)
        elif label == "에러":
            error_info.append(content)
        elif label == "autopilot":
            autopilot_info = content
        elif label == "team":
            team_info = content
        elif label == "ulw":
            ulw_info = content
        # "수정_파일_경로" labels are consumed below for dynamic RLM hints (C2)

    if task_info:
        output_lines.append(f"■ 현재 작업: {task_info}")
    if latest_instruction:
        output_lines.append(f"■ 최근 지시: {latest_instruction}")
    output_lines.append(f"■ 마지막 저장: {age_str} 전")

    if stats_info:
        for s in stats_info[:3]:
            output_lines.append(f"■ {s}")
    if files_info:
        output_lines.append(f"■ {files_info}")
    if reads_info:
        output_lines.append(f"■ {reads_info}")

    # Completion state and git status (Change 4)
    if completion_info:
        output_lines.append(f"■ 완료상태: {'; '.join(completion_info[:3])}")
    if git_info:
        output_lines.append(f"■ Git: {', '.join(git_info[:5])}")
    # C1: Surface errors, autopilot, team state for immediate awareness
    if error_info:
        output_lines.append(f"■ ⚠ 최근 에러: {'; '.join(error_info[:3])}")
    if autopilot_info:
        output_lines.append(f"■ Autopilot: {autopilot_info}")
    if team_info:
        output_lines.append(f"■ Team: {team_info}")
    if ulw_info:
        output_lines.append(f"■ ULW: {ulw_info}")

    # E6: Fallback note (if using archive instead of latest.md)
    if fallback_note:
        output_lines.append("")
        output_lines.append(fallback_note)

    # SOT warning
    if sot_warning:
        output_lines.append("")
        output_lines.append(f"⚠️ {sot_warning}")

    # Knowledge Archive pointers (Area 1: Cross-Session)
    # Use get_snapshot_dir(project_dir) — NOT os.path.dirname(latest_path)
    # (E6 fallback may point latest_path to sessions/ subdirectory, breaking path derivation)
    ka_snapshot_dir = get_snapshot_dir(project_dir) if project_dir else os.path.dirname(latest_path)
    ki_path = os.path.join(ka_snapshot_dir, "knowledge-index.jsonl")
    sessions_dir = os.path.join(ka_snapshot_dir, "sessions")

    has_archive = os.path.exists(ki_path) or os.path.isdir(sessions_dir)
    if has_archive:
        output_lines.append("")
        if os.path.exists(ki_path):
            output_lines.append(f"■ 과거 세션 인덱스: {ki_path}")
            recent = _get_recent_sessions(ki_path, 3)
            for s in recent:
                ts = s.get("timestamp", "")[:10]
                task = s.get("user_task", "(기록 없음)")[:80]
                output_lines.append(f"  - [{ts}] {task}")
            # CM-4: RLM query examples — activate programmatic probing
            output_lines.append("  RLM 쿼리 예시 (Grep tool 사용):")
            output_lines.append(f'  - Grep "design_decisions" {ki_path} → 설계 결정 포함 세션')
            output_lines.append(f'  - Grep "error_patterns" {ki_path} → 에러 패턴 포함 세션')
            output_lines.append(f'  - Grep "phase_flow.*implementation" {ki_path} → 구현 단계 세션')
            output_lines.append(f'  - Grep "ulw_active" {ki_path} → ULW 세션')
            output_lines.append(f'  - Grep "diagnosis_patterns" {ki_path} → 진단 패턴 포함 세션')
            # C2: Dynamic RLM query hints (context-aware)
            file_paths = [c for l, c in summary if l == "수정_파일_경로"]
            if file_paths:
                path_tags = extract_path_tags(file_paths)
                for tag in path_tags[:2]:
                    output_lines.append(f'  - Grep "tags.*{tag}" {ki_path} → {tag} 관련 세션')
            if error_info:
                output_lines.append(f'  - Grep "resolution" {ki_path} → 에러→해결 패턴 포함 세션')

            # P0-RLM: Active Knowledge Retrieval — relevance-scored
            # Surface past sessions most relevant to CURRENT work context
            file_paths_for_retrieval = [c for l, c in summary if l == "수정_파일_경로"]
            relevant = _retrieve_relevant_sessions(
                ki_path, task_info or "", file_paths_for_retrieval
            )
            if relevant:
                output_lines.append("")
                output_lines.append("■ ACTIVE RETRIEVAL — 현재 작업과 관련된 과거 세션:")
                for score, sess in relevant:
                    ts = sess.get("timestamp", "")[:10]
                    past_task = (sess.get("user_task", "") or "(기록 없음)")[:80]
                    session_id_short = sess.get("session_id", "?")[:8]
                    output_lines.append(
                        f"  - [{ts}] {past_task} (relevance:{score:.1f}, id:{session_id_short})"
                    )
                    # Surface actionable Grep for the most relevant session
                    if score >= 5.0:
                        sid = sess.get("session_id", "")
                        if sid:
                            output_lines.append(
                                f'    → Grep "{sid[:12]}" {ki_path} → 이 세션의 상세 정보'
                            )

            # P1-1: Proactive Error→Resolution surfacing
            # Surface recent error patterns + resolutions directly (no manual Grep)
            error_resolutions = _extract_recent_error_resolutions(recent)
            if error_resolutions:
                output_lines.append("")
                output_lines.append("■ 최근 에러→해결 패턴 (자동 표면화):")
                for er in error_resolutions[:3]:
                    output_lines.append(f"  - {er}")

            # P1-2: Proactive Diagnosis Pattern surfacing
            # Surface recent diagnosis patterns for cross-session learning
            diagnosis_hints = _extract_recent_diagnosis_patterns(recent)
            if diagnosis_hints:
                output_lines.append("")
                output_lines.append("■ 최근 진단 패턴 (자동 표면화):")
                for dh in diagnosis_hints[:3]:
                    output_lines.append(f"  - {dh}")

            # P1-3: Proactive Team Summary surfacing
            # Surface recent team coordination history for quality continuity
            team_hints = _extract_recent_team_summaries(recent)
            if team_hints:
                output_lines.append("")
                output_lines.append("■ 최근 팀 실행 이력 (자동 표면화):")
                for th in team_hints[:3]:
                    output_lines.append(f"  - {th}")

            # P3-RLM: Active Quarterly Archive consumption (long-term patterns)
            qa_path = os.path.join(ka_snapshot_dir, "knowledge-archive-quarterly.jsonl")
            qa_insights = _extract_quarterly_insights(qa_path)
            if qa_insights:
                output_lines.append("")
                output_lines.append("■ 장기 패턴 (Quarterly Archive — 자동 표면화):")
                for insight in qa_insights[:5]:
                    output_lines.append(f"  - {insight}")
                output_lines.append(f"  (원본: {qa_path})")
            elif os.path.exists(qa_path):
                output_lines.append(f"■ 분기별 아카이브: {qa_path}")
                output_lines.append(f'  - Grep "error_patterns_aggregated" {qa_path} → 장기 에러 추세')

        if os.path.isdir(sessions_dir):
            output_lines.append(f"■ 세션 아카이브: {sessions_dir}")

    # Autopilot Mode context injection (conditional)
    # Uses project_dir passed from main() — NOT derived from snapshot path
    # (path derivation fails when best_path points to sessions/ subdirectory)
    if project_dir:
        try:
            ap_state = read_autopilot_state(project_dir)
            if ap_state:
                output_lines.append("")
                output_lines.append("━━━ AUTOPILOT MODE ACTIVE ━━━")
                wf_name = ap_state.get("workflow_name", "N/A")
                cur_step = ap_state.get("current_step", "?")
                approved = ap_state.get("auto_approved_steps", [])
                output_lines.append(f"워크플로우: {wf_name}")
                output_lines.append(f"현재 단계: Step {cur_step}")
                if approved:
                    output_lines.append(f"자동 승인된 단계: {approved}")
                output_lines.append("")
                output_lines.append("■ AUTOPILOT EXECUTION RULES (MANDATORY):")
                output_lines.append("  1. EVERY step must be FULLY executed — NO step skipping")
                output_lines.append("  2. EVERY output must be COMPLETE — NO abbreviation")
                output_lines.append("  3. (human) steps: auto-approve with QUALITY-MAXIMIZING default")
                output_lines.append("  4. (hook) exit code 2: STILL BLOCKS — autopilot does NOT override")
                output_lines.append("  5. BEFORE advancing: verify output EXISTS + NON-EMPTY → record in SOT")
                output_lines.append("  6. (human) step 완료 시: autopilot-logs/step-N-decision.md 생성")

                # SOT schema validation (P1 — structural integrity)
                schema_warnings = validate_sot_schema(ap_state)
                if schema_warnings:
                    output_lines.append("")
                    output_lines.append("■ SOT SCHEMA VALIDATION:")
                    for warning in schema_warnings:
                        output_lines.append(f"  [WARN] {warning}")

                # Previous step output validation
                outputs = ap_state.get("outputs", {})
                if outputs:
                    output_lines.append("")
                    output_lines.append("■ PREVIOUS STEP OUTPUT VALIDATION:")
                    for step_key in sorted(outputs.keys(), key=lambda k: int(k.replace("step-", "")) if k.startswith("step-") and k.replace("step-", "").isdigit() else 0):
                        step_num = int(step_key.replace("step-", "")) if step_key.startswith("step-") and step_key.replace("step-", "").isdigit() else 0
                        if step_num > 0:
                            is_valid, reason = validate_step_output(
                                project_dir, step_num, outputs
                            )
                            mark = "[OK]" if is_valid else "[FAIL]"
                            output_lines.append(f"  {mark} {reason}")
        except Exception:
            pass  # Non-blocking — autopilot injection is supplementary

    # ULW (Ultrawork) Mode context injection (conditional)
    # Detects from snapshot content — transcript not available at SessionStart
    # "startup" excluded: ULW deactivates implicitly in new sessions (design decision)
    # Only inject for clear/compact/resume where the same logical session continues
    if (snapshot_content
            and source != "startup"
            and ("ULW 상태" in snapshot_content or "Ultrawork Mode State" in snapshot_content)):
        output_lines.append("")
        output_lines.append("━━━ ULTRAWORK (ULW) MODE ACTIVE ━━━")
        output_lines.append("")
        output_lines.append("■ ULW INTENSIFIERS (MANDATORY — thoroughness overlay):")
        output_lines.append("  1. Sisyphus Persistence — 최대 3회 재시도, 각 시도는 다른 접근법. 100% 완료 또는 불가 사유 보고")
        output_lines.append("  2. Mandatory Task Decomposition — 요청을 TaskCreate로 분해, TaskUpdate로 추적, TaskList로 검증")
        output_lines.append("  3. Bounded Retry Escalation — 동일 대상 3회 초과 재시도 금지(품질 게이트는 별도 예산 적용), 초과 시 사용자 에스컬레이션")

        # Detect Autopilot combination state
        ap_state = read_autopilot_state(project_dir)
        if ap_state:
            output_lines.append("")
            output_lines.append("■ ULW + AUTOPILOT COMBINED: 품질 게이트 재시도 한도 10→15회 상향")

    # Predictive Debugging: Surface high-risk files
    if risk_data and isinstance(risk_data, dict):
        top_risk = risk_data.get("top_risk_files", [])
        files_map = risk_data.get("files", {})
        data_sessions = risk_data.get("data_sessions", 0)
        if top_risk and data_sessions >= 5:
            output_lines.append("")
            output_lines.append("■ PREDICTIVE DEBUGGING — 고위험 파일 (과거 에러 이력 기반):")
            for rf in top_risk[:5]:
                fdata = files_map.get(rf, {})
                score = fdata.get("risk_score", 0)
                ec = fdata.get("error_count", 0)
                types = fdata.get("error_types", {})
                types_str = ", ".join(
                    f"{k}:{v}" for k, v in sorted(
                        types.items(), key=lambda x: x[1], reverse=True
                    )[:3]
                )
                rr = fdata.get("resolution_rate", 0)
                output_lines.append(
                    f"  ⚠ {rf} — score:{score:.1f}, errors:{ec} ({types_str}), "
                    f"resolution:{rr:.0%}"
                )

    # Phase 1-A: Thesis continuity markers (pending gates + blocked steps)
    thesis_continuity = _extract_thesis_continuity(project_dir)
    if thesis_continuity:
        output_lines.append("")
        output_lines.append("■ THESIS CONTINUITY:")
        pg = thesis_continuity.get("pending_gates", [])
        if pg:
            output_lines.append(f"  Pending gates: {', '.join(pg)}")
        bs = thesis_continuity.get("blocked_steps", [])
        if bs:
            output_lines.append(f"  Blocked steps: {', '.join(bs)}")

    # Phase 1-C: Quality gate trend (pass/fail history from knowledge-index)
    if os.path.exists(ki_path) if has_archive else False:
        gate_trend = _get_quality_gate_trend(ki_path)
        if gate_trend:
            output_lines.append("")
            output_lines.append(f"■ Quality Gate Trend: {gate_trend}")

    # MEMORY.md Health Check (deterministic — P1 compliant)
    memory_warnings = _check_memory_health(project_dir)
    if memory_warnings:
        output_lines.append("")
        output_lines.append("■ MEMORY.md 건강 검진:")
        for mw in memory_warnings:
            output_lines.append(f"  ⚠ {mw}")

    # Today/Yesterday Session Summary (deterministic — P1 compliant)
    if os.path.exists(ki_path) if has_archive else False:
        day_summary = _get_today_yesterday_summary(ki_path)
        if day_summary:
            output_lines.append("")
            for ds in day_summary:
                output_lines.append(f"■ {ds}")

    # Instruction for Claude
    output_lines.extend([
        "",
        "⚠️ 작업을 계속하기 전에 반드시 위 파일을 Read tool로 읽어",
        "   이전 세션의 전체 맥락을 복원하세요.",
    ])

    return "\n".join(output_lines)


def _get_recent_sessions(ki_path, n=3):
    """Read last N entries from knowledge-index.jsonl.

    Deterministic: reads file, parses JSON lines, returns last N.
    Non-blocking: returns empty list on any error.
    """
    try:
        entries = []
        with open(ki_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries[-n:] if entries else []
    except Exception:
        return []


def _extract_recent_error_resolutions(recent_sessions):
    """P1-1: Extract error→resolution pairs from recent Knowledge Archive sessions.

    Proactively surfaces past error patterns and their resolutions at
    SessionStart, eliminating the need for manual Grep queries.

    P1 Compliance: Deterministic extraction from structured JSON data.
    Returns: list of human-readable strings (max 3).
    """
    results = []
    for session in reversed(recent_sessions):
        error_patterns = session.get("error_patterns", [])
        if not isinstance(error_patterns, list):
            continue
        for ep in error_patterns:
            if not isinstance(ep, dict):
                continue
            etype = ep.get("type", "unknown")
            tool = ep.get("tool", "?")
            efile = ep.get("file", "")
            resolution = ep.get("resolution")
            if isinstance(resolution, dict) and resolution:
                res_tool = resolution.get("tool", "?")
                res_file = resolution.get("file", "")
                loc = f" in {efile}" if efile else ""
                res_loc = f" on {res_file}" if res_file else ""
                results.append(
                    f"{etype}{loc} ({tool}) → 해결: {res_tool}{res_loc}"
                )
            elif etype != "unknown":
                loc = f" in {efile}" if efile else ""
                results.append(
                    f"{etype}{loc} ({tool}) → 해결: 미확인"
                )
        if len(results) >= 3:
            break
    return results[:3]


def _extract_recent_diagnosis_patterns(recent_sessions):
    """P1-2: Extract diagnosis patterns from recent Knowledge Archive sessions.

    Proactively surfaces past diagnosis history (step, gate, hypothesis) at
    SessionStart, enabling cross-session learning for retry quality improvement.
    Symmetric with _extract_recent_error_resolutions (P1-1).

    P1 Compliance: Deterministic extraction from structured JSON data.
    Returns: list of human-readable strings (max 3).
    """
    results = []
    for session in reversed(recent_sessions):
        diagnosis_patterns = session.get("diagnosis_patterns", [])
        if not isinstance(diagnosis_patterns, list):
            continue
        for dp in diagnosis_patterns:
            if not isinstance(dp, dict):
                continue
            step = dp.get("step")
            gate = dp.get("gate", "?")
            hyp = dp.get("selected_hypothesis", "?")
            ev_count = dp.get("evidence_count", 0)
            step_str = f"Step {step}" if step else "Step ?"
            results.append(
                f"{step_str} {gate} → {hyp} (evidence: {ev_count}건)"
            )
        if len(results) >= 3:
            break
    return results[:3]


def _extract_recent_team_summaries(recent_sessions):
    """P1-3: Extract team coordination history from recent Knowledge Archive sessions.

    Proactively surfaces past team execution patterns at SessionStart,
    enabling continuity of team coordination across context resets.
    Symmetric with _extract_recent_error_resolutions (P1-1).

    P1 Compliance: Deterministic extraction from structured JSON data.
    Returns: list of human-readable strings (max 3).
    """
    results = []
    for session in reversed(recent_sessions):
        team_summaries = session.get("team_summaries", [])
        if not isinstance(team_summaries, list):
            continue
        for ts in team_summaries:
            if isinstance(ts, dict):
                team = ts.get("team", "?")
                status = ts.get("status", "?")
                agents = ts.get("agents", [])
                agent_str = ", ".join(agents[:3]) if isinstance(agents, list) else str(agents)
                results.append(f"{team} ({status}) — {agent_str}")
            elif isinstance(ts, str):
                results.append(ts[:80])
        if len(results) >= 3:
            break
    return results[:3]


def parse_snapshot_sections(md_text):
    """P1-RLM: Parse snapshot into sections using SECTION markers.

    Splits a snapshot markdown string at <!-- SECTION:name --> boundaries,
    returning a dict mapping section names to their content.

    If no markers are found (pre-P1 snapshot), returns {"_full": md_text}.
    Non-blocking: returns partial results on any parse error.

    P1 Compliance: Deterministic string splitting.
    """
    marker_pattern = _SECTION_MARKER_RE

    sections = {}
    current_name = "_preamble"
    current_lines = []

    for line in md_text.split("\n"):
        match = marker_pattern.match(line.strip())
        if match:
            # Save previous section (even if empty)
            sections[current_name] = "\n".join(current_lines)
            current_name = match.group(1)
            current_lines = []
        else:
            current_lines.append(line)

    # Save last section
    sections[current_name] = "\n".join(current_lines)

    # If no markers found, return full text
    if len(sections) <= 1 and "_preamble" in sections:
        return {"_full": md_text}

    return sections


# IMMORTAL sections that should always be loaded during selective peek
IMMORTAL_SECTIONS = {
    "header", "task", "next_step", "sot", "autopilot",
    "quality_gate", "team", "ulw", "diagnosis", "decisions",
    "resume", "completion", "git",
}


def _retrieve_relevant_sessions(ki_path, task_info, file_paths, max_results=3):
    """P0-RLM: Active Knowledge Retrieval — relevance-scored session matching.

    Instead of showing only the N most recent sessions, this function scores
    ALL knowledge-index entries by relevance to the current session context
    (task description + modified files) and returns the top matches.

    Scoring heuristic (deterministic, P1 compliant):
      - Keyword overlap between current task and past user_task/last_instruction
      - File path overlap between current modified files and past modified_files
      - Tag overlap between current path_tags and past tags

    Returns: list of (score, session_dict) tuples, sorted by score desc.
    Non-blocking: returns empty list on any error.
    """
    if not os.path.exists(ki_path):
        return []

    try:
        all_sessions = []
        with open(ki_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        all_sessions.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        if not all_sessions:
            return []

        # Build current context keywords
        current_keywords = _tokenize(task_info)
        current_files = set(file_paths) if file_paths else set()
        current_file_basenames = {os.path.basename(f) for f in current_files if f}

        scored = []
        for session in all_sessions:
            score = 0.0

            # 1. Task keyword overlap (weight: 2.0 per match)
            past_task = session.get("user_task", "") or ""
            past_last = session.get("last_instruction", "") or ""
            past_keywords = _tokenize(past_task) | _tokenize(past_last)
            keyword_overlap = current_keywords & past_keywords
            score += len(keyword_overlap) * 2.0

            # 2. File path exact match (weight: 5.0 per match)
            past_files = session.get("modified_files", [])
            if isinstance(past_files, list):
                past_file_set = set(past_files)
                file_overlap = current_files & past_file_set
                score += len(file_overlap) * 5.0

                # 2b. Basename overlap (weight: 2.0) — catches path variations
                past_basenames = {os.path.basename(f) for f in past_files if f}
                basename_overlap = current_file_basenames & past_basenames
                score += len(basename_overlap - {os.path.basename(f) for f in file_overlap}) * 2.0

            # 3. Tag overlap (weight: 3.0 per match)
            past_tags = session.get("tags", [])
            if isinstance(past_tags, list) and current_files:
                current_tags = set(extract_path_tags(list(current_files)))
                tag_overlap = current_tags & set(past_tags)
                score += len(tag_overlap) * 3.0

            # 4. Error pattern type match (weight: 1.5) — same error types recur
            past_errors = session.get("error_patterns", [])
            if isinstance(past_errors, list) and past_errors:
                # M8: Proportional error pattern scoring (count-based + resolution bonus)
                resolved = sum(1 for e in past_errors if isinstance(e, dict) and e.get("resolution"))
                score += min(len(past_errors) * 0.3, 3.0)  # Count-based, capped at 3.0
                score += min(resolved * 0.5, 2.5)  # Resolution bonus, capped at 2.5

            if score > 0:
                scored.append((score, session))

        # Sort by score descending, take top N
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:max_results]
    except Exception:
        return []


def _extract_quarterly_insights(qa_path):
    """P3-RLM: Extract actionable insights from quarterly archive.

    Reads knowledge-archive-quarterly.jsonl and surfaces:
    - Top recurring error types across quarters
    - Persistent high-touch files (frequently modified)
    - Design decision continuity

    P1 Compliance: Deterministic aggregation from structured JSON data.
    Non-blocking: returns empty list on any error.
    Returns: list of human-readable insight strings.
    """
    if not os.path.exists(qa_path):
        return []

    try:
        quarters = []
        with open(qa_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        quarters.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        if not quarters:
            return []

        insights = []

        # 1. Aggregate error patterns across all quarters
        error_totals = {}
        total_sessions = 0
        for q in quarters:
            total_sessions += q.get("session_count", 0)
            for etype, count in q.get("error_patterns_aggregated", {}).items():
                error_totals[etype] = error_totals.get(etype, 0) + count

        if error_totals:
            top_errors = sorted(error_totals.items(), key=lambda x: x[1], reverse=True)[:3]
            error_str = ", ".join(f"{t}({c})" for t, c in top_errors)
            insights.append(f"반복 에러: {error_str} (총 {total_sessions} 세션)")

        # 2. Top modified files across quarters
        file_totals = {}
        for q in quarters:
            for fpath, count in q.get("top_modified_files", {}).items():
                file_totals[fpath] = file_totals.get(fpath, 0) + count
        if file_totals:
            top_files = sorted(file_totals.items(), key=lambda x: x[1], reverse=True)[:3]
            for fpath, count in top_files:
                basename = os.path.basename(fpath)
                insights.append(f"고빈도 수정: {basename} ({count}회)")

        # 3. Design decision count
        total_decisions = sum(
            len(q.get("design_decisions", [])) for q in quarters
        )
        if total_decisions > 0:
            insights.append(f"누적 설계 결정: {total_decisions}개 ({len(quarters)}분기)")

        return insights
    except Exception:
        return []


def _find_best_snapshot(snapshot_dir, latest_path):
    """E6: Find the best available snapshot when latest.md is inadequate.

    Quality criterion: file size (more structured data = larger file).
    P1 Compliance: file size is a deterministic metric.

    Falls back to sessions/ archive if latest.md has < 3KB of content
    (indicating a likely empty or minimal snapshot).
    """
    MIN_QUALITY_SIZE = 3000  # bytes

    latest_size = 0
    try:
        if os.path.exists(latest_path):
            latest_size = os.path.getsize(latest_path)
    except OSError:
        pass

    if latest_size >= MIN_QUALITY_SIZE:
        return latest_path, latest_size  # Sufficient quality

    # Scan sessions/ for a better recent archive
    sessions_dir = os.path.join(snapshot_dir, "sessions")
    if not os.path.isdir(sessions_dir):
        return latest_path, latest_size

    best_path = latest_path
    best_size = latest_size

    try:
        for fname in os.listdir(sessions_dir):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(sessions_dir, fname)
            fsize = os.path.getsize(fpath)
            fmtime = os.path.getmtime(fpath)

            # Only consider archives from the last hour, larger than current best
            if (time.time() - fmtime) < 3600 and fsize > best_size:
                best_path = fpath
                best_size = fsize
    except Exception:
        pass

    return best_path, best_size


def _format_age(seconds):
    """Format age in seconds to human-readable string."""
    if seconds < 60:
        return f"{int(seconds)}초"
    elif seconds < 3600:
        return f"{int(seconds / 60)}분"
    elif seconds < 86400:
        return f"{int(seconds / 3600)}시간"
    else:
        return f"{int(seconds / 86400)}일"


def _generate_risk_scores_cache(project_dir, snapshot_dir):
    """Generate risk-scores.json cache for PreToolUse hook.

    Called once per SessionStart. Writes cache to context-snapshots/.
    Non-blocking: returns empty dict on any error.

    P1 Compliance: Delegates to aggregate_risk_scores() which is
    deterministic arithmetic. Cache write uses atomic_write().
    """
    try:
        ki_path = os.path.join(snapshot_dir, "knowledge-index.jsonl")
        risk_data = aggregate_risk_scores(ki_path, project_dir)

        # Write cache for predictive_debug_guard.py
        cache_path = os.path.join(snapshot_dir, "risk-scores.json")
        cache_json = json.dumps(risk_data, ensure_ascii=False, indent=2)
        atomic_write(cache_path, cache_json)

        return risk_data
    except Exception:
        return {}


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Non-blocking: log error but don't crash the hook
        print(f"restore_context error: {e}", file=sys.stderr)
        sys.exit(0)
