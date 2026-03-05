# Doctoral Research Workflow v1.0 (박사 논문 연구 워크플로우)

연구 주제 탐색부터 학술지 투고까지, 박사급 전문 AI 에이전트가 체계적으로 논문 연구를 지원하는 워크플로우.

**GRA(Grounded Research Architecture)** 기반 할루시네이션 방지 및 학술적 엄밀성 보증 시스템 적용.

## Overview

- **Input**: 연구주제(Default) | 연구질문/가설 | 기존문헌검토 | 학습모드
- **Output**: 문헌검토 패키지 + 연구설계서 + 논문 초안 + 투고 전략
- **Frequency**: On-demand
- **Quality Level**: 박사급 전문가 수준 (토큰 비용 무관, 학술적 엄밀성 최우선)
- **Architecture**: GRA (Grounded Research Architecture) + External Memory Strategy
- **Research Types**: 양적연구, 질적연구, 혼합연구 모두 지원

---

## 핵심 아키텍처

### 1. GRA (Grounded Research Architecture)

3계층 품질 보증 시스템으로 할루시네이션을 원천 차단하고 학술적 엄밀성을 보장합니다.

```
┌─────────────────────────────────────────────────────────────┐
│                  GRA 3-Layer Architecture                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Layer 1: Agent Self-Verification                            │
│  ├─ GroundedClaim 출력 스키마 준수                          │
│  ├─ Hallucination Firewall 통과                             │
│  ├─ Academic Citation Standards 준수                        │
│  └─ Mini-SRCS 자기 평가                                     │
│                                                              │
│  Layer 2: Cross-Validation Gates                             │
│  ├─ Gate 1: Wave 1 → Wave 2 (기초분석 검증)                 │
│  ├─ Gate 2: Wave 2 → Wave 3 (심층분석 검증)                 │
│  ├─ Gate 3: Wave 3 → Wave 4 (통합분석 검증)                 │
│  └─ Gate 4: Wave 4 → Wave 5 (최종검증)                      │
│                                                              │
│  Layer 3: Unified SRCS Evaluation                            │
│  ├─ 전체 클레임 종합 평가                                   │
│  ├─ 교차 일관성 검사                                        │
│  ├─ 학술적 기여도 평가                                      │
│  └─ 최종 품질 인증                                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 2. External Memory Strategy (3-File Architecture)

컨텍스트 윈도우 한계를 극복하기 위한 외부 메모리 전략입니다.

```
┌─────────────────────────────────────────────────────────────┐
│  External Memory Files (외부 메모리 파일)                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1️⃣ Context File (컨텍스트 파일)                            │
│     📄 session.json                                         │
│     - 연구 목표/방향성                                      │
│     - 입력 정보 (주제, 모드, 연구유형)                      │
│     - 옵션 설정                                              │
│     - context_snapshots (HITL 스냅샷)                       │
│                                                              │
│  2️⃣ Todo File (할 일 파일)                                  │
│     📄 todo-checklist.md                                    │
│     - 150단계 체크리스트                                    │
│     - 완료 표시 [x] / 미완료 [ ]                            │
│     - 마지막 작업 지점 파악용                                │
│                                                              │
│  3️⃣ Insights File (인사이트 파일)                           │
│     📄 research-synthesis.md                                │
│     - 연구 결과 압축본 (3000-4000자)                        │
│     - 핵심 문헌, 이론, 발견 추출                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 3. Context Reset Model

컨텍스트 리셋 시 자동 복구를 위한 체크포인트 시스템입니다.

| 리셋 포인트    | 로드할 파일                                           | 목적                   |
| -------------- | ----------------------------------------------------- | ---------------------- |
| **HITL-2 후**  | session.json, literature-synthesis.md, checklist      | Research Design 진입   |
| **HITL-4 후**  | session.json, research-design.md, synthesis, checklist | Writing Phase 진입     |
| **HITL-6 후**  | session.json, thesis-draft.md, checklist              | Revision/Submit 진입   |
| **HITL-8 후**  | session.json, thesis-final.md, checklist              | 완료 확인              |

---

## Input Mode Selection

워크플로우 시작 시 입력 모드를 확인합니다.

| Mode                        | Input                    | Flow                                                        |
| --------------------------- | ------------------------ | ----------------------------------------------------------- |
| **Mode A** (Default)        | 연구 주제/관심사         | 주제 분석 → 연구질문 도출 → 문헌검토                       |
| **Mode B**                  | 연구질문/가설 직접 입력  | 바로 Literature Review 단계 진입                            |
| **Mode C**                  | 기존 문헌검토 보유       | 문헌검토 분석 → Gap 식별 → Research Design                 |
| **Mode D** (Learning)       | 학습모드                 | 연구방법론 튜토리얼 → 실습 → 피드백 루프                   |
| **Mode E** (Paper Upload) ⭐| 선행연구 논문 업로드     | 논문 분석 → 갭 식별 → 가설 도출 → 연구 설계 제안           |
| **Mode F** (Proposal Upload) ⭐| 연구 프로포절 업로드  | 프로포절 분석 → 계획 추출 → 계획 기반 문헌검토 → 연구 수행 |
| **Mode G** (Custom Input)    | 자유 형식 상세 입력   | 입력 해석 → Mode A/B 경로 합류 (사전 설정 적용)            |

---

## Phase 0: Initialization (초기화)

### 0-1. 세션 초기화

- `thesis-output/_temp/` 폴더 생성
- `session.json` 초기화 (Context File)
- `todo-checklist.md` 생성 (Todo File, 150단계)
- `user-resource/` 폴더 확인 (사용자 참고 자료)

### 0-2. 사용자 리소스 관리

`user-resource/` 폴더에 자료를 넣으면 **최우선 참조**됩니다.

| 우선순위   | 소스               | 설명                          |
| ---------- | ------------------ | ----------------------------- |
| 1 (최우선) | `user-resource/`   | 사용자 제공 자료              |
| 2          | 학술 DB 검색       | Google Scholar, SSRN, JSTOR 등 |
| 3          | 웹 검색            | 학술 논문, 보고서             |
| 4          | 기본 지식          | AI 내장 지식                  |

### 0-3. 연구 유형 선택

- **Checkpoint**: `HITL-0`
- **Options**:
  ```
  [연구 유형]
  ○ 양적연구 (Quantitative Research)
  ○ 질적연구 (Qualitative Research)
  ○ 혼합연구 (Mixed Methods Research)
  ○ 아직 미정 (문헌검토 후 결정)

  [학문 분야]
  ○ 경영학/경제학
  ○ 사회과학
  ○ 인문학
  ○ 자연과학/공학
  ○ 의학/보건학
  ○ 교육학
  ○ 기타: [직접 입력]
  ```
- **Command**: `/thesis:init`

---

## Mode D: Learning Mode (학습모드)

논문 연구 방법론을 체계적으로 학습하는 특별 모드입니다.

