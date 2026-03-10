---
description: Start or continue the doctoral thesis research workflow. Reads SOT to determine current position and executes the next steps.
---

# Thesis Start / Continue

Resume or start the thesis workflow execution.

## Protocol

### Step 1: Read Current State

```bash
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/checklist_manager.py \
  --status \
  --project-dir "$CLAUDE_PROJECT_DIR/thesis-output/{project}"
```

If no project exists, redirect to `/thesis:init`.

### Step 2: Determine Next Action

Based on current_step and input_mode in SOT:

| Current Position | Action |
|-----------------|--------|
| Step 0 (fresh) | Begin Phase 0 initialization |
| Phase 0-A steps | Topic exploration with @topic-explorer |
| Phase 0-D steps | Learning mode with Agent Team |
| HITL-1 | Present research question candidates for user approval |
| Wave 1-5 steps | Literature review with Agent Teams |
| Gate steps | Run cross-validation gate |
| HITL-2+ | Present results for user review |
| Phase 2 steps | Research design with Agent Team |
| Phase 3 steps | Thesis writing with Agent Team |
| Phase 4 steps | Publication strategy |

### Step 3: Get Invocation Plan

Query the P1-computed invocation plan to determine remaining orchestrator invocations:

```bash
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/query_step.py \
  --invocation-plan --step {current_step} --project-dir "$CLAUDE_PROJECT_DIR/thesis-output/{project}"
```

Where `{current_step}` is the value obtained from Step 1's SOT status.

This returns a list of invocation blocks (17 total), each with `start`, `end`, `label`, and `status` (pending/in_progress/completed). Use this to determine which invocations remain.

### Step 4: Execute via Orchestrator Loop

For each **pending** or **in_progress** invocation block from the plan, invoke the thesis-orchestrator:

```
Agent: subagent_type="thesis-orchestrator", prompt="
  Project directory: thesis-output/{project}
  Current step: {current_step} (from SOT)
  Invocation: {invocation_number}/{total_invocations} — {label}
  Step range: {start}-{end}
  Execution mode: {execution_mode}
  Research topic: {research_question}

  Execute steps {start} through {end} following your Execution Protocol.
  Use step consolidation where query_step.py indicates (consolidate_with > 1 step).
  Report back: completed steps, outputs created, any gate results.
"
```

**After each orchestrator return:**
1. Re-read SOT to verify progress
2. Display countdown to user: `[{completed}/{total} invocations — {pct}%]`
3. If orchestrator did not reach the expected `end` step, re-invoke for the remaining range
4. Proceed to the next pending invocation block

**Do NOT perform orchestrator duties directly.** Always delegate to the thesis-orchestrator agent, which has the full tool set (TeamCreate, TaskCreate, SendMessage, TaskList, TaskUpdate) and execution protocol.

### Step 5: Report Progress (Korean)

After each orchestrator invocation, show:
- Completed step description
- Current progress (step/total, percentage)
- Next step preview
- Any quality gate results
