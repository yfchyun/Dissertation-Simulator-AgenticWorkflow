# Dissertation Simulator: Architecture and Philosophy

이 문서는 **Dissertation Simulator** — AgenticWorkflow 코드베이스에서 태어난 박사 논문 연구 시뮬레이션 시스템의 **도메인 고유 아키텍처와 설계 철학**을 기술한다.

> **부모-자식 문서 분리**: 이 프로젝트는 "만능줄기세포" (AgenticWorkflow)와 그로부터 태어난 "자식 시스템" (Dissertation Simulator)을 구분한다. 부모 문서(`AGENTICWORKFLOW-*.md`)는 방법론/프레임워크를, 이 문서(`DISSERTATION-SIMULATOR-*.md`)는 도메인 고유 아키텍처를 기술한다. 이 분리는 자식 시스템이 독립적으로 이해·운영될 수 있게 한다.

---

## 1. 설계 철학

### 1.1 존재 이유: DNA 유전의 실증

Dissertation Simulator는 AgenticWorkflow의 "만능줄기세포 → 분화된 세포" 철학을 **최초로 실증**하는 대규모 자식 시스템이다. 부모의 전체 게놈(절대 기준, SOT 패턴, 4계층 QA, Safety Hook, Context Preservation)이 박사 논문 도메인에 맞게 발현된다.

| 부모 게놈 (DNA) | 자식에서의 발현 |
|---------------|--------------|
| 절대 기준 1 (품질) | 학술적 엄밀성 절대주의 — 토큰 비용보다 논문 품질 |
| 절대 기준 2 (SOT) | `session.json` — 논문 전용 단일 상태 파일 |
| 4계층 QA | GRA 3계층 (Agent Self-Verification → Cross-Validation Gate → SRCS) |
| P2 (전문성 기반 위임) | 48개 전문 에이전트 — 역할별 극도의 전문화 |
| Context Preservation | 4개 HITL 컨텍스트 리셋 포인트 + 3-File External Memory |
| Safety Hook | GroundedClaim 검증 + Hallucination Firewall |

### 1.2 핵심 신념: 연구의 엄밀성은 자동화할 수 있다

박사 논문 연구는 인간 전문가만의 영역으로 여겨지지만, 이 시스템은 핵심 전제를 세운다:

> **엄밀한 프로세스를 설계하면, AI 에이전트가 인간 연구자를 보조하여 박사급 품질의 연구 산출물을 생산할 수 있다.**

단, "보조"가 핵심이다. 9개 HITL 체크포인트에서 인간 연구자가 방향을 승인하고, AI는 실행·검증·합성을 담당한다.

### 1.3 GRA (Grounded Research Architecture)

Dissertation Simulator의 고유 품질 보장 체계:

```
Layer 1: Agent Self-Verification
  └── GroundedClaim 스키마 강제 (id, text, sources[], confidence, verification)
  └── Hallucination Firewall (blocked patterns: "all studies agree", "100%", "universally accepted")
  └── MIN_CONFIDENCE 임계값 (FACTUAL:95, EMPIRICAL:85, THEORETICAL:75)

Layer 2: Cross-Validation Gates
  └── Gate 1-4: Wave 간 교차 검증 (이전 Wave claim 품질 검증)
  └── Gate 5: 연구 설계 최종 검증

Layer 3: Unified SRCS Evaluation
  └── 4축 평가: Source, Rigor, Confidence, Specificity
  └── Claim 유형별 가중치 (EMPIRICAL vs THEORETICAL vs FACTUAL)
  └── 75점 임계값 — 미달 claim은 플래그
```

---

## 2. 아키텍처 전체 조감도

### 2.1 Phase/Wave/Gate/HITL 구조

