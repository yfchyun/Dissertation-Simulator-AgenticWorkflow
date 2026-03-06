---
description: Manually trigger Korean translation for a specific thesis workflow step. Translates English output via @translator and validates with T1-T12 checks.
---

# Thesis Translate

Manually translate a specific step's English output to Korean.

## Protocol

### Step 1: Read SOT and Determine Target

```bash
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/checklist_manager.py \
  --status \
  --project-dir "$CLAUDE_PROJECT_DIR/thesis-output/{project}"
```

Parse the user's request:
- If `--step N` is specified → translate step N only
- If `--all-missing` is specified → translate all steps with English output but no Korean pair
- Default: ask user which step to translate

### Step 2: Verify English Output Exists (L0 Guard)

For each target step N:

```bash
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/validate_task_completion.py \
  --file {english_output_path} --min-size 100
```

**If L0 fails** → STOP. Report: "Step {N}의 영어 원본이 없습니다. 먼저 해당 단계를 실행하세요."

### Step 3: Call @translator

```
Agent: subagent_type="translator", prompt="
  Translate the following file to Korean following your 7-step protocol:

  English source: {english_output_path}
  Output to: {english_output_path with .ko.md extension}
  Glossary: translations/glossary.yaml
  Step number: {N}

  Execute ALL 7 steps: Load glossary → Read source → Translate → Self-review + pACS → Update glossary → Write output → Write pACS log.
"
```

### Step 4: Run Deterministic Validation (Layer 1 — Python, hallucination 0%)

```bash
# T1-T9: Existing structural checks
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/validate_translation.py \
  --step {N} --project-dir "$CLAUDE_PROJECT_DIR/thesis-output/{project}" \
  --check-pacs --check-sequence

# T10-T12: Term/number/citation preservation checks
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/verify_translation_terms.py \
  --en-file {english_output_path} \
  --ko-file {korean_output_path} \
  --glossary "$CLAUDE_PROJECT_DIR/translations/glossary.yaml"
```

**If any check FAIL** → Report specific failures and ask user:
- "T10 FAIL: 3 glossary terms not translated correctly. 재번역할까요?"
- "T12 FAIL: 2 citations missing in Korean. 수정할까요?"

### Step 5: (Optional) Semantic Verification (Layer 2 — LLM)

For high-importance steps (Gate steps, Phase 2-3 outputs), invoke @translation-verifier:

```
Agent: subagent_type="translation-verifier", prompt="
  Verify the translation quality:
  English source: {english_output_path}
  Korean translation: {korean_output_path}
  Glossary: translations/glossary.yaml
  Step: {N}

  Layer 1 (deterministic) results: {T10-T12 JSON results}

  Focus on: meaning fidelity, naturalness, academic rigor.
  Provide independent pACS (Ft, Ct, Nt) and Verdict.
"
```

### Step 6: Record in SOT

```bash
python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/scripts/checklist_manager.py \
  --record-translation \
  --project-dir "$CLAUDE_PROJECT_DIR/thesis-output/{project}" \
  --step {N} \
  --ko-path {korean_output_path}
```

### Step 7: Report Results (Korean)

```
## 번역 완료 보고

- 단계: Step {N} — {step_description}
- 영어 원본: {english_output_path}
- 한국어 번역: {korean_output_path}
- 용어 사전: {new_terms_added}개 신규 용어 추가
- 검증 결과: T1-T12 {PASS/FAIL 상세}
- Translation pACS: Ft={score}, Ct={score}, Nt={score} → {pACS}
- 상태: SOT에 기록 완료
```