### Learning Track Options

```
[학습 트랙 선택]
○ Track 1: 논문의 기초 (What is a Thesis?)
  - 논문의 정의와 목적
  - 학술적 글쓰기의 특성
  - 논문의 구조와 구성요소

○ Track 2: 연구 설계 기초 (Research Design Fundamentals)
  - 연구질문 수립 방법
  - 가설 설정의 원리
  - 변수와 조작적 정의

○ Track 3: 문헌검토 방법론 (Literature Review Methods)
  - 체계적 문헌검토 방법
  - 비판적 읽기와 분석
  - 문헌 매트릭스 작성법

○ Track 4: 양적연구 방법론 (Quantitative Methods)
  - 연구설계 유형 (실험, 준실험, 조사)
  - 표본추출과 표본크기
  - 통계분석 기초 (기술통계, 추론통계)
  - 신뢰도와 타당도

○ Track 5: 질적연구 방법론 (Qualitative Methods)
  - 질적연구 패러다임
  - 자료수집 방법 (인터뷰, 관찰, 문서분석)
  - 질적 자료 분석 (코딩, 주제분석)
  - 신뢰성과 엄밀성 확보

○ Track 6: 혼합연구 방법론 (Mixed Methods)
  - 혼합연구의 철학적 기반
  - 설계 유형 (수렴적, 설명적, 탐색적)
  - 자료 통합 전략

○ Track 7: 학술적 글쓰기 (Academic Writing)
  - APA/MLA/Chicago 스타일
  - 논증 구조와 논리전개
  - 표절 방지와 인용 윤리

○ Track 8: 종합 실습 (Integrated Practice)
  - 미니 연구 프로젝트 수행
  - 단계별 피드백
  - 포트폴리오 구성
```

### Learning Mode Agents

```yaml
learning-agents:
  methodology-tutor:
    description: "연구방법론 튜터"
    expertise: "연구방법론 교육, 개념 설명"
    teaching_style: "소크라테스식 질문법 + 예시 기반 설명"

  practice-coach:
    description: "실습 코치"
    expertise: "실습 과제 설계, 피드백 제공"
    
  assessment-agent:
    description: "학습 평가 에이전트"
    expertise: "이해도 평가, 학습 진도 추적"
```

### Learning Flow

```
[Track 선택] → [개념 학습] → [예시 분석] → [실습 과제] → [피드백] → [복습/다음 단계]
                    ↑                                          │
                    └──────────── 반복 학습 루프 ──────────────┘
```

- **Command**: `/thesis:learn`
- **Sub-commands**:
  - `/thesis:learn track [1-8]` - 특정 트랙 시작
  - `/thesis:learn quiz` - 이해도 퀴즈
  - `/thesis:learn practice` - 실습 과제
  - `/thesis:learn progress` - 학습 진도 확인

---

## Phase 1: Research (연구)

### 1. 연구 주제 탐색 프로세스

#### 1-1. [Mode A] 주제 기반 연구질문 도출

- **Agent**: `@topic-explorer`
- **Task**:
  - 입력된 관심 주제의 학술적 맥락 분석
  - 주요 연구 흐름 및 트렌드 파악
  - 잠재적 연구질문 5-7개 도출
  - 각 연구질문의 학술적 기여 가능성 평가
- **Output**: `topic-analysis.md`, `research-questions-candidates.md`

#### 1-2. [Mode C] 기존 문헌검토 분석

- **Agent**: `@literature-analyzer`
- **Task**:
  - 사용자 제공 문헌검토 분석
  - 커버된 영역과 Gap 식별
  - 연구 방향 제안
- **Output**: `existing-review-analysis.md`

### 2. (human) 연구질문/가설 확정 및 옵션 설정

- **Checkpoint**: `HITL-1`
- **Display**: 연구질문 후보 목록 + 학술적 기여도 분석
- **Options**:
  ```
  [연구질문 선택] 제시된 후보 중 선택 또는 직접 입력

  [문헌검토 깊이]
  ○ Standard: 최근 10년, 핵심 문헌 50편 내외
  ○ Comprehensive: 최근 20년, 100편 이상
  ○ Systematic: 체계적 문헌검토 프로토콜 적용

  [이론적 프레임워크]
  ☑ 기존 이론 검토 및 적용
  ☐ 새로운 이론적 프레임워크 개발
  ```
- **Command**: `/thesis:set-research-question`

---

### 3. 심층 문헌검토 (15개 Sub-agents + GRA)

연구질문 확정 후, 하이브리드 실행 방식으로 15개 전문 분석 수행.
**모든 에이전트는 GRA 규칙을 준수하여 GroundedClaim 형식으로 출력합니다.**

#### Execution Strategy: Hybrid Parallel-Sequential with Cross-Validation Gates

```
[병렬 실행 - Wave 1: 기초 문헌 탐색]
┌─ @literature-searcher (문헌 검색)
├─ @seminal-works-analyst (핵심 문헌 분석)
├─ @trend-analyst (연구 트렌드 분석)
└─ @methodology-scanner (방법론 스캔)
        │
        ▼ [Cross-Validation Gate 1]

[병렬 실행 - Wave 2: 심층 분석]
┌─ @theoretical-framework-analyst (이론적 프레임워크)
├─ @empirical-evidence-analyst (실증적 증거 분석)
├─ @gap-identifier (연구 갭 식별)
└─ @variable-relationship-analyst (변수 관계 분석)
        │
        ▼ [Cross-Validation Gate 2]

[병렬 실행 - Wave 3: 비판적 분석]
┌─ @critical-reviewer (비판적 검토)
├─ @methodology-critic (방법론 비평)
├─ @limitation-analyst (한계점 분석)
└─ @future-direction-analyst (미래 연구방향)
        │
        ▼ [Cross-Validation Gate 3]

[순차 실행 - Wave 4: 종합 및 통합]
├─ @synthesis-agent (문헌 종합)
└─ @conceptual-model-builder (개념적 모델 구축)
        │
        ▼ [SRCS Full Evaluation]

[순차 실행 - Wave 5: 품질 보증]
└─ @plagiarism-checker (표절 검사)
        │
        ▼ [Final Quality Gate]
```

---

#### 3-1. 문헌 검색 (Literature Search)

- **Agent**: `@literature-searcher`
- **Expertise**: 학술 데이터베이스 검색 전문가
- **Task**:
  - 검색 전략 수립 (키워드, Boolean 연산자)
  - 다중 데이터베이스 검색 (Google Scholar, SSRN, JSTOR, PubMed 등)
  - 검색 결과 스크리닝 (제목/초록 기반)
  - 포함/배제 기준 적용
  - PRISMA 흐름도 생성
- **GRA Compliance**: 검색 전략 및 결과 투명하게 문서화
- **Output**: `01-literature-search-strategy.md`, `search-results.json`

#### 3-2. 핵심 문헌 분석 (Seminal Works Analysis)

