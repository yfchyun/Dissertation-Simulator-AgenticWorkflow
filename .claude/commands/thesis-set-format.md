---
description: Set thesis format and citation style (HITL-5). Configure APA/MLA/Chicago, institutional requirements, and document structure.
---

# Set Format (HITL-5)

Human-in-the-loop checkpoint for format configuration.

## Protocol

### Step 1: Present Format Options
- **Citation Style**: APA 7th (default) / MLA 9th / Chicago-Turabian
- **Document Format**: Institutional template / Standard academic
- **Language**: English (default) / Korean / Bilingual
- **Heading Style**: Numbered / Unnumbered
- **Reference Manager**: Manual / Zotero / Mendeley / EndNote

### Step 2: User Selection
User confirms format preferences.

### Step 3: Update SOT
Record format settings in SOT `format_settings` field.

### Step 4: Record HITL-5
```bash
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/checklist_manager.py \
  --project-dir "$CLAUDE_PROJECT_DIR/thesis-output/{project}" \
  --record-hitl hitl-5 --status completed
```

### Step 5: Save Checkpoint
```bash
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/checklist_manager.py \
  --save-checkpoint --checkpoint hitl-5-format \
  --project-dir "$CLAUDE_PROJECT_DIR/thesis-output/{project}"
```
