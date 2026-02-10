# WorkFlow Agent (듀듀) - 역할 분배 & 기술 스택 (v5 Final)

> 멘토 피드백 전체 반영 / 기간 무제한 / Claude Max 전원 / 데이터 3,800개 / Google Services 통합

---

# Part 1. 멘토 피드백 기반 변경 사항

> 아래 내용은 멘토님 조언을 반영하여 기존 계획에서 변경된 사항입니다.
> 전원 숙지 필요합니다.

---

## 변경 1. LangChain → LangGraph 전환

### 왜 바꾸는가
멘토님이 "LangChain은 종속되는 느낌이 있고, LangGraph가 요즘 많이 사용된다"고 추천하셨습니다. 우리 프로젝트는 3개의 Agent(판단/문서/일정)를 하나의 오케스트레이터가 라우팅하는 구조인데, LangGraph가 이 패턴에 정확히 맞습니다.

### 뭐가 다른가

**LangChain (기존)**
- 체인(Chain) 기반 → 순차적 파이프라인에 강함
- Agent 간 분기/합류가 복잡해지면 코드가 꼬임
- 프레임워크에 종속되는 느낌이 강함

**LangGraph (변경)**
- 그래프(Graph) 기반 → 노드(Agent)와 엣지(라우팅)로 표현
- 상태(State)를 명시적으로 관리 → 멀티턴 대화, 조건부 분기에 강함
- Agent 간 데이터 전달이 자연스러움

### 우리 프로젝트에 적용하면

```
[사용자 입력]
     ↓
[Intent 분류 노드] → state에 intent 저장
     ↓ (조건부 엣지)
     ├── intent == "judgment"     → [판단 Agent 노드]
     ├── intent == "doc_*"        → [문서 Agent 노드]
     ├── intent == "schedule_*"   → [일정 Agent 노드]
     └── confidence < 0.7         → [재질문 노드]
     ↓
[응답 포맷팅 노드]
     ↓
[사용자에게 스트리밍 응답]
```

각 노드가 독립적이라서 팀원 B/C/D가 각자 Agent를 만들고, 팀원 A가 그래프로 엮는 구조가 됩니다.

### 영향 받는 팀원
- **팀원 A**: Agent 오케스트레이터를 LangGraph StateGraph로 구현
- **팀원 B**: 판단 Agent를 LangGraph 노드 인터페이스에 맞춰 개발
- **팀원 C**: 문서 Agent를 LangGraph 노드 인터페이스에 맞춰 개발
- **팀원 D**: 일정 Agent를 LangGraph 노드 인터페이스에 맞춰 개발

### 팀원 전원 참고: 노드 인터페이스 규칙
```python
# 모든 Agent는 이 형태를 따릅니다 (팀원 A가 1단계에서 확정)
from typing import TypedDict

class AgentState(TypedDict):
    user_input: str
    intent: str
    confidence: float
    context: list        # RAG 검색 결과
    agent_response: dict  # 각 Agent의 응답
    chat_history: list

# 각 Agent 노드 함수 형태
def judgment_agent(state: AgentState) -> AgentState:
    # 팀원 B가 구현
    ...
    return {**state, "agent_response": result}
```

---

## 변경 2. Reranking 단계 추가

### 왜 추가하는가
멘토님이 Reranking을 언급하셨습니다. 현재 Hybrid Search(BM25 + Vector)만으로는 검색 결과에 노이즈가 섞일 수 있습니다. Reranker가 검색 결과를 한 번 더 정밀하게 재정렬해서 진짜 관련 있는 규정만 LLM에 전달합니다.

### 변경 전후 비교

**기존 RAG 파이프라인**
```
사용자 질문 → BM25 검색 (Top 10) + Vector 검색 (Top 10)
           → 합산 정렬 (Top 5)
           → sLLM에 전달
```

**변경된 RAG 파이프라인**
```
사용자 질문 → BM25 검색 (Top 15) + Vector 검색 (Top 15)
           → 합산 (Top 20)
           → [Reranker] 관련도 재정렬 (Top 5)
           → sLLM에 전달
```

### 사용 모델
- **BAAI/bge-reranker-v2-m3**: 다국어 지원, 한국어 성능 우수, 경량
- 입력: (질문, 문서) 쌍 → 출력: 관련도 점수 (0~1)

### 효과
- 판단 Agent: 관련 규정을 더 정확하게 찾아서 판단 정확도 향상
- 문서 Agent: 리스크 감지 시 정확한 위반 조항 매칭

### 영향 받는 팀원
- **팀원 B**: RAG 파이프라인에 Reranking 단계 추가 구현 (주 담당)

---

## 변경 3. 파인튜닝 용도별 2개로 분리

### 왜 나누는가
멘토님이 "요약보단 RAG에 하는 게 좋다", "몇 개 할 건지 정해라", "튜닝도 다양한 버전 시도하기"라고 하셨습니다. 하나의 모델로 판단도 하고 요약도 하면 둘 다 중간만 하게 됩니다. 용도별로 나눠서 각각 잘하는 모델을 만드는 게 더 좋습니다.

