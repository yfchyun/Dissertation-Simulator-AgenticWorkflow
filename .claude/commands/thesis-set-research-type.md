---
description: Set the research type (quantitative/qualitative/mixed) for the thesis workflow (HITL-3). Determines which Phase 2 agents are activated.
---

# Set Research Type (HITL-3)

Human-in-the-loop checkpoint for research type confirmation.

## Protocol

### Step 1: Present Options
Based on literature review findings, present research type recommendation:
- **Quantitative**: hypothesis-developer, research-model-developer, sampling-designer, statistical-planner
- **Qualitative**: paradigm-consultant, participant-selector, qualitative-data-designer, qualitative-analysis-planner
- **Mixed Methods**: mixed-methods-designer, integration-strategist + relevant agents from both tracks

### Step 2: User Selection
User confirms or overrides the recommended research type.

### Step 3: Update SOT
Record research type in SOT `research_type` field.
Activate the corresponding Phase 2 agent set.

### Step 4: Record HITL-3
```bash
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/checklist_manager.py \
  --project-dir "$CLAUDE_PROJECT_DIR/thesis-output/{project}" \
  --record-hitl hitl-3 --status completed
```

### Step 5: Save Checkpoint
```bash
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/checklist_manager.py \
  --save-checkpoint --checkpoint hitl-3-research-type \
  --project-dir "$CLAUDE_PROJECT_DIR/thesis-output/{project}"
```
