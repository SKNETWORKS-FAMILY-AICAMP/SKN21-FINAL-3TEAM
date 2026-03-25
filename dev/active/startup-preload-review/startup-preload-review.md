# Startup Preload 아키텍처 리뷰

**리뷰 일자**: 2026-03-26
**대상 파일**:
- `backend/app/main.py` (L56-191)
- `ai/rag/qdrant_pipeline.py`
- `ai/rag/hybrid_search.py` (L340-360)
- `ai/rag/reranker.py`
- `ai/agents/orchestrator.py` / `intent_classifier.py`
- `ai/llm/factory.py`

---

## 1. 현재 Startup 순서 및 타이밍 분석

서버 기동 시 `@app.on_event("startup")` 3개가 **등록 순서대로 순차 실행**된다:

| 순서 | 핸들러 | 실행 방식 | 예상 소요시간 |
|------|--------|-----------|---------------|
| 1 | `startup_db_migrations` (L56) | **blocking** | 1-3초 (DDL + 템플릿 시딩) |
| 2 | `startup_slack_scheduler` (L123) | 즉시 반환 (asyncio.create_task) | <10ms |
| 3 | `startup_preload` (L156) | 즉시 반환 (asyncio.create_task) | <10ms (등록만) |

`startup_preload` 내부 백그라운드 태스크:

| 단계 | 작업 | 예상 소요시간 | 비고 |
|------|------|---------------|------|
| 0 | `asyncio.sleep(3)` (L174) | 3초 | 의도적 지연 |
| 1 | `EmbeddingModel.load_model()` — `jhgan/ko-sbert-nli` 다운로드/로드 | 2-5초 (캐시 있을 때) | SentenceTransformer |
| 2 | `QdrantVectorStore.initialize()` — 컬렉션 확인/생성 | 0.5-1초 | 네트워크 I/O |
| 3 | `HybridSearcher.build_bm25_index()` — 전체 문서 조회 + 토크나이징 | 1-5초 (문서량 의존) | CPU bound |

**서버가 요청 수락 가능한 시점**: startup 핸들러 3개 완료 후 = **약 1-3초**
**RAG 파이프라인 실제 가용 시점**: 서버 시작 후 **약 6-14초** (3초 sleep + 파이프라인 초기화)

---

## 2. Lazy Loading 컴포넌트 분석

현재 첫 번째 요청 시 lazy load되는 컴포넌트:

| 컴포넌트 | 로드 시점 | 예상 소요시간 | 위치 |
|----------|-----------|---------------|------|
| **Reranker** (bge-reranker-v2-m3) | `use_reranker=True` 첫 요청 | **5-10초** | `reranker.py` L33-38 |
| **Intent Classifier** (ONNX 앙상블) | 첫 채팅 요청 | **1-3초** (ONNX) / **5-10초** (PyTorch) | `intent_classifier.py` L78-153 |
| **LLM Provider** (OpenAI/Anthropic) | 첫 LLM 호출 | **<0.5초** (API 클라이언트 생성만) | `factory.py` L40-46 |
| **kiwipiepy** (형태소 분석기) | 모듈 import 시 | **1-2초** | `hybrid_search.py` L29-30 |

---

## 3. 문제점 및 개선 제안

### 3.1 [높음] Intent Classifier를 startup으로 옮겨야 함

**현재**: `get_classifier()`가 첫 채팅 요청에서 호출되어 lazy load
**문제**: 첫 사용자 채팅에서 1-3초(ONNX) 또는 5-10초(PyTorch) 추가 지연 발생. 채팅이 가장 빈번한 기능이므로 cold start penalty가 **모든 서버 재시작마다** 첫 사용자에게 전가됨.

**제안**: `startup_preload` 백그라운드 태스크에서 RAG 파이프라인과 **병렬로** 로드

```python
# main.py startup_preload 내부
async def _background_preload():
    await asyncio.sleep(3)

    # 병렬 실행
    loop = asyncio.get_event_loop()
    await asyncio.gather(
        asyncio.wait_for(
            loop.run_in_executor(None, get_qdrant_pipeline),
            timeout=180,
        ),
        asyncio.wait_for(
            loop.run_in_executor(None, _preload_classifier),
            timeout=60,
        ),
    )

def _preload_classifier():
    from ai.agents.intent_classifier import get_classifier
    clf = get_classifier()
    clf.load_model()
```

**효과**: 첫 채팅 응답 시간 1-10초 단축, 추가 startup 시간 0초 (병렬이므로)