### 파인튜닝 구조

**동일한 베이스 모델 (7~8B)에서 LoRA 어댑터만 다르게 학습**

| 구분 | v1: RAG 판단 특화 | v2: 문서 분석 특화 |
|------|-----------------|------------------|
| **목적** | 규정 검색 결과를 보고 Yes/No 판단 + 근거 + 대안 생성 | 회의록 구조화, 문서 요약, 리스크 감지 |
| **학습 데이터** | 판단 1,000개 + 규정 Q&A 1,000개 = **2,000개** | 회의록 700 + 요약 500 + 생성 400 + 리스크 200 = **1,800개** |
| **출력 형식** | Yes/No + [근거] 조항 + [대안] 목록 | JSON (결정사항, Action Item, 기한) / 요약문 |
| **담당** | 팀원 B (메인) | 팀원 C (메인) |
| **사용처** | 판단 Agent | 문서 Agent |

### vLLM에서 LoRA 어댑터 교체
vLLM은 LoRA 어댑터를 런타임에 교체할 수 있습니다 (핫스왑). 베이스 모델 하나만 메모리에 올려두고, 요청에 따라 판단용/문서용 어댑터를 바꿔 끼우면 됩니다. GPU 메모리 효율적입니다.

```
[베이스 모델: Qwen3-8B] ← 메모리에 상주
     ├── + LoRA v1 (판단)  → 판단 Agent가 호출
     └── + LoRA v2 (문서)  → 문서 Agent가 호출
```

### 데이터 3,800개 상세 분배

| 카테고리 | 수량 | 데이터 형식 | 사용 어댑터 | 담당 |
|---------|------|-----------|----------|------|
| 규정 기반 Yes/No 판단 | **1,000개** | instruction/input(규정+질문)/output(판단+근거+대안) | LoRA v1 | 팀원 B |
| 규정 해석 Q&A | **1,000개** | instruction/input(규정+질문)/output(해석) | LoRA v1 + v2 공용 | 팀원 C (작성) + 팀원 B (검증) |
| 회의록 → 결정사항/Action Item 추출 | **700개** | input(회의록)/output(JSON) | LoRA v2 | 팀원 C |
| 문서 요약 | **500개** | input(문서)/output(요약문) | LoRA v2 | 팀원 C |
| 문서 생성 (템플릿 기반) | **400개** | input(요약+요구)/output(생성문서) | LoRA v2 | 팀원 C |
| 리스크 감지 | **200개** | input(문서+규정)/output(리스크JSON) | LoRA v2 | 팀원 C |
| **합계** | **3,800개** | | | |

#### 어댑터별 학습 데이터

| 어댑터 | 데이터 | 합계 |
|--------|-------|------|
| **LoRA v1** (판단 특화) | 판단 1,000 + Q&A 1,000 | **2,000개** |
| **LoRA v2** (문서 특화) | 회의록 700 + 요약 500 + 생성 400 + 리스크 200 | **1,800개** |

- 검증용 15% 별도 분리 (학습에 사용하지 않음)
- Claude/GPT-4로 초안 생성 → 사람이 검증/수정하는 방식으로 품질 확보

### 영향 받는 팀원
- **팀원 B**: v1 파인튜닝 메인 + 판단 데이터 1,000개 구축
- **팀원 C**: v2 파인튜닝 메인 + 문서 데이터 2,800개 구축 (Q&A 1,000개 포함)
- **팀원 A**: 오케스트레이터에서 Agent별 LoRA 어댑터 지정 호출

---

## 변경 4. 판단 Agent 기능 확장

### 왜 키우는가
멘토님이 "판단 Agent 더 키워야 함. 문서 Agent에서 조금 더 나아간 정도로 보인다"고 하셨습니다. 판단이 우리 프로젝트의 핵심 차별점인데, 단순 Yes/No만으로는 경쟁사 대비 차별화가 약합니다.

### 추가되는 기능

**① 다중 규정 교차 판단**
```
질문: "인턴에게 AWS 콘솔 접근 권한을 줘도 되나요?"

[기존] 정보보안 규정 3.2조 기반 → No

[변경] 
- 정보보안 규정 3.2조: 수습 6개월 내 프로덕션 접근 불가 → No
- 개발 가이드라인 5.1조: 테스트 환경은 팀장 승인 후 가능 → 조건부 Yes
- 인사 규정 2.3조: 인턴은 수습 기간 적용
→ 종합 판단: 조건부 가능 (테스트 환경 한정, 팀장 승인 필요)
```

**② 판단 confidence score**
- 높음 (0.8~1.0): 명확한 규정 근거 있음
- 중간 (0.5~0.8): 관련 규정은 있으나 해석 여지 있음 → "관리자 검토 권고" 표시
- 낮음 (0.5 미만): 관련 규정 없음 → "규정 추가 필요" 안내

**③ 조건부 판단 세분화**
- Yes / No / 조건부 가능 / 규정 없음 (4가지)
- 조건부일 때: 어떤 조건을 충족하면 가능한지 구체적으로 제시

