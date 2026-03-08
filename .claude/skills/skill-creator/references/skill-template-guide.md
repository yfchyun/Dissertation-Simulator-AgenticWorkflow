# Skill Template Guide

Reference document for skill-creator. Provides structural templates and
conventions for generating new Claude Code skills.

## SKILL.md Frontmatter Schema

```yaml
---
name: string          # kebab-case identifier (e.g., "data-analyzer")
description: string   # Korean description for skill matching
---
```

The `description` field is used by Claude Code's skill matching system.
Include trigger phrases in Korean that users might say.

## Required Sections

### 1. Inherited DNA

Every skill must declare which genome components from soul.md it inherits:

| Component | Required? | Notes |
|-----------|-----------|-------|
| Absolute Criteria | YES | Must be contextualized, not copy-pasted |
| SOT Pattern | If stateful | Only if the skill manages persistent state |
| 3-Stage Structure | YES | Research → Planning → Implementation |
| Quality Gates | YES | At minimum L0 + L1 |
| P1 Enforcement | If applicable | Deterministic tasks need Python validation |
| Safety Hooks | If applicable | When skill performs risky operations |

### 2. Protocol Steps

Steps should be:
- **Numbered sequentially** (Step 1, Step 2, ...)
- **Imperative** ("Analyze the input" not "The input is analyzed")
- **Concrete** (specify file paths, tool names, output formats)
- **English** (internal instructions for AI performance)

### 3. Quality Gates

Define at minimum:
- **L0 (Anti-Skip)**: File exists + non-empty + minimum size
- **L1 (Verification)**: Domain-specific validation criteria

Optional:
- **L1.5 (pACS)**: Self-assessment scoring
- **L2 (Adversarial Review)**: Independent critic agent — `Review:` field in workflow step
  - Research domain: `@fact-checker` + `@reviewer` (parallel)
  - Development domain: `@code-reviewer`
  - On Review FAIL: triggers **Adversarial Dialogue** (Generator-Critic iteration loop)
  - `Dialogue:` field sets domain + max_rounds; P1 validators: DA1-DA5, CI1-CI4

### 4. References Directory

```
references/
├── {domain}-guide.md       # Domain expertise
├── {domain}-checklist.md   # Quality verification items
└── {domain}-examples.md    # Concrete examples (optional)
```

## Anti-Patterns to Avoid

1. **Placeholder content**: "TBD", "TODO", "[fill in later]"
2. **Copy-paste DNA**: Don't just paste soul.md — contextualize for the domain
3. **Missing P1 boundary**: If a task is deterministic, it MUST have Python enforcement
4. **Overly generic steps**: "Do the analysis" — specify what analysis, with what tool
5. **No quality gates**: Every skill must define success criteria

## Example Skills in This Project

| Skill | Domain | Key Pattern |
|-------|--------|-------------|
| `workflow-generator` | Workflow design | Interview → Design → Generate |
| `doctoral-writing` | Academic writing | Style analysis → Transformation → Review |
