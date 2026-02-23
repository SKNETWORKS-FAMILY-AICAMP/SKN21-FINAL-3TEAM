# 작업 로그 — 윤경은 (AI 서브)

> 세션 종료 시 Claude가 자동으로 업데이트합니다.

---

## 2026-02-11 (화)

**모델 벤치마크 테스트셋 + 스크립트 구현 (#7):**
- 벤치마크 테스트셋 70개 생성 (judgment 21, qa 16, meeting 16, summary 5, risk 5, korean 7)
- `run_benchmark.py` 전체 구현 (4-bit 추론 + 자동 평가 + 비교 리포트 생성)
- 평가 4축: 한국어, 규정해석, 판단형식, 속도
- RunPod 셋업/실행 스크립트 추가 (`runpod_setup.sh`, `runpod_run_all.sh`)
- 사내규정 PDF + 판단 1,000건 + 규정 Q&A 500건 데이터 추가

**벤치마크 테스트셋 QA (#7):**
- judgment 21개: input에 규정 조항 + 근거 텍스트 추가 (RAG 실서비스와 동일 형태)
- regulation_qa 16개: input에 관련 규정 조항명 추가
- 실서비스에서 RAG가 규정 원문을 붙여주는 것과 동일한 조건으로 평가하도록 수정

**벤치마크 스크립트 리팩토링 (커밋 완료):**
- `scripts/` 루트의 벤치마크 파일들을 `scripts/benchmark/` 패키지로 재구성
- `benchmark_config.yaml` → `config.yaml`, `run_benchmark.py` → `run.py`, `create_benchmark_testset.py` → `create_testset.py`
- `regulation_texts.py` 분리, `__init__.py` 추가
- `benchmark_testset.jsonl` 업데이트 (70 → 115건으로 확장)

**3개 모델 벤치마크 실행 완료 (RunPod):**
- EXAONE-3.5-7.8B / Kanana-1.5-8B / Qwen3-8B 벤치마크 실행 (테스트셋 87개)
- 평가 4축 결과 (가중치: 한국어 0.2, 규정해석 0.35, 판단형식 0.25, 속도 0.2):
  - 1위 Kanana-1.5-8B (종합 0.652) — 규정해석·속도·JSON유효율 우수
  - 2위 EXAONE-3.5-7.8B (종합 0.597) — 한국어·속도 최고
  - 3위 Qwen3-8B (종합 0.509) — 판단형식 최고, 속도 최하
- 추천 베이스 모델: **Kanana-1.5-8B** 선정
- `data/evaluation/benchmark_report.md` 비교 리포트 생성
- `data/evaluation/benchmark_results/` 에 모델별 결과 JSON 저장

**다음 할 일:**
- 벤치마크 결과 팀 공유 및 최종 확정
- RAG 파이프라인 구현 시작 (#8)
- Kanana-1.5-8B 기반 파인튜닝 데이터 준비 검토

---

## 2026-02-12 (수)

**RAG 파이프라인 전체 구현 (#8) — 2단계 완료:**
- `ai/rag/embeddings.py` — SentenceTransformer("jhgan/ko-sbert-nli") 싱글턴 임베딩 모델
- `ai/rag/vectorstore.py` — Qdrant PersistentClient, cosine 유사도, scope 필터, upsert 지원
- `ai/rag/hybrid_search.py` — BM25 + Vector 하이브리드 검색, RRF(k=60) 합산, scope 필터 (BM25/Vector 양쪽)
- `ai/rag/reranker.py` — CrossEncoder("BAAI/bge-reranker-v2-m3") 싱글턴 리랭커
- `ai/rag/pipeline.py` — 오케스트레이션 (initialize → add_documents → retrieve), 배치 처리(batch_size=100), 싱글턴 팩토리
- `ai/rag/__init__.py` — 공개 API (RAGPipeline, get_pipeline, reset_pipeline)

**RAG QA 및 버그 수정:**
- BM25 scope 필터 누락 (보안 이슈) → personal 문서 격리 로직 추가
- Qdrant n_results > collection.count() 에러 → min(top_k, count) 캡 추가
- collection.add() 중복 ID 에러 → upsert()로 변경
- user_id=None일 때 전체 문서 반환 → company 문서만 반환하도록 정책 변경

**RAG 개선 사항 반영:**
- `AgentState.context` 타입 변경: `list[str]` → `list[dict]` (source/score 정보 포함)
- BM25 토크나이저: konlpy Okt 형태소 분석기 적용 (Java 없으면 공백 분리 fallback)
- add_documents 배치 처리 추가 (batch_size 단위 분할)
- `ai/requirements.txt`에 `konlpy==0.6.0` 추가

**judgment_agent LLM API 연동 (#39):**
- `ai/agents/judgment_agent.py` 전체 구현 (async)
- RAG retrieve(top_k=5) → LLM generate(temp=0.1) → JSON 파싱 → agent_response 저장
- _build_context_prompt: RAG 결과 → "[규정 N] 출처\n내용" 텍스트 변환
- _build_user_prompt: 규정 context + 질문 + 대화 이력(최근 3턴) 합성
- _parse_llm_response: regex 3단계 JSON 추출 (code block → 인라인 {} → fallback)
- 에러 시 graceful fallback 응답 반환

**테스트 코드 작성:**
- `ai/tests/test_rag_pipeline.py` — 18개 테스트 케이스 전부 PASSED
  - 기본 검색 동작 (4), scope 필터링 (4), user_id=None 정책 (2)
  - 빈 컬렉션 (2), 배치 처리 (1), 토크나이저 (2), VectorStore 개별 (3)
- judgment_agent 헬퍼 함수 단위 테스트 5개 PASSED

**의존성 수정:**
- `ai/requirements.txt`: `langgraph==0.2.0` → `langgraph>=0.2.20` (langchain-core==0.3.0 호환)
- `backend/requirements.txt`: `python-jose[cryptography]==3.3.0` 제거 (PyJWT로 통일, 방치 패키지)
- 두 requirements.txt 간 의존성 충돌 분석 완료

**다음 할 일:**
- PM(지용)에게 state.py 변경 공유 (context: list[str] → list[dict])
- PM(지용)에게 judgment_agent async 전환 공유 (ainvoke 필요)
- 승언과 규정 문서 ingestion 스크립트 역할 합의 (파서 완료 후)
- 3단계 #12 판단 Agent 고도화 (다중 규정 교차 판단, 판단 이력, 스트리밍)

---

## 2026-02-12 (수) — 오후 세션

**3단계: 판단 Agent 고도화 (#12):**

**1. 다중 규정 교차 판단 구현:**
- `_group_regulations()` — RAG 검색 결과를 규정 출처별 그룹핑 (예: "취업규칙", "재택근무 규정" 등)
- `_build_context_prompt()` 리팩토링 — 규정별 그룹 헤더 + 관련도 점수 표시, 다중 규정 시 "교차 분석 필요" 경고 자동 삽입
- 시스템 프롬프트에 `cross_references` 필드 추가 — 규정 간 관계(보완/충돌/상위규정) 분석 지시
- RAG top_k 5→7 확대 (다중 규정 커버리지 확보)

**2. confidence 보정 시스템 구현:**
- `_calibrate_confidence()` — LLM raw confidence를 3가지 요소로 가중 보정:
  - LLM 판단값 60% + RAG 평균 score 25% + 규정 커버리지 15%
  - 규정 간 충돌 시 추가 감점 (-0.1/건)
- 시스템 프롬프트에 confidence 기준표 추가 (0.9↑ 명확, 0.7~0.9 해석 필요, 0.5↓ 근거 부족)

**3. 판단 이력 참조 구현:**
- `_extract_judgment_history()` — chat_history에서 이전 judgment 타입 JSON 자동 추출
- `_build_user_prompt()` 확장 — 최근 3건 판단 이력을 프롬프트에 주입 (일관성 유지)
- 시스템 프롬프트에 이력 참조 규칙 추가 ("규정 근거가 다르면 차이 설명")

**4. SSE 스트리밍 대응:**
- `judgment_agent_stream()` 신규 함수 — AsyncGenerator로 토큰 단위 yield
- 완료 후 `[DONE]` + 구조화 JSON 응답 yield (프론트엔드 파싱용)
- `llm.stream_generate()` 활용 (OpenAI/Anthropic Provider 모두 지원)

**5. 시스템 프롬프트 고도화 (`prompts.py`):**
- `cross_references` 필드 스키마 추가
- 다중 규정 교차 분석 규칙 4개 추가
- confidence 산정 기준표 명시
- 판단 이력 일관성 유지 규칙 추가

**개선 효과 수치 (eval_judgment_improvement.py):**

| 평가 항목 | 결과 |
|-----------|------|
| confidence 보정 방향 정확도 | **100.0%** (5/5 시나리오) |
| 규정 그룹핑 정확도 | **100.0%** (4/4 시나리오) |
| 판단 이력 추출 정확도 | **100.0%** (5/5 시나리오) |

| 항목 | 기존 (2단계) | 고도화 (3단계) |
|------|-------------|---------------|
| 규정 교차 분석 | X (단일 패스) | O (그룹핑 + cross_references) |
| confidence 보정 | X (LLM raw 값) | O (RAG+커버리지+충돌 가중) |
| 판단 이력 참조 | X | O (최근 3건 자동 추출) |
| SSE 스트리밍 | X | O (judgment_agent_stream) |
| RAG top_k | 5 | 7 (커버리지 확대) |
| 응답 필드 | 6개 | 8개 (+cross_references, regulation_groups) |
| 테스트 케이스 | 5개 | **27개 (5.4배 증가)**, 전체 PASSED |

**confidence 보정 시나리오별 결과:**

| 시나리오 | 기존(raw) | 보정후 | 변화량 |
|---------|----------|-------|--------|
| 높은RAG + 다중규정 | 0.900 | 0.940 | +0.040 (적절 유지) |
| 높은LLM + 낮은RAG (과신) | 0.950 | 0.723 | -0.227 (하향 보정) |
| 규정 없음 (환각 방지) | 0.800 | 0.300 | -0.500 (대폭 하향) |
| 규정 충돌 (불확실) | 0.850 | 0.702 | -0.148 (하향 보정) |
| 낮은LLM + 높은RAG (보수적) | 0.500 | 0.700 | +0.200 (상향 보정) |

**오케스트레이터 호환성 확인:**
- 함수 시그니처 동일 유지 (`async def judgment_agent(state) -> AgentState`)
- orchestrator.py의 `safe_judgment_agent`에서 `await` 정상 호출 확인
- `format_response` 노드가 `message` 필드 자동 보장 → 호환 OK
- agent_response에 `cross_references`, `regulation_groups` 필드 추가됨 (지용 공유 필요)

**테스트 결과:**
- `ai/tests/test_judgment_agent.py` — **27개 전부 PASSED** (68초)
  - 그룹핑 (4), 컨텍스트 프롬프트 (4), 이력 추출 (4), 프롬프트 구성 (5), LLM 파싱 (5), confidence 보정 (5)
- `ai/tests/eval_judgment_improvement.py` — 개선 효과 수치 평가 스크립트

**다음 할 일:**
- PM(지용)에게 agent_response 필드 확장 공유 (cross_references, regulation_groups)
- PM(지용)에게 judgment_agent_stream 함수 공유 (SSE 오케스트레이터 연동용)
- 승언과 규정 문서 ingestion 스크립트 역할 합의
- 실 규정 데이터로 E2E 테스트 (RAG → judgment_agent → 응답)

---

## 2026-02-16 (일)

**E2E 테스트 작성 — `ai/tests/test_e2e_judgment.py` (#12 관련):**

6단계 E2E 테스트 스크립트 구현 (RAG → judgment_agent → 오케스트레이터 전체 흐름 검증):

| Step | 테스트 항목 | 내용 |
|------|-----------|------|
| 1 | Qdrant 연결 + 데이터 확인 | 컬렉션 존재 여부, documents 포인트 수 확인 |
| 2 | 규정 PDF → Qdrant 적재 | PyMuPDF 추출 → 조항 기반 청킹 → 임베딩 → Qdrant 저장 |
| 3 | RAG 하이브리드 검색 | 5개 쿼리 (연차/재택/보안/출장비/개인정보) BM25+Vector 검증 |
| 4 | judgment_agent 단독 | 3개 판단 케이스 (연차/재택/보안위반), 응답 형식 + result 검증 |
| 5 | 오케스트레이터 judgment 라우팅 | intent 분류 → judgment_agent 라우팅 정확도 |
| 6 | 오케스트레이터 general 라우팅 | stream_mode=True로 backend 의존성 없이 라우팅만 검증 |

**QA — 버그 3건 발견 및 수정:**

| # | 위치 | 문제 | 수정 |
|---|------|------|------|
| 1 | Step 2 PDF 추출 | `doc.close()` 후 `doc.page_count` 접근 — PyMuPDF 버전별 에러 가능 | close 전에 `page_count` 저장 |
| 2 | Step 1 + main | 연결 실패 시 `return 0` → `0 >= 0 = True`로 PASS 처리됨 | 실패 시 `-1` 반환, main에서 분기 추가 |
| 3 | Step 4 vs Step 5 | `stream_mode: None` vs `False` 불일치 | `False`로 통일 |

**5개 개선사항 구현:**

1. **타임아웃 처리** — 모든 Step에 `asyncio.wait_for` + `asyncio.to_thread` 적용, `--timeout N` CLI 옵션 (기본 60초)
2. **fail-fast/fail-late** — 기본 fail-fast (첫 실패에서 중단 + 요약 출력), `--continue-on-failure`로 전체 실행 모드
3. **메타데이터 검증 + 강제 재적재** — `validate_existing_data()` 신규 (Qdrant scroll로 샘플 10개 source/scope 패턴 확인), `--force-ingest` 옵션
4. **general 테스트 분리** — 기존 Step 5에서 general 분리 → Step 6으로. `stream_mode=True`로 backend LLM 호출 없이 라우팅만 검증
5. **expected_result WARN** — judgment test cases에 `expected_result` 추가 (USB→`no`, 연차→`conditional`). 형식 맞으면 PASS, expected 불일치 시 `[WARN]`만 (LLM 비결정성 허용)

**CLI 사용법:**
```bash
python -m ai.tests.test_e2e_judgment                       # 기본 (fail-fast, 60s)
python -m ai.tests.test_e2e_judgment --continue-on-failure  # 실패해도 계속
python -m ai.tests.test_e2e_judgment --force-ingest         # 강제 재적재
python -m ai.tests.test_e2e_judgment --timeout 120          # 타임아웃 변경
```


**E2E 테스트 실 환경 실행 + 규정 PDF 재적재 (#12 관련):**

**1. E2E 테스트 실 환경 실행 — 6단계 전체 PASS:**
- Qdrant Cloud 연결, RAG 하이브리드 검색 5/5, judgment_agent 3/3, 오케스트레이터 라우팅 2/2 전부 통과
- 기존 12개 문서(간단한 요약형)로도 기본 동작은 확인

**2. 규정 PDF 재적재 — 조항 기반 세밀한 청킹:**
- 기존 12개 → **44개** 청크로 3.7배 증가
- 청킹 전략 개선:
  - 표지/목차 자동 스킵
  - 장(제N장) 헤더 → chapter 메타데이터 추적 (10개 장)
  - 조(제N조) 헤더 → 새 청크 시작 (32개 조)
  - 긴 조항(>400자) → ● 불릿 기준 서브 분할
- 청크 통계: 평균 260자, 최소 60자, 최대 482자
- `--force-ingest` 시 기존 컬렉션 삭제 후 재생성 로직 추가

**3. 판단 품질 개선 확인:**

| 케이스 | Before (12청크) | After (44청크) | 변화 |
|--------|----------------|---------------|------|
| 연차 (입사 1년 미만) | `no_regulation` (0.46) | `conditional` (0.70) | 정확해짐! 제8조 근거 |
| 재택근무 근태관리 | `yes` (0.70) | `yes` (0.70) | 제9조 근거 유지 |
| USB 복사 | `no` (0.70) | `no` (0.70) | 제10조 복무의무 근거 |
| 클라우드 서비스 | `no_regulation` (0.40) | `no` (0.70) | 제20조 정확히 찾음! |

**4. regulation_groups 그룹핑 버그 수정:**
- `_group_regulations()` 정규식 버그: `re.split(r"\s*\d", "제8조")` → `['제', '조']` → `'제'`
- 수정: `chapter` 메타데이터 우선 사용, source에서 `.pdf` 확장자 제거, `제N조` 형태면 title 대체
- 결과: `['제']` → `['제8조', '제5조', '제12조', ...]` 조항별 정확한 그룹핑

**다음 할 일:**
- PM(지용)에게 E2E 테스트 결과 공유 (44청크 재적재 + 판단 품질 개선)
- PM(지용)에게 agent_response 필드 확장 공유 (`cross_references`, `regulation_groups`)
- PM(지용)에게 `judgment_agent_stream` 함수 공유 (SSE 오케스트레이터 연동용)
- 5단계 성능 평가 (#13) 준비 — 평가 메트릭 설계, 테스트셋 확장
- 승언과 규정 문서 ingestion 스크립트 역할 합의

---

## 2026-02-19 (수) — 멘토 피드백 반영 + 고도화

**멘토 피드백 6개 항목 구현 (우선순위순):**

### Priority 1: Confidence Score 신뢰성 강화 — 4중 보조장치 (`judgment_agent.py`)

| 보조장치 | 함수 | 역할 |
|---------|------|------|
| 1. 환각 탐지 | `_check_keyword_match()` | LLM 인용 조항이 RAG 결과에 실제 있는지 cross-check (0.0~1.0) |
| 2. 조항 존재 검증 | `_validate_article_exists()` | 인용된 "제8조" 등이 RAG context에 존재하는지 validate |
| 3. 카테고리 제한 | `_validate_result_category()` | yes/no/conditional/no_regulation 외 결과 자동 reject |
| 4. 일관성 모니터링 | `_check_consistency()` | 동일 쿼리 캐싱, 이전과 다른 답이면 flag |

- `_calibrate_confidence()` 보정 공식 확장: 기존 3요소 + 환각 감점 + 조항 미존재 감점
- `_judgment_cache` 메모리 누수 방지: `_CACHE_MAX_SIZE=500` + FIFO 퇴출
- 응답에 `article_validations`, `consistency_flag`, `warnings` 필드 추가

### Priority 2: 판단 Agent vs 문서 Agent 경계 문서화

- `docs/판단Agent_vs_문서Agent_리스크감지.md` 신규 작성
- 입력/목적/RAG 대상/출력/트리거 차이 비교표
- 라우팅 시나리오 4개 + 기술 차이 테이블 + 발표 토킹포인트

### Priority 3: Query Refinement 모듈 구현 (`query_refiner.py`)

- `ai/rag/query_refiner.py` 신규 — kiwipiepy 형태소 분석 + 도메인 동의어 20개 + 불용어 35개
- BM25용: 키워드 추출 + 동의어 확장 (`refine_query_for_bm25`)
- Vector용: 구어체→문어체 변환 15개 패턴 (`refine_query_for_vector`)
  - 예: "연차 몇 일이나 쓸 수 있어요?" → "연차 일수 기준 사용 가능 여부?"
- `hybrid_search.py`에 통합 — BM25/Vector 각각 다른 쿼리 사용
- kiwipiepy 인스턴스 `hybrid_search.py`와 공유 (이중 로딩 방지, ~30MB 절약)

### Priority 4: 다양한 문서 RAG 테스트

- 가이드 작성 완료 (실제 테스트는 문서 확보 후 진행)

### Priority 5: vLLM 아키텍처 분리 (`vllm_client.py`)

- `ai/serving/vllm_client.py` — `VLLMProvider(BaseLLM)` 전체 구현
  - generate / stream_generate / chat / stream_chat 4개 메서드
  - `with_lora(adapter_name)` — LoRA 어댑터 핫스왑
  - OpenAI SDK 사용 (vLLM의 OpenAI 호환 API)
- `ai/llm/factory.py` — `LLM_PROVIDER=vllm` 시 VLLMProvider 연결
- 환경변수: `VLLM_BASE_URL`, `VLLM_MODEL`, `VLLM_API_KEY`

### Priority 6: agent_response 표준 문서화

- `docs/agent_response_표준.md` 신규 — 7개 Agent 응답 형식 표준 정의
- 공통 필수 필드 (`type`, `message`) + Agent별 상세 스키마
- 복합 쿼리에서 이전 Agent 결과 참조 패턴 문서화

---

### 추가 개선 3건 (멘토 피드백 후속)

**1. 조항 패턴 범위 확장:**
- 기존 `제N조`만 지원 → 5가지 패턴으로 확장
  - `제N조 제N항`, `제N장/편/절/관`, `별표 N`, `부칙 N`, `N.N조`
- `judgment_agent.py`의 `_extract_cited_articles` + `_validate_article_exists` 통일
- `query_refiner.py`의 `_extract_article_refs`도 동일 패턴 적용

**2. Confidence Score breakdown 시각화 데이터:**
- `_calibrate_confidence()` 반환값 변경: `float` → `tuple[float, dict]`
- `confidence_breakdown` 필드가 응답에 포함:
  ```
  LLM raw 0.90 → ×0.6 = 0.540
  RAG score 0.75 → ×0.25 = 0.234
  Coverage → ×0.15 = 0.150
  환각 감점 -0.000, 조항 감점 -0.000
  → 최종 0.85
  ```
- 스트리밍 버전(`judgment_agent_stream`)에도 동일 적용
- `docs/agent_response_표준.md`에 breakdown 필드 상세 문서화

**3. Vector 쿼리 구어체→문어체 변환:**
- `_COLLOQUIAL_TO_FORMAL` 15개 regex 패턴
- 문장 구조 보존하면서 구어 표현만 문서체로 변환
- LLM 호출 없이 즉시 처리 (비용/지연 0)

---

### QA 자체 점검 — 버그 5건 발견 및 수정

| # | 위치 | 문제 | 수정 |
|---|------|------|------|
| 1 | `judgment_agent.py` | `_check_keyword_match` + `_validate_article_exists` 이중 호출 (calibrate 내부 + agent 함수) | 한 번만 호출 후 결과를 파라미터로 전달 |
| 2 | `judgment_agent.py` | `keyword_match=0.5`(중립)일 때 불필요한 감점 | `< 0.5`일 때만 감점하도록 조건 수정 |
| 3 | `judgment_agent.py` | `_judgment_cache` 무한 증가 (메모리 누수) | `_CACHE_MAX_SIZE=500` + FIFO 퇴출 |
| 4 | `query_refiner.py` | kiwipiepy 이중 인스턴스 (~60MB 낭비) | `hybrid_search.py` 인스턴스 재사용 |
| 5 | `judgment_agent.py` | 스트리밍 버전 `message` 필드 누락 | `parsed["message"]` 추가 |

---

### 참고 파일 목록

| 파일 | 설명 |
|------|------|
| `ai/agents/judgment_agent.py` | 판단 Agent 메인 — 4중 보조장치 + confidence breakdown |
| `ai/rag/query_refiner.py` | Query Refinement — 키워드 추출, 동의어 확장, 구어체→문어체 |
| `ai/rag/hybrid_search.py` | 하이브리드 검색 — query_refiner 통합 (BM25/Vector 분리 쿼리) |
| `ai/serving/vllm_client.py` | vLLM Provider — BaseLLM 호환, LoRA 핫스왑 |
| `ai/llm/factory.py` | LLM 팩토리 — vllm provider 연결 |
| `ai/llm/base.py` | BaseLLM 추상 인터페이스 (vLLM 구현 시 참고) |
| `ai/llm/prompts.py` | 시스템 프롬프트 (JUDGMENT_SYSTEM_PROMPT 등) |
| `ai/agents/state.py` | AgentState TypedDict 정의 |
| `ai/agents/orchestrator.py` | LangGraph 오케스트레이터 (라우팅 + 복합쿼리) |
| `ai/rag/qdrant_pipeline.py` | Qdrant 기반 RAG 파이프라인 |
| `ai/rag/qdrant_store.py` | Qdrant 벡터 스토어 |
| `docs/agent_response_표준.md` | agent_response 표준 형식 (confidence_breakdown 포함) |
| `docs/판단Agent_vs_문서Agent_리스크감지.md` | 판단 Agent vs 문서 Agent 경계 문서 |

**다음 할 일:**
- 지영(Frontend)과 `warnings` 배열, `confidence_breakdown` 렌더링 방식 논의
- PM(지용)에게 `confidence_breakdown` 필드 추가 공유
- 실 규정 문서의 조항 번호 체계 확인 → `_ARTICLE_PATTERNS` 정규식 검증
- Priority 4: 다양한 문서(AWS 정책, 논문, 계약서) RAG 테스트 — 문서 확보 후 진행
- 5단계 성능 평가 (#13) — 환각 탐지 정확도, confidence 보정 효과 정량 평가

---

## 2026-02-20 (목)

### judgment_agent_stream SSE 연동 완료

**1. orchestrator.py — judgment 스트리밍 분기 추가:**
- `safe_judgment_agent()`에 `stream_mode` 체크 추가
- `stream_mode=True`일 때 `stream_pending=True` 반환 → chat.py에서 직접 스트리밍 처리
- `general_response_node`와 동일한 패턴 적용

**2. chat.py — judgment SSE 핸들러 추가:**
- `judgment_agent` 노드 이벤트에서 `judgment_agent_stream()` 호출
- 토큰 단위 `{'type': 'token', 'value': ...}` SSE 전송
- `\n[DONE]` 이후 JSON 파싱 → `final_state["agent_response"]`에 저장
  - `confidence_breakdown`, `cross_references`, `regulation_groups` 등 전부 포함
- `format_response`에서 `judgment` intent 토큰 중복 전송 방지 (`intent not in ("general", "doc_search", "judgment")`)

**SSE 이벤트 흐름:**
```
intent → status("judgment_agent 처리 중...")
       → token (토큰 단위 스트리밍)
       → result (confidence_breakdown, cross_references, regulation_groups 포함)
       → done
```

### document_parser 스텁 → 실제 구현 완성

| 파일 | 구현 내용 |
|------|----------|
| `docling_parser.py` | Docling PDF 구조화 파싱 + `split_by_sections()` 조항 단위 청킹 (표지/목차 스킵, 제N장 chapter 추적, 제N조 청크 분할, 400자 초과 시 불릿 서브 분할) |
| `docx_parser.py` | python-docx 파싱 (Heading 스타일 → 마크다운 헤딩, 테이블 → 마크다운 테이블 변환) |
| `ocr_parser.py` | PaddleOCR lazy 초기화 + `extract_text()` 이미지 OCR + `extract_text_from_pdf()` 스캔 PDF 페이지별 OCR |
| `parser.py` | 확장자별 자동 분기 라우터 + PDF OCR fallback (Docling 결과 50자 미만 시) + `parse_and_chunk()` 원스톱 메서드 |

### ingestion 스크립트 작성

- `scripts/ingest_documents.py` 신규 — 문서 파싱 → Qdrant RAG 적재 CLI 스크립트
- 승언의 `DocumentParser`(파싱+청킹) → 경은의 `QdrantRAGPipeline`(임베딩+적재) 연결
- CLI 옵션: `--scope`, `--user-id`, `--force` (재적재), `--test` (검색 테스트), `--batch-size`
- 사용법: `python scripts/ingest_documents.py data/regulations/ --force --test "연차 휴가"`

### 커밋 & 머지

- `feat/ai-yoon` → origin push 완료 (`34c4f0b`)
- `develop` ← `feat/ai-yoon` Fast-forward 머지 완료 (충돌 없음)

**다음 할 일:**
- 지영(Frontend)과 judgment 스트리밍 응답(`confidence_breakdown`, `warnings`) 렌더링 협의
- `ingest_documents.py`로 실제 규정 PDF 적재 테스트 (`data/regulations/dudu_tech_regulations.pdf`)
- 다양한 문서 형식(DOCX, 스캔 PDF) 파싱 테스트
- 5단계 성능 평가 (#13) — 환각 탐지 정확도, confidence 보정 효과 정량 평가

---

## 2026-02-23 (일) — 규정 문서 확보 + RAG 검색 고도화

### 가상 규정 문서 7개 생성 (3단계 RAG 커버리지 확보)

기존 `dudu_tech_regulations.pdf` 1개(30조)로는 교차 규정 판단이 불가능하여,
듀듀 테크놀로지 스타일의 가상 규정 .txt 파일 7개를 생성하여 `data/regulations/`에 추가:

| # | 파일명 | 문서번호 | 조항 수 | 주요 내용 |
|---|--------|---------|---------|----------|
| 1 | 급여규정_NC-HR-2026-002.txt | NC-HR-2026-002 | 21조 | 급여체계, 수당, 상여금, 퇴직금 |
| 2 | 출장규정_NC-HR-2026-003.txt | NC-HR-2026-003 | 17조 | 국내/해외출장, 출장비, 정산 |
| 3 | 교육훈련규정_NC-HR-2026-004.txt | NC-HR-2026-004 | 14조 | 직무교육, 법정교육, 교육비 지원 |
| 4 | 복리후생규정_NC-HR-2026-005.txt | NC-HR-2026-005 | 17조 | 건강검진, 경조사, 자녀학자금, 동호회 |
| 5 | 징계규정_NC-HR-2026-006.txt | NC-HR-2026-006 | 17조 | 징계종류, 사유, 절차, 이의신청 |
| 6 | 개인정보처리규정_NC-IT-2026-001.txt | NC-IT-2026-001 | 20조 | 개인정보 수집/이용/파기, CCTV, 침해사고 |
| 7 | 윤리강령_NC-GV-2026-001.txt | NC-GV-2026-001 | 21조 | 이해충돌, 부정청탁, 금품수수, 내부고발 |

- 총 127개 조항, 규정 간 교차 참조 포함 (징계규정↔개인정보처리규정 등)
- 기존 PDF(제N장 > 제N조 > 불릿)와 동일한 조항 구조

### Qdrant 적재 완료 — 270개 청크

- docling 설치 후 PDF 포함 전체 재적재 (`--force`)
- PDF: 101 청크 + TXT 7개: 169 청크 = **총 270개 청크**
- 기존 44개 → 270개로 **6.1배 증가**

### 교차 규정 검색 품질 개선

"출장 중 개인정보 유출 시 처분은?" 쿼리로 교차 규정 검색 테스트 후 3가지 문제 발견 및 해결:

**문제 1: 단일 규정 독점** — 개인정보처리규정이 top-5 전체 점령
→ **해결**: `hybrid_search.py`에 `max_per_source=3` 소스 다양성 적용 (RRF 합산 후)

**문제 2: BM25 토큰 불일치** — "징계의"와 "징계"가 매칭 안 됨 (공백 기반 토크나이징)
→ **해결**: `hybrid_search.py`의 `tokenize()`에 `_strip_suffixes()` 한국어 접미사 제거 추가

**문제 3: 쿼리 키워드 추출 실패** — "처분은?" → "처분은" (조사 잔류)
→ **해결**: `query_refiner.py`의 `_extract_keywords()`에 `_strip_suffixes()` 추가, "처분" → 동의어 "징계" 확장

**개선 결과:**
- 징계규정이 rank 8에 등장 (제7조 중징계 사유: "고객 개인정보를 고의로 유출한 경우")
- 5개 이상 규정에서 교차 검색 결과 확보
- 기존 4개 쿼리 회귀 테스트 전부 통과

### 수정된 파일 (4개)

| 파일 | 변경 내용 |
|------|----------|
| `ai/agents/judgment_agent.py` | top_k 7→10 (일반 + 스트리밍 양쪽) |
| `ai/rag/hybrid_search.py` | `_strip_suffixes()` + `max_per_source=3` 소스 다양성 |
| `ai/rag/query_refiner.py` | `_strip_suffixes()` fallback + 동의어 확장 개선 |
| `scripts/ingest_documents.py` | test top_k 5→10 |

### Git — 커밋 & 푸시 완료

- `feat/ai-yoon` 커밋 (11 files, 970 insertions) → origin push
- `develop` ← `feat/ai-yoon` 머지 + origin pull(프론트엔드 변경 반영) → push
- 양쪽 브랜치 origin과 동기화 완료 (`158c53a`)

**다음 할 일:**
- 5단계 성능 평가 (#13) — 판단 정확도, RAG MRR, 교차 규정 검색 정량 평가
- 공개 규정 다운로드 검토 (현재 270 청크로 충분한지 평가 후 결정)
- ~~4단계 파인튜닝 데이터 준비 (#9, #10) — 판단 1,000건 JSONL 변환, 규정 Q&A 수집~~ ✅ 완료
- E2E 교차 규정 판단 테스트 (judgment_agent 실제 호출)

---

## 2026-02-23 (일) — 4단계: 파인튜닝 데이터 준비 (#9, #10)

### Step 1: 데이터 변환 스크립트 — `scripts/prepare_finetuning_data.py` (신규)

Excel 2개 → JSONL chat format 변환 스크립트 구현:

**Judgment (1,000건) 변환:**
- 조항 컬럼 → `regulation_texts.py`에서 원문 자동 조회 (30개 조항 전체 매핑)
- 판단유형 → result 매핑 (Yes→yes, No→no, 조건부→conditional)
- 근거/대안 → reasoning + conditions/alternatives 분기
- user message = `## 관련 규정 문서\n### 제N조(...)\n{원문}\n\n## 사용자 질문\n{질문}` (프로덕션 동일)
- assistant message = `JUDGMENT_SYSTEM_PROMPT` 기반 JSON 응답

**QA (500건) 변환:**
- 답변 텍스트 키워드 기반 판단 카테고리 자동 분류
  - 불가/금지/안 됩니다 → no, 가능/허용/됩니다 → yes, 조건/단,/다만 → conditional
- 순수 설명형 Q&A → yes (규정 존재 확인)

**Confidence 기준:**
- Judgment: Yes/No → 0.92, 조건부 → 0.75
- QA: Yes/No → 0.88, 조건부 → 0.72 (추론 분류이므로 약간 낮게)

### Step 2: 설정 업데이트 — `ai/finetuning/configs/v1_judgment.yaml`

- `base_model`: `Qwen/Qwen3-8B` → `kakaocorp/kanana-1.5-8b-instruct-2505` (벤치마크 #7 선정)

### Step 3: 학습 스크립트 — `ai/finetuning/train_v1_judgment.py` (스텁 → 전체 구현)

`train_qa_lora.py` 패턴 기반으로 전체 구현:
- YAML config 로드 (`configs/v1_judgment.yaml`)
- 모델: Kanana-1.5-8B + BitsAndBytesConfig 4-bit QLoRA
- 데이터: messages 배열 → `tokenizer.apply_chat_template()` → `{"text": ...}`
- LoRA: r=16, alpha=32, target=q/k/v/o_proj, dropout=0.05
- Training: 3 epochs, batch=4, accum=4, lr=2e-4, cosine scheduler
- 평가: judgment 전용 메트릭 (판단 정확도, JSON 유효율, 카테고리별 정확도)

### Step 4: 데이터 변환 실행 + 검증 결과

| 항목 | 결과 |
|------|------|
| 총 건수 | **1,500건** (judgment 1,000 + QA 500) |
| Train / Eval | **1,351 / 149** (90/10 층화추출) |
| JSON 파싱 성공 | **100%** (1,500/1,500) |
| 규정 원문 포함 | **100%** (1,500/1,500) |
| Result 분포 | yes=710, conditional=411, no=379 |
| Source 분포 | judgment=1,000, qa=500 |

### 수정/생성 파일

| 파일 | 작업 | 설명 |
|------|------|------|
| `scripts/prepare_finetuning_data.py` | 신규 | Excel → JSONL 변환 스크립트 |
| `data/training/v1_judgment/train.jsonl` | 신규 | 학습 데이터 (1,351건) |
| `data/training/v1_judgment/eval.jsonl` | 신규 | 평가 데이터 (149건) |
| `ai/finetuning/train_v1_judgment.py` | 수정 | TODO 스텁 → QLoRA + SFTTrainer 전체 구현 |
| `ai/finetuning/configs/v1_judgment.yaml` | 수정 | base_model → Kanana-1.5-8B |

**다음 할 일:**
- RunPod에서 `train_v1_judgment.py` 실제 학습 실행 (A100 40GB)
- 학습 완료 후 eval 메트릭 확인 (판단 정확도 목표 ≥85%)
- vLLM 서빙에 LoRA 어댑터 연결 테스트
- 5단계 성능 평가 (#13) — 파인튜닝 전/후 비교

---

## 2026-02-23 (일) — 매뉴얼/설명서 PDF 파싱 지원 파서 개선

### 문제

기존 `DocumentParser`의 PDF 청킹이 `제N장/제N조` 패턴(한국어 사내 규정)에만 특화되어 있어,
MakerBot METHOD 매뉴얼처럼 `1장 소개`, `## 안전 경고 기호`, `**무선 사양**` 같은
일반 헤딩 구조를 가진 문서는 청킹이 제대로 안 됨.

### 구현 내용

**1. `ai/document_parser/manual_parser.py` (신규) — 매뉴얼 전용 섹션 분할기:**

| 기능 | 설명 |
|------|------|
| 마크다운 헤딩 | `#`, `##`, `###` 기반 섹션 분할 |
| 숫자 헤딩 | `1장`, `2장`, `Chapter 1` 등 인식 |
| 굵은 텍스트 헤딩 | `**제목**` (줄 전체 볼드) 인식 |
| 표지/목차 스킵 | DoclingParser와 동일한 toc_patterns 재활용 |
| 긴 섹션 서브 분할 | 400자 초과 시 단락(`\n\n`) 기준 분할 |
| 메타데이터 | `section`(상위 섹션), `title`(현재 헤딩), `chapter`(장 번호), `article`(빈 문자열) |

**2. `ai/document_parser/parser.py` (수정) — 문서 유형 자동 판별 라우팅:**

- `__init__`에 `ManualParser` 인스턴스 추가
- `parse_and_chunk()`에 `doc_type` 파라미터 추가 (`"auto"` / `"regulation"` / `"manual"`)
- `_detect_doc_type()` 정적 메서드 추가: `제N조` 패턴 2회 이상 → `regulation`, 미만 → `manual`
- 기본값 `doc_type="auto"` → 기존 호출부 수정 불필요 (하위 호환)

**3. `scripts/ingest_documents.py` (수정) — CLI 옵션 추가:**

- `--doc-type` argparse 옵션 추가 (`auto` / `regulation` / `manual`)
- `parse_and_chunk()`, `ingest()` 함수에 `doc_type` 파라미터 전달
- 사용법: `python scripts/ingest_documents.py manual.pdf --doc-type manual`

### 기존 코드 영향

- 기존 규정 PDF: `doc_type="auto"` → `제N조` 패턴 감지 → 기존 DoclingParser 로직 그대로
- 기존 DOCX/TXT: 변경 없음
- 기존 호출부: `parse_and_chunk()` 기본값 `doc_type="auto"` → 수정 불필요

### 수정/생성 파일

| 파일 | 작업 |
|------|------|
| `ai/document_parser/manual_parser.py` | 신규 |
| `ai/document_parser/parser.py` | 수정 |
| `scripts/ingest_documents.py` | 수정 |

**다음 할 일:**
- MakerBot 매뉴얼 PDF로 `doc_type="auto"` 실 파싱 테스트
- 기존 규정 PDF 회귀 테스트 (기존과 동일하게 조항 청킹 되는지 확인)
- RunPod에서 `train_v1_judgment.py` 실제 학습 실행 (A100 40GB)
- 5단계 성능 평가 (#13) — 파인튜닝 전/후 비교