**④ 판단 이력 참조** (선택적 구현)
- 과거 유사 질문에 대한 판단 기록 조회
- 이전 판단과 모순되는 답변 방지

### 영향 받는 팀원
- **팀원 B**: 판단 Agent 프롬프트 및 로직 확장 (주 담당)
- **팀원 A**: 오케스트레이터에서 판단 이력 DB 조회 지원
- **팀원 D**: 판단 이력 테이블 추가 (judgments 테이블)
- **팀원 E**: 판단 응답 UI 확장 (confidence 뱃지, 다중 규정 표시, 조건부 판단 카드)

---

## 변경 5. Streaming 응답 구현

### 왜 필요한가
멘토님이 "기다려서 보여주는 거랑, 생성하는 즉시 보여주는 게 사용자 입장에서 굉장히 다르다. 많은 팀이 어려워했다"고 하셨습니다. LLM 응답이 3~5초 걸리는데, 빈 화면으로 기다리는 것과 글자가 하나씩 나오는 것은 체감이 완전히 다릅니다.

### 구현 방식: SSE (Server-Sent Events)

**전체 흐름**
```
[React 챗봇] ←──── SSE 스트림 ────── [FastAPI] ←── 토큰 스트림 ── [vLLM]
    │                                    │
    │  "분석 중..." 표시                   │  Intent 분류 결과 전송
    │  토큰 하나씩 렌더링                   │  Agent 호출 상태 전송
    │  완료 후 카드 UI로 정리               │  LLM 토큰 스트리밍
```

**Backend (팀원 A 담당)**
```python
from fastapi.responses import StreamingResponse

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    async def event_generator():
        # 1. Intent 분류 결과 전송
        intent = classify_intent(request.message)
        yield f"data: {json.dumps({'type': 'intent', 'value': intent})}\n\n"
        
        # 2. Agent 호출 상태 전송
        yield f"data: {json.dumps({'type': 'status', 'value': '판단 Agent 호출 중...'})}\n\n"
        
        # 3. LLM 응답 토큰 스트리밍
        async for token in agent.stream(request.message):
            yield f"data: {json.dumps({'type': 'token', 'value': token})}\n\n"
        
        # 4. 완료
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

**Frontend (팀원 E 담당)**
```javascript
const eventSource = new EventSource('/api/chat/stream');

eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    switch(data.type) {
        case 'intent':
            // 의도 분류 뱃지 표시
            showIntentBadge(data.value);
            break;
        case 'status':
            // "판단 Agent 호출 중..." 표시
            showStatus(data.value);
            break;
        case 'token':
            // 글자 하나씩 추가
            appendToken(data.value);
            break;
        case 'done':
            // 최종 카드 UI로 정리
            renderFinalCard();
            eventSource.close();
            break;
    }
};
```

**vLLM 스트리밍 (팀원 B 담당)**
```python
# vLLM 서버 실행 시 스트리밍 자동 지원
# --enable-chunked-prefill 옵션으로 더 빠른 첫 토큰 생성
```

### 영향 받는 팀원
- **팀원 A**: FastAPI SSE 엔드포인트 구현, 스트리밍 오케스트레이션
- **팀원 B**: vLLM 스트리밍 출력 설정
- **팀원 E**: EventSource 수신 + 실시간 토큰 렌더링 + 완료 후 카드 UI 변환

---

## 변경 6. 문서 전처리 도구 교체

### 왜 바꾸는가
멘토님이 "PDF나 Excel 비정형 문서 전처리가 쉽지 않다"고 경고하셨고, "Docling 또는 PaddleOCR"을 추천하셨습니다. 기존 PyPDF2 + pytesseract로는 테이블이 있는 PDF나 복잡한 레이아웃의 문서를 제대로 파싱하기 어렵습니다.

### 변경 전후

**기존**
- PyPDF2: 단순 텍스트 추출만 가능, 테이블/레이아웃 인식 불가
- pytesseract: 한국어 OCR 성능 보통

**변경**
- **Docling (IBM)**: PDF의 테이블, 헤더, 본문 구조를 인식해서 마크다운으로 변환. 규정 문서처럼 조항 구조가 있는 문서에 최적
- **PaddleOCR**: 한국어 OCR 성능 최상급. 스캔된 문서나 이미지 기반 문서에 사용

### 적용 전략
```
문서 업로드
    ↓
파일 형식 확인
    ├── 디지털 PDF → Docling으로 구조화 파싱
    ├── 스캔 PDF / 이미지 → PaddleOCR로 텍스트 추출 → Docling으로 구조화
    ├── DOCX → python-docx로 파싱
    └── TXT → 직접 읽기
    ↓
구조화된 텍스트 (마크다운)
    ↓
청킹 → 임베딩 → Vector DB 저장
```

### Docling 사용 예시
```python
from docling.document_converter import DocumentConverter

converter = DocumentConverter()
result = converter.convert("규정문서.pdf")

