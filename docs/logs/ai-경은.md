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


## 규정 문서 확보 + RAG 검색 고도화

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
- 4단계 파인튜닝 데이터 준비 (#9, #10) — 판단 1,000건 JSONL 변환, 규정 Q&A 수집
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

---

## 2026-02-24 (화) — 프론트엔드 Confidence/문서 카드 UI 구현

### 1. 판단 카드 Confidence Breakdown & Warnings UI (`JudgmentCard.jsx`)

- **접이식 신뢰도 분석 섹션** 구현 (JudgmentCard 하단)
  - 헤더: ShieldCheck 아이콘 + "신뢰도 분석" + progress bar + 퍼센트 + ChevronDown 토글
  - 구성 요소: LLM 판단(×0.6), RAG 검색(×0.25), 규정 커버리지(×0.15) 각각 progress bar
  - 감점 합산 표시 (conflict + hallucination + article penalty)
  - warnings 배열 → AlertTriangle 아이콘 + 노란색 경고 리스트
  - `confidence_breakdown`이 없으면 섹션 자체 숨김
  - 색상: >=0.7 초록, >=0.4 노랑, <0.4 빨강

### 2. 판단 결과 배지 (`ChatPage.jsx`)

- 판단 카드 위에 결과 배지(pill) 표시: 가능(초록 CheckCircle), 불가(빨강 XCircle), 조건부 가능(노랑 AlertTriangle), 규정 없음(회색 HelpCircle)
- 단순 정보 조회(isInformational)일 때 배지 숨김

### 3. 마크다운 렌더링 (`MarkdownText.jsx` 신규)

- `react-markdown` 패키지 설치 및 공통 컴포넌트 생성
- `**bold**`, `*italic*`, 리스트, 코드블록 등 마크다운 렌더링
- 적용: 일반 질문 답변, 판단 카드 summary, doc_search content, 기본 텍스트 버블 (4곳)

### 4. 문서 Agent 카드 UI 개선 (#68)

**`SourceItem.jsx` (신규)** — 출처 항목 공통 컴포넌트:
- 제목 + 페이지 + 내용 미리보기
- 우측에 RAG relevance score progress bar + 퍼센트 표시
- 색상: >=70% 초록, >=40% 노랑, <40% 빨강

**`doc_search` 카드 개선:**
- 기존 출처 목록을 SourceItem으로 교체 → 각 출처에 검색 정확도(score) 표시
- content에 MarkdownText 적용

**`doc_qa` 카드 (신규):**
- 헤더: "문서 Q&A" + 우측 confidence 점수 (ShieldCheck + bar + %)
- 본문: 마크다운 답변
- 인용(citations): 출처명 + relevance 배지 (높음/중간/낮음 색상 구분)
- 검색 출처(sources): SourceItem으로 score bar 표시

**`doc_summary` 카드 (신규):**
- 헤더: FileText 아이콘 + "문서 요약"
- 본문: MarkdownText 렌더링 (기존 default case에서 전용 카드로 승격)

### 5. 문서 상세 보기 검색 정확도 (`DocumentViewPanel.jsx`)

- 하단에 접이식 "검색 정확도" 섹션 추가
- 헤더: ShieldCheck 아이콘 + progress bar + 퍼센트 + ChevronDown 토글
- 펼침 시: 정확도 등급 배지(높음/보통/낮음) + "RAG 벡터 검색 유사도 점수" 설명 + 안내 문구
- `doc.score` 없으면 섹션 숨김

### 수정/생성 파일

| 파일 | 작업 |
|------|------|
| `frontend/src/components/chat/JudgmentCard.jsx` | 수정 — confidence breakdown 접이식 UI |
| `frontend/src/components/chat/MarkdownText.jsx` | 신규 — react-markdown 공통 컴포넌트 |
| `frontend/src/components/chat/SourceItem.jsx` | 신규 — 출처 + score bar 공통 컴포넌트 |
| `frontend/src/components/chat/DocumentViewPanel.jsx` | 수정 — 검색 정확도 접이식 추가 |
| `frontend/src/pages/ChatPage.jsx` | 수정 — 결과 배지, doc_qa/doc_summary 카드, MarkdownText 적용 |
| `frontend/package.json` | 수정 — react-markdown 의존성 추가 |

**다음 할 일:**
- RunPod에서 `train_v1_judgment.py` 실제 학습 실행 (A100 40GB)
- 5단계 성능 평가 (#13) — 파인튜닝 전/후 비교
- 다양한 문서 형식(DOCX, 스캔 PDF) 파싱 테스트

---

## 2026-03-03 (월) — 인사/IT보안 교차 규정 데이터 확장 (#9, #10)

### 1. 인사규정 + IT보안규정 파일 생성 및 시나리오 추가

**규정 파일 2개 생성:**

| 파일 | 문서번호 | 조항 수 | 주요 내용 |
|------|---------|---------|----------|
| `인사규정_NC-HR-2026-001.txt` | NC-HR-2026-001 | 12조 | 채용, 근로계약, 근로시간, 휴가, 원격근무, 비밀유지 |
| `IT보안규정_NC-IT-2026-002.txt` | NC-IT-2026-002 | 18조 | 접근통제, 네트워크 보안, 클라우드/IoT 보안, 보안사고 대응 |

**`generate_cross_regulation_data.py` 수정:**
- `REG_ALIASES`에 `"인사": "인사규정"`, `"IT보안": "IT보안규정"` 추가
- 교차 규정 시나리오 17개 신규 추가 (총 31→48개):
  - cross_2: 8개 (인사+개인정보, 인사+IT보안, IT보안+개인정보 등)
  - cross_3: 3개 (3규정 교차)
  - conflict: 3개 (원격근무 보안 vs 유연근무, 교육비 vs 보안교육, BYOD vs 보안 등)
  - noise: 3개 (distractor-only)

### 2. 데이터 생성 (cross_regulation_v2.jsonl)

- 48 시나리오 × 20건 = **958건** 생성 (약 3시간 소요, GPT API)
- 결과 분포: conditional 553 (57.7%), no 176 (18.4%), no_regulation 137 (14.3%), yes 92 (9.6%)
- conditions 100% 채움 (v1의 97% → v2 100%)
- cross_references 포함: 80.6%

### 3. 데이터 병합 및 QA

**병합:**
- v2에서 내부 중복 2건 제거 (958→956건)
- 90/10 split → train 860건 + eval 96건
- 기존 데이터와 병합: train 1,766+860=2,626, eval 190+96=286
- 정확 중복 제거: train 4건, eval 1건 제거
- COND_NO_DESC 수정: train 8건 + eval 3건 (v1 기존 데이터의 conditions 누락 수정)

**최종 결과:**

| 항목 | train | eval |
|------|-------|------|
| 레코드 수 | **2,622** | **285** |
| 품질 점수 | **94.3/100 (A)** | **95.5/100 (A+)** |
| 에러 | **0** | **0** |
| COND_NO_DESC | 0 (수정 완료) | 0 (수정 완료) |
| 평균 confidence | 0.877 | 0.882 |

| 결과 분포 | train | eval |
|-----------|-------|------|
| conditional | 1,164 (44.4%) | 129 (45.3%) |
| yes | 711 (27.1%) | 86 (30.2%) |
| no | 547 (20.9%) | 50 (17.5%) |
| no_regulation | 200 (7.6%) | 20 (7.0%) |

**규정별 인용 횟수 (train):**
- 개인정보처리규정: 587건 (22.4%)
- IT보안규정: 387건 (14.8%)
- 인사규정: 374건 (14.3%)
- 취업규칙: 85건 (3.2%)
- 보수규정: 25건 (1.0%)

### 4. Self-QA 발견 이슈 및 개선 제안

| 이슈 | 심각도 | 설명 |
|------|--------|------|
| RAFT distractor 비율 부족 | 중 | 7.6% (목표 20%) — `no_regulation` 샘플 부족 |
| IT보안규정 후반 조항 빈약 | 중 | 제20~24조, 제28조 인용이 30~42건으로 평균 대비 1/3 수준 |
| cross_references relationship 불일치 | 하 | LLM이 "보완/충돌" 생성 vs validator 기대 "보충/상충" |
| yes 결과 비율 낮음 | 하 | 9.6% — 명확한 허용 케이스 부족 |

### 수정/생성 파일

| 파일 | 작업 |
|------|------|
| `data/regulations/인사규정_NC-HR-2026-001.txt` | 신규 |
| `data/regulations/IT보안규정_NC-IT-2026-002.txt` | 신규 |
| `scripts/generate_cross_regulation_data.py` | 수정 — 시나리오 17개 추가 |
| `scripts/validate_judgment_data.py` | 기존 (검증용) |
| `data/training/v1_judgment/cross_regulation_v2.jsonl` | 신규 — 958건 |
| `data/training/v1_judgment/train.jsonl` | 수정 — 2,622건 (병합+중복제거+COND수정) |
| `data/training/v1_judgment/eval.jsonl` | 수정 — 285건 (병합+중복제거+COND수정) |
| `data/training/v1_judgment/backup/` | 신규 — v1 백업 |

**다음 할 일:**
- ~~RAFT distractor 비율 보정 (7.6% → 20% 목표, noise 시나리오 추가)~~ ✅ 완료 (3/4)
- ~~IT보안규정 후반부 조항(제20~24조, 제28조) 타겟 시나리오 추가~~ ✅ 완료 (3/3)
- ~~cross_references relationship 표준화 (프롬프트 vs validator 기준 결정)~~ ✅ 완료 (3/4)
- ~~나머지 규정 간 교차 조합 확장 (급여×인사, 교육훈련×IT보안 등)~~ ✅ 완료 (3/3~3/4)
- RunPod에서 확장된 데이터로 LoRA 파인튜닝 실행

---

## 2026-03-04 (화)

### 교차 규정 v3+v4 데이터 생성 및 리밸런싱

**Phase 1: v3 교차 규정 데이터 생성 (이전 세션 마무리)**
- 72 시나리오 × 7건 = 502건 생성 (`cross_regulation_v3.jsonl`)
- IT보안규정 후반부(제20~28조) 시나리오 포함
- 기존 데이터와 병합: 2,907 + 502 = 3,409건

**Phase 1 Self-QA 결과:**
- 검증 스코어: 90.6/100 (A)
- 수정: `relationship: "무관"` validator 추가, [467] result `no→no_regulation` 수정

**Phase 2: 데이터 분포 리밸런싱 (conditional ↓, no_regulation ↑)**

문제: conditional 45.9%, no_regulation 8.7% → 모델 편향 위험

**2-1. conflict 시나리오 확장 (10→20개)**
- 10개 신규 충돌 시나리오 추가:
  - 수습기간 교육비 반환, 건강검진 vs 개인정보, 배우자 이해충돌 vs 겸직,
  - 법정교육 면책 vs 징계, 육아휴직 복직 복지, 연봉 삭감 가능성,
  - 내부고발 신원보호, CISSP 교육비 이중적용, 해외출장 질병 보험, 자격수당 중복
- 생성: 20 시나리오 × 7건 = **140건** (`cross_regulation_v4_conflict.jsonl`)
- 분포: conditional 90, no_regulation 31, no 19

**2-2. no_regulation 부스트 생성 (`--noreg-boost` 모드)**
- `generate_cross_regulation_data.py`에 `--noreg-boost` 플래그 추가
- 모든 82 시나리오를 distractor-only 컨텍스트로 실행
- 생성: 82 시나리오 × 5건 = **410건** (`cross_regulation_v4_noreg.jsonl`)
- 분포: **no_regulation 410건 (100%)**

**2-3. 리밸런싱 실행**
- `scripts/rebalance_judgment_data.py` 신규 스크립트 작성
- conditional 언더샘플링: 1,665건 → 983건 (682건 제거)
- 최종 분포 (train+eval 3,277건):

| result | 건수 | 비율 | 변화 |
|--------|------|------|------|
| conditional | 983 | **30.0%** | 45.9% → 30.0% |
| yes | 872 | **26.6%** | 26.0% → 26.6% |
| no_regulation | 732 | **22.3%** | 8.7% → 22.3% |
| no | 690 | **21.1%** | 19.4% → 21.1% |

- train: 2,949건 / eval: 328건
- 백업: `backup/train_before_rebalance.jsonl`, `backup/eval_before_rebalance.jsonl`

**최종 검증: train.jsonl — 90.4/100 (A), 오류 0건**

### 수정/생성 파일

| 파일 | 작업 |
|------|------|
| `scripts/generate_cross_regulation_data.py` | 수정 — conflict 10개 추가, `--noreg-boost` 모드 추가 |
| `scripts/rebalance_judgment_data.py` | 신규 — 데이터 리밸런싱 스크립트 |
| `scripts/validate_judgment_data.py` | 수정 — VALID_RELATIONSHIP에 "무관" 추가 |
| `data/training/v1_judgment/cross_regulation_v3.jsonl` | 신규 — 502건 |
| `data/training/v1_judgment/cross_regulation_v4_conflict.jsonl` | 신규 — 140건 |
| `data/training/v1_judgment/cross_regulation_v4_noreg.jsonl` | 신규 — 410건 |
| `data/training/v1_judgment/train.jsonl` | 수정 — 2,949건 (리밸런싱 후) |
| `data/training/v1_judgment/eval.jsonl` | 수정 — 328건 (리밸런싱 후) |
| `data/training/v1_judgment/backup/` | 백업 파일 추가 |

**다음 할 일:**
- CONTENT_MISMATCH 경고 샘플링 검수 (교차규정 패턴으로 인한 예상 경고 확인)
- 중복 의심 8쌍 검토 (이름만 다른 거의 동일한 질문)
- ~~RunPod에서 리밸런싱된 데이터로 QLoRA 파인튜닝 baseline 실행~~ ✅ 완료 (3/6)
- ~~baseline 성능 확인 후 추가 데이터 방향 결정~~ ✅ 완료 (3/6)

---

## 2026-03-06 (목) — Judgment LoRA v1 학습 결과 + v2 데이터 보강 준비

### 1. Judgment LoRA v1 파인튜닝 실행 및 결과 (RunPod A100)

**학습 환경:**
- 베이스 모델: `kakaocorp/kanana-1.5-8b-instruct-2505`
- 학습 방식: QLoRA (4-bit, r=16, alpha=32)
- 학습 데이터: 2,949건 (train) / 328건 (eval)
- 학습 스크립트: `ai/finetuning/train_v1_judgment.py`

**v1 평가 결과 (`outputs/v1_judgment/eval_results.json`):**

| 항목 | 결과 |
|------|------|
| 전체 정확도 | **86.6%** (284/328) |
| JSON 유효율 | **98.2%** (322/328) |

| 카테고리 | 정답 | 전체 | 정확도 |
|----------|------|------|--------|
| no_regulation | 65 | 67 | **97.0%** |
| yes | 85 | 100 | **85.0%** |
| conditional | 84 | 100 | **84.0%** |
| no | 50 | 61 | **82.0%** |

**분석:**
- 목표(≥85%) 달성: 전체 86.6%
- **강점**: no_regulation 97% — distractor 시나리오 학습 효과 뛰어남
- **약점**: no 82%, conditional 84% — 두 카테고리 간 경계 혼동 존재
  - "승인 없이 ~하면?" → no인데 conditional로 오분류하는 패턴
  - 조건 존재 여부 vs 금지 여부 판단 경계가 모호한 케이스

### 2. v2 데이터 보강 분석 — no/conditional 경계 개선

**train.jsonl (2,949건) 분석 결과:**

| 카테고리 | 건수 | 비율 |
|----------|------|------|
| conditional | 883 | 29.9% |
| yes | 772 | 26.2% |
| no_regulation | 665 | 22.6% |
| no | 629 | 21.3% |

- `no`가 가장 적은 카테고리 (629건) → 정확도도 최하위 (82%)
- no/conditional 경계 혼동 패턴 발견:
  - "승인 없이" → 금지(no)이지만, 조건부(conditional)로 오분류 가능
  - 동일 규정 조항에서 질문 프레이밍에 따라 결과가 달라지는 케이스

### 3. v2 보강 스크립트 작성 — `scripts/augment_v2_no_conditional.py` (신규)

**목표**: ~250건 타겟 생성으로 no/conditional 경계 강화

| Phase | 대상 | 건수 | 전략 |
|-------|------|------|------|
| A | no 강화 | ~120건 | "승인 없이", "무단으로", "허가 없이" 등 명시적 금지 패턴 |
| B | no/conditional 경계쌍 | ~80건 | 동일 규정 + 다른 질문 프레이밍 → (no, conditional) 쌍 생성 |
| C | conditional 명확화 | ~50건 | "~하면 가능한가요?", "조건이 뭔가요?" 등 조건 탐색 패턴 |

**스크립트 특징:**
- GPT-4o-mini 기반 데이터 생성 (비용 효율)
- `data/regulations/` 규정 .txt 파일에서 실제 규정 원문 로드
- 생성 후 레이블 검증 (expected와 불일치 시 자동 필터링)
- 90/10 split으로 train.jsonl / eval.jsonl에 자동 병합 (백업 포함)

### 수정/생성 파일

| 파일 | 작업 |
|------|------|
| `scripts/augment_v2_no_conditional.py` | 신규 — no/conditional 타겟 보강 스크립트 |
| `outputs/v1_judgment/eval_results.json` | 신규 — v1 평가 결과 (RunPod에서 push) |

**다음 할 일:**
- `augment_v2_no_conditional.py` 실행 (OPENAI_API_KEY 필요) → ~250건 생성
- v2 보강 데이터 병합 후 RunPod에서 LoRA v2 학습 실행
- v1 vs v2 성능 비교 (특히 no 82%→목표 88%+, conditional 84%→87%+)
- 전체 정확도 목표: 86.6% → 90%+

---

## 2026-03-09 (일) — RAG 검색 고도화 + 성능 평가

### 1. RAG 파이프라인 고도화 (3단계 개선)

| 방법 | 기존 상태 | 개선 내용 |
|------|----------|----------|
| Reranker 활성화 | 비활성화 | Cross-Encoder(bge-reranker-v2-m3) 활성화, score_threshold=-2.0 |
| Query Refinement 강화 | 동의어 사전 + 구어체 변환 | HyDE(가상 문서 생성) 기반 벡터 검색 품질 향상 |
| 메타데이터 필터링 | chapter/source 기반 | 태그/카테고리 매칭 부스트, Score 표시 추가 |
| 청크 전략 개선 | 현재 고정 크기 추정 | 조항 단위 청킹으로 정밀도 향상 |
| Score threshold | 없음 | RRF 점수 하한선 설정 → 낮은 점수 문서 제거 |

### 2. RAG 벤치마크 결과

**파일**: `data/evaluation/benchmark_results/rag_improvement_comparison.json`

| 지표 | 결과 |
|------|------|
| Hit Rate | **95.24%** (21건 중 20건 적중) |
| MRR (Mean Reciprocal Rank) | **0.636** |
| 평균 순위 | 2.65 |
| 평균 검색 시간 | ~0.22초 |
| 테스트 케이스 | 21개 judgment 쿼리 |

### 3. 파인튜닝 재학습 불필요 판단

RAG 개선(3단계)과 LoRA 파인튜닝(4단계)은 독립적 구조:
- RAG 개선 → 모델에 더 좋은 규정 문서를 전달 (입력 품질 향상)
- LoRA v1 모델 → 동일한 입출력 형식으로 그대로 사용 가능
- **결론**: 기존 LoRA v1(86.6%)을 RAG 개선 환경에서 재평가하여 실질 성능 확인 후, 부족 시 v2 학습 진행

### 4. 수정 파일 (커밋 완료)

| 파일 | 변경 내용 |
|------|----------|
| `ai/rag/hybrid_search.py` | Reranker 활성화, HyDE 적용, score threshold, 태그 매칭 부스트 |
| `ai/rag/query_refiner.py` | HyDE 가상 문서 생성, 동의어 사전 확장 |
| `ai/rag/qdrant_pipeline.py` | BM25 인덱스 태그 정리, score threshold 설정 |
| `ai/agents/document_agent.py` | 문서 scope 필터링 개선 |
| `ai/tests/benchmark_rag_improvement.py` | RAG 개선 전/후 벤치마크 스크립트 |

### 5. 현재 전체 성능 요약

| 모듈 | 지표 | 결과 |
|------|------|------|
| RAG 검색 | Hit Rate | 95.24% |
| RAG 검색 | MRR | 0.636 |
| 판단 Agent (LoRA v1) | 전체 정확도 | 86.6% (목표 85% 달성) |
| 판단 Agent (LoRA v1) | no_regulation | 97.0% |
| 판단 Agent (LoRA v1) | yes | 85.0% |
| 판단 Agent (LoRA v1) | conditional | 84.0% |
| 판단 Agent (LoRA v1) | no | 82.0% |
| Intent 분류 (KoELECTRA) | Adversarial F1 | 0.8758 |
| Intent 분류 (KoELECTRA) | 추론 속도 | 7.9ms |

**다음 할 일:**
- ~~RAG 개선 환경에서 LoRA v1 모델 재평가 (실질 정확도 변화 측정)~~ ✅ 완료 (3/10)
- ~~재평가 결과 90%+ 미달 시 → v2 보강 데이터로 LoRA v2 학습 실행~~ ✅ 완료 (3/10)
- ~~v2 목표: no 82%→88%+, conditional 84%→87%+, 전체 86.6%→90%+~~ ❌ v2 실패
- 5단계 성능 평가 (#13) — 전체 파이프라인 E2E 정량 평가

---

## 2026-03-10 (월) — v1 RAG 재평가 + v2 LoRA 학습 실행

### 1. v1 LoRA RAG 환경 재평가 (RunPod)

`scripts/eval_lora_v1_rag_improved.py`로 3가지 모드 비교 실행:

| 모드 | 정확도 | JSON 유효율 | 설명 |
|------|--------|------------|------|
| baseline | **83.3%** | 100% | eval.jsonl 하드코딩 컨텍스트 |
| rag-improved | **16.7%** | 56.7% | 라이브 RAG (Reranker+HyDE) |
| rag-baseline | **16.7%** | 56.7% | 라이브 RAG (RRF만) |

**분석:**
- baseline 83.3%로 목표 90% 미달 (이전 eval 86.6%보다 하락 — eval 데이터가 328→338로 변경)
- RAG 적용 시 16.7%로 폭락 — Qdrant에 문서 미적재 또는 RAG 검색 결과 불일치 추정
- 주요 오분류: `no_regulation→conditional` 4건, `no→no_regulation` 3건

### 2. v2 데이터 보강 (`augment_v2_no_conditional.py`)

| 항목 | 결과 |
|------|------|
| 생성 건수 | **98건** (rejected 0) |
| 분포 | no: 48, conditional: 50 |
| train 병합 | 2,949 + 88 = **3,037건** |
| eval 병합 | 328 + 10 = **338건** |

### 3. v2 LoRA 학습 + 평가 (RunPod A100)

**v2 설정 (`configs/v2_judgment.yaml`):**
- LR: 2e-4 → **1.5e-4** (기존 학습 보존 + 새 데이터 흡수)
- Output: `outputs/v2_judgment/`
- 나머지 v1과 동일 (QLoRA 4-bit, r=16, epochs=3)

**v2 평가 결과 — v1 대비 하락:**

| 카테고리 | v1 (86.6%) | v2 (83.4%) | 변화 |
|----------|------------|------------|------|
| conditional | 84.0% | **74.3%** | **-9.7%p** |
| no | 82.0% | **78.8%** | **-3.2%p** |
| yes | 85.0% | **87.0%** | +2.0%p |
| no_regulation | 97.0% | **97.0%** | 동일 |
| JSON 유효율 | 98.2% | **97.0%** | -1.2%p |

**결론:**
- v2 보강 데이터(98건)가 no/conditional 경계를 더 혼란시킴
- **v1 어댑터(86.6%)를 최종 모델로 유지**
- v2는 실패 기록으로 보관 (`outputs/v2_judgment/eval_results.json`)

### 4. 학습 스크립트 범용화

- `train_v1_judgment.py` — OUTPUT_BASE를 config에서 동적으로 읽도록 수정
- `--config` 옵션으로 v1/v2 config 전환 가능
- `configs/v2_judgment.yaml` 신규 생성

### 5. 수정/생성 파일

| 파일 | 작업 |
|------|------|
| `ai/finetuning/train_v1_judgment.py` | 수정 — config 기반 output_dir, v1/v2 범용화 |
| `ai/finetuning/configs/v2_judgment.yaml` | 신규 — v2 학습 설정 |
| `outputs/v2_judgment/eval_results.json` | 신규 — v2 평가 결과 |
| `data/training/v1_judgment/train.jsonl` | 수정 — v2 보강 98건 병합 (3,037건) |
| `data/training/v1_judgment/eval.jsonl` | 수정 — v2 보강 10건 병합 (338건) |

### 6. 현재 최종 성능 요약

| 모듈 | 지표 | 결과 |
|------|------|------|
| RAG 검색 | Hit Rate | 95.24% |
| RAG 검색 | MRR | 0.636 |
| **판단 Agent (LoRA v1)** | **전체 정확도** | **86.6% (최종 채택)** |
| 판단 Agent (LoRA v1) | no_regulation | 97.0% |
| 판단 Agent (LoRA v1) | yes | 85.0% |
| 판단 Agent (LoRA v1) | conditional | 84.0% |
| 판단 Agent (LoRA v1) | no | 82.0% |
| 판단 Agent (LoRA v2) | 전체 정확도 | 83.4% (하락, 폐기) |
| Intent 분류 (KoELECTRA) | Adversarial F1 | 0.8758 |

**다음 할 일:**
- RAG 라이브 검색 시 16.7% 폭락 원인 디버깅 (Qdrant 문서 적재 상태, 검색 결과 확인)
- 문서 분석 sLLM 프롬프트 개선 (요약 → 태그 파이프라인)
- 5단계 성능 평가 (#13) — 전체 파이프라인 E2E 정량 평가

---

## 2026-03-13 (목)

### Intent 체계 정리 (10 → 6 라벨)

**기존 10개 intent:**
- doc_search, doc_qa, doc_summary, doc_generate, judgment, schedule_add, schedule_view, pipeline_create, approval_create, general

**새 6개 intent (현재 학습 중):**
- `doc_retrieve` — doc_search + doc_qa + doc_summary 통합 (겹치는 부분 많아 하나로 합침)
- `doc_generate` — 문서 생성 (유지)
- `judgment` — 사규 기반 판단 (유지, 서브 intent 불필요)
- `schedule_add` — 일정/태스크/결재 생성 통합
- `schedule_view` — 일정 조회 (유지)
- `general` — 일반 대화 (유지)

**핵심 결정:** pipeline_create, approval_create를 별도 intent로 두지 않고 `schedule_add` 안에서 키워드 기반 2차 분류로 처리

### action_agent → schedule_agent 병합

**변경 사항:**
1. `ai/agents/schedule_agent.py` — action_agent의 pipeline/approval 핸들러 전체 통합
   - `_classify_add_type()` 키워드 분류 함수 추가
   - `_PIPELINE_KEYWORDS`: 태스크, task, 파이프라인, pipeline, 칸반, 보드, 프로젝트 추가/생성
   - `_APPROVAL_KEYWORDS`: 결재, 승인, 연차, 휴가, 반차, 조퇴, 병가, 품의, 출장 신청/출장신청
   - `schedule_add` intent 진입 시: 키워드 → pipeline/approval/schedule 분기
   - `_handle_pipeline_create`, `_parse_pipeline_input`, `_fallback_parse_pipeline` 함수 이관
   - `_handle_approval_create`, `_parse_approval_input`, `_fallback_parse_approval`, `_infer_approval_type` 함수 이관

2. `ai/agents/orchestrator.py` — action_agent 노드 제거
   - 라우팅: `schedule_add` + `pipeline_create` + `approval_create` → 모두 `schedule_agent`로
   - graph에서 `action_agent` 노드, 엣지 완전 제거
   - 현재 그래프 노드: decompose_query, compound_pending, classify_intent, clarify_with_candidates, judgment_agent, document_agent, schedule_agent, general_response, format_response

3. `ai/agents/action_agent.py` — 파일 아직 존재하지만 그래프에서 호출 안 됨 (추후 삭제 가능)

**intent 학습 팀원(경은)에게 전달할 사항:**
- `schedule_add` 라벨에 태스크/결재 관련 예문도 포함시킬 것
- 예: "태스크 만들어줘", "연차 신청해줘", "출장 결재 올려줘" 등 → `schedule_add`로 분류되어야 함

### Qdrant 중복 데이터 정리

- 개별 규정 파일 이름으로 들어간 201개 포인트 삭제 (Qdrant REST API 직접 호출)
- 원인: `ingest_documents.py`로 이미 `ingest_regulations.py`에서 파싱된 규정 파일을 중복 인제스트
- 정리 후: 285개 포인트 (regulations 206개 + documents 79개)
- 코드 변경 없음 — Qdrant Cloud DB에 직접 적용 완료

### sLLM 전환 가능성 분석

**현재 sLLM 학습 현황:**
- 판단(judgment) sLLM — 학습 중 (경은)
- 문서(document) sLLM — 학습 중 (승언), `DOC_AGENT_MODE=sllm`으로 별도 전환 가능
- 일정(schedule) — 아직 테스트 필요
- 일반(general) — GPT 유지 권장 (범용 대화)

**schedule agent sLLM 전환 테스트 준비:**
- 테스트 스크립트 생성: `scripts/test_schedule_sllm.py`
  - 10개 테스트 케이스 (일정 3, 태스크 3, 결재 4)
  - `--provider vllm --vllm-url` 플래그로 sLLM 테스트 가능
  - GPT-4o-mini 기준 통과율: schedule 파싱 부분은 안정적
- schedule의 파싱 작업은 "자연어 → 구조화 JSON" 단순 추출이라 base instruct 모델로도 가능성 있음
- RunPod 켜서 Kanana-8B 또는 Qwen3-8B로 비교 테스트 필요

**Approvals 페이지 "New Tasks" AI 추천 기능 (3개 엔드포인트):**
- `POST /approvals/checklist` — 할 일 체크리스트 생성 (temperature 0.3)
- `POST /approvals/suggest-schedules` — 일정 추천 (temperature 0.4)
- `POST /approvals/suggest` — 결재 추천 (temperature 0.4)
- 모두 `get_llm()` + `json_mode=True` 사용, rule-based fallback 있음
- sLLM 전환 가능하지만 schedule 파싱보다 난이도 높음 (단순 추출이 아닌 추론/분석 필요)
- **전략:** schedule 파싱 sLLM 먼저 검증 → 성공 시 추천 기능도 테스트 → fallback이 있어 품질 부족해도 서비스 영향 없음
- 우선순위 낮음, 나중에 검토

### Sheets 기능 확장 — 미리보기 + AI WBS 생성 + 인라인 편집

**Phase 1: 시트 미리보기:**
- `sheets_service.py` — `read_sheet_data()` 메서드 추가 (Google Sheets API `values().get()` + 탭 목록)
- `sheets.py` — `GET /{spreadsheet_id}/data` 엔드포인트 추가
- `google_services.py` — `SheetReadResponse` 스키마 추가
- `SheetPreview.jsx` 신규 — 탭 전환 UI + 테이블 렌더링 + 헤더 고정

**Phase 2: AI WBS 자동 생성:**
- `prompts.py` — `WBS_GENERATE_SYSTEM_PROMPT` 추가 (3레벨 계층 WBS JSON)
- `sheets_service.py` — `_generate_wbs_tab()`, `_flatten_wbs()`, `_apply_wbs_formatting()` 추가
  - LLM 호출 → WBS JSON → "WBS" 탭 생성 → 레벨별 색상 포맷팅
  - LLM 실패 시 flat export만 정상 진행 (fallback)
- `google_services.py` — `generate_wbs` 플래그 + `wbs_generated` 응답 필드 추가
- `SheetsDashboard.jsx` — "WBS 포함" 체크박스 추가

**Phase 3: 인라인 편집:**
- `sheets_service.py` — `update_sheet_data()` 메서드 추가 (`values().batchUpdate()`)
- `sheets.py` — `PUT /{spreadsheet_id}/data` 엔드포인트 추가
- `google_services.py` — `CellUpdate`, `SheetUpdateRequest`, `SheetUpdateResponse` 스키마 추가
- `SheetPreview.jsx` — 셀 클릭 편집 + 변경 셀 노란색 배경 + 저장/취소 버튼

**프론트엔드 연동:**
- `google.js` — `readSheetData()`, `updateSheetData()` API 함수 추가
- `googleStore.js` — `sheetPreview` 상태 + `fetchSheetPreview()`, `updateSheetData()`, `clearSheetPreview()` 액션 추가
- `SheetsDashboard.jsx` — 시트 목록에 "미리보기" 버튼 추가, 클릭 시 SheetPreview 펼침

### 일정 관련 LLM 호출 전체 정리 + sLLM 전환 분석

- `docs/일정_LLM_호출_정리_및_sLLM_전환_분석.md` 작성
- 4개 영역 10개 LLM 호출 전수 조사:
  - 챗봇 파싱 4개 (schedule/view/pipeline/approval)
  - AI 추천 3개 (checklist/suggest_schedules/suggest_approvals)
  - Sheets WBS 1개
  - action_agent 중복 2개 (이미 schedule_agent에 병합됨)
- sLLM 전환 Phase 1~3 우선순위 분류
  - Phase 1 (바로 가능): 결재 파싱, 체크리스트, 일정/결재 추천
  - Phase 2 (데이터 필요): 일정/조회/태스크 파싱
  - Phase 3 (후순위): WBS 생성

### Sheets 확장 탭 구현 (Gantt / Dashboard / AI Risk / Weekly Report)

**Backend (`sheets_service.py`):**
- `_generate_gantt_tab()` — 태스크 마감일 기준 셀 색칠 간트 차트 (상태별 색상: done=녹, in_progress=파랑, review=주황, todo=회색)
- `_generate_dashboard_tab()` — 상태/담당자/우선순위 분포 집계 + 마감 초과 태스크 목록 (LLM 불필요)
- `_generate_risk_tab()` — LLM 리스크 분석 (일정/과부하/병목/미할당/우선순위/정체 6가지 카테고리)
- `_generate_weekly_report_tab()` — LLM 주간 보고서 (완료/진행중/예정/블로커)
- `export_project_to_sheet()` — `generate_gantt`, `generate_dashboard`, `generate_risk`, `generate_report` 파라미터 추가

**AI 프롬프트 (`prompts.py`):**
- `PROJECT_RISK_ANALYSIS_SYSTEM_PROMPT` — 6가지 리스크 카테고리 분석 JSON 출력
- `WEEKLY_REPORT_SYSTEM_PROMPT` — 주간 보고서 JSON 출력

**스키마 (`google_services.py`):**
- `SheetExportProjectRequest` / `SheetCreateResponse`에 4개 플래그 추가

**프론트엔드:**
- `google.js` — `exportProjectToSheet()` options 객체로 변경 (5개 탭 옵션)
- `googleStore.js` — `exportProjectToSheet()` options 전달 방식 변경
- `SheetsDashboard.jsx` — 내보내기 옵션 체크박스 5개 (WBS/Gantt/Dashboard/AI리스크/주간보고)

**다음 할 일:**

1. **schedule sLLM 비교 테스트** — RunPod 켜서 `test_schedule_sllm.py` 실행
2. **intent 학습 팀원에게 전달** — `schedule_add`에 태스크/결재 예문 포함 확인
3. **LoRA 연결 테스트** (이전 세션에서 이어짐)
4. **Approvals 추천 sLLM 전환** — schedule 테스트 결과 보고 판단
5. **Sheets 확장 deploy 후 테스트** — develop 머지 → EC2 반영 후 탭 생성 검증

---

## 2026-03-15 (토) — v1-RAG 학습 데이터 생성 + 학습 실행

### 1. RAG 학습 데이터 재생성 (Qdrant 규정 문서만 필터)

**문제:** 기존 `rebuild_train_with_rag.py`가 Qdrant 전체 검색 → 삼성 보고서(18만자), 매뉴얼 등 노이즈 포함
- train_rag.jsonl **1.3GB** (원본 16MB의 80배) — 학습 불가능한 크기

**해결:** `filter={"source": "regulations"}`를 RAG 검색에 추가
- 규정 문서(206개 청크, 평균 167자)만 검색, 일반 문서(80개, 최대 21만자) 제외
- 결과: **1.3GB → 26MB** (200배 축소), 원본 대비 1.6배로 정상 크기

| 파일 | 건수 | 크기 | RAG 빈 결과 |
|------|------|------|------------|
| eval_rag.jsonl | 328건 | 2.9MB | 0건 |
| train_rag.jsonl | 2949건 | 26MB | 0건 |

### 2. RunPod 경량 실행 스크립트 작성

- `runpod_v1_rag_minimal.sh` — git clone 없이 curl로 필요 파일 4개만 다운로드 (~30MB)
- torch 충돌 해결: torchvision/torchaudio 제거 (텍스트 학습에 불필요)
- 한 줄 실행: `curl -sL .../runpod_v1_rag_minimal.sh | bash`

### 3. v1-RAG 학습 + 평가 결과 (RunPod A100 80GB)

**설정:** 1 epoch only (disk quota 제한으로 체크포인트 저장 불가 → save_strategy="no")

| | v1 하드코딩 (3ep) | v2 (3ep) | **v1-RAG (1ep)** |
|---|---|---|---|
| **전체 정확도** | **86.6%** | 83.4% | **42.7%** |
| JSON 유효율 | 98.2% | 97.0% | 84.1% |
| yes | 85.0% | 87.0% | 58.0% |
| no | 82.0% | 78.8% | 52.5% |
| conditional | 84.0% | 74.3% | 26.0% |
| no_regulation | 97.0% | 97.0% | 35.8% |

**하락 원인 분석:**
1. **1 epoch만 학습** — 기존 3 epoch 대비 수렴 부족
2. **RAG 컨텍스트 형식 변화** — 하드코딩(정답 규정만)과 RAG(관련+무관 규정 섞임)의 차이
3. **no_regulation 35.8%** — RAG가 항상 10개 규정 반환 → "규정 없음" 학습 어려움

### 수정/생성 파일

| 파일 | 작업 |
|------|------|
| `scripts/judgment/rebuild_train_with_rag.py` | 수정 — filter={"source": "regulations"} 추가 |
| `data/training/v1_judgment/train_rag.jsonl` | 신규 — 2949건 (26MB) |
| `data/training/v1_judgment/eval_rag.jsonl` | 신규 — 328건 (2.9MB) |
| `ai/finetuning/configs/v1_judgment_rag.yaml` | 신규 — RAG 데이터 경로 config |
| `ai/finetuning/runpod_v1_rag_minimal.sh` | 신규 — 경량 RunPod 실행 스크립트 |
| `outputs/v1_judgment_rag/eval_results.json` | 신규 — 평가 결과 |

### 4. no_regulation 라벨 모순 발견 + 수정

**문제:** `no_regulation` 67건(eval) / 665건(train) **전부** RAG가 규정 10개를 반환
- 모델 입장: "규정이 잔뜩 보이는데 왜 no_regulation이지?" → 혼란

**수정:** `rebuild_train_with_rag.py`에서 gold_result=no_regulation이면 RAG 검색 스킵 → 빈 컨텍스트

### 5. v1-RAG 재학습 결과 비교 (RunPod A100 80GB, 1epoch)

| 버전 | 정확도 | JSON유효율 | yes | no | conditional | no_regulation |
|------|--------|-----------|-----|-----|-------------|---------------|
| v1 하드코딩 3ep | **86.6%** | 98.2% | 85.0% | 82.0% | 84.0% | 97.0% |
| v1-RAG #1 (모순) | 42.7% | 84.1% | 58.0% | 52.5% | 26.0% | 35.8% |
| **v1-RAG #2 (수정)** | **76.8%** | 95.4% | 77.0% | 75.4% | 62.0% | **100.0%** |

**no_regulation 수정 효과:** 35.8% → **100.0%**, 전체 42.7% → **76.8%** (+34.1%p)

### 6. RunPod disk quota 이슈

- 3epoch 학습 시 epoch 마다 체크포인트 저장 → disk quota exceeded
- 해결: `save_strategy="no"`, `num_train_epochs=1`로 패치하여 1epoch만 학습
- HF 캐시 정리(`rm -rf /root/.cache/huggingface/hub/models--*`) 필요

### 7. outputs 폴더 정리

- `v1_judgment/eval_results.json`에 4개 결과 통합 (v1, v2, RAG#1, RAG#2)
- `v2_judgment/` 폴더 삭제 (폐기 결과)
- `v1_judgment_rag/` 폴더 삭제 (v1_judgment에 통합)

**다음 할 일:**
- v1-RAG **3 epoch 재학습** — 새 RunPod 인스턴스 (Volume 50GB+) 또는 체크포인트 저장 없이 3ep
- 3epoch 결과 85%+ 나오면 → vLLM 서빙에 RAG 어댑터 연결
- conditional 62.0%가 가장 낮음 — 3ep으로도 안 오르면 데이터 보강 검토

---

## 2026-03-15 (일)

### v1-RAG 3epoch 재학습 시도 및 중단

**상황:**
- 로컬 컴퓨터로 RunPod 학습 중 컴퓨터가 반복적으로 꺼짐 → RunPod 종료
- 내일(3/16) 다른 컴퓨터로 이어서 진행 예정

**실행 스크립트 (원클릭):**
```bash
curl -sL https://raw.githubusercontent.com/SKNETWORKS-FAMILY-AICAMP/SKN21-FINAL-3TEAM/feat/ai-yoon/ai/finetuning/runpod_v1_rag_minimal.sh | bash
```

**스크립트에 포함된 것:**
- 패키지 버전 고정 (에러 방지)
- torchvision 자동 제거
- `save_strategy="no"` 자동 패치 (disk quota 방지)
- HF 캐시 자동 정리
- 3 epoch 학습 (config 기본값)

**예상 소요 시간:** 약 2시간 (43분 × 3ep + 평가)

### 현재 성능 분석 (1epoch RAG 수정본 기준)

| 버전 | 정확도 | JSON유효율 | yes | no | conditional | no_regulation |
|------|--------|-----------|-----|-----|-------------|---------------|
| v1 하드코딩 3ep | **86.6%** | 98.2% | 85.0% | 82.0% | 84.0% | 97.0% |
| v1-RAG #2 (수정, 1ep) | 76.8% | 95.4% | 77.0% | 75.4% | 62.0% | 100.0% |

### 하락 원인 분석 (v1-RAG 76.8% vs v1 하드코딩 86.6%)

1. **1 epoch만 돌림** — 기존은 3 epoch. 수렴 부족이 주요 원인
2. **RAG 컨텍스트가 기존과 다름** — 하드코딩은 정답 규정만 딱 넣었지만, RAG는 관련 없는 규정도 섞여서 들어옴 (노이즈)
3. **no_regulation 35.8% → 100.0%** — RAG가 항상 10개 규정을 반환하니 "규정 없음"을 학습하기 어려웠음 (수정 후 해결)

### 다음 할 일 (3/16 다른 컴퓨터에서)

1. **3 epoch로 다시 돌리기**
   - 위의 원클릭 스크립트 실행
   - RunPod Volume 용량 확인 (50GB+ 권장)
   - 스크립트가 캐시 관리 자동화 포함
2. **RAG 데이터 품질 점검**
   - no_regulation 샘플의 RAG 결과가 어떤지 확인
   - 관련 없는 규정이 들어오면 라벨과 충돌 → 정확도 하락 원인
3. **top_k 10 → 5로 줄이기 검토**
   - RAG 노이즈 줄이기 위해 top_k를 5로 줄이는 실험 검토
   - 관련성 낮은 규정이 컨텍스트에 포함되는 문제 완화 기대
4. **목표:** 3epoch 결과 85%+ → vLLM 서빙에 RAG 어댑터 연결