---

### 3.2 [높음] Reranker를 startup으로 옮겨야 함

**현재**: `reranker.py` L60-61에서 `rerank()` 첫 호출 시 lazy load
**문제**: `bge-reranker-v2-m3`은 ~1.1GB 모델. 첫 reranker 사용 시 5-10초 지연. 문서 검색 품질에 직결되는 기능.

**제안**: 위 `asyncio.gather`에 추가

```python
def _preload_reranker():
    from ai.rag.reranker import Reranker
    Reranker().load_model()
```

**트레이드오프**: 메모리 ~1.1GB 추가 점유. reranker를 사용하지 않는 배포 환경에서는 환경변수 플래그로 제어 가능.

---

### 3.3 [중간] `asyncio.sleep(3)` 의도적 지연 제거 가능

**현재**: `main.py` L174 — 서버가 요청을 먼저 받을 수 있도록 3초 대기
**문제**: `asyncio.create_task`로 등록된 백그라운드 태스크는 이미 **startup 핸들러가 모두 완료된 뒤** event loop에서 실행됨. FastAPI의 lifespan은 startup 완료 후 요청 수락을 시작하므로, sleep(3)은 불필요한 3초 낭비.

**제안**: `await asyncio.sleep(3)` 제거 또는 `await asyncio.sleep(0.1)` 정도로 축소

**효과**: RAG 가용 시점 3초 단축

---

### 3.4 [중간] RAG 초기화가 순차 실행됨 — 부분 병렬화 가능

**현재** (`qdrant_pipeline.py` L53-71):
```
임베딩 모델 로드 (2-5초) → Qdrant 초기화 (0.5-1초) → BM25 인덱스 구축 (1-5초)
```
모두 순차 실행.

**병렬화 가능한 부분**:
- 임베딩 모델 로드 + Qdrant 초기화는 독립적 → 병렬 가능
- BM25 인덱스 구축은 Qdrant 초기화 완료 후에만 가능 (Qdrant에서 문서 조회 필요) → 순차 유지

```python
def initialize(self):
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f_emb = executor.submit(self.embedding_model.load_model)
        f_qdrant = executor.submit(self.vector_store.initialize, 768)
        f_emb.result()
        f_qdrant.result()
    # BM25는 Qdrant 이후
    self.searcher.build_bm25_index()
```

**효과**: 초기화 시간 약 1-3초 단축 (임베딩 로드와 Qdrant 연결이 겹침)

---

### 3.5 [낮음] kiwipiepy 모듈 레벨 초기화

**현재**: `hybrid_search.py` L28-33에서 모듈 import 시 `Kiwi()` 생성
**분석**: 이 모듈은 `QdrantRAGPipeline.__init__` → `HybridSearcher` import 시점에 실행됨. 즉, startup_preload 백그라운드 태스크 내에서 이미 처리됨.

**현재 상태 적절함** — 변경 불필요.

---

### 3.6 [낮음] LLM Provider는 lazy loading 유지가 적절

**현재**: `factory.py` L40-46 — `get_llm()` 첫 호출 시 생성
**분석**: API 클라이언트 생성은 <0.5초이고, 환경변수에 따라 다른 provider가 선택됨. startup에서 미리 생성해도 이점이 미미.

**현재 상태 적절함** — 변경 불필요.

---

### 3.7 [중간] DB 마이그레이션 ALTER TABLE 방식 개선

**현재**: `main.py` L84-120 — 매 startup마다 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` 10개 + UPDATE + DELETE 실행
**문제**:
- Alembic을 사용하고 있으면서 수동 ALTER TABLE을 병행하는 이중 관리
- 매 startup마다 불필요한 DDL 실행 (이미 존재하는 컬럼 추가 시도)
- L101-103: 랜덤 team 배정 UPDATE가 **매번** 실행됨 (`WHERE team IS NULL` 조건이 있지만 불필요한 쿼리)
- L111: `DELETE FROM action_items WHERE created_by IS NULL`이 매 startup마다 실행 — 의도치 않은 데이터 삭제 위험

**제안**:
1. Alembic 마이그레이션으로 통합 (한 번 실행 후 startup에서 제거)
2. 최소한 `IF NOT EXISTS` 결과를 체크하여 불필요한 후속 쿼리 스킵

---

## 4. 최적화 적용 시 예상 타이밍

### Before (현재)

```
[0.0s] startup_db_migrations 시작
[1-3s] startup_db_migrations 완료
[1-3s] startup_slack_scheduler 등록
[1-3s] startup_preload 백그라운드 등록 → 서버 요청 수락 시작
[4-6s] (sleep 3초 후) RAG 파이프라인 초기화 시작
[8-17s] RAG 파이프라인 로드 완료
---
첫 채팅 요청 시: Intent Classifier 로드 +1-10초
첫 reranker 요청 시: Reranker 로드 +5-10초
```

**Cold start 후 첫 채팅 응답**: **9-27초**

### After (제안 적용 시)

```
[0.0s] startup_db_migrations 시작
[1-3s] startup_db_migrations 완료
[1-3s] startup_slack_scheduler + startup_preload 등록 → 서버 요청 수락 시작
[1-3s] 백그라운드 병렬 로드 시작:
       ├── RAG 파이프라인 (임베딩 + Qdrant 병렬 → BM25 순차)
       ├── Intent Classifier (ONNX)
       └── Reranker