# 마크다운으로 변환 (테이블, 헤더 구조 유지)
markdown_text = result.document.export_to_markdown()

# 조항 단위로 분할
sections = split_by_sections(markdown_text)
```

### 영향 받는 팀원
- **팀원 C**: 문서 파싱 파이프라인 전면 교체 (Docling + PaddleOCR) — 주 담당

---

## 변경 7. 모델 서빙 vLLM 확정 + 모델 후보 업데이트

### 모델 서빙
멘토님이 "HuggingFace vLLM 프레임워크 서빙하면 좋겠다"고 하셨습니다.

**vLLM 확정 이유**
- PagedAttention으로 GPU 메모리 효율 최고
- 스트리밍 출력 기본 지원 (변경 5번과 연결)
- LoRA 어댑터 핫스왑 지원 (변경 3번과 연결 — 판단용/문서용 전환)
- RunPod에서 바로 사용 가능
- OpenAI 호환 API 제공 → 프론트엔드 연동 편리

### 모델 후보 업데이트
멘토님이 "퀜3? 카나나? 베이스라인 비교하기"라고 하셨습니다.

| 모델 | 크기 | 한국어 성능 | 특징 | 우선순위 |
|------|------|-----------|------|---------|
| **Qwen3** | 8B | 상위권 | 멘토 직접 언급, 다국어 강세, 커뮤니티 활발 | ⭐ 1순위 |
| **Kanana** | 8B | 한국어 특화 | 멘토 직접 언급, 카카오 개발 | ⭐ 1순위 |
| **EXAONE 3.5** | 7.8B | 상위권 | LG AI Research, Apache 2.0 | 2순위 |

→ **1단계에서 이 3개 모델을 동일 테스트셋으로 베이스라인 비교 후 선정**
→ 비교 지표: 한국어 이해도, 규정 해석 정확도, 판단 형식 준수율, 추론 속도
→ 멘토님 말씀대로 "튜닝 해봐야 소용없겠다는 판단"을 이 단계에서 내림

### RunPod 비용 고려
멘토님이 "파인튜닝해서 RunPod 비용 많이 들 것으로 예상. 7~8B 이내"라고 하셨습니다.

- 모델 크기: **8B 이내로 확정** (SOLAR 10.7B는 비용 문제로 제외)
- 권장 GPU: A100 40GB 또는 A6000 48GB
- 파인튜닝 예상: 3,800개 × 3~5 epoch ≈ 3~6시간/회 (A100)
- **실험 계획을 먼저 세우고 체계적으로 실행** (무계획 실험 → 비용 폭증)

### 영향 받는 팀원
- **팀원 B**: 모델 벤치마크 + vLLM 서빙 환경 구축 (주 담당)
- **팀원 C**: 벤치마크 테스트 데이터 준비 (보조)

---

## 변경 8. 회사/개인 문서 분리

### 왜 필요한가
멘토님이 "회사/개인 문서 분리"를 언급하셨습니다. 규정 문서는 전 직원이 검색할 수 있어야 하지만, 개인이 올린 메모나 초안은 본인만 봐야 합니다.

### 구현 방식

**DB 스키마 변경 (팀원 D)**
```sql
-- documents 테이블에 scope 컬럼 추가
ALTER TABLE documents ADD COLUMN scope VARCHAR(10) DEFAULT 'company';
-- scope: 'company' (회사 공용) / 'personal' (개인)
```

**RAG 검색 필터 (팀원 B/C)**
```python
# 검색 시 회사 문서는 항상 포함 + 개인 문서는 본인 것만
def search_documents(query, user_id):
    filter = {
        "$or": [
            {"scope": "company"},
            {"scope": "personal", "uploaded_by": user_id}
        ]
    }
    return vector_db.search(query, filter=filter)
