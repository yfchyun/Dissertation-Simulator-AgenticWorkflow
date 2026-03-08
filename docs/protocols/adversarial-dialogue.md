# Adversarial Dialogue Protocol

> 이 문서는 AgenticWorkflow의 Adversarial Dialogue(적대적 대화) 패턴의 완전한 명세이다.
> 기존 L0→L1→L1.5 품질 게이트 이후 **L2 품질 게이트**로 작동한다.
> CLAUDE.md, AGENTS.md §5.5, quality-gates.md와 함께 읽는다.

## 핵심 원칙

Adversarial Dialogue는 **Generator-Critic 반복 루프**다. Generator가 초안을 작성하면, Critic이
독립적으로 비판한다. Critic의 피드백을 받아 Generator가 수정하고, Critic이 재검증한다.
이 루프는 합의(Consensus) 또는 최대 라운드 도달까지 반복된다.

```
[Normal Execution: Tier 1/2/3]
    ↓ output (Round 1 = primary output)
[E5: L0 Anti-Skip → L1 Verification → L1.5 pACS]
    ↓ all pass
[L2 Adversarial Dialogue] ← 이 문서의 대상
    ↓ PASS (consensus)
[Step Advance via checklist_manager --advance]
```

**Adversarial Dialogue는 기존 Tier 1/2/3 실행 구조를 대체하지 않는다.**
L0~L1.5가 통과된 산출물에 대해 추가 품질 보장 계층으로 작동한다.

---

## 도메인별 패턴

### Research Domain (논문/연구 산출물)

**Critic 구성**: `@fact-checker` (Primary) + `@reviewer` (Secondary) — **병렬 실행**

```
Round K:
  Generator (Tier 2 sub-agent) → dialogue-logs/step-N-draft-rK.md
       ↓ 병렬 실행 (독립적 — 확증 편향 방지)
  @fact-checker → dialogue-logs/step-N-rK-fc.md
  @reviewer     → dialogue-logs/step-N-rK-rv.md
       ↓ Orchestrator 합성
  둘 다 PASS → Consensus
  어느 하나 FAIL → Generator 피드백 주입 → Round K+1
```

**병렬 실행이 필수인 이유**: @reviewer가 @fact-checker 보고서를 먼저 보면 확증 편향
발생 → Pre-mortem 독립성 훼손. 두 Critic은 반드시 동일한 draft를 동시에 독립 분석한다.

**@fact-checker Primary인 이유**: 연구 산출물의 환각은 사실적 주장의 정확성에서 발생한다.
@reviewer는 구조/논리를 검증하고, @fact-checker는 외부 사실을 검증한다. 순서가 아닌
병렬로 실행하여 두 관점을 동시에 확보한다.

### Development Domain (코드 구현)

**Critic 구성**: `@code-reviewer` (단독)

```
Round K:
  Orchestrator가 코드 파일을 직접 편집 (in-place, draft 파일 없음)
       ↓
  @code-reviewer → dialogue-logs/step-N-rK-cr.md
       ↓
  PASS → Consensus
  FAIL → Orchestrator가 targeted fix (실패한 file:line만 수정) → Round K+1
```

**Development 도메인에서 `dialogue-logs/step-N-draft-rK.md`는 생성하지 않는다.**
코드는 소스 파일을 직접 편집하므로 draft 파일이 없다. @code-reviewer는 실제
소스 파일을 직접 읽는다.

---

## 파일 구조