```
Phase 0: Initialization & Topic (Step 1-38)
├── Step 1-8: 프로젝트 초기화 (SOT, 체크리스트, 리소스)
├── Step 9-14: Mode A — 연구 주제 탐색 (@topic-explorer)
├── Step 15-34: Mode D — 학습 모드 (8 Track, @methodology-tutor)
└── HITL-0/1: 연구 질문 확인 및 승인

Phase 1: Literature Review (Step 39-104)
├── Wave 1 (Step 39-54): 기초 문헌 검색
│   └── @literature-searcher + @seminal-works-analyst + @trend-analyst + @methodology-scanner
│   └── ── Gate-1 ──▶
├── Wave 2 (Step 55-70): 심층 분석
│   └── @theoretical-framework-analyst + @empirical-evidence-analyst + @gap-identifier + @variable-relationship-analyst
│   └── ── Gate-2 ──▶
├── Wave 3 (Step 71-86): 비판적 분석
│   └── @critical-reviewer + @methodology-critic + @limitation-analyst + @future-direction-analyst
│   └── ── Gate-3 ──▶
├── Wave 4 (Step 87-94): 통합 합성
│   └── @synthesis-agent + @conceptual-model-builder
│   └── ── Gate-4 ──▶
├── Wave 5 (Step 95-98): 품질 보증
│   └── @plagiarism-checker + SRCS Full Evaluation
│   └── ── Final Quality Gate ──▶
└── HITL-2 (Step 99-104): 문헌 검토 결과 승인 (Context Reset Point 1)

Phase 2: Research Design (Step 105-132)
├── HITL-3: 연구 유형 확정 (quantitative/qualitative/mixed)
├── 조건부 분기:
│   ├── Quantitative Path: @hypothesis-developer → @quantitative-designer → @sampling-designer → @statistical-planner
│   ├── Qualitative Path: @paradigm-consultant → @participant-selector → @qualitative-data-designer → @qualitative-analysis-planner
│   └── Mixed Methods Path: @mixed-methods-designer → @integration-strategist
├── 공통: @ethics-reviewer + @instrument-developer + @data-collection-planner
├── Gate-5: 연구 설계 검증
└── HITL-4 (Step 125-132): 연구 설계 승인 (Context Reset Point 2)

Phase 3: Writing & Editing (Step 133-168)
├── @thesis-architect: 개요 설계
├── @thesis-writer: 챕터별 집필
├── @thesis-reviewer: 초고 검토
├── @citation-manager + @manuscript-formatter
├── HITL-5: 논문 형식 선택
├── HITL-6: 개요 승인 (Context Reset Point 3)
└── HITL-7: 초고 리뷰

Phase 4: Publication (Step 169-180)
├── @publication-strategist + @journal-matcher
├── @submission-preparer + @cover-letter-writer
└── HITL-8: 최종 확정 (Context Reset Point 4)

Translation (Step 181-210)
└── @translator: 전체 산출물 한국어 번역
```

### 2.2 Input Modes (7가지 진입 경로)

| Mode | 진입 조건 | 시작 Phase |
|------|---------|-----------|
| **A** (기본) | 연구 주제 제공 → 연구 질문 생성 | Phase 0-A |
| **B** | 연구 질문 직접 입력 | Phase 1 (Wave 1) |
| **C** | 기존 문헌 리뷰 분석 | Phase 1 (분석) |
| **D** | 학습 모드 — 방법론 튜토리얼 | Phase 0-D |
| **E** | 선행 논문 업로드 → 분석 | Phase 1 (분석) |
| **F** | 연구 제안서 업로드 → 분석 | Phase 2 |
| **G** | 커스텀 입력 | 사용자 해석 |

### 2.3 3-File External Memory 전략

컨텍스트 윈도우 한계를 극복하기 위한 외부 기억 아키텍처:

| 파일 | 역할 | 크기 제한 |
|------|------|---------|
| `session.json` | SOT — 진행 상태, Gate, HITL, 산출물 경로 | 구조화 JSON |
| `todo-checklist.md` | 체크리스트 — 150 step `[x]/[ ]` 추적 | ~10KB |
| `research-synthesis.md` | 연구 합성 — 3000-4000단어 압축 인사이트 | ~15KB |

**Context Reset Model**: HITL-2, HITL-4, HITL-6, HITL-8에서 컨텍스트를 리셋하고, 3-File에서 상태를 복원하여 세션 연속성을 보장한다.

---

## 3. 에이전트 아키텍처 (48+3 agents)

### 3.1 에이전트 계층 구조

```
thesis-orchestrator (총괄)
├── Phase 0 에이전트 (5)
│   ├── topic-explorer (LS-T)
│   ├── literature-analyzer (LS-A)
│   ├── methodology-tutor (MT)
│   ├── practice-coach (PCH)
│   └── assessment-agent (AA)
├── Phase 1 에이전트 — Wave별 (19)
│   ├── Wave 1: literature-searcher, seminal-works-analyst, trend-analyst, methodology-scanner
│   ├── Wave 2: theoretical-framework-analyst, empirical-evidence-analyst, gap-identifier, variable-relationship-analyst
│   ├── Wave 3: critical-reviewer, methodology-critic, limitation-analyst, future-direction-analyst
│   ├── Wave 4: synthesis-agent, conceptual-model-builder
│   └── Wave 5: plagiarism-checker
├── Phase 2 에이전트 — 경로별 (14)
│   ├── Quantitative: hypothesis-developer, research-model-developer, quantitative-designer, sampling-designer, statistical-planner
│   ├── Qualitative: paradigm-consultant, participant-selector, qualitative-data-designer, qualitative-analysis-planner
│   ├── Mixed: mixed-methods-designer, integration-strategist
│   └── 공통: ethics-reviewer, instrument-developer, data-collection-planner
├── Phase 3 에이전트 (7)
│   ├── thesis-architect, thesis-writer, thesis-reviewer
│   ├── abstract-writer, citation-manager, manuscript-formatter
│   └── thesis-plagiarism-checker
├── Phase 4 에이전트 (4)
│   ├── publication-strategist, journal-matcher
│   └── submission-preparer, cover-letter-writer
└── 품질 에이전트 (2)
    ├── unified-srcs-evaluator (PC-SRCS)
    └── research-synthesizer (SA-RS)
```

