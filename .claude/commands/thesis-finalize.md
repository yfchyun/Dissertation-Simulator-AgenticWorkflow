---
description: Finalize the thesis (HITL-8). Final review, quality certification, and workflow completion.
---

# Finalize (HITL-8)

Human-in-the-loop checkpoint for thesis completion.

## Protocol

### Step 1: Final Quality Check
Run comprehensive quality assessment:
- Full SRCS evaluation on all claims
- Final plagiarism check
- Citation completeness (bidirectional)
- Formatting compliance verification
- GRA grounding rate calculation

### Step 2: Present Final Report
Display to user:
- Overall quality metrics
- Publication readiness assessment
- Remaining issues (if any)
- Complete output file inventory

### Step 3: User Decision
Ask user to:
1. **Complete** — mark workflow as finished
2. **Revise** — return to specific phase for corrections
3. **Proceed to Publication** — activate Phase 4 agents

### Step 4: Record HITL-8
```bash
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/checklist_manager.py \
  --project-dir "$CLAUDE_PROJECT_DIR/thesis-output/{project}" \
  --record-hitl hitl-8 --status completed
```

### Step 5: Save Final Checkpoint
```bash
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/checklist_manager.py \
  --save-checkpoint --checkpoint hitl-8-finalize \
  --project-dir "$CLAUDE_PROJECT_DIR/thesis-output/{project}"
```
