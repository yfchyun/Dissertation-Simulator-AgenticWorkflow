---
description: Take a learning comprehension quiz for the current thesis learning track. Uses @assessment-agent for evaluation.
---

# Learning Quiz

Assess understanding of the current learning track content.

## Protocol

1. Read SOT to identify current learning track and completed lessons
2. Delegate to @assessment-agent:
   - Generate 5-10 questions covering completed track content
   - Mix question types: multiple choice, short answer, application
   - Evaluate responses and provide detailed feedback
3. Record quiz results in SOT under `learning_progress.quiz_results`
4. If score < 70%: recommend review of weak areas before proceeding
5. If score >= 70%: unlock next track section
