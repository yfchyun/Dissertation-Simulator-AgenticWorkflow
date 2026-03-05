---
name: subagent-creator
description: Meta-skill that generates Claude Code agent definition files (.md). Creates specialized agents with proper tool access, model selection, and behavioral instructions. Use when asked to "create an agent", "make a sub-agent", or "generate agent for X".
---

# Sub-Agent Creator — Meta-Skill for Generating Agent Definitions

A meta-skill that produces Claude Code agent `.md` files. It designs agents
with appropriate expertise, tool access, behavioral rules, and quality
requirements following AgenticWorkflow conventions.

## When to Use

- User asks to create a new agent for a specific task
- System needs to generate agents for a workflow (e.g., thesis agents)
- Batch creation of multiple related agents

## Agent File Schema

Agent definitions live in `.claude/agents/` and follow this structure:

```markdown
---
name: {agent-name}           # kebab-case
description: {brief description}
model: opus                   # opus | sonnet | haiku
tools: Read, Write, Glob, Grep  # comma-separated tool list
maxTurns: {N}                 # max reasoning turns (default: 20)
memory: project               # project | none
---

{Agent behavioral instructions in English}
```

## Generation Protocol

### Step 1: Agent Design Analysis

Determine the agent's requirements:

1. **Primary task**: What is the agent's core responsibility?
2. **Expertise domain**: What specialized knowledge does it need?
3. **Input/Output**: What does it receive and produce?
4. **Quality criteria**: What makes a good output for this agent?
5. **Tool needs**: Which tools does it require?

### Step 2: Model Selection

Select the appropriate model based on task complexity:

| Model | Use When | Examples |
|-------|----------|---------|
| `opus` | Complex analysis, synthesis, critical reasoning | Thesis writer, critical reviewer, synthesis agent |
| `sonnet` | Structured tasks, search, data processing | Literature searcher, formatting specialist |
| `haiku` | Simple, repetitive tasks | File validation, format checking |

**Default to `opus`** when quality is the absolute criterion (Absolute Criteria 1).

### Step 3: Tool Selection

Assign tools based on the agent's needs:

| Tool | When to Include |
|------|-----------------|
| `Read` | Agent needs to read files (almost always) |
| `Write` | Agent produces output files |
| `Glob` | Agent needs to find files by pattern |
| `Grep` | Agent needs to search file contents |
| `Bash` | Agent needs to run commands (use sparingly) |
| `WebSearch` | Agent needs to search the web |
| `WebFetch` | Agent needs to fetch web content |
| `Agent` | Agent needs to delegate to sub-agents |

### Step 4: Generate Agent Definition

Write the agent `.md` file with:

1. **Frontmatter**: name, description, model, tools, maxTurns, memory
2. **Role definition**: "You are a [role] specializing in [domain]."
3. **Task instructions**: Step-by-step protocol for the agent's work
4. **Output format**: Exact specification of expected output structure
5. **Quality rules**: Domain-specific quality requirements
6. **GRA compliance** (if research agent): GroundedClaim schema, Hallucination Firewall rules

### Step 5: GRA Integration (Research Agents Only)

For agents that produce research claims, include:

```markdown
## GRA Compliance

All claims must follow the GroundedClaim schema:

- **id**: "{CLAIM_PREFIX}-{NNN}" (e.g., "LS-001")
- **claim_type**: FACTUAL | EMPIRICAL | THEORETICAL | METHODOLOGICAL | INTERPRETIVE | SPECULATIVE
- **sources**: At least one PRIMARY or SECONDARY source with reference and DOI
- **confidence**: 0-100 score
- **effect_size**: When applicable (statistical findings)
- **uncertainty**: Explicit limitation statement

### Hallucination Firewall
- BLOCK: "all studies agree", "100%", "no exceptions"
- REQUIRE_SOURCE: Any statistical claim (p-values, effect sizes)
- SOFTEN: "certainly", "obviously", "clearly" → add hedging
- VERIFY: "it is known that" → add citation
```

### Step 6: Validate Agent Definition

Verify the generated agent:
- [ ] Frontmatter has all required fields
- [ ] name matches filename (kebab-case)
- [ ] Instructions are in English (AI performance)
- [ ] Output format is clearly specified
- [ ] Tool list matches actual needs
- [ ] GRA compliance section present (if research agent)
- [ ] No placeholder content

### Step 7: Register Agent

Output:
1. Agent file location: `.claude/agents/{name}.md`
2. How to invoke: `@{name}` in prompts or via Agent tool
3. Claim prefix (if GRA agent): `{PREFIX}`

## Language Rules

- **Agent instructions (body)**: English — AI performance optimization
- **Description (frontmatter)**: English — for agent matching
- **Output instructions for user-facing text**: Include Korean translation directive

## Batch Creation

When creating multiple related agents:
1. Design all agents together for consistency
2. Ensure claim prefixes are unique across the set
3. Define inter-agent dependencies explicitly
4. Verify no overlapping responsibilities

## Quality Checklist

- [ ] Agent follows AgenticWorkflow conventions
- [ ] Model selection justified by task complexity
- [ ] Tool list is minimal but sufficient
- [ ] Instructions are specific and actionable
- [ ] GRA compliance complete (for research agents)
- [ ] Claim prefix unique (for GRA agents)
- [ ] No hardcoded file paths
