---
description: Run plagiarism check on thesis output using @plagiarism-checker agent.
---

# Check Plagiarism

Manual plagiarism check on thesis output files.

## Protocol

1. Read thesis draft chapters from `thesis-output/{project}/wave-results/`
2. Delegate to @plagiarism-checker:
   - Compare text against known sources
   - Check for improper paraphrasing
   - Verify all direct quotes are properly attributed
   - Calculate similarity percentages by section
3. Display results:
   - Overall similarity score
   - Flagged passages with source attribution
   - Recommendations for revision
4. If similarity > 15%: halt and require revision before proceeding
