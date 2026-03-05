# Agent Template Guide

Reference document for subagent-creator. Provides templates and conventions
for generating Claude Code agent definition files.

## Frontmatter Reference

```yaml
---
name: string              # kebab-case, matches filename
description: string       # English, concise
model: opus|sonnet|haiku  # Model selection
tools: string             # Comma-separated tool names
maxTurns: integer         # Default: 20, range: 5-50
memory: project|none      # project = cross-session memory
---
```

## Agent Body Structure

### Research Agent Template

```markdown
You are a {role} specializing in {domain}. You produce rigorous,
evidence-based analysis following GRA (Grounded Research Architecture)
standards.

## Core Task

{Detailed description of what this agent does}

## Protocol

### Step 1: {Action}
{Specific instructions}

### Step 2: {Action}
{Specific instructions}

## Output Format

Write your analysis to `{output-path}` with this structure:
- **Section 1**: {description}
- **Section 2**: {description}
- **Claims**: All claims in GroundedClaim format

## GRA Compliance

### Claim Prefix: {PREFIX}
### GroundedClaim Schema
{Schema details}

### Hallucination Firewall
{BLOCK/REQUIRE_SOURCE/SOFTEN/VERIFY rules}

## Quality Criteria
- {Criterion 1}
- {Criterion 2}
```

### Utility Agent Template

```markdown
You are a {role} specializing in {domain}.

## Core Task

{Detailed description}

## Protocol

### Step 1: {Action}
{Instructions}

## Output Format

{Specification}

## Quality Criteria
- {Criterion 1}
- {Criterion 2}
```

## Existing Agents in This Project

| Agent | Type | Model | Purpose |
|-------|------|-------|---------|
| `translator` | Utility | opus | English-to-Korean translation |
| `reviewer` | Quality | opus | Adversarial code/output review |
| `fact-checker` | Quality | opus | Independent fact verification |

## Claim Prefix Registry

When creating GRA-compliant research agents, each must have a unique
claim prefix. Current allocations:

| Prefix | Agent |
|--------|-------|
| LS | literature-searcher |
| SWA | seminal-works-analyst |
| TRA | trend-analyst |
| MS | methodology-scanner |
| TFA | theoretical-framework-analyst |
| EEA | empirical-evidence-analyst |
| GI | gap-identifier |
| VRA | variable-relationship-analyst |
| CR | critical-reviewer |
| MC | methodology-critic |
| LA | limitation-analyst |
| FDA | future-direction-analyst |
| SA | synthesis-agent |
| CMB | conceptual-model-builder |
| PC | plagiarism-checker |

## Common Mistakes

1. **Too many tools**: Only grant tools the agent actually needs
2. **Vague instructions**: "Analyze the data" → specify what analysis, what output
3. **Missing output format**: Agent must know exactly what file to create
4. **No GRA section for research agents**: All research agents need GroundedClaim
5. **Duplicate claim prefixes**: Each agent must have a unique prefix
6. **Korean instructions**: Internal instructions should be in English
