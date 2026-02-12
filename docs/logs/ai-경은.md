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
- `ai/rag/vectorstore.py` — ChromaDB PersistentClient, cosine 유사도, scope 필터, upsert 지원
- `ai/rag/hybrid_search.py` — BM25 + Vector 하이브리드 검색, RRF(k=60) 합산, scope 필터 (BM25/Vector 양쪽)
- `ai/rag/reranker.py` — CrossEncoder("BAAI/bge-reranker-v2-m3") 싱글턴 리랭커
- `ai/rag/pipeline.py` — 오케스트레이션 (initialize → add_documents → retrieve), 배치 처리(batch_size=100), 싱글턴 팩토리
- `ai/rag/__init__.py` — 공개 API (RAGPipeline, get_pipeline, reset_pipeline)

**RAG QA 및 버그 수정:**
- BM25 scope 필터 누락 (보안 이슈) → personal 문서 격리 로직 추가
- ChromaDB n_results > collection.count() 에러 → min(top_k, count) 캡 추가
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