```

**업로드 UI (팀원 E)**
- 문서 업로드 시 "회사 공용 / 개인" 선택 라디오 버튼
- 문서 목록에서 범위별 필터

### 영향 받는 팀원
- **팀원 D**: DB 스키마에 scope 필드 추가
- **팀원 B**: RAG 검색 시 scope 필터 적용
- **팀원 C**: 문서 Agent에서 scope 반영
- **팀원 E**: 업로드 UI에 구분 선택 추가

---

## 변경 9. 성능 평가 체계 수립

### 왜 필요한가
멘토님이 "성능평가 (정성적, 정량적) 고민하라"고 하셨습니다. 파인튜닝 전/후 비교, Agent별 성능 측정이 발표에서 핵심 근거가 됩니다.

### 정량적 평가

| 평가 대상 | 지표 | 목표 | 담당 |
|----------|------|------|------|
| Intent 분류 | Accuracy, F1-score (카테고리별) | 90%+ | 팀원 A |
| 판단 Agent | 판단 정확도 (Yes/No 일치율) | 85%+ | 팀원 B |
| 판단 근거 | 근거 조항 적합성 (정답 조항 포함 여부) | 80%+ | 팀원 B |
| RAG 검색 | MRR (Mean Reciprocal Rank), Recall@5 | MRR 0.7+ | 팀원 B |
| 문서 요약 | ROUGE-L, BERTScore | ROUGE-L 0.4+ | 팀원 C |
| Action Item 추출 | Precision, Recall, F1 | F1 80%+ | 팀원 C |
| 응답 속도 | 평균 응답 시간 | 5초 이내 | 팀원 B |

### 정성적 평가
- 판단 근거의 자연스러움 (1~5점, 팀원 간 교차 평가)
- 요약 가독성 및 핵심 포함 여부
- 대안 제시의 실용성
- 전체 사용자 시나리오 워크스루

### 베이스라인 비교 (필수)
```
[베이스 모델 (튜닝 전)] vs [LoRA 튜닝 후] 성능 차이 측정
→ "파인튜닝으로 판단 정확도 XX% → YY%로 향상" 형태로 발표 근거 확보
```

### 영향 받는 팀원
- **팀원 A**: Intent 분류 평가
- **팀원 B**: 판단 + RAG + 응답 속도 평가
- **팀원 C**: 문서 요약 + Action Item 추출 평가

---

## 변경 10. GitHub 브랜치 전략

### 왜 필요한가
멘토님이 "기능별 branch 따로, Agent별로 나눈다든지, commit도 기능 하나 추가될 때마다 하면 좋다"고 하셨습니다.

### 브랜치 구조
```
main (배포용)
 └── develop (통합 개발)
      ├── feature/intent-classification    (팀원 A)
      ├── feature/agent-orchestrator       (팀원 A)
      ├── feature/judgment-agent           (팀원 B)
      ├── feature/rag-pipeline             (팀원 B)
      ├── feature/reranker                 (팀원 B)
      ├── feature/finetuning-judgment      (팀원 B)
      ├── feature/document-agent           (팀원 C)
      ├── feature/document-parser          (팀원 C)
      ├── feature/finetuning-document      (팀원 C)
      ├── feature/schedule-agent           (팀원 D)
      ├── feature/google-calendar          (팀원 D)
      ├── feature/google-services          (팀원 D) ← NEW
      ├── feature/auth-system              (팀원 D)
      ├── feature/database                 (팀원 D)
      ├── feature/dashboard-ui             (팀원 E)
      ├── feature/chatbot-ui               (팀원 E)
      ├── feature/calendar-ui              (팀원 E)
      ├── feature/google-services-ui       (팀원 E) ← NEW
      └── feature/streaming-ui             (팀원 E)
```

### 커밋 컨벤션
```
feat: 새 기능 추가
fix: 버그 수정
docs: 문서 수정
refactor: 코드 리팩토링
test: 테스트 추가
chore: 설정/환경 변경

