# Document Agent 리팩토링 변경 기록

- **작업일**: 2026-02-22
- **담당**: 신지용 (PM)
- **목적**: meeting_generate 제거, doc_summary + doc_qa 추가 → 문서 검색/생성/요약/QA 4기능 체계

---

## 변경 요약

| Before (7개 intent) | After (8개 intent) |
|---|---|
| judgment | judgment |
| doc_search | doc_search |
| doc_generate | doc_generate (회의록 포함) |
| meeting_generate (삭제) | doc_summary (신규) |
| schedule_add | schedule_add |
| schedule_view | schedule_view |
| general | general |
| - | doc_qa (신규) |

### 핵심 변경점
- `meeting_generate` intent **제거** → `doc_generate`의 `meeting_minutes` 템플릿으로 통합
- `doc_summary` intent **신규** — 문서 요약 (document_content 또는 extracted_text 기반)
- `doc_qa` intent **신규** — 문서 내용 기반 질의응답 (RAG + LLM)
- BERT weights **비활성화** → fallback 모드 강제 (8라벨 재학습은 experiments_v2에서 별도)

---

## 수정 파일 목록 (12개)

### AI Layer (6개)

| 파일 | 변경 내용 |
|------|----------|
| `ai/agents/state.py` | `document_id`, `document_content` 필드 추가, intent 주석 업데이트 |
| `ai/llm/prompts.py` | `DOC_SUMMARY_SYSTEM_PROMPT`, `DOC_QA_SYSTEM_PROMPT` 추가 |
| `ai/agents/intent_classifier.py` | 8개 라벨, LLM 프롬프트, 임베딩 예시, KNOWN_OVERRIDES 업데이트 |
| `ai/models/intent_classifier/label_map.json` | 8개 id2label/label2id 매핑 |
| `ai/agents/document_agent.py` | 핵심 리팩토링 (아래 상세) |
| `ai/agents/orchestrator.py` | 라우팅: `doc_summary`, `doc_qa` → document_agent |

### Backend (2개)

| 파일 | 변경 내용 |
|------|----------|
| `backend/app/schemas/chat.py` | `ChatRequest`에 `document_id` 추가, `MeetingResultData` 삭제, `DocSummaryResultData`/`DocQAResultData` 신규 |
| `backend/app/api/v1/chat.py` | 라우팅 업데이트, `_build_initial_state`에 `template_type`/`document_id`/`document_content` 추가, document_id DB 로딩 |

### Frontend (3개)

| 파일 | 변경 내용 |
|------|----------|
| `frontend/src/utils/constants.js` | 8개 intent 타입/라벨/아이콘, 추천 질문 업데이트 |
| `frontend/src/components/chat/AgentIndicator.jsx` | `doc_summary`, `doc_qa` agent config 추가 |
| `frontend/src/components/admin/SystemStats.jsx` | 통계 색상/라벨 업데이트, `meeting` 분류 로직 제거 |

### Tests (1개)

| 파일 | 변경 내용 |
|------|----------|
| `tests/test_document_agent.py` | meeting_generate 테스트 → doc_generate(meeting_minutes)로 변경, doc_summary/doc_qa 테스트 추가 |

### 기타

| 파일 | 변경 내용 |
|------|----------|
| `ai/models/intent_classifier/model.safetensors` | → `model.safetensors.bak_7label`로 이름 변경 (fallback 강제) |

---

## document_agent.py 상세 변경

### 제거
- `_handle_meeting_generate()` 함수 삭제

### 추가
- `_detect_template_type(user_input)` — 키워드 기반 템플릿 자동 감지 (회의록/JD/제안서/보고서)
- `_generate_meeting_minutes(user_input)` — 회의록 전용 생성 (doc_generate 내부 분기)
- `_handle_doc_summary()` — 문서 요약 (stream_pending 패턴 지원)
- `_handle_doc_qa()` — 문서 QA (RAG 검색 + JSON/스트리밍 모드)
- `_build_sources()` — 출처 정보 구성 공통 유틸 (doc_search, doc_qa 공유)

### 라우팅 로직
```
doc_generate 진입 시:
  1. state.template_type 확인 (프론트에서 전달)
  2. 없으면 _detect_template_type()로 키워드 감지
  3. meeting_minutes이면 _generate_meeting_minutes() 호출
  4. 나머지는 기존 doc_generate 로직

doc_summary 진입 시:
  1. document_content = state.document_content || state.extracted_text
  2. 없으면 "문서를 선택해주세요" 안내
  3. stream_mode면 stream_pending 반환 (chat.py에서 스트리밍)

doc_qa 진입 시:
  1. context 비어있으면 RAG 검색
  2. stream_mode면 자연어 답변 스트리밍 + sources는 result 이벤트
  3. 비스트리밍이면 JSON mode (answer, citations, confidence)
```

---

## doc_search vs doc_qa 구분

| | doc_search | doc_qa |
|---|---|---|
| 목적 | 문서 **찾기** | 문서 내용 기반 **답변** |
| 입력 예시 | "마케팅 문서 찾아줘" | "지난 회의 결정사항이 뭐야?" |
| 출력 | 문서 목록 + 요약 | 답변 + 인용 + 신뢰도 |

---

## 검증 결과

| 테스트 | 결과 |
|--------|------|
| Test 1: doc_search | PASS |
| Test 2: doc_generate (report) | PASS |
| Test 3: doc_generate (meeting_minutes) | PASS |
| Test 4: doc_summary (content 있음) | PASS |
| Test 4-1: doc_summary (content 없음 → 안내) | PASS |
| Test 4-2: doc_summary (extracted_text fallback) | PASS |
| Test 5: doc_qa | PASS |
| Test 6: risk_detect | PASS |
| 파일 간 일관성 (AI/Backend/Frontend) | PASS |
| BERT fallback 모드 | PASS |

---

## 후속 작업

- [ ] experiments_v2에서 8개 라벨 BERT 재학습
- [ ] doc_qa의 category 필터 (규정 vs 업무 문서 구분)
- [ ] doc_summary 프론트엔드 UI (문서 선택 → document_id 전송)
- [ ] 실제 Solar API 연동 E2E 테스트
