---
description: Resume thesis workflow after context reset. Loads checkpoint and restores state from session.json, checklist, and research synthesis.
---

# Thesis Resume

Recover thesis workflow state after context loss (compact/clear/new session).

## Protocol

### Step 1: Find Active Project

```bash
ls thesis-output/
```

If multiple projects exist, ask user which to resume.

### Step 2: Read Recovery Files

Read these files in order (Context Reset Model from workflow.md):

1. `thesis-output/{project}/session.json` — Current SOT state
2. `thesis-output/{project}/todo-checklist.md` — Step completion status
3. `thesis-output/{project}/research-synthesis.md` — Accumulated insights

### Step 3: Determine Resume Point

Based on SOT current_step, identify:
- Which phase we're in
- What was the last completed step
- What is the next step to execute
- Whether any gate is pending

### Step 3.5: Check for Mid-Consolidation State

Use the P1 deterministic helper to compute the next execution step — handles consolidation
restart logic automatically (no manual math required):

```bash
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/query_step.py \
  --next-step --project-dir "$CLAUDE_PROJECT_DIR/thesis-output/{project}" --json
```

Output includes `next_step`, `reason` ("normal" or "restart_consolidated_group"), and
`consolidated_group` (list of step numbers if applicable). If `reason` is
"restart_consolidated_group", the entire group must be re-executed from `next_step`.
This is also surfaced by `restore_context.py` in the IMMORTAL section.

### Step 4: Restore Checkpoint (if available)

```bash
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/checklist_manager.py \
  --status \
  --project-dir "$CLAUDE_PROJECT_DIR/thesis-output/{project}"
```

### Step 5: Report Recovery (Korean)

Display:
- Recovered project name and state
- Current position in workflow
- Last completed step
- **Execution mode** (from SOT `execution_mode` field)
- Next action
- Any pending gates or HITL checkpoints

### Step 6: Re-activate Execution Mode

Read `execution_mode` from SOT and re-activate the corresponding behavior per thesis-orchestrator's "Execution Mode Activation" table. This ensures Autopilot/ULW survive context resets.

### Step 7: Continue Execution

Proceed with the next step following thesis-orchestrator protocol.