- **Agent**: `@seminal-works-analyst`
- **Expertise**: 학술사 및 핵심 문헌 전문가
- **Task**:
  - 분야의 기초 문헌(Seminal Works) 식별
  - 인용 네트워크 분석
  - 핵심 저자 및 연구 그룹 파악
  - 이론적 발전 계보 추적
- **GRA Compliance**: 인용 수, 출처 명시 필수
- **Output**: `02-seminal-works-analysis.md`

#### 3-3. 연구 트렌드 분석 (Research Trend Analysis)

- **Agent**: `@trend-analyst`
- **Expertise**: 계량서지학, 연구 트렌드 분석
- **Task**:
  - 시계열적 연구 동향 분석
  - 떠오르는 주제(Emerging Topics) 식별
  - 연구 핫스팟 및 프론티어 파악
  - 학술지별 게재 트렌드
- **GRA Compliance**: 데이터 기반 분석, 출처 명시
- **Output**: `03-research-trend-analysis.md`

#### 3-4. 방법론 스캔 (Methodology Scan)

- **Agent**: `@methodology-scanner`
- **Expertise**: 연구방법론 전문가
- **Task**:
  - 선행연구 방법론 유형 분류
  - 표본 크기, 연구설계 패턴 분석
  - 자료수집 및 분석 방법 정리
  - 방법론적 강점과 약점 요약
- **GRA Compliance**: 방법론 세부사항 정확히 기술
- **Output**: `04-methodology-scan.md`

#### 3-5. 이론적 프레임워크 분석 (Theoretical Framework Analysis)

- **Agent**: `@theoretical-framework-analyst`
- **Expertise**: 이론 분석 및 개념화 전문가
- **Task**:
  - 관련 이론 식별 및 검토
  - 이론 간 관계 및 발전 과정 분석
  - 본 연구에 적합한 이론적 렌즈 제안
  - 이론적 프레임워크 초안 작성
- **GRA Compliance**: 이론 원전 인용, 해석의 근거 명시
- **Output**: `05-theoretical-framework.md`

#### 3-6. 실증적 증거 분석 (Empirical Evidence Analysis)

- **Agent**: `@empirical-evidence-analyst`
- **Expertise**: 실증연구 분석 전문가
- **Task**:
  - 주요 실증연구 결과 정리
  - 효과 크기(Effect Size) 비교 분석
  - 연구 결과 간 일관성/불일치 파악
  - 메타분석적 관점에서의 종합
- **GRA Compliance**: 통계치 정확히 인용, 원문 참조
- **Output**: `06-empirical-evidence-synthesis.md`

#### 3-7. 연구 갭 식별 (Research Gap Identification)

- **Agent**: `@gap-identifier`
- **Expertise**: 연구 기회 분석 전문가
- **Task**:
  - 이론적 갭 식별
  - 방법론적 갭 식별
  - 맥락적 갭 식별 (지역, 산업, 시간)
  - 실천적 갭 식별
  - 갭의 중요성 및 연구 기회 평가
- **GRA Compliance**: 갭 주장의 근거 명시
- **Output**: `07-research-gap-analysis.md`

#### 3-8. 변수 관계 분석 (Variable Relationship Analysis)

- **Agent**: `@variable-relationship-analyst`
- **Expertise**: 변수 관계 및 인과관계 분석
- **Task**:
  - 주요 변수 식별 및 정의
  - 변수 간 관계 유형 분석 (상관, 인과, 매개, 조절)
  - 기존 연구의 변수 조작화 방식 검토
  - 개념적 모델 구성 요소 도출
- **GRA Compliance**: 변수 정의의 출처 명시
- **Output**: `08-variable-relationship-analysis.md`

#### 3-9. 비판적 검토 (Critical Review)

- **Agent**: `@critical-reviewer`
- **Expertise**: 학술 비평 전문가
- **Task**:
  - 선행연구의 논리적 일관성 평가
  - 주장과 증거의 정합성 검토
  - 대안적 해석 가능성 탐색
  - 연구의 가정과 전제 비판적 검토
- **GRA Compliance**: 비판의 근거와 대안 제시
- **Output**: `09-critical-review.md`

#### 3-10. 방법론 비평 (Methodology Critique)

- **Agent**: `@methodology-critic`
- **Expertise**: 연구방법론 비평 전문가
- **Task**:
  - 내적 타당도 위협 요인 분석
  - 외적 타당도(일반화 가능성) 평가
  - 측정의 신뢰도/타당도 검토
  - 통계적 결론 타당도 평가
- **GRA Compliance**: 방법론적 문제의 구체적 근거 제시
- **Output**: `10-methodology-critique.md`

#### 3-11. 한계점 분석 (Limitation Analysis)

- **Agent**: `@limitation-analyst`
- **Expertise**: 연구 한계 분석 전문가
- **Task**:
  - 선행연구의 공통 한계점 정리
  - 한계점의 유형별 분류
  - 본 연구에서 극복 가능한 한계 식별
  - 불가피한 한계와 대응 전략
- **GRA Compliance**: 한계점의 출처 및 영향 명시
- **Output**: `11-limitation-analysis.md`

#### 3-12. 미래 연구방향 분석 (Future Research Direction)

- **Agent**: `@future-direction-analyst`
- **Expertise**: 연구 어젠다 설정 전문가
- **Task**:
  - 선행연구가 제안한 후속 연구 정리
  - 연구 커뮤니티의 공통 관심사 파악
  - 본 연구의 포지셔닝 전략 제안
  - 연구의 학술적/실천적 기여 예측
- **GRA Compliance**: 제안의 근거 및 타당성 명시
- **Output**: `12-future-research-directions.md`

#### 3-13. 문헌 종합 (Literature Synthesis)

- **Agent**: `@synthesis-agent`
- **Expertise**: 학술 종합 및 통합 전문가
- **Task**:
  - 주제별/연대기별/방법론별 종합
  - 핵심 발견사항의 통합적 서술
  - 연구 분야의 현재 상태(State of the Art) 정리
  - 문헌검토 초안 작성
- **GRA Compliance**: Wave 1-3 결과와 교차 검증
- **Output**: `13-literature-synthesis.md`

#### 3-14. 개념적 모델 구축 (Conceptual Model Building)

- **Agent**: `@conceptual-model-builder`
- **Expertise**: 개념화 및 모델링 전문가
- **Task**:
  - 연구 변수 간 관계의 시각화
  - 가설 도출을 위한 논리적 근거 제시
  - 이론적 프레임워크와 연구모델 연결
  - 연구모델 다이어그램 생성
- **GRA Compliance**: 모델의 각 경로에 대한 문헌적 근거 명시
- **Output**: `14-conceptual-model.md`, `research-model.mermaid`

#### 3-15. 표절 검사 (Plagiarism Check)

