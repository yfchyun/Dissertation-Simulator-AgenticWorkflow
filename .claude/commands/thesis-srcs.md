---
description: Run SRCS (Source-Rigor-Confidence-Specificity) evaluation on thesis claims. Computes 4-axis quality scores.
---

# Thesis SRCS Evaluation

Run unified SRCS 4-axis evaluation on all GroundedClaims.

## Protocol

1. Collect all claim files from wave-results/
2. Run `compute_srcs_scores.py` for deterministic axes (CS, VS)
3. Run LLM evaluation for semantic axes (GS, US)
4. Compute weighted SRCS score per claim type
5. Flag claims below threshold (75)
6. Generate srcs-summary.json report

## SRCS Axes
| Axis | Weight (EMPIRICAL) | Type |
|------|-------------------|------|
| CS (Citation Score) | 0.35 | Deterministic (P1) |
| GS (Grounding Score) | 0.35 | LLM evaluation |
| US (Uncertainty Score) | 0.10 | LLM evaluation |
| VS (Verifiability Score) | 0.20 | Deterministic (P1) |
