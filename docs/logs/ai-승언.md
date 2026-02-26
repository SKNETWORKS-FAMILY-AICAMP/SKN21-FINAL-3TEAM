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

## 2026-02-19 (목) — 2차 세션

### 작업 내용

#### 1. GitHub Actions CI/CD 구축 (`.github/workflows/deploy.yml`)
- develop 브랜치 push 시 EC2에 자동 배포되도록 설정
- `appleboy/ssh-action@v1.0.3` 사용
- GitHub Secrets 등록: `EC2_HOST`, `EC2_USER`, `EC2_KEY`
- **문제 해결 과정**:
  - `status=143 (SIGTERM)` 반복 발생 → `disown` → `setsid` 시도 모두 실패
  - 근본 원인: SSH 세션 종료 시 프로세스 그룹 전체에 SIGTERM 전달
  - **최종 해결**: `nohup` 방식 포기 → `sudo systemctl restart workflow-agent` 방식으로 전환

#### 2. systemd 서비스 설정 (`/etc/systemd/system/workflow-agent.service`)
- EC2 재부팅 시 uvicorn 자동 시작 + 크래시 시 자동 재시작
- `start.sh` 스크립트 생성 (EC2 프로젝트 루트)
  - `PYTHONPATH` 설정 포함 (`프로젝트루트:프로젝트루트/backend`)
  - `exec uvicorn` 절대 경로 사용
- **문제 해결**: `status=127` → `start.sh` 파일이 EC2에 없었던 것이 원인

#### 3. `ModuleNotFoundError: No module named 'app'` 해결
- **원인**: `backend/app/main.py` 내부에서 `from app.config import ...` 사용 중인데 PYTHONPATH에 `backend/` 경로 누락
- **수정**: `PYTHONPATH`에 `/home/ubuntu/SKN21-FINAL-3TEAM/backend` 추가
- **적용 위치**: `start.sh`, `deploy.yml`

#### 4. EC2 GitHub SSH 인증 설정
- `git pull` 시 `fatal: could not read Username` 에러 발생
- EC2에서 SSH 키 생성 후 GitHub Deploy Key 등록
- git remote URL을 HTTPS → SSH 방식으로 변경

#### 5. sudo 권한 설정
- ubuntu 사용자가 비밀번호 없이 서비스 재시작 가능하도록 설정
- `/etc/sudoers.d/workflow-agent` 추가

#### 6. 프론트엔드 API 엔드포인트 EC2로 변경
- **파일**: `frontend/vite.config.js`
- `localhost:8000` → `3.37.118.197:8000` (EC2 퍼블릭 IP)
- 로컬 개발 환경에서 EC2 백엔드로 테스트 가능

#### 7. RDS SSL 연결 에러 해결
- **에러**: `no pg_hba.conf entry for host ... no encryption`
- **원인**: RDS 연결 시 SSL 미적용
- **수정**: `.env`의 `DATABASE_URL` 끝에 `?ssl=require` 추가

#### 8. server.log 타임스탬프 추가
- `start.sh` 수정: uvicorn 출력을 `while read` 파이프로 받아 타임스탬프 붙여 `server.log`에 저장

### 다음 할 일

1. **Alembic 마이그레이션 실행** (`alembic upgrade head`) — `relation "users" does not exist` 에러 해결 필요
2. Google OAuth 콜백 URL EC2 IP로 업데이트
3. 전체 E2E 동작 확인 (로그인 → 채팅 → RAG 검색)

---

## 2026-02-24 (월)

### 작업 내용

#### 1. 문서 요약 (doc_summary) 환각 버그 수정
- **원인 1**: `_extract_docx`가 `doc.paragraphs`만 순회, 테이블 내용 누락
- **수정**: `doc.tables` 순회 추가 + 빈 단락 필터링 + 디버그 print 추가
- **원인 2**: `_handle_doc_summary`에서 `document_content` 없을 때 `user_input` fallback 사용 → LLM이 짧은 쿼리를 문서로 인식해 환각 생성
- **수정**: `user_input` fallback 완전 제거, 대신 `doc_pick` 마커 반환
- **파일**: `backend/app/services/document_service.py`, `ai/agents/document_agent.py`

#### 2. Intent 신뢰도 임계값 하향 조정
- **문제**: confidence 0.8인 의도도 clarify UI 재질문 발생
- **수정**: `INTENT_CONFIDENCE_THRESHOLD` 0.85 → 0.75
- **파일**: `ai/agents/config.py`

#### 3. doc_pick 기능 구현 (문서 선택 UI)
- **기능**: 파일 업로드 없이 문서 요약 요청 시 Qdrant 문서 목록 리스트 표시, 선택 시 해당 문서 요약 진행
- **구현**:
  - `_handle_doc_summary`: `document_content` 없을 때 `get_qdrant_pipeline().list_documents()` 호출 → `doc_pick` 타입 반환
  - `chat.py`: `doc_pick` 타입 수신 시 Qdrant 목록 그대로 사용 (DB 조회 제거)
  - `ChatPage.jsx`: `doc_pick` case 추가 — 문서 버튼 클릭 시 `setSelectedDocument` + `onSelectClarify` 호출, `max-h-64 overflow-y-auto` 스크롤 적용
- **파일**: `ai/agents/document_agent.py`, `backend/app/api/v1/chat.py`, `frontend/src/pages/ChatPage.jsx`

#### 4. Qdrant `list_documents_by_source` 구현
- offset 기반 페이지네이션으로 전체 포인트 수집
- `document_id` 기준 중복 제거 (청크 → 고유 문서)
- `scope="personal"` 문서는 본인 것만 포함 (`user_id` 필터)
- **파일**: `ai/rag/qdrant_store.py`, `ai/rag/qdrant_pipeline.py`

#### 5. Qdrant document_id=None 포인트 재인덱싱
- **문제**: `seed_sample_documents.py`가 Qdrant 직접 저장 시 `document_id` 미포함 → `list_documents_by_source`에서 스킵됨
- **원인 분석**: 86개 포인트 중 83개 `document_id=None`, 3개만 유효 (UI 업로드 경로만 `document_id` 포함)
- **해결**: `ai/tests/reindex_documents.py` 스크립트 작성 및 실행 → 19개 문서 DB 신규 생성 + Qdrant 재인덱싱 완료 (document_id 22~40)
- **파일**: `ai/tests/reindex_documents.py` (신규)

### 다음 할 일

1. **doc_pick 선택 후 요약 플로우 검증** — 선택한 문서가 실제로 요약되는지 E2E 확인
2. **clarify 플로우 state 손실 문제 해결** — clarify 선택 시 원본 쿼리 및 `document_id` 유실 문제
3. **doc_qa 검색 품질 개선** — Qdrant RAG 검색 결과 정확도 확인

---
