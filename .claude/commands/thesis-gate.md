---
description: Run or check a Cross-Validation Gate for the current thesis workflow phase. Validates wave outputs and records results.
---

# Thesis Gate

Execute a Cross-Validation Gate to validate wave outputs before proceeding.

## Protocol

### Step 1: Identify Gate
Read SOT to determine which gate is next based on current_step.

### Step 2: Run Gate Validation
```bash
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/validate_wave_gate.py \
  --project-dir "$CLAUDE_PROJECT_DIR/thesis-output/{project}" \
  --gate {gate-name}
```

### Step 3: Record Result
```bash
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/checklist_manager.py \
  --project-dir "$CLAUDE_PROJECT_DIR/thesis-output/{project}" \
  # Record gate pass/fail via Python API
```

### Step 4: Report (Korean)
- If PASS: Display success, proceed to next wave
- If FAIL: Display failing criteria, suggest remediation