```
{project-dir}/
├── dialogue-logs/                    ← 모든 중간 dialogue 파일 (review-logs/와 분리 필수)
│   ├── step-N-draft-r1.md           ← Research domain: Round 1 Generator 산출물
│   ├── step-N-draft-r2.md           ← Research domain: Round 2 Generator 산출물
│   ├── step-N-r1-fc.md              ← Round 1 @fact-checker 보고서
│   ├── step-N-r1-rv.md              ← Round 1 @reviewer 보고서
│   ├── step-N-r2-fc.md              ← Round 2 @fact-checker 보고서 (Incremental Mode)
│   ├── step-N-r2-rv.md              ← Round 2 @reviewer 보고서
│   ├── step-N-rK-cr.md              ← Development domain: Round K @code-reviewer
│   └── step-N-summary.md            ← Dialogue 완료 요약 (RLM 보존용)
└── review-logs/
    └── step-N-review.md             ← 최종 합의 리뷰 (기존 validate_review.py R1-R5 대상)
```

**`dialogue-logs/`를 `review-logs/`와 반드시 분리하는 이유**:
`_context_lib.py`의 `_extract_quality_gate_state()`가 `review-logs/`의 모든 파일에서
step 번호를 추출하여 최대 step을 결정한다. 중간 dialogue 파일이 `review-logs/`에 있으면
잘못된 `max_step`이 감지되어 RLM 컨텍스트 스냅샷이 오염된다.

---

## workflow.md 적용 방법

워크플로우 단계에서 `Dialogue:` 선택 필드로 활성화한다:

```markdown
### Step N: Research Analysis

- **Agent**: `@literature-reviewer`
- **Dialogue**: `@fact-checker + @reviewer [max-rounds: 10]`  ← Research domain
- **Verification**: ...
```

```markdown
### Step N: Feature Implementation

- **Agent**: `@code-implementation`
- **Dialogue**: `@code-reviewer [max-rounds: 10]`             ← Development domain
- **files-to-review**: `[auth.py, db.py, api.py]`
```

`Dialogue:` 필드가 없는 단계는 기존 단일 리뷰(@reviewer 또는 없음)를 사용한다.

---

## Orchestrator 실행 프로토콜

### Step 1: Dialogue 시작

```bash
python3 .claude/hooks/scripts/checklist_manager.py \
  --dialogue-start --step N --domain research|development \
  --max-rounds 10 --project-dir {dir}
```

### Step 2: 각 Round 실행

**Research domain:**
```
# 병렬 실행 (Agent tool 두 번 동시 호출)
Agent: subagent_type="fact-checker", prompt="Full/Incremental verification of {draft_path}. Round: K."
Agent: subagent_type="reviewer",     prompt="Review {draft_path}. Round: K. Independent analysis."
```

**Development domain:**
```
Agent: subagent_type="code-reviewer",
       prompt="Review files: {files_to_review}. Round: K. Previous issues: {accumulated_issues}."
```

### Step 3: P1 검증

```bash
# Research domain Round K (K >= 2):
python3 .claude/hooks/scripts/validate_claim_inheritance.py \
  --step N --round K --project-dir {dir}

# 모든 domain Round K:
python3 .claude/hooks/scripts/validate_dialogue_state.py \
  --step N --round K --project-dir {dir}
```

### Step 4: 라운드 기록

```bash
python3 .claude/hooks/scripts/checklist_manager.py \
  --dialogue-round --step N --round K --verdict PASS|FAIL --project-dir {dir}
```

### Step 5: 합의 완료 또는 에스컬레이션

**합의 (모든 Critic PASS):**
```bash
# 1. 최종 합의 파일을 review-logs/step-N-review.md로 복사/생성
#    (validate_review.py R1-R5 통과를 위해 기존 경로 유지)

# 2. validate_review.py 실행 (기존 P1 검증)
python3 .claude/hooks/scripts/validate_review.py --step N --project-dir {dir}

# Development domain: file coverage 추가 검증
python3 .claude/hooks/scripts/validate_review.py \
  --step N --check-file-coverage "auth.py,db.py" --project-dir {dir}

# 3. Dialogue 종료 기록
python3 .claude/hooks/scripts/checklist_manager.py \
  --dialogue-end --step N --outcome consensus --project-dir {dir}

# 4. RLM 보존: dialogue 요약 저장 (Orchestrator 직접 Write 도구 사용)
# dialogue-logs/step-N-summary.md 작성 (아래 형식 준수)

# 5. Step advance
python3 .claude/hooks/scripts/checklist_manager.py \
  --advance --step N --project-dir {dir}
```

