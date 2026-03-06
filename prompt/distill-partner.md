# Distill Partner Guide

Reference guide for workflow-generator SKILL.md Step 13 (Distill Validation).

## W1-W9 Validation Codes

| Code | Check | Description |
|------|-------|-------------|
| W1 | Header | Workflow frontmatter contains required fields (name, version, description) |
| W2 | Patterns | At least 1 Claude Code pattern used (Sub-agent, Team, Hook, etc.) |
| W3 | Principles | Absolute Criteria 1-3 referenced or contextualized |
| W4 | CAP | Coding Anchor Points (CAP-1~4) present in implementation steps |
| W5 | SOT | Single-file SOT pattern defined with team write control |
| W6 | Quality | Quality gates (L0-L2) referenced for verification steps |
| W7 | Safety | Safety hooks referenced (block_destructive_commands, output_secret_filter) |
| W8 | Traceability | Cross-step traceability markers present (CT1-CT5 compatible) |
| W9 | English-First | Workflow execution steps are in English |

## Usage

```bash
python3 .claude/hooks/scripts/validate_workflow.py --workflow-path ./workflow.md
```

## Interpreting Results

The validator outputs JSON with `valid` (boolean) and `warnings` (list of failed checks with W-code prefixes). Each warning includes the specific code and description. Use `remediations` field for fix instructions.
