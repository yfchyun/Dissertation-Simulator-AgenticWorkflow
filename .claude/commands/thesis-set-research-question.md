---
description: Set or update the research question and configure literature review options for the thesis workflow.
---

# Set Research Question

Configure the research question, literature review depth, and theoretical framework preferences.

## Protocol

1. Display current research question candidates (from topic analysis)
2. User selects or inputs research question
3. Configure options:
   - Literature review depth: Standard (50 papers) / Comprehensive (100+) / Systematic
   - Theoretical framework: Existing theory / New framework development
4. Update SOT with selected research question and options
5. Record HITL-1 completion
6. Save checkpoint for HITL-1:
   ```bash
   python3 .claude/hooks/scripts/checklist_manager.py \
     --save-checkpoint --checkpoint hitl-1-research-question \
     --project-dir thesis-output/{project}
   ```