- **Agent**: `@plagiarism-checker`
- **Expertise**: 학술 윤리 및 표절 검사 전문가
- **Task**:
  - 문헌검토 초안의 원본성 검사
  - 부적절한 패러프레이징 식별
  - 인용 누락 탐지
  - 자기표절 가능성 검토
  - 수정 권고사항 제시
- **GRA Compliance**: 유사도 비율 및 문제 구간 명시
- **Output**: `15-plagiarism-report.md`

---

### 4. SRCS 평가 (자동)

- **Agent**: `@unified-srcs-evaluator`
- **Task**:
  - 전체 연구 클레임 종합 평가
  - 교차 일관성 검사 (에이전트 간 모순 탐지)
  - 학술적 품질 보고서 생성
- **Output**: `srcs-summary.json`, `quality-report.md`

### 5. 연구 결과 종합

- **Agent**: `@research-synthesizer`
- **Task**:
  - 15개 분석 결과를 3000-4000자로 압축
  - 핵심 인사이트 추출
  - Context Reset 대비 Insights File 생성
- **Output**: `research-synthesis.md`

### 6. (human) Literature Review 결과 검토

- **Checkpoint**: `HITL-2`
- **Display**:
  - 15개 분석 결과 종합 요약
  - SRCS 학술 품질 보고서
  - 표절 검사 결과
  - 검토 필요 클레임 목록
- **Options**:
  ```
  [검토 방식]
  ○ 요약본만 확인 (권장)
  ○ 전체 상세 보고서 확인
  ○ 특정 영역 심층 확인: [영역 선택]

  [추가 연구 요청]
  ☐ 특정 영역 보완 연구 요청
  ☐ 추가 문헌 검색 요청
  ☐ 낮은 신뢰도 클레임 재검증
  ☐ 표절 의심 구간 수정
  ```
- **Command**: `/thesis:review-literature`
- **Output**: `literature-review-package.md` (종합본)
- **Context Reset Point**: 이 시점에서 컨텍스트 리셋 가능

---

## Phase 2: Research Design (연구설계)

### 7. 연구 유형별 설계 분기

#### 7-1. (human) 연구 유형 최종 확정

- **Checkpoint**: `HITL-3`
- **Options**:
  ```
  [연구 유형 확정]
  ○ 양적연구 (Quantitative Research)
    - 실험연구 (Experimental)
    - 준실험연구 (Quasi-Experimental)
    - 조사연구 (Survey)
    - 2차자료 분석 (Secondary Data Analysis)

  ○ 질적연구 (Qualitative Research)
    - 현상학적 연구 (Phenomenology)
    - 근거이론 (Grounded Theory)
    - 사례연구 (Case Study)
    - 문화기술지 (Ethnography)
    - 내러티브 연구 (Narrative Inquiry)

  ○ 혼합연구 (Mixed Methods)
    - 수렴적 설계 (Convergent Design)
    - 설명적 순차 설계 (Explanatory Sequential)
    - 탐색적 순차 설계 (Exploratory Sequential)
    - 내재적 설계 (Embedded Design)
  ```
- **Command**: `/thesis:set-research-type`

### 8. 양적연구 설계 경로

#### 8-1. 가설 정교화

- **Agent**: `@hypothesis-developer`
- **Task**:
  - 연구질문 기반 가설 도출
  - 귀무가설/대립가설 설정
  - 방향성 가설 vs 비방향성 가설 결정
  - 가설 간 논리적 연결 확인
- **Output**: `hypotheses.md`

#### 8-2. 연구모델 정교화

- **Agent**: `@research-model-developer`
- **Task**:
  - 변수 조작적 정의
  - 측정 도구 선정/개발 계획
  - 통제변수 선정
  - 연구모델 최종 확정
- **Output**: `research-model-final.md`

#### 8-3. 표본 설계

- **Agent**: `@sampling-designer`
- **Task**:
  - 모집단 정의
  - 표본추출 방법 결정
  - 표본크기 산정 (검정력 분석)
  - 표본추출 프레임 설계
- **Output**: `sampling-design.md`

#### 8-4. 통계분석 계획

- **Agent**: `@statistical-planner`
- **Task**:
  - 가설별 적합한 통계기법 선정
  - 분석 전제조건 확인 계획
  - 통계 소프트웨어 및 절차 설정
  - 민감도 분석 계획
- **Output**: `statistical-analysis-plan.md`

### 9. 질적연구 설계 경로

#### 9-1. 연구 패러다임 정립

- **Agent**: `@paradigm-consultant`
- **Task**:
  - 인식론적/존재론적 입장 명확화
  - 연구 패러다임 선택 근거
  - 연구자 관점(Reflexivity) 정리
- **Output**: `research-paradigm.md`

#### 9-2. 참여자 선정 전략

- **Agent**: `@participant-selector`
- **Task**:
  - 의도적 표본추출 전략 수립
  - 참여자 선정 기준 설정
  - 포화(Saturation) 기준 설정
  - 접근 및 관계 형성 전략
- **Output**: `participant-selection-strategy.md`

#### 9-3. 자료수집 설계

- **Agent**: `@qualitative-data-designer`
- **Task**:
  - 자료수집 방법 선정 (인터뷰, 관찰, 문서 등)
  - 인터뷰 프로토콜/가이드 개발
  - 관찰 프로토콜 설계
  - 자료수집 일정 계획
- **Output**: `data-collection-protocol.md`

#### 9-4. 분석 전략 수립

- **Agent**: `@qualitative-analysis-planner`
- **Task**:
  - 분석 접근법 선정 (주제분석, 내용분석 등)
  - 코딩 전략 수립
  - 분석 소프트웨어 선정
  - 신뢰성 확보 전략 (삼각검증, 동료검토 등)
- **Output**: `qualitative-analysis-plan.md`

### 10. 혼합연구 설계 경로

#### 10-1. 혼합연구 설계 유형 정교화

- **Agent**: `@mixed-methods-designer`
- **Task**:
  - 설계 유형 세부 명세화
  - 양적/질적 연구의 우선순위 결정
  - 통합 지점(Point of Interface) 설계
  - 시간적 순서 결정
- **Output**: `mixed-methods-design.md`

#### 10-2. 통합 전략 수립

- **Agent**: `@integration-strategist`
- **Task**:
  - 자료 통합 전략 수립
  - 결과 통합 방법 설계
  - 불일치 처리 전략
  - Joint Display 설계
- **Output**: `integration-strategy.md`

### 11. (human) 연구설계 검토 및 승인

- **Checkpoint**: `HITL-4`
- **Display**: 연구설계 문서 전체
- **Options**:
  ```
  [연구설계 검토]
  ○ 승인 - 논문 작성 진행
  ○ 수정 요청 - 피드백 제공
  ○ 재설계 요청 - 다른 접근법으로 재설계

  [세부 조정]
  ☐ 가설/연구질문 수정
  ☐ 표본 설계 변경
  ☐ 분석 방법 변경
  ☐ 자료수집 방법 변경
  ```