[5-10s] 모든 백그라운드 로드 완료
```

**Cold start 후 첫 채팅 응답**: **0.5-2초** (LLM API 호출 시간만)

---

## 5. 메모리 영향 분석

| 컴포넌트 | 메모리 | 로드 시점 (현재) | 로드 시점 (제안) |
|----------|--------|------------------|------------------|
| 임베딩 모델 (ko-sbert-nli) | ~250MB | startup 백그라운드 | 동일 |
| Qdrant 클라이언트 | ~10MB | startup 백그라운드 | 동일 |
| BM25 인덱스 | ~50-200MB (문서량) | startup 백그라운드 | 동일 |
| Reranker (bge-reranker-v2-m3) | **~1.1GB** | 첫 reranker 요청 | startup 백그라운드 |
| Intent Classifier (ONNX x5) | **~200-400MB** | 첫 채팅 | startup 백그라운드 |
| kiwipiepy | ~50MB | 모듈 import | 동일 |
| LLM Provider | <10MB | 첫 LLM 호출 | 동일 (유지) |

**총 상주 메모리**: 현재 ~560MB → 제안 후 ~2.1GB (Reranker가 가장 큼)

**프로덕션 권장**: EC2 인스턴스 최소 **4GB RAM** (여유 포함 8GB 권장)

---

## 6. 프로덕션 배포 고려사항

### 6.1 Health Check 엔드포인트 필요

현재 preload가 백그라운드로 실행되므로, 로드밸런서가 서버를 라우팅 대상에 추가하기 전에 "모든 컴포넌트 준비 완료"를 확인할 방법이 없다.

**제안**: `/health` 엔드포인트에 readiness 상태 추가

```python
# 전역 플래그
_preload_ready = False

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "rag_ready": _preload_ready,
        "classifier_ready": _classifier_instance is not None,
    }
```

### 6.2 Graceful Degradation

현재 구현은 preload 실패 시 `except`로 무시하고 계속 진행 (L187-188). 이는 적절하지만, 로그 레벨이 `print`로만 출력되어 모니터링 시스템에 잡히지 않을 수 있다.

**제안**: `logger.error()` 사용 + 메트릭 전송

### 6.3 Docker 빌드 시 모델 캐시

SentenceTransformer/CrossEncoder 모델은 첫 실행 시 Hugging Face Hub에서 다운로드한다. Docker 이미지 빌드 시 모델을 미리 다운로드하여 캐시에 포함시키면 cold start가 더 빨라진다.

```dockerfile
# Dockerfile
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('jhgan/ko-sbert-nli')"
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('BAAI/bge-reranker-v2-m3')"
```

---

## 7. 우선순위별 액션 아이템

| 우선순위 | 항목 | 예상 효과 | 난이도 |
|----------|------|-----------|--------|
| **P0** | Intent Classifier startup 병렬 로드 (3.1) | 첫 채팅 1-10초 단축 | 낮음 |
| **P0** | `asyncio.sleep(3)` 제거 (3.3) | RAG 가용 3초 단축 | 매우 낮음 |
| **P1** | Reranker startup 병렬 로드 (3.2) | 첫 검색 5-10초 단축 | 낮음 |
| **P1** | RAG 초기화 부분 병렬화 (3.4) | 초기화 1-3초 단축 | 낮음 |
| **P2** | Health check readiness (6.1) | 배포 안정성 향상 | 낮음 |
| **P2** | DB 마이그레이션 정리 (3.7) | startup 안정성, 코드 정리 | 중간 |
| **P3** | Docker 모델 캐시 (6.3) | cold start 추가 단축 | 낮음 |
