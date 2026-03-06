---
name: skill-creator
description: Meta-skill that generates new Claude Code skills. Given a domain description, it creates a complete SKILL.md + references/ structure following AgenticWorkflow conventions. Use when asked to "create a skill", "make a new skill", or "generate skill for X".
---

# Skill Creator — Meta-Skill for Generating Claude Code Skills

A meta-skill that produces new skill packages. It analyzes the target domain,
designs the skill structure, and generates all required files following
AgenticWorkflow's DNA inheritance patterns.

## When to Use

- User asks to create a new skill for a specific domain
- User wants to automate a repeatable workflow as a skill
- System needs to generate skills for thesis workflow agents

## Inherited DNA

This meta-skill inherits the AgenticWorkflow genome. As a skill that generates other skills, it must itself embody the DNA it enforces.

| DNA Component | Expression in skill-creator |
|--------------|---------------------------|
| Absolute Criteria 1 (Quality) | Generated skills are evaluated solely on output quality, not speed or token cost |
| Absolute Criteria 2 (SOT) | Generated skills must define their SOT pattern; skill-creator validates this |
| Absolute Criteria 3 (CCP) | Generated skills include CCP contextualization; CAP-1~4 anchored to domain |
| English-First | All generated skill instructions are in English; user-facing triggers may be bilingual |
| P1 Compliance | Generated skills must include deterministic validation scripts |
| Quality Gates | Generated skills reference L0-L2 quality layers appropriate to their domain |

## Generation Protocol

### Step 1: Domain Analysis

Analyze the target domain:
1. What is the primary output of this skill?
2. What inputs does it require?
3. What quality criteria apply?
4. Which tasks are deterministic (P1) vs. semantic (LLM)?

Ask the user a maximum of 4 questions (P4 rule), each with up to 3 choices.
If the domain is clear enough, proceed without questions.

### Step 2: Skill Architecture Design

Design the skill structure:

```
.claude/skills/{skill-name}/
├── SKILL.md              ← Main skill file (WHY + HOW)
└── references/           ← Supporting documents (WHAT/VERIFY)
    ├── {domain}-guide.md      ← Domain-specific guidance
    ├── {domain}-checklist.md  ← Quality checklist
    └── {domain}-examples.md   ← Before/after examples (if applicable)
```

### Step 3: Generate SKILL.md

The generated SKILL.md must follow this template:

```markdown
---
name: {skill-name}
description: {one-line description for skill matching}
---

# {Skill Title}

{Brief description of what the skill does.}

## Inherited DNA
{Absolute criteria contextualized for this domain}

## Protocol
{Step-by-step execution protocol}

## Quality Gates
{Domain-specific quality criteria}

## P1 Enforcement
{List of deterministic validations, if any}
```

### Step 4: Generate Reference Files

Create supporting documents in `references/`:
- **Domain guide**: Detailed domain knowledge and best practices
- **Checklist**: Verification items for quality assurance
- **Examples**: Concrete examples of good/bad outputs (when applicable)

### Step 5: Validate Generated Skill

Verify the generated skill:
- [ ] SKILL.md has valid frontmatter (name, description)
- [ ] Inherited DNA section present with all applicable genome components
- [ ] Protocol has clear, numbered steps
- [ ] Quality gates defined
- [ ] References directory populated
- [ ] No hardcoded paths (uses relative references)
- [ ] Language: internal instructions in English, user-facing in Korean

### Step 6: Register Skill

Inform the user:
1. Skill location: `.claude/skills/{skill-name}/`
2. How to trigger it (matching patterns from description)
3. Any required setup (dependencies, configuration)

## Language Rules

- **SKILL.md internal instructions**: English (for AI performance)
- **SKILL.md description (frontmatter)**: Korean (for user-facing matching)
- **Reference files**: English (domain knowledge for AI consumption)
- **Generated output for users**: Korean (user-facing reports)

## Quality Checklist

- [ ] Generated skill follows AgenticWorkflow conventions
- [ ] DNA inheritance is complete (not just referenced)
- [ ] Steps are concrete and actionable
- [ ] P1 tasks identified and separated from LLM tasks
- [ ] No placeholder content — all sections are substantive