- **Command**: `/thesis:approve-design`
- **Output**: `research-design-final.md`
- **Context Reset Point**: 이 시점에서 컨텍스트 리셋 가능

---

## Phase 3: Writing (논문 작성)

### 12. 논문 구조 설정

#### 12-1. (human) 논문 형식 선택

- **Checkpoint**: `HITL-5`
- **Options**:
  ```
  [논문 형식]
  ○ 전통적 5장 구조
    - Ch.1: 서론
    - Ch.2: 이론적 배경/문헌검토
    - Ch.3: 연구방법
    - Ch.4: 연구결과
    - Ch.5: 결론 및 논의

  ○ 3편 논문 형식 (Three-Paper Format)
    - Essay 1: 문헌검토 논문
    - Essay 2: 실증연구 논문 1
    - Essay 3: 실증연구 논문 2

  ○ 모노그래프 형식 (유연한 장 구성)

  [인용 스타일]
  ○ APA 7th Edition
  ○ Chicago/Turabian
  ○ MLA 9th Edition
  ○ Harvard
  ○ 학교/학과 지정 스타일

  [언어]
  ○ 한국어
  ○ 영어
  ○ 한영 병행
  ```
- **Command**: `/thesis:set-format`

### 13. 논문 아웃라인 작성

- **Agent**: `@thesis-architect`
- **Task**:
  - 선택된 형식에 맞는 상세 아웃라인 설계
  - 장별 핵심 내용 및 논증 흐름 설계
  - 절/항 수준의 세부 구조 설계
  - 예상 분량 배분
- **Output**: `thesis-outline.md`

### 14. (human) 아웃라인 승인

- **Checkpoint**: `HITL-6`
- **Display**: 논문 아웃라인 전체
- **Options**:
  ```
  [아웃라인 검토]
  ○ 승인 - 집필 진행
  ○ 수정 요청 - 피드백 제공
  ○ 재구성 요청 - 다른 구조로 재설계

  [세부 조정]
  ☐ 장 순서 변경
  ☐ 특정 장 분할/통합
  ☐ 내용 강조점 조정
  ```
- **Command**: `/thesis:approve-outline`
- **Context Reset Point**: 이 시점에서 컨텍스트 리셋 가능

### 15. 장별 집필

- **Agent**: `@thesis-writer`
- **Task**:
  - 승인된 아웃라인 기반 장별 집필
  - 선행 분석 결과 통합
  - 선택된 인용 스타일 준수
  - 논증의 논리적 전개
  - 학술적 문체 유지
- **Iterative Process**:
  ```
  Ch.1 서론 작성 → 검토 → Ch.2 문헌검토 작성 → 검토 → ...
  ```
- **Output**: `thesis-draft-ch[N].md`

### 16. 품질 검토

- **Agent**: `@thesis-reviewer`
- **Task**:
  - 학술적 엄밀성 검토
  - 논리적 일관성 점검
  - 인용 정확성 검토
  - 문체 및 표현 점검
  - APA/Chicago 스타일 준수 확인
- **Output**: `review-report.md`

### 17. 표절 검사 (최종)

- **Agent**: `@plagiarism-checker`
- **Task**:
  - 전체 논문 초안 표절 검사
  - 부적절한 인용 식별
  - 수정 필요 구간 표시
- **Output**: `final-plagiarism-report.md`

### 18. (human) 초안 검토 및 수정 요청

- **Checkpoint**: `HITL-7`
- **Display**: 논문 초안 전체 + 품질 검토 리포트 + 표절 검사 결과
- **Options**:
  ```
  [검토 결과]
  ○ 승인 - 최종 수정 진행
  ○ 수정 요청 - 피드백 반영
  ○ 특정 장 재작성 요청

  [수정 요청 유형]
  ☐ 특정 부분 보완 (직접 지정)
  ☐ 논증 강화
  ☐ 문헌 추가 인용
  ☐ 분량 조정
  ☐ 문체/어조 변경
  ☐ 표절 의심 구간 수정
  ```
- **Command**: `/thesis:review-draft`

### 19. 최종 논문 완성

- **Agent**: `@thesis-writer`
- **Task**: 피드백 반영하여 최종본 완성
- **Output**: `thesis-final.md`

---

## Phase 4: Publication Strategy (투고 전략)

### 20. 학술지 선정 전략

- **Agent**: `@publication-strategist`
- **Expertise**: 학술 출판 전략 전문가
- **Task**:
  - 연구 주제/방법론에 적합한 학술지 추천 (5-10개)
  - 각 학술지의 특성 분석
    - Impact Factor / SJR / CiteScore
    - 게재 범위(Scope) 적합성
    - 심사 기간
    - 게재율(Acceptance Rate)
    - 게재료(APC) 정보
  - 투고 우선순위 추천
  - 각 학술지별 포맷팅 요구사항 정리
- **Output**: `journal-recommendation.md`

### 21. 투고용 원고 변환

- **Agent**: `@manuscript-formatter`
- **Task**:
  - 선택된 학술지 형식에 맞게 원고 변환
  - Abstract 작성/수정
  - Keywords 선정
  - Highlights/Graphical Abstract 준비
  - Cover Letter 초안 작성
  - Author Guidelines 체크리스트 확인
- **Output**: `submission-package/`

### 22. (human) 투고 전략 검토 및 완료

- **Checkpoint**: `HITL-8`
- **Display**: 학술지 추천 목록 + 투고 패키지
- **Options**:
  ```
  [투고 전략 검토]
  ○ 승인 - 최종 완료
  ○ 다른 학술지 추천 요청
  ○ 투고 패키지 수정 요청
  ```
- **Command**: `/thesis:finalize`
- **Context Reset Point**: 최종 완료

---

## GRA Quality Assurance (품질 보증)

### GroundedClaim Schema

모든 연구 에이전트는 다음 형식으로 클레임을 출력합니다:

```yaml
claims:
  - id: "LIT-001"
    text: "조직 몰입과 직무 성과 간에는 정적 상관관계가 있다"
    claim_type: EMPIRICAL
    sources:
      - type: PRIMARY
        reference: "Meyer & Allen (1991), Journal of Applied Psychology"
        doi: "10.1037/0021-9010.76.6.733"
        verified: true
      - type: PRIMARY
        reference: "Mathieu & Zajac (1990), Psychological Bulletin"
        doi: "10.1037/0033-2909.108.2.171"
        verified: true
    confidence: 92
    effect_size: "r = 0.35 (meta-analytic)"
    uncertainty: "개인 수준 분석에 한정"
```

### 클레임 유형 (ClaimType)

