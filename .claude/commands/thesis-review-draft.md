---
description: Review the thesis draft (HITL-7). Present draft for human review with quality metrics, plagiarism check, and revision suggestions.
---

# Review Draft (HITL-7)

Human-in-the-loop checkpoint for thesis draft review.

## Protocol

### Step 1: Load Draft
Read thesis draft chapters from @thesis-writer output.

### Step 2: Present Quality Report
Display to user:
- Chapter completion status and word counts
- SRCS quality scores per chapter
- Plagiarism check results (@plagiarism-checker)
- @thesis-reviewer feedback summary
- Citation completeness verification

### Step 3: User Decision
Ask user to:
1. **Approve** — proceed to final revision and formatting
2. **Revise** — specify chapters/sections needing revision
3. **Rewrite** — request full rewrite of specific sections

### Step 4: Record HITL-7
```bash
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/checklist_manager.py \
  --project-dir "$CLAUDE_PROJECT_DIR/thesis-output/{project}" \
  --record-hitl hitl-7 --status completed
```

### Step 5: Save Checkpoint
```bash
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/checklist_manager.py \
  --save-checkpoint --checkpoint hitl-7-draft-review \
  --project-dir "$CLAUDE_PROJECT_DIR/thesis-output/{project}"
```
