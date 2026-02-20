# 작업 로그 — 진승언 (AI 리드)

> 세션 종료 시 Claude가 자동으로 업데이트합니다.

---

## 2026-02-12 (수)

### 작업 내용

#### 1. Document Agent State 전달 확인 및 검증
- **목적**: Orchestrator에서 Document Agent로 State가 제대로 전달되는지 확인
- **작업 상세**:
  - `document_agent.py` 코드 분석 (intent 분기, LLM 호출 구조 확인)
  - `orchestrator.py` 분석 (safe_document_agent wrapper를 통한 state 전달 확인)
  - `state.py` TypedDict 정의 확인

#### 2. 테스트 코드 작성 및 실행
- **파일 생성**:
  - `test_document_agent.py` — Document Agent 단독 테스트 (성공)
  - `test_orchestrator_document.py` — Orchestrator 통합 테스트 (Intent Classifier 모델 없음으로 실패)
  - `test_orchestrator_document_direct.py` — Intent 직접 설정 테스트 (성공)

- **테스트 결과**:
  - ✅ Document Agent 단독 동작: 정상 (Solar API 호출 성공)
  - ✅ State 전달: 완벽 (intent, user_input, context, template_id, source_page, template_fields 모두 전달됨)
  - ✅ Agent Response 생성: 정상 (doc_search, doc_generate, meeting_generate 모두 동작)
  - ❌ Intent Classifier: 모델 없음 (`ai/models/intent_classifier` 경로에 weights 없음)

#### 3. 발견한 이슈
1. **Intent Classifier 모델 미구현** (blocker)
   - 현재 fallback 모드로 모든 입력이 `general` intent로 분류됨
   - Confidence 0.0 → `clarify` 노드로 라우팅되어 Document Agent까지 도달 안함
   - 해결 방안: Issue #4 (Intent 학습 데이터) 기반 모델 학습 필요

2. **Windows 콘솔 인코딩 이슈** (minor)
   - 한글 출력 시 깨짐 (cp949 인코딩)
   - UTF-8 출력 필요 시 별도 처리 필요

#### 4. 검증 완료 사항
- ✅ Orchestrator → Document Agent State 전달 메커니즘 정상
- ✅ Document Agent의 intent 분기 로직 정상 (doc_search, doc_generate, meeting_generate)
- ✅ Solar API (LLM) 호출 정상
- ✅ AgentState TypedDict 구조 적절

### 다음 할 일

1. **Intent Classifier 모델 학습 (Priority: 높음)**
   - Issue #4 데이터셋 확인
   - `klue/bert-base` 파인튜닝
   - `ai/models/intent_classifier/` 경로에 모델 저장
   - 7개 카테고리 분류: judgment, doc_search, doc_generate, meeting_generate, schedule_add, schedule_view, general

2. **Document Agent 개선**
   - RAG Context 연동 (현재는 mock context 사용)
   - 템플릿 렌더링 구현 (`BaseTemplate.render()` 메서드)
   - 리스크 감지 로직 구현 (`_handle_risk_detect`)

3. **테스트 코드 정리**
   - 3개 테스트 파일 통합 or 용도별 분리
   - CI/CD 파이프라인에 테스트 추가

4. **문서 작업 (Issue #17)**
   - 템플릿 시스템 완성 (회의록, 보고서, JD, 제안서)
   - Docling 파서 통합

---

## 2026-02-19 (목)

### 작업 내용

#### 1. Judgment Agent 빈 응답 버그 수정
- **원인**: `judgment_agent.py`가 `agent_response`에 `message` 필드를 포함하지 않아 프론트에 빈 응답 전달
- **수정**: `parsed["message"] = parsed.get("reasoning", "")` 추가 (`judgment_agent` 함수)
- **파일**: `ai/agents/judgment_agent.py`

#### 2. 출처 "제목 없음" 버그 수정
- **원인**: `hybrid_search.py`가 검색 결과 조립 시 `title`, `chapter`, `article` 메타데이터를 3곳에서 모두 드롭
  - `_bm25_search` 결과, RRF 합산 루프(BM25/Vector), 최종 반환 모두 `source`만 유지
- **수정**: 3곳 모두 `title`, `chapter`, `article` 필드 추가 전달
- **파일**: `ai/rag/hybrid_search.py`, `ai/agents/document_agent.py`

#### 3. 통합 requirements.txt 생성
- **원인**: `Dockerfile.backend`가 `ai/requirements.txt`를 설치하지 않아 배포 시 `langgraph`, `torch` 등 누락
- **수정**: `backend/requirements.txt` + `ai/requirements.txt` 합본을 프로젝트 루트 `requirements.txt`로 생성
- **파일**: `requirements.txt` (신규 생성)

#### 4. AWS 배포 준비 (git clone 방식)
- Linux 배포 스크립트 `run.sh` 생성 (프로젝트 루트)
  - PYTHONPATH 자동 설정, `.venv` 활성화, `--workers 2` 프로덕션 설정
- **파일**: `run.sh` (신규 생성)

### 다음 할 일

1. EC2에서 git clone 후 배포 실행 및 동작 확인
2. RDS 연결 및 alembic 마이그레이션 확인
3. Google OAuth 콜백 URL EC2 IP로 업데이트

---
