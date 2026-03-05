---
description: Review literature analysis results (HITL-2). Present synthesis, identify gaps, and get human approval before proceeding to Research Design.
---

# Review Literature (HITL-2)

Human-in-the-loop checkpoint for literature review approval.

## Protocol

### Step 1: Load Literature Outputs
Read all wave results (Wave 1-5) from `thesis-output/{project}/wave-results/`.

### Step 2: Present Synthesis
Display to user:
- Key findings summary (top 20 most cited papers)
- Theoretical framework candidates
- Research gaps identified
- Methodological patterns observed
- SRCS quality scores for all claims

### Step 3: User Decision
Ask user to:
1. **Approve** — proceed to Research Design phase
2. **Revise** — specify areas needing deeper analysis
3. **Restart** — redo specific waves with adjusted parameters

### Step 4: Record HITL-2
```bash
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/checklist_manager.py \
  --project-dir "$CLAUDE_PROJECT_DIR/thesis-output/{project}" \
  --record-hitl hitl-2 --status completed
```

### Step 5: Save Checkpoint
```bash
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/checklist_manager.py \
  --save-checkpoint --checkpoint hitl-2-literature-review \
  --project-dir "$CLAUDE_PROJECT_DIR/thesis-output/{project}"
```