### 3.2 GroundedClaim 스키마

모든 에이전트는 통합 GroundedClaim 형식으로 claim을 생산한다:

```json
{
  "id": "LS-001",
  "text": "Recent meta-analyses show...",
  "claim_type": "EMPIRICAL",
  "sources": ["Smith et al. (2024)", "DOI:10.1234/..."],
  "confidence": 85,
  "verification": "verified"
}
```

**43개 고유 Claim Prefix**:

| Phase | 에이전트 | Prefix |
|-------|---------|--------|
| Wave 1 | literature-searcher, seminal-works-analyst, trend-analyst, methodology-scanner | LS, SWA, TRA, MS |
| Wave 2 | theoretical-framework-analyst, empirical-evidence-analyst, gap-identifier, variable-relationship-analyst | TFA, EEA, GI, VRA |
| Wave 3 | critical-reviewer, methodology-critic, limitation-analyst, future-direction-analyst | CR, MC, LA, FDA |
| Wave 4 | synthesis-agent, conceptual-model-builder | SA, CMB |
| Phase 2 Quant | hypothesis-developer, research-model-developer, quantitative-designer, sampling-designer, statistical-planner | VRA-H, CMB-M, QND, SD, SP |
| Phase 2 Qual | paradigm-consultant, participant-selector, qualitative-data-designer, qualitative-analysis-planner | TFA-P, MS-PS, QDD, MS-QA |
| Phase 2 Mixed | mixed-methods-designer, integration-strategist | MMD, MS-IS |
| Phase 3 | thesis-architect, thesis-writer 등 | SA-TA, TW, TR, AW, CM, MF, TPC |
| Phase 4 | publication-strategist, journal-matcher 등 | FDA-PB, JM, SUB, CLW |
| Quality | unified-srcs-evaluator, research-synthesizer | PC-SRCS, SA-RS |

### 3.3 SRCS 가중치 체계

| Claim 유형 | Source (CS) | Rigor (GS) | Confidence (US) | Specificity (VS) |
|-----------|------------|------------|-----------------|------------------|
| EMPIRICAL | 0.35 | 0.35 | 0.10 | 0.20 |
| THEORETICAL | 0.30 | 0.30 | 0.15 | 0.25 |
| FACTUAL | 0.40 | 0.25 | 0.05 | 0.30 |
| METHODOLOGICAL | 0.30 | 0.35 | 0.10 | 0.25 |
| INTERPRETIVE | 0.25 | 0.30 | 0.20 | 0.25 |
| SPECULATIVE | 0.20 | 0.25 | 0.25 | 0.30 |

---

## 4. 핵심 인프라

### 4.1 SOT 관리 (`session.json`)

시스템 SOT(`state.yaml`)와 완전히 독립된 논문 전용 상태 파일:

