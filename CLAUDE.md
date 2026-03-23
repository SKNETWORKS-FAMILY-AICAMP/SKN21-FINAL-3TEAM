# WorkFlow Agent (듀듀) — 프로젝트 컨텍스트

## 작업 참고 문서

작업 전 반드시 아래 문서를 확인할 것:

- `docs/logs/` — **팀원별 작업 로그** (이전 세션에서 뭘 했는지 확인)
  - `jiyong.md` / `ai-경은.md` / `ai-승언.md` / `backend-혜빈.md` / `frontend-지영.md`
- `README.md` — **프로젝트 소개 및 전체 개요** (세션 시작 시 반드시 참고)
- `docs/TASK_BOARD.md` — **일일 작업 기준 문서** (이슈 목록, 체크리스트, 담당자, 단계별 할 일)
- `docs/역할분배_기술스택_v5_final.md` — 기술 결정 배경, 멘토 피드백, 아키텍처 상세 (수정하지 않음)

## 세션 시작 시 규칙

1. `git config user.name`으로 사용자 자동 인식:
   - `sjy361872` → 신지용 (PM)
   - `ykgstar37-lab` → 윤경은 (AI서브)
   - `jse8406` → 진승언 (AI리드)
   - `hyebinhy` → 안혜빈 (Backend)
   - `moon-613` → 문지영 (Frontend)
   - 매핑 안 되면 현재 브랜치로 판단, 그래도 안 되면 직접 질문
2. 해당 팀원의 `docs/logs/{이름}.md`를 읽고 이전 작업 맥락 파악
3. PM(지용)인 경우 다른 팀원 로그도 필요 시 확인

## 세션 종료 시 규칙

**사용자가 "끝" 이라고 입력하면:**

1. `git config user.name`으로 현재 사용자 확인
2. 이번 세션에서 한 작업을 정리하여 `docs/logs/{이름}.md`에 추가:
   - 날짜
   - 한 일 (구체적으로)
   - 다음 할 일
3. 사용자에게 커밋/push 여부 확인 후 진행

## 개발 전략

**LLM API 먼저 → sLLM은 나중에**

```
1. LLM API(GPT/Claude)로 전체 기능 먼저 구현
2. 실제 동작 확인하면서 input/output 형태 확정
3. 확정된 형태에 맞춰 데이터 수집 (4단계)
4. 파인튜닝 → sLLM(vLLM) 교체 (모델만 갈아끼우면 됨)
```

