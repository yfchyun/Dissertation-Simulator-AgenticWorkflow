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

### Step 3: Execute

Follow the thesis-orchestrator agent's execution protocol:
1. Create appropriate Agent Team or call sub-agent
2. Execute the step in English
3. Validate output (L0 Anti-Skip)
4. Call @translator for Korean pair
5. Record in SOT
6. Advance to next step

### Step 4: Report Progress (Korean)

After each step completion, show:
- Completed step description
- Current progress (step/total, percentage)
- Next step preview
- Any quality gate results
