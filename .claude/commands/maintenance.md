---
description: "Hook 시스템 주기적 건강 검진 및 정리"
---

## Setup Maintenance 점검 결과 분석

`.claude/hooks/setup.maintenance.log` 파일을 분석하고 필요한 정리 작업을 수행합니다.

### 분석 프로토콜:

**1단계 — 로그 읽기:**
`.claude/hooks/setup.maintenance.log`를 Read tool로 읽으세요.
파일이 없으면 사용자에게 안내: "`claude --maintenance`로 Maintenance Hook을 먼저 실행해야 합니다."

**2단계 — 항목별 분석:**

**P1 원칙**: 아래 표시 정보는 모두 `setup_maintenance.py`가 **결정론적으로 사전 계산**하여 로그에 포함합니다. 에이전트는 로그에서 읽어 사용자에게 **그대로 전달**하세요. 직접 파일을 세거나 크기를 계산하지 마세요.

| 항목 | WARN/FAIL 시 조치 | 로그에 포함된 표시 정보 |
|------|------------------|---------------------|
| **Session archives** | 30일 초과 아카이브 목록 제시 → AskUserQuestion으로 삭제 범위 확인 | 대상 파일 수, 총 크기(KB), 최오래 3개·최신 3개 파일명 |
| **Knowledge index** | 잘못된 JSON 라인 번호 확인 → 해당 라인 제거 제안 | 전체 라인 수, 잘못된 라인 번호·내용 미리보기(첫 80자) |
| **Work log** | 1MB 초과 시 이전 로그 정리 제안 (백업 후 삭제) | 현재 크기(KB), 라인 수, 최초·최종 기록 타임스탬프 |
| **Script syntax** | 오류 있는 스크립트를 Read → 수정 | 오류 파일명, 라인 번호, 에러 메시지 |
| **Doc-code sync** | 코드 상수와 문서 값의 불일치 — WARN 메시지에 표시된 파일과 값을 확인 후, 문서 또는 코드를 일치하도록 수정 | 불일치 파일 쌍, 코드 값 vs 문서 값 |
| **verification-logs/** | 30일 초과 검증 로그 정리 제안 | 대상 파일 수, 총 크기(KB), 최오래 3개 파일명 |
| **pacs-logs/** | 30일 초과 pACS 로그 정리 제안 | 대상 파일 수, 총 크기(KB), 최오래 3개 파일명 |
| **autopilot-logs/** | 30일 초과 Decision Log 정리 제안 | 대상 파일 수, 총 크기(KB), 최오래 3개 파일명 |

**3단계 — 정리 작업 (사용자 승인 필수):**

⚠️ **절대 삭제 금지 대상:**
- `knowledge-index.jsonl` — RLM Knowledge Archive (세션 간 지식)
- `latest.md` — 최신 스냅샷 (세션 복원 기반)

삭제 가능 대상 (사용자 확인 후):
- `sessions/*.md` — 30일 초과 세션 아카이브
- `work_log.jsonl` — 비정상적으로 큰 작업 로그 (백업 후)

**4단계 — 최종 보고:**
```
## Maintenance 결과

### 건강 상태 요약
- 전체: N개 항목
- 정상: N개
- 이슈: N개

### 수행한 정리 작업
- [작업 내용] → [결과]

### 시스템 상태
- Context Preservation System: [정상 / 주의 필요]
- Knowledge Archive: [N entries, NKB]
- Session Archives: [N files, NKB]
```

### 권장 실행 주기:
- **주간**: 일반적인 사용 빈도
- **수시**: Hook 스크립트 수정 후, 또는 세션 복원 이상 시