- Agent 코드는 LLM 호출 인터페이스만 바꾸면 되는 구조 (#39 공통 모듈)
- 파인튜닝 관련 이슈(#9,#10,#11,#14,#16,#41)는 4단계에서 진행

## 팀원 매핑

| 이름 | 역할 | GitHub 라벨 | 브랜치 | GitHub ID |
|------|------|-------------|--------|-----------|
| 신지용 | PM + Intent + 오케스트레이션 | `지용:PM` | `feat/jiyong` | sjy361872 |
| 윤경은 | AI서브 (LLM API + 판단 Agent + RAG) | `경은:AI서브` | `feat/ai-경은` | ykgstar37-lab |
| 진승언 | AI리드 (문서 Agent + 파서 + 템플릿) | `승언:AI리드` | `feat/ai-승언` | jse8406 |
| 안혜빈 | Backend + DB + 인증 + Google Services | `혜빈:Backend` | `feat/backend-혜빈` | hyebinhy |
| 문지영 | Frontend 전담 | `지영:Frontend` | `feat/frontend-지영` | moon-613 |

## 마일스톤 구조

| # | 마일스톤 | 핵심 이슈 |
|---|---------|----------|
| 1 | 1단계: 설계 및 환경 세팅 | #2 API 스키마, #3 AgentState, #7 모델 비교, #15 Docling, #19 DB, #24 Figma |
| 2 | 2단계: 기반 개발 + LLM API 연동 | #4 Intent 데이터, #8 RAG, #39 LLM API 모듈, #40 doc LLM, #20 JWT, #25 #26 UI |
| 3 | 3단계: Agent 개발 + 핵심 기능 | #5 #6 Intent+오케스트레이터, #12 판단Agent, #17 문서Agent, #22 일정Agent, #27 #28 UI, #33 #34 #35 Google |
| 4 | 4단계: 데이터 수집 + 파인튜닝 | #9 #10 판단데이터+LoRA v1, #14 #16 문서데이터+LoRA v2, #11 vLLM, #41 추가수집 |
| 5 | 5단계: 통합 및 테스트 | #30 E2E, #13 #18 성능평가, #29 관리자UI |
| 6 | 6단계: 배포 및 마무리 | #31 AWS 배포 |

## GitHub 이슈 컨벤션

### 이슈 제목 형식
```
[X-N] 이슈 제목
```
- X = 담당자 코드: A(지용), B(경은), C(승언), D(혜빈), E(지영)
- N = 해당 담당자의 순번

### 라벨 규칙
- **담당자 라벨**: `지용:PM`, `경은:AI서브`, `승언:AI리드`, `혜빈:Backend`, `지영:Frontend`
- **단계 라벨**: `1단계:설계`, `2단계:기반+LLM`, `3단계:Agent`, `4단계:파인튜닝`, `5단계:통합`, `6단계:마무리`
- **우선순위**: `priority:높음`, `priority:보통`, `blocker`

### 이슈 생성 시
1. 제목: `[X-N]` 접두사 필수
2. 라벨: 담당자 + 단계 + 우선순위
3. 마일스톤: 해당 단계에 맞는 마일스톤 지정
4. 담당자(assignee): GitHub ID로 지정

## Git 브랜치 / 커밋 규칙

### 브랜치
```
main (배포용 - PM 지용만 머지)
 └── develop (통합 개발)
      ├── feat/jiyong
      ├── feat/ai-경은
      ├── feat/ai-승언
      ├── feat/backend-혜빈
      └── feat/frontend-지영
```

- develop push 전 반드시 사용자에게 확인 (자동 push 금지)
- main 직접 커밋 금지 — develop → main은 PM만
- 충돌은 자기 브랜치에서 해결

### 커밋 형식
```
<type>: <설명> #이슈번호

feat:     새 기능
fix:      버그 수정
hotfix:   긴급 수정 (develop 직접 허용, 슬랙 공유 필수)
docs:     문서 수정
refactor: 리팩토링
test:     테스트
chore:    설정/환경
```

### PR 규칙
- PR 제목: 커밋 형식과 동일
- PR 본문: 변경사항 요약 + 테스트 방법 + `Closes #이슈번호`
- 머지 방식: Squash and merge

## 프로젝트 구조

```
backend/app/          — FastAPI 백엔드 (혜빈)
  api/v1/             — REST API (chat, auth, documents, meetings, schedules, calendar, google_connect, tasks, gmail, sheets, regulations, admin)
  models/             — ORM 모델 (12개 테이블)
  services/           — 비즈니스 로직 (Google Services 포함)
  schemas/            — Pydantic 스키마

ai/                   — AI/ML 모듈
  agents/             — LangGraph Agent (지용: orchestrator, 경은: judgment, 승언: document, 혜빈: schedule)
  llm/                — LLM 공통 모듈 (factory, openai/anthropic/vllm provider, prompts)
  rag/                — RAG 파이프라인 (경은: hybrid_search, reranker, vectorstore)
  templates/          — 문서 템플릿 (승언: 회의록, 보고서, JD, 제안서)
  document_parser/    — 문서 파싱 (Docling, PaddleOCR, DOCX)
  skills/             — 문서 생성 스킬 (회의록, 보고서, 제안서)
  finetuning/         — LoRA 학습 (4단계)
  serving/            — vLLM 클라이언트 (4단계)

frontend/src/         — React 프론트엔드 (지영)
  components/         — UI 컴포넌트 (chat, dashboard, documents, meetings, schedules, auth, admin)
  pages/              — 11개 페이지 (MeetingMinutesPage, DocumentGeneratePage 포함)
  store/              — Zustand (auth, chat, ui, google, scheduleType)
  hooks/              — useAuth, useSSE, useChat, useGoogleServices
```

## 기술 스택 요약

| 영역 | 기술 |
|------|------|
| AI | LangGraph, GPT/Claude API (현재) → vLLM + LoRA (추후), Qdrant, BM25, bge-reranker |
| Backend | FastAPI + SSE, PostgreSQL, SQLAlchemy + Alembic, JWT, Google OAuth 2.0 |
| Frontend | React (Vite), Zustand, TanStack Query, Tailwind + shadcn/ui, FullCalendar |
| Infra | AWS (EC2+S3+RDS), Docker, GitHub Actions, RunPod (A100) |

## Compact Instructions

컨텍스트 압축 시 반드시 보존할 것:

- 현재 작업 중인 파일 목록 및 수정 내역
- 테스트/빌드 실행 결과 (성공/실패 여부, 에러 메시지)
- Intent 분류 체계 (8종) 및 Agent 라우팅 로직
- 현재 사용자가 누구인지 (팀원 매핑 결과)
- 세션에서 내린 아키텍처/설계 결정사항
- 진행 중인 이슈 번호 및 작업 맥락
- Google Services 연동 패턴 (OAuth, 4개 서비스 구조)

## 금지 사항

- `git push --force` 금지
- `git reset --hard` 금지
- main에 직접 push 금지 — develop → main은 PM만
- develop 직접 push — **초기 단계 한정 허용**, 추후 PR 방식으로 전환 시 금지
- **커밋/push는 반드시 사용자 확인 후 실행** (자동 커밋 금지)
- `.env`, `credentials.json` 등 시크릿 파일 커밋 금지
- `node_modules/`, `__pycache__/`, `.venv/` 커밋 금지