| 유형          | 설명                      | 기대 신뢰도 | 필수 출처          |
| ------------- | ------------------------- | ----------- | ------------------ |
| FACTUAL       | 검증 가능한 객관적 사실   | 95+         | PRIMARY/SECONDARY  |
| EMPIRICAL     | 실증연구 결과             | 85+         | PRIMARY 필수       |
| THEORETICAL   | 이론적 주장               | 75+         | PRIMARY 필수       |
| METHODOLOGICAL| 방법론적 주장             | 80+         | SECONDARY 이상     |
| INTERPRETIVE  | 해석적 주장               | 70+         | 근거 명시          |
| SPECULATIVE   | 추측/제안                 | 60+         | 제한 없음          |

### Hallucination Firewall

생성 시점에서 할루시네이션을 차단하는 규칙:

| 레벨               | 동작             | 패턴 예시                                  |
| ------------------ | ---------------- | ------------------------------------------ |
| **BLOCK**          | 출력 차단        | "모든 연구가 일치", "100%", "예외 없이"    |
| **REQUIRE_SOURCE** | 출처 없으면 차단 | "p < .001", "효과크기 d = X" (단독)        |
| **SOFTEN**         | 경고 + 완화 권고 | "확실히", "명백히", "분명히"               |
| **VERIFY**         | 검증 태그 추가   | "OO가 주장", "일반적으로"                  |

### SRCS 4축 평가

| 축                                 | 설명               | 가중치 (EMPIRICAL 기준) |
| ---------------------------------- | ------------------ | ----------------------- |
| **CS** (Citation Score)            | 출처 점수          | 0.35                    |
| **GS** (Grounding Score)           | 근거 품질 점수     | 0.35                    |
| **US** (Uncertainty Score)         | 불확실성 표현 점수 | 0.10                    |
| **VS** (Verifiability Score)       | 검증가능성 점수    | 0.20                    |

---

## Agent Thinking Process

### CoT (Chain of Thought)

순차적 추론이 필요한 경우:

```
Step 1: [문헌 식별] → Step 2: [내용 분석] → Step 3: [비판적 평가] → Step 4: [종합]
```

### ToT (Tree of Thought)

복수 가설/해석 탐색이 필요한 경우:

```
       Root: 연구질문
      /     |     \
   해석A  해석B  해석C
     |      |      |
   검증    검증   검증
     \      |      /
      최적 해석 선택
```

### Thought Loop (최대 3회)

결론 도달까지 반복 사고:

```
Loop 1: 초기 분석 → 불충분
Loop 2: 추가 탐색 → 보완 필요
Loop 3: 최종 분석 → 결론 도출
(3회 초과 시 LOOP_EXHAUSTED 반환)
```

---

## Agent Failure Handling

에이전트 실패 시 처리 방식:

| 실패 유형               | 설명                     | 처리                        |
| ----------------------- | ------------------------ | --------------------------- |
| `LOOP_EXHAUSTED`        | 3회 사고 후에도 미해결   | 부분 결과 + 실패 지점 명시  |
| `SOURCE_UNAVAILABLE`    | 필수 문헌 접근 불가      | 대체 문헌 탐색 또는 스킵    |
| `INPUT_INVALID`         | 잘못된 입력              | 재입력 요청                 |
| `CONFLICT_UNRESOLVABLE` | 상충되는 연구결과        | 양쪽 견해 병기 + 분석       |
| `OUT_OF_SCOPE`          | 범위 이탈                | 범위 내 결과만 반환         |

---

## Final Outputs (최종 산출물)

```
📁 thesis-output/[연구제목-YYYY-MM-DD]/
├── 📄 session.json                      # 세션 상태 (Context File)
├── 📄 todo-checklist.md                 # 진행 체크리스트 (Todo File)
├── 📁 literature-review-package/        # 문헌검토 패키지
│   ├── 01-literature-search-strategy.md
│   ├── 02-seminal-works-analysis.md
│   ├── 03-research-trend-analysis.md
│   ├── 04-methodology-scan.md
│   ├── 05-theoretical-framework.md
│   ├── 06-empirical-evidence-synthesis.md
│   ├── 07-research-gap-analysis.md
│   ├── 08-variable-relationship-analysis.md
│   ├── 09-critical-review.md
│   ├── 10-methodology-critique.md
│   ├── 11-limitation-analysis.md
│   ├── 12-future-research-directions.md
│   ├── 13-literature-synthesis.md
│   ├── 14-conceptual-model.md
│   └── 15-plagiarism-report.md
├── 📄 research-synthesis.md             # 연구 종합본 (Insights File)
├── 📄 srcs-summary.json                 # SRCS 평가 결과
├── 📄 quality-report.md                 # 품질 보고서
├── 📁 research-design/                  # 연구설계 패키지
│   ├── hypotheses.md
│   ├── research-model-final.md
│   ├── sampling-design.md               # (양적연구)
│   ├── statistical-analysis-plan.md     # (양적연구)
│   ├── research-paradigm.md             # (질적연구)
│   ├── participant-selection-strategy.md# (질적연구)
│   ├── data-collection-protocol.md
│   ├── qualitative-analysis-plan.md     # (질적연구)
│   ├── mixed-methods-design.md          # (혼합연구)
│   └── integration-strategy.md          # (혼합연구)
├── 📄 thesis-outline.md                 # 논문 아웃라인
├── 📁 thesis-drafts/                    # 논문 초안
│   ├── thesis-draft-ch1.md
│   ├── thesis-draft-ch2.md
│   ├── thesis-draft-ch3.md
│   ├── thesis-draft-ch4.md
│   └── thesis-draft-ch5.md
├── 📄 review-report.md                  # 품질 검토 리포트
├── 📄 final-plagiarism-report.md        # 최종 표절 검사
├── 📄 thesis-final.md                   # 최종 논문
├── 📁 submission-package/               # 투고 패키지
│   ├── journal-recommendation.md
│   ├── manuscript-formatted.md
│   ├── cover-letter.md
│   └── submission-checklist.md
└── 📁 learning-portfolio/               # 학습모드 포트폴리오
    ├── learning-progress.json
    ├── practice-exercises/
    └── quiz-results/
```

---

## Claude Code Configuration

### Sub-agents (28개)

