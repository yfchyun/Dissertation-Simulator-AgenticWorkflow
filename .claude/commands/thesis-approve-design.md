---
description: Approve the research design (HITL-4). Review methodology, sampling, instruments, and analysis plan before proceeding to Writing phase.
---

# Approve Research Design (HITL-4)

Human-in-the-loop checkpoint for research design approval.

## Protocol

### Step 1: Load Design Outputs
Read Phase 2 outputs from `thesis-output/{project}/wave-results/`.

### Step 2: Present Design Summary
Display to user:
- Research methodology and justification
- Sampling strategy and sample size calculations
- Data collection instruments and protocols
- Analysis plan (statistical or qualitative)
- Ethical considerations
- Limitations identified

### Step 3: User Decision
Ask user to:
1. **Approve** — proceed to Writing phase
2. **Revise** — specify design elements needing modification
3. **Change type** — switch research type (returns to HITL-3)

### Step 4: Record HITL-4
```bash
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/checklist_manager.py \
  --project-dir "$CLAUDE_PROJECT_DIR/thesis-output/{project}" \
  --record-hitl hitl-4 --status completed
```

### Step 5: Save Checkpoint
```bash
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/checklist_manager.py \
  --save-checkpoint --checkpoint hitl-4-research-design \
  --project-dir "$CLAUDE_PROJECT_DIR/thesis-output/{project}"
```
