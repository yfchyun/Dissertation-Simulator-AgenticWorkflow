---
description: Save or restore a thesis workflow checkpoint for context recovery.
---

# Thesis Checkpoint

Save the current state or restore from a previous checkpoint.

## Usage
- Save: `/thesis:checkpoint save {name}` — Save current state
- Restore: `/thesis:checkpoint restore {name}` — Restore from checkpoint
- List: `/thesis:checkpoint list` — Show available checkpoints

## Protocol

### Save
```bash
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/checklist_manager.py \
  --save-checkpoint --project-dir "$CLAUDE_PROJECT_DIR/thesis-output/{project}" \
  --checkpoint {name}
```

### Restore
```bash
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/checklist_manager.py \
  --restore-checkpoint --project-dir "$CLAUDE_PROJECT_DIR/thesis-output/{project}" \
  --checkpoint {name}
```

### List
```bash
ls "$CLAUDE_PROJECT_DIR/thesis-output/{project}/checkpoints/"
```