```yaml
agents:
  # Phase 0: Input Processing & Learning
  topic-explorer:
    description: "연구 주제 탐색 및 연구질문 도출 전문가"
    expertise: "학술 트렌드, 연구 기회 식별"

  literature-analyzer:
    description: "기존 문헌검토 분석 전문가"
    expertise: "문헌 분석, Gap 식별"

  methodology-tutor:
    description: "연구방법론 튜터 (학습모드)"
    expertise: "연구방법론 교육, 소크라테스식 교수법"
    mode: learning

  practice-coach:
    description: "실습 코치 (학습모드)"
    expertise: "실습 설계, 피드백 제공"
    mode: learning

  assessment-agent:
    description: "학습 평가 에이전트 (학습모드)"
    expertise: "이해도 평가, 학습 진도 추적"
    mode: learning

  # Phase 1: Literature Review (15 Agents)
  literature-searcher:
    description: "학술 데이터베이스 검색 전문가"
    expertise: "검색 전략, PRISMA"
    gra_compliance: true
    claim_prefix: "LS"

  seminal-works-analyst:
    description: "핵심 문헌 분석 전문가"
    expertise: "학술사, 인용 네트워크"
    gra_compliance: true
    claim_prefix: "SWA"

  trend-analyst:
    description: "연구 트렌드 분석 전문가"
    expertise: "계량서지학, 트렌드 분석"
    gra_compliance: true
    claim_prefix: "TRA"

  methodology-scanner:
    description: "선행연구 방법론 스캔 전문가"
    expertise: "연구방법론 분류"
    gra_compliance: true
    claim_prefix: "MS"

  theoretical-framework-analyst:
    description: "이론적 프레임워크 분석 전문가"
    expertise: "이론 분석, 개념화"
    depends_on: [seminal-works-analyst]
    gra_compliance: true
    claim_prefix: "TFA"

  empirical-evidence-analyst:
    description: "실증적 증거 분석 전문가"
    expertise: "메타분석적 종합"
    depends_on: [methodology-scanner]
    gra_compliance: true
    claim_prefix: "EEA"

  gap-identifier:
    description: "연구 갭 식별 전문가"
    expertise: "연구 기회 분석"
    depends_on: [theoretical-framework-analyst, empirical-evidence-analyst]
    gra_compliance: true
    claim_prefix: "GI"

  variable-relationship-analyst:
    description: "변수 관계 분석 전문가"
    expertise: "변수 관계, 인과관계 분석"
    depends_on: [empirical-evidence-analyst]
    gra_compliance: true
    claim_prefix: "VRA"

  critical-reviewer:
    description: "비판적 검토 전문가"
    expertise: "학술 비평"
    depends_on: [gap-identifier]
    gra_compliance: true
    claim_prefix: "CR"

  methodology-critic:
    description: "방법론 비평 전문가"
    expertise: "타당도 평가"
    depends_on: [methodology-scanner]
    gra_compliance: true
    claim_prefix: "MC"

  limitation-analyst:
    description: "한계점 분석 전문가"
    expertise: "연구 한계 분석"
    depends_on: [critical-reviewer, methodology-critic]
    gra_compliance: true
    claim_prefix: "LA"

  future-direction-analyst:
    description: "미래 연구방향 분석 전문가"
    expertise: "연구 어젠다 설정"
    depends_on: [gap-identifier, limitation-analyst]
    gra_compliance: true
    claim_prefix: "FDA"

  synthesis-agent:
    description: "문헌 종합 전문가"
    expertise: "학술 종합, 통합"
    depends_on: [all-wave-3-agents]
    gra_compliance: true
    claim_prefix: "SA"

  conceptual-model-builder:
    description: "개념적 모델 구축 전문가"
    expertise: "개념화, 모델링"
    depends_on: [synthesis-agent]
    gra_compliance: true
    claim_prefix: "CMB"

  # Quality Assurance
  plagiarism-checker:
    description: "표절 검사 전문가"
    expertise: "학술 윤리, 표절 탐지"
    
  unified-srcs-evaluator:
    description: "통합 SRCS 평가 시스템"
    expertise: "품질 검증, 할루시네이션 탐지"

  research-synthesizer:
    description: "연구 결과 종합 및 압축 전문가"
    expertise: "정보 압축, 핵심 추출"

  # Phase 2: Research Design
  hypothesis-developer:
    description: "가설 개발 전문가"
    expertise: "가설 설정, 논리 구조"
    mode: quantitative

  research-model-developer:
    description: "연구모델 개발 전문가"
    expertise: "변수 조작화, 모델 설계"
    mode: quantitative

  sampling-designer:
    description: "표본 설계 전문가"
    expertise: "표본추출, 검정력 분석"
    mode: quantitative

  statistical-planner:
    description: "통계분석 계획 전문가"
    expertise: "통계기법 선정, 분석 설계"
    mode: quantitative

  paradigm-consultant:
    description: "연구 패러다임 컨설턴트"
    expertise: "인식론, 존재론"
    mode: qualitative

  participant-selector:
    description: "참여자 선정 전략가"
    expertise: "의도적 표본추출, 포화"
    mode: qualitative

  qualitative-data-designer:
    description: "질적 자료수집 설계 전문가"
    expertise: "인터뷰, 관찰 프로토콜"
    mode: qualitative

  qualitative-analysis-planner:
    description: "질적 분석 계획 전문가"
    expertise: "코딩, 주제분석"
    mode: qualitative

  mixed-methods-designer:
    description: "혼합연구 설계 전문가"
    expertise: "혼합연구 설계 유형"
    mode: mixed

  integration-strategist:
    description: "자료 통합 전략가"
    expertise: "자료/결과 통합"
    mode: mixed

  # Phase 3: Writing
  thesis-architect:
    description: "논문 구조 설계 전문가"
    expertise: "논문 구성, 논증 설계"

  thesis-writer:
    description: "논문 작성 전문가"
    expertise: "학술적 글쓰기"

  thesis-reviewer:
    description: "논문 품질 검토 전문가"
    expertise: "학술 비평, 편집"

  # Phase 4: Publication
  publication-strategist:
    description: "학술지 투고 전략 전문가"
    expertise: "학술 출판, 저널 선정"

  manuscript-formatter:
    description: "투고용 원고 포맷팅 전문가"
    expertise: "저널 스타일, 투고 요건"

  # Orchestrator
  thesis-orchestrator:
    description: "박사논문 연구 워크플로우 총괄 오케스트레이터"
    expertise: "워크플로우 관리, 상태 추적"
    model: opus
```

### Slash Commands (20개)

