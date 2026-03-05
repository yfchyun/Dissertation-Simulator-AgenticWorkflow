---
description: Approve the thesis outline (HITL-6). Review chapter structure, argumentation flow, and section assignments before full writing.
---

# Approve Outline (HITL-6)

Human-in-the-loop checkpoint for thesis outline approval.

## Protocol

### Step 1: Load Outline
Read thesis outline from @thesis-architect output.

### Step 2: Present Outline
Display to user:
- Full chapter/section hierarchy with estimated word counts
- Argumentation flow diagram
- Key claims mapped to supporting evidence
- Section-to-literature mapping

### Step 3: User Decision
Ask user to:
1. **Approve** — proceed to full thesis writing
2. **Revise** — specify structural changes
3. **Restructure** — request alternative outline from @thesis-architect

### Step 4: Record HITL-6
```bash
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/checklist_manager.py \
  --project-dir "$CLAUDE_PROJECT_DIR/thesis-output/{project}" \
  --record-hitl hitl-6 --status completed
```

### Step 5: Save Checkpoint
```bash
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/checklist_manager.py \
  --save-checkpoint --checkpoint hitl-6-outline \
  --project-dir "$CLAUDE_PROJECT_DIR/thesis-output/{project}"
```