```json
{
  "project_name": "my-thesis",
  "status": "running",
  "current_step": 0,
  "total_steps": 210,
  "research_type": "undecided",
  "input_mode": "A",
  "research_question": "",
  "academic_field": "",
  "outputs": {},
  "gates": {
    "gate-1": { "status": "pending", "timestamp": null },
    "gate-2": { "status": "pending", "timestamp": null },
    "gate-3": { "status": "pending", "timestamp": null },
    "srcs-full": { "status": "pending", "timestamp": null },
    "final-quality": { "status": "pending", "timestamp": null }
  },
  "hitl_checkpoints": {
    "hitl-0": { "status": "pending", "timestamp": null },
    "hitl-1": { "status": "pending", "timestamp": null },
    "...": "..."
  },
  "fallback_history": [],
  "context_snapshots": [],
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

**검증 규칙 (TS1-TS10)**: 스키마 타입, 필수 키, 상태 열거형, 범위 검증, 타임스탬프 형식 등 10개 결정론적 규칙.

### 4.2 인프라 스크립트

| 스크립트 | 역할 | 카테고리 |
|---------|------|---------|
| `checklist_manager.py` | SOT CRUD, 체크리스트 관리, Gate/HITL 기록, Checkpoint | Core |
| `query_workflow.py` | 관측성 — dashboard, weakest-step, blocked, retry | Observability |
| `validate_grounded_claim.py` | GroundedClaim ID·스키마 검증, Hallucination Firewall | Quality |
| `fallback_controller.py` | 3-tier Fallback 제어 (Team→Sub-agent→Direct) | Resilience |
| `compute_srcs_scores.py` | SRCS 4축 결정론적 점수 계산 | Quality |
| `guard_sot_write.py` | SOT 쓰기 보호 (비인가 쓰기 차단) | Safety |
| `validate_wave_gate.py` | Wave/Gate 교차 검증 실행·기록 | Quality |
| `validate_step_sequence.py` | 스텝 순서·의존성 검증 | Integrity |
| `validate_thesis_output.py` | 산출물 파일 존재·크기 검증 | Quality |
| `validate_srcs_threshold.py` | SRCS 75점 임계값 검증 | Quality |
| `teammate_health_check.py` | 에이전트 팀 건강 점검 | Resilience |
| `validate_task_completion.py` | 태스크 완료 검증 | Integrity |

### 4.3 E2E 테스트 (108 tests, 5 Track)

| Track | 파일 | 테스트 수 | 검증 대상 |
|-------|------|---------|---------|
| 1 | `test_e2e_lifecycle.py` | 30 | init → advance → gate → HITL → checkpoint → restore |
| 2 | `test_e2e_sot_integrity.py` | 17 | 스키마 검증, 필드 일관성, 원자적 쓰기, 타임스탬프 |
| 3 | `test_e2e_cross_component.py` | 17 | checklist_manager ↔ query_workflow ↔ context_summary |
| 4 | `test_e2e_cli_flags.py` | 26 | 모든 argparse 플래그 성공/에러 시나리오 |
| 5 | `test_e2e_error_recovery.py` | 18 | 손상 SOT, 누락 파일, 의존성 차단, 체크포인트 복구 |

---

## 5. 부모에서 상속된 DNA

Dissertation Simulator가 AgenticWorkflow로부터 상속한 게놈 구성요소:

| 부모 구성요소 | 자식에서의 발현 | 상세 참조 |
|------------|--------------|---------|
| 절대 기준 3개 | 논문 도메인에 맞게 맥락화 | `AGENTS.md §2` |
| Context Preservation | HITL 리셋 포인트 + 3-File Memory | `docs/protocols/context-preservation-detail.md` |
| Safety Hook 체계 | GroundedClaim 검증 + Hallucination Firewall | `.claude/hooks/scripts/validate_grounded_claim.py` |
| Autopilot Mode | Wave 내 자동 진행 (Gate/HITL에서만 정지) | `AGENTS.md §5.1` |
| ULW Mode | 학술 연구의 철저함 보장 | `docs/protocols/ulw-mode.md` |
| Hub-and-Spoke 문서 | 부모(`AGENTICWORKFLOW-*.md`) vs 자식(`DISSERTATION-SIMULATOR-*.md`) 분리 | 이 문서 자체 |
| `soul.md` | DNA 유전 철학 | `soul.md` |

---

## 부록: 용어 정리

| 용어 | 정의 |
|------|------|
| **GRA** | Grounded Research Architecture — 3계층 품질 보장 (Self-Verification → Gate → SRCS) |
| **SRCS** | Source-Rigor-Confidence-Specificity — 4축 claim 품질 평가 |
| **Wave** | Phase 1 내의 병렬 작업 단위. 각 Wave는 4개 에이전트가 병렬 실행 |
| **Gate** | Wave 간 교차 검증 관문. 이전 Wave의 claim 품질 미달 시 진행 차단 |
| **HITL** | Human-In-The-Loop — 인간 연구자의 승인이 필수인 체크포인트 |
| **GroundedClaim** | 출처와 신뢰도가 명시된 연구 주장 단위 |
| **Context Reset Point** | HITL-2/4/6/8에서 컨텍스트를 리셋하고 3-File에서 복원하는 지점 |
| **3-tier Fallback** | Team → Sub-agent → Direct 실행 강등 체계 |
| **Claim Prefix** | 에이전트별 고유 2-3자리 대문자 식별자 (예: LS, TFA, GI) |