```yaml
commands:
  /thesis:init:
    description: "연구 워크플로우 초기화 및 연구유형 선택"
    checkpoint: HITL-0
    action: "3-File Architecture 초기화 + 연구유형 설정"

  /thesis:start:
    description: "박사논문 연구 워크플로우 시작"
    args:
      - name: mode
        type: choice
        options: [topic, question, review, learning]
        default: topic
      - name: input
        type: string
        required: true
    action: "모드별 처리 시작"

  /thesis:learn:
    description: "학습모드 시작/진행"
    args:
      - name: track
        type: choice
        options: [1, 2, 3, 4, 5, 6, 7, 8]
        default: 1
    action: "선택된 학습 트랙 진행"

  /thesis:learn-quiz:
    description: "학습 이해도 퀴즈"
    agent: assessment-agent

  /thesis:learn-practice:
    description: "학습 실습 과제"
    agent: practice-coach

  /thesis:learn-progress:
    description: "학습 진도 확인"
    reads: [learning-progress.json]

  /thesis:set-research-question:
    description: "연구질문/가설 확정"
    checkpoint: HITL-1

  /thesis:review-literature:
    description: "문헌검토 결과 검토"
    checkpoint: HITL-2
    context_reset_point: true

  /thesis:set-research-type:
    description: "연구 유형 최종 확정"
    checkpoint: HITL-3

  /thesis:approve-design:
    description: "연구설계 승인"
    checkpoint: HITL-4
    context_reset_point: true

  /thesis:set-format:
    description: "논문 형식 및 인용 스타일 설정"
    checkpoint: HITL-5

  /thesis:approve-outline:
    description: "논문 아웃라인 승인"
    checkpoint: HITL-6
    context_reset_point: true

  /thesis:review-draft:
    description: "논문 초안 검토"
    checkpoint: HITL-7

  /thesis:finalize:
    description: "최종 검토 및 완료"
    checkpoint: HITL-8
    context_reset_point: true

  /thesis:status:
    description: "현재 워크플로우 진행 상태 확인"
    reads: [session.json, todo-checklist.md]

  /thesis:resume:
    description: "컨텍스트 리셋 후 자동 재개"
    reads: [session.json, todo-checklist.md, research-synthesis.md]
    action: "마지막 완료 지점부터 자동 재개"

  /thesis:check-plagiarism:
    description: "표절 검사 수동 실행"
    agent: plagiarism-checker

  /thesis:evaluate-srcs:
    description: "SRCS 평가 수동 실행"
    agent: unified-srcs-evaluator

  /thesis:journal-search:
    description: "적합 학술지 검색"
    agent: publication-strategist

  /thesis:format-manuscript:
    description: "투고용 원고 변환"
    agent: manuscript-formatter
```

### Execution Configuration

```yaml
execution:
  mode: hybrid

  waves:
    wave-1:
      mode: parallel
      agents:
        - literature-searcher
        - seminal-works-analyst
        - trend-analyst
        - methodology-scanner
      gate: gate-1

    wave-2:
      mode: parallel
      depends_on: wave-1
      agents:
        - theoretical-framework-analyst
        - empirical-evidence-analyst
        - gap-identifier
        - variable-relationship-analyst
      gate: gate-2

    wave-3:
      mode: parallel
      depends_on: wave-2
      agents:
        - critical-reviewer
        - methodology-critic
        - limitation-analyst
        - future-direction-analyst
      gate: gate-3

    wave-4:
      mode: sequential
      depends_on: wave-3
      agents:
        - synthesis-agent
        - conceptual-model-builder
      evaluation: full-srcs

    wave-5:
      mode: sequential
      depends_on: wave-4
      agents:
        - plagiarism-checker
      gate: final-quality-gate

  auto_pause_on: human

  quality_settings:
    priority: quality_over_cost
    token_limit: unlimited
    model_preference: claude-opus

  gra_settings:
    hallucination_firewall: enabled
    cross_validation_gates: enabled
    srcs_threshold: 75
    grounding_rate_threshold: 90
```

### External Memory Configuration

```yaml
external_memory:
  strategy: 3-file-architecture

  files:
    context_file: session.json
    todo_file: todo-checklist.md
    insights_file: research-synthesis.md

  checklist:
    total_steps: 150
    manager: scripts/checklist_manager.py

  context_reset_points:
    - checkpoint: HITL-2
      load: [session.json, literature-synthesis.md, todo-checklist.md]
    - checkpoint: HITL-4
      load: [session.json, research-design-final.md, research-synthesis.md]
    - checkpoint: HITL-6
      load: [session.json, thesis-outline.md, research-synthesis.md]
    - checkpoint: HITL-8
      load: [session.json, thesis-final.md]

  resume_command: /thesis:resume
```

### Error Handling

```yaml
error_handling:
  on_agent_failure:
    action: handle_by_type
    types:
      LOOP_EXHAUSTED:
        action: return_partial
        notify: true
      SOURCE_UNAVAILABLE:
        action: seek_alternative
        fallback: skip_with_note
      INPUT_INVALID:
        action: request_retry
      CONFLICT_UNRESOLVABLE:
        action: present_both_views
      OUT_OF_SCOPE:
        action: return_in_scope_only

  on_research_incomplete:
    action: partial_proceed
    notify: true
    message: "[영역명] 분석이 불완전합니다. 계속 진행하시겠습니까?"

  on_validation_failure:
    action: request_human_review

  on_srcs_below_threshold:
    action: flag_for_review
    threshold: 75

  on_plagiarism_detected:
    action: halt_and_revise
    threshold: 15
    message: "유사도 [X]% 구간이 발견되었습니다. 수정이 필요합니다."
```

---

## Usage Examples

### Example 1: 연구 주제로 시작 (Default Mode)

```
/thesis:start topic 조직 내 심리적 안전감이 혁신 행동에 미치는 영향
```

### Example 2: 연구질문으로 시작

```
/thesis:start question "디지털 전환이 중소기업의 조직 학습에 미치는 영향은 무엇인가?"
```

### Example 3: 기존 문헌검토 활용

```
/thesis:start review [기존 문헌검토 파일 첨부]
```

### Example 4: 학습모드 시작

```
/thesis:start learning
/thesis:learn track 4  # 양적연구 방법론 학습
```

### Example 5: 컨텍스트 리셋 후 재개

```
/thesis:resume
```

### Example 6: 진행 상태 확인

```
/thesis:status
```

### Example 7: 학술지 검색

```
/thesis:journal-search
```

---

## 150-Step Workflow Checklist

전체 워크플로우는 150개 세부 단계로 구성되며, `todo-checklist.md`에서 추적됩니다.

### 단계 구성 요약

| Phase                        | 단계 수 | 설명                    |
| ---------------------------- | ------- | ----------------------- |
| Phase 0                      | 8       | 세션 초기화             |
| Phase 0-A (Topic Mode)       | 6       | 주제 탐색               |
| Phase 0-D (Learning Mode)    | 20      | 학습모드 (별도 트랙)    |
| HITL-1                       | 4       | 연구질문 확정           |
| Wave 1                       | 16      | 기초 문헌 탐색          |
| Wave 2                       | 16      | 심층 분석               |
| Wave 3                       | 16      | 비판적 분석             |
| Wave 4                       | 8       | 종합 및 통합            |
| Wave 5                       | 4       | 품질 보증               |
| HITL-2                       | 6       | 문헌검토 검토           |
| Phase 2 Design               | 20      | 연구설계                |
| HITL-3/4                     | 8       | 연구유형/설계 확정      |
| Phase 3 Writing              | 24      | 논문 작성               |
| HITL-5/6/7                   | 12      | 형식/아웃라인/초안 검토 |
| Phase 4 Publication          | 8       | 투고 전략               |
| HITL-8                       | 4       | 최종 완료               |

---

## Version History

| Version | Date       | Changes                                                                                           |
| ------- | ---------- | ------------------------------------------------------------------------------------------------- |
| 1.0.0   | 2026-01-18 | Initial release - 설교연구 워크플로우 기반 박사논문 연구 지원 시스템, GRA Architecture, 4가지 입력모드, 학습모드, 양적/질적/혼합연구 지원, 표절검사, 학술지 투고 전략 |