예시:
feat: 판단 Agent Yes/No 판단 로직 구현
feat: Reranker 파이프라인 추가
fix: Intent 분류 confidence 임계값 조정
docs: API 스키마 문서 업데이트
```

### 영향 받는 팀원
- **전원**: 브랜치 규칙 준수

---

# Part 2. 역할 분배 (v5 Final)

---

## 📋 5인 역할 분배

### 팀원 A — PM + Intent 분류 & Agent 오케스트레이션

**PM 업무**
- 전체 일정/스프린트 관리
- 각 Agent 입출력 인터페이스(스키마) 정의 및 조율
- API 스키마 문서 작성 (프론트-백엔드 계약)
- AWS 배포 및 CI/CD 파이프라인 (GitHub Actions)
- 팀 커뮤니케이션 및 주간 보고

**AI 개발 업무**
- Intent Classification 모델 개발 (klue/bert-base)
  - 7개 카테고리: judgment, doc_search, doc_summary, doc_generate, meeting_analysis, schedule_add, schedule_view
  - 학습 데이터 구축 (카테고리별 150~200문장, Claude/GPT-4로 증강)
  - 분류 정확도 평가 (목표: F1 90%+)
- **LangGraph 기반 Agent Orchestrator 구현**
  - StateGraph로 Intent → Agent 라우팅
  - 멀티턴 대화 컨텍스트 관리
  - Agent 호출 실패 시 폴백 처리
  - confidence 낮을 때 재질문 로직
- **FastAPI SSE 스트리밍 엔드포인트 구현**
- FastAPI 메인 앱 구조 설계 (라우터, 미들웨어, 에러 핸들링)

**담당 요구사항**: FR-CB-001, FR-CB-002, FR-JDG-005, FR-JDG-006, NF-ST-001, NF-EXT-001

**산출물**: Intent 분류 모델, LangGraph 오케스트레이터, FastAPI 앱 구조 + SSE 스트리밍, API 스키마 문서, 배포 환경

---

### 팀원 B — AI 엔진 리드 (파인튜닝 v1 + 판단 Agent + RAG)

**파인튜닝 v1: RAG 판단 특화 (메인)**
- 모델 선정: Qwen3 / Kanana / EXAONE 3개 베이스라인 비교 후 확정
- LoRA/QLoRA Fine-tuning 실행 (판단 데이터 2,000개)
- 학습 데이터 품질 관리 및 최종 검증
- 베이스라인 vs 파인튜닝 성능 비교
- **vLLM 모델 서빙 환경 구축** (스트리밍 출력 포함)

**판단 Agent (확장된 버전)**
- 다중 규정 교차 판단 로직
- 조건부 판단 (Yes / No / 조건부 가능 / 규정 없음)
- confidence score 산출
- 판단 이력 참조 (선택)
- 프롬프트 엔지니어링 최적화

**RAG 파이프라인**
- Hybrid Search (BM25 + Vector Search)
- **Reranking 단계 추가** (BAAI/bge-reranker-v2-m3)
- Vector DB(ChromaDB) 구축 및 인덱싱
- 임베딩 모델 최적화 (jhgan/ko-sbert-nli)
- Chunk 전략 설계 (규정: 조항 단위, 회의록: 문단 단위)

**성능 평가**
- 판단 정확도, 근거 적합성, RAG MRR/Recall@K, 응답 속도 측정
- 베이스라인 대비 개선율 리포트

**담당 요구사항**: FR-JDG-001, FR-JDG-002, FR-LLM-001~004, FR-DOC-005, FR-DOC-006

**산출물**: 파인튜닝 모델(v1), vLLM 서빙 환경, RAG + Reranking 파이프라인, 판단 Agent 코드, 성능 평가 리포트

---

### 팀원 C — AI 엔진 서브 (파인튜닝 v2 + 문서 Agent)

**파인튜닝 v2: 문서 분석 특화 (메인)**
- 학습 데이터셋 구축 (문서 관련 2,800개: 회의록 700 + 요약 500 + 생성 400 + 리스크 200 + Q&A 1,000)
- LoRA Fine-tuning 실행 (문서 분석 데이터 1,800개)
- 팀원 B와 교차 검증
- 다양한 하이퍼파라미터 실험

**문서 Agent**
- 회의록 파싱 → 결정사항, Action Item, 참석자, 기한 자동 추출 (JSON)
- 문서 요약 모듈 (sLLM 활용)
- **템플릿 기반 문서 생성** (회의록, JD, 보고서, 제안서) → `ai/templates/` 참조
  - 사용자가 챗봇에서 "회의록 만들어줘" → 요약 입력 → 템플릿 기반 생성 → 미리보기 + 다운로드
- **회의록 자동 인식 + 템플릿 감지** (FR-DOC-002): 업로드 시 회의록 여부 자동 감지
- **규정 리스크 자동 감지** (RAG 기반 규정 대조 → 리스크 레벨: 높음/중간/낮음)
- **문서 처리 완료 후 규정 이슈 자동 스캔** (FR-DOC-010)

**문서 전처리 파이프라인 (변경됨)**
- **Docling**: 디지털 PDF 구조화 파싱 (테이블, 헤더, 조항 인식)
- **PaddleOCR**: 스캔 문서/이미지 한국어 텍스트 추출
- python-docx: DOCX 파싱
- 파일 형식별 자동 분기 처리

**회사/개인 문서 구분**
- 문서 Agent에서 scope(company/personal) 반영
- RAG 검색 시 scope 필터 적용

**성능 평가**
- 요약 품질 (ROUGE-L, BERTScore), Action Item 추출 (F1)
- 베이스라인 대비 개선율 리포트

**담당 요구사항**: FR-DOC-001~004, FR-DOC-007~011

**산출물**: 파인튜닝 모델(v2), 학습 데이터셋, 문서 Agent 코드, Docling+PaddleOCR 파싱 모듈, **문서 템플릿 시스템** (`ai/templates/`), 성능 평가 리포트

---

### 팀원 D — Backend + DB + 인증 + 일정 Agent + Google Services 통합

**DB & 인증**
- PostgreSQL DB 스키마 설계
  - users, documents (scope 포함), document_templates, regulations, meetings, action_items, schedules, judgments (판단 이력), chat_logs, oauth_tokens (scopes 필드), **google_sheet_trackers**
- SQLAlchemy ORM 모델 + Alembic 마이그레이션
- JWT 인증 시스템 (로그인/회원가입/토큰 관리/**비밀번호 찾기·변경**)
- 사용자 권한 관리 (일반/관리자) + **권한별 페이지 접근 제한**
- 데이터 암호화 (AES-256)

**일정 Agent**
- Action Item → 일정 자동 등록/조회/수정/삭제 API
- 마감일 기반 우선순위 자동 설정 (D-day 계산)
- 담당자 자동 지정 로직
- **4개 Google 서비스 오케스트레이션** (ScheduleService.create_with_google_services)

**Google Services 통합 연동 (Calendar + Tasks + Gmail + Meet + Sheets)**
- **GoogleBaseService** 베이스 클래스: OAuth 토큰 관리, scope 검증, 토큰 자동 갱신
- **통합 OAuth**: 단일 플로우로 여러 scope 관리 (connect/callback/disconnect/status)
- **Google Calendar**: 이벤트 Push/Pull + **Meet 링크 자동 생성** (conferenceData)
- **Google Tasks**: Action Item → Task 동기화 + 완료/미완료 양방향 동기화
- **Gmail**: 담당자 기한 알림 메일 + 회의 초대 메일 (Meet 링크 포함) 자동 발송
- **Google Sheets**: Action Item 추적 스프레드시트 생성 + 행 동기화
- Google API 장애 시 자체 캘린더 폴백

**시스템**
- 사용자 질의/Agent 응답 로그 저장 + **질의 로그 탭 API** (NF-ST-002)
- 에러 로그 관리
- 관리자 API (사용자 CRUD, 규정 관리, 시스템 통계, **Top 질의 통계**)
- **문서 파싱 상태 관리** (uploading → parsing → completed)
- **문서 생성/다운로드 API** (template_service 연동)

**담당 요구사항**: FR-SCH-001~004, NF-SEC-001~003, NF-PRF-003, NF-ST-002, NF-EXT-002

**산출물**: DB 스키마 문서, 일정 Agent API, **Google Services 통합 모듈 (5개 서비스)**, JWT 인증 시스템, 관리자 API, 로그 시스템

---

### 팀원 E — Frontend 전담

**핵심 화면 (7개)**
- **대시보드**: 통계 카드, 최근 질의, **Top 질의 (TopQueries: 월/주/일 탭)**, 진행 중 Action Items, 최근 활동 타임라인, 리스크 알림 레벨 뱃지, **빠른 규정 검색 바 (QuickSearch)**, **자동 스캔 뱃지 (AutoScanBadge)**
- **AI 챗봇**: 의도 분류 뱃지, **SSE 스트리밍 실시간 렌더링**, 판단 응답 카드 (confidence 뱃지, 다중 규정 표시, 조건부 판단), 문서 분석 카드, **문서 생성 카드 (GenerateCard: 미리보기 + 다운로드)**, **회의 요약 카드 (MeetingSummaryCard)**, 일정 확인 카드, **Agent 호출 인디케이터 (AgentIndicator)**, **에러/폴백 메시지 (ErrorMessage + 재시도)**, **추천 질문 칩 (SuggestedQuestions)**, **관련 규정 패널 (RegulationPanel)**
- **문서 관리**: 검색창 + **키워드 하이라이트 (KeywordHighlight)**, 필터(분류/상태), **업로드 시 회사/개인 구분 선택**, 카드 리스트, 규정 상세 패널, **파싱 상태 표시 (ParsingStatus)**
- **회의 관리**: 회의 목록, 상세 패널 (정보/원문/AI분석/Action Item), 리스크 레벨 뱃지, **원본 JSON 보기 (JsonViewer)**
- **일정 관리**: FullCalendar 주간/월간, 일정 타입 색상 구분, **Google 서비스 통합 UI** (GoogleServicesConnect: 4개 서비스 토글 연결, TasksPanel: 할 일 체크/Push/Pull, MeetLinkBadge: Meet 링크 뱃지, EmailReminderButton: 알림 메일 발송, SheetsDashboard: 추적 시트 대시보드, ScheduleForm: Meet 토글 + 참석자 이메일)
- **로그인/회원가입**: 이메일 인증, Google 계정 연결, **비밀번호 찾기/변경 (PasswordReset)**
- **관리자**: 사용자 관리, **권한별 접근 제한 설정**, 규정 관리, 시스템 통계, **질의 로그 탭**

**공통**
- 디자인 시스템 (배경: #FFFEF5/#FAF9F6, 메인: #3B82F6, 포인트: #8B5CF6)
- 반응형 디자인
- API 연동 + 상태 관리 (Zustand + React Query)
- **SSE(EventSource) 스트리밍 수신 + 실시간 토큰 렌더링**

**담당 요구사항**: FR-UI-001~006

**산출물**: Figma 디자인, React 전체 컴포넌트, 사용자 가이드

---

## 🤖 Agent 오너십 + 데이터 흐름

```
사용자 질문
     ↓