**최대 라운드 도달 시 에스컬레이션:**
```bash
python3 .claude/hooks/scripts/checklist_manager.py \
  --dialogue-end --step N --outcome escalated --project-dir {dir}
```

- `interactive` mode: HITL checkpoint로 에스컬레이션 (`AskUserQuestion` 호출)
- `autopilot` mode: WARNING 플래그 + 최선 산출물로 강제 진행 + step 기록에 `escalated` 표시

---

## Dialogue Summary 형식 (RLM 보존 필수)

`dialogue-logs/step-N-summary.md` 는 Orchestrator가 `--dialogue-end` 직후 Write 도구로 작성:

```markdown
# Adversarial Dialogue Summary — Step N: {Step Name}

Date: {YYYY-MM-DD}
Domain: research|development
Rounds Used: K / Max: 10
Outcome: consensus|escalated

## Round History

| Round | Fact-Check Verdict | Review Verdict | Key Issues |
|-------|-------------------|----------------|------------|
| 1     | FAIL              | FAIL           | [issue summary] |
| 2     | PASS              | PASS           | — |

## Changes Made

- Round 1 → Round 2: {what Generator fixed, concise}

## Final Verdict

PASS — consensus reached in Round K.
```

---

## @fact-checker Incremental Mode

Round 2+에서 @fact-checker는 **Incremental Mode**로 실행된다.

**Orchestrator 호출 방법:**
```
Agent: subagent_type="fact-checker",
  prompt="Incremental verification for Round K.
  Previous report: dialogue-logs/step-N-r{K-1}-fc.md
  Current draft: dialogue-logs/step-N-draft-rK.md
  Previous draft: dialogue-logs/step-N-draft-r{K-1}.md"
```

**Degenerate case**: Round K-1에서 verified claim이 0개이면 Incremental Mode를
적용하지 않는다. Full Verification Mode로 전환한다.

Incremental Mode 상세: `.claude/agents/fact-checker.md` §Incremental Fact-Check Mode

---

## Max Rounds 및 Retry Budget

Dialogue round 카운터는 `validate_retry_budget.py --gate dialogue`로 관리된다:

```bash
python3 .claude/hooks/scripts/validate_retry_budget.py \
  --step N --gate dialogue --check-and-increment --project-dir {dir}
```

- Non-ULW: `DEFAULT_MAX_RETRIES = 10`
- ULW: `ULW_MAX_RETRIES = 15`

카운터 파일: `dialogue-logs/.step-N-retry-count`

---

## Absolute Rules (Orchestrator 필수 준수)

1. **dialogue loop 종료 전 `--advance` 호출 금지**: `--dialogue-end` 완료 후에만
   `--advance` 실행 가능. 중간 라운드에서 step을 advance하면 SOT 일관성 손상.

2. **최종 합의 파일은 `review-logs/step-N-review.md`에 저장**: 기존
   `validate_review.py` R1-R5 검증이 이 경로를 확인한다.

3. **중간 파일은 반드시 `dialogue-logs/`에 저장**: `review-logs/`에 저장하면
   `_extract_quality_gate_state()`의 max_step 탐지가 오염되어 RLM 파괴.

4. **@fact-checker + @reviewer는 반드시 병렬 실행**: Research domain에서
   순차 실행은 확증 편향을 유발하여 리뷰 독립성을 손상한다.

5. **Dialogue Summary 파일 필수 작성**: `--dialogue-end` 직후 `dialogue-logs/step-N-summary.md`
   작성. 컨텍스트 리셋 후 RLM 복원 시 이 파일로 dialogue 상태를 재현한다.
