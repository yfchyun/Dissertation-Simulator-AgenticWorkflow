---
description: Enter learning mode for research methodology education. Provides interactive tutorials on 8 tracks from thesis basics to advanced methods.
---

# Thesis Learning Mode

Interactive research methodology education with Agent Team (tutor + coach + assessor).

## Usage
- `/thesis:learn` — Select a learning track
- `/thesis:learn track {1-8}` — Start specific track
- `/thesis:learn quiz` — Take understanding quiz
- `/thesis:learn progress` — Check learning progress

## Learning Tracks

| Track | Topic | Description |
|-------|-------|-------------|
| 1 | Thesis Basics | Definition, purpose, structure |
| 2 | Research Design | Questions, hypotheses, variables |
| 3 | Literature Review | Systematic review, critical reading |
| 4 | Quantitative Methods | Experimental design, statistics |
| 5 | Qualitative Methods | Interviews, coding, thematic analysis |
| 6 | Mixed Methods | Philosophical foundations, integration |
| 7 | Academic Writing | Citation styles, argumentation |
| 8 | Integrated Practice | Mini research project |

## Protocol

### Step 1: Create Learning Agent Team
Create a team with @methodology-tutor, @practice-coach, @assessment-agent.

### Step 2: Execute Learning Loop
```
Concept Learning → Example Analysis → Practice Exercise → Feedback → Review
```

### Step 3: Track Progress in SOT
Record learning progress in session.json under learning_progress key.

### Step 4: Assessment
@assessment-agent provides understanding quiz and generates learning portfolio.