[팀원 A] Intent Classification (klue/bert-base)
     ↓
[팀원 A] LangGraph Agent Orchestrator
     ↓ (조건부 라우팅)
     ├── judgment
     │    → [팀원 B] RAG (Hybrid Search + Reranker) → sLLM (LoRA v1)
     │    → 다중 규정 교차 판단 + confidence score
     │
     ├── doc_*
     │    → [팀원 C] Docling/PaddleOCR 파싱 → sLLM (LoRA v2)
     │    → 요약/생성/리스크 감지
     │
     └── schedule_*
          → [팀원 D] 일정 CRUD + Google 서비스 통합 (Calendar+Tasks+Gmail+Meet+Sheets)
     ↓
[팀원 A] SSE 스트리밍 응답
     ↓
[팀원 E] 실시간 토큰 렌더링 → 완료 후 카드 UI
```

---

## 🛠 기술 스택 (멘토 피드백 반영)

### AI / ML
| 구분 | 기술 | 변경 여부 |
|------|------|---------|
| Base LLM | **Qwen3 / Kanana / EXAONE 3.5 (7~8B)** | 🔄 후보 업데이트 |
| Fine-tuning | LoRA (PEFT) + Hugging Face Transformers | 유지 |
| 양자화 | bitsandbytes (4-bit QLoRA) | 유지 |
| 추론 서빙 | **vLLM (확정)** | 🔄 TGI 옵션 제거 |
| Agent Framework | **LangGraph** | 🔴 LangChain에서 전환 |
| Vector DB | ChromaDB | 유지 |
| Embedding | jhgan/ko-sbert-nli | 유지 |
| **Reranker** | **BAAI/bge-reranker-v2-m3** | 🆕 추가 |
| 키워드 검색 | BM25 (rank_bm25) | 유지 |
| Intent 분류 | klue/bert-base | 유지 |
| 데이터 생성 | GPT-4 / Claude | 유지 |

### Backend
| 구분 | 기술 | 변경 여부 |
|------|------|---------|
| Framework | FastAPI | 유지 |
| **스트리밍** | **FastAPI StreamingResponse (SSE)** | 🆕 추가 |
| DB | PostgreSQL | 유지 |
| ORM | SQLAlchemy + Alembic | 유지 |
| 인증 | JWT (PyJWT) + Google OAuth 2.0 | 유지 |
| Google API | google-api-python-client + google-auth | 유지 |
| 문서 파싱 | **Docling + PaddleOCR** + python-docx | 🔄 PyPDF2/pytesseract에서 교체 |
| Task Queue | Celery + Redis | 유지 |
| 암호화 | cryptography (Fernet/AES) | 유지 |

### Frontend
| 구분 | 기술 | 변경 여부 |
|------|------|---------|
| Framework | React (Vite) | 유지 |
| 상태관리 | Zustand | 유지 |
| 서버 상태 | React Query (TanStack Query) | 유지 |
| **스트리밍** | **EventSource (SSE)** | 🆕 추가 |
| 스타일링 | Tailwind CSS + shadcn/ui | 유지 |
| 캘린더 | FullCalendar (React) | 유지 |
| 차트 | Recharts | 유지 |
| 라우팅 | React Router v6 | 유지 |

### Infra / DevOps
| 구분 | 기술 | 변경 여부 |
|------|------|---------|
| 클라우드 | AWS (EC2 + S3 + RDS) | 유지 |
| **GPU (학습)** | **RunPod (A100 40GB)** | 🆕 명시 |
| GPU (추론) | AWS g5.xlarge 또는 로컬 RTX 4090 | 유지 |
| 컨테이너 | Docker + Docker Compose | 유지 |
| CI/CD | GitHub Actions | 유지 |
| 버전관리 | **Git + GitHub (기능별 브랜치)** | 🔄 전략 구체화 |

---

## ⏱ 개발 타임라인

| 단계 | A (PM+Intent) | B (파인튜닝v1+판단) | C (파인튜닝v2+문서) | D (Backend+일정) | E (Frontend) |
|------|--------------|-------------------|-------------------|-----------------|-------------|
| **1단계: 설계** | API 스키마 정의 (문서 생성/다운로드 API 포함), LangGraph 구조 설계, Docker, GitHub 세팅 | 모델 3개 베이스라인 비교, RAG 설계, Reranker 테스트 | 학습 데이터 구축 시작 (1,500개), Docling/PaddleOCR 테스트, **문서 템플릿 구조 설계** | DB ERD 확정, JWT 인증, Google Cloud 설정 | Figma 디자인, 컴포넌트 설계, Mock API |
| **2단계: 데이터+기반** | Intent 학습 데이터 구축 | 판단 데이터 500개 구축 + 모델 확정 | 문서 데이터 구축 + 증강 | Google OAuth + Calendar API | 공통 컴포넌트 + 대시보드 |
| **3단계: 핵심 AI** | Intent 분류 모델 학습 + 평가 | LoRA v1 학습 + RAG+Reranker 구축 | LoRA v2 학습 + Docling 파싱 파이프라인 | 일정 Agent API + Google Services 연동 | 챗봇 UI + SSE 스트리밍 |
| **4단계: Agent** | LangGraph 오케스트레이터 + SSE 스트리밍 | 판단 Agent 확장 (다중규정, confidence) | 문서 Agent (요약/생성/리스크) | 관리자 API + 로그 | 문서관리 + 회의관리 + 일정관리 |
| **5단계: 통합** | 전체 파이프라인 연결 + E2E | 판단 정확도 튜닝 + 성능 평가 | 요약/추출 품질 튜닝 + 성능 평가 | API 최적화 + 에러 핸들링 | API 연동 + 통합 UI |
| **6단계: 마무리** | AWS 배포 + 최종 테스트 | vLLM 최적화 + 최종 평가 리포트 | 리스크 감지 검증 + 최종 평가 리포트 | 성능 테스트 + 캘린더 동기화 검증 | 반응형 + 최종 QA |
