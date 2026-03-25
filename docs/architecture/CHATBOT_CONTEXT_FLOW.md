# 챗봇 대화 맥락 이해 + Agent 간 공유 아키텍처

> 최종 업데이트: 2026-03-26

## 개요

챗봇은 사용자와의 대화를 기억하고, 여러 Agent가 이전 대화 맥락을 공유하여 자연스러운 멀티턴 대화를 지원합니다.

---

## 1단계: 대화 저장 & 로딩

사용자가 메시지를 보낼 때마다 DB에 저장되고, 다음 요청 시 로드됩니다.

```
[DB: ChatLog 테이블]
  turn 1: "보안 문서 찾아줘"
    → agent_response: {type: doc_retrieve,
       sources: [{title: "보안사고_회의록", document_id: 90}, ...]}

  turn 2: "두 번째 문서 요약해줘"
    → agent_response: {type: doc_retrieve, sub_type: summary, ...}

  turn 3: "이걸로 규정 위반 여부 판단해줘"
    → agent_response: {type: judgment, ...}
```

### 로딩 (chat.py `_load_chat_context`)

| 데이터 | 소스 | 설명 |
|--------|------|------|
| **chat_history** | ChatLog에서 최근 10개 로드 | 각 ChatLog에서 user+assistant 2개 메시지 생성 → 최대 10턴(20메시지). assistant 메시지에 `agentResponse` (전체 응답 JSON) 포함 |
| **chat_summary** | ChatSession.summary | ChatLog 5개(사용자 메시지 5개) 초과 시 sLLM(Kanana)으로 요약 생성. 5턴 이전의 대화 맥락 보존용 |
| **prev_agent_context** | `_extract_prev_agent_context()` | chat_history에서 직전 Agent 결과를 압축 추출 (cross-agent 맥락 전달용). 3턴 이상 전 결과는 무시 |

### prev_agent_context 구조

```python
{
    "agent_type": "document",         # document | judgment | schedule
    "intent": "doc_retrieve",
    "turn_ago": 1,                     # 직전 턴
    "document": {
        "title": "보안사고_회의록",
        "document_id": 90,
        "summary": "보안 TF 회의에서...",  # 300자 제한
        "sources_count": 5,
    }
}
```

---

## 2단계: AgentState에 담아서 전달

모든 Agent가 공유하는 상태 객체(가방)에 담깁니다.

```
AgentState = {
    user_input: "이걸로 규정 위반 여부 판단해줘",
    user_id: 6,
    user_team: "CS",
    chat_history: [turn1~turn10 메시지들],       ← 최근 10턴
    chat_summary: "이전에 보안 문서를 검색하고...",  ← 요약
    prev_agent_context: {                         ← 직전 Agent 결과
        agent_type: "document",
        document: {title: "보안사고_회의록", ...}
    },
    intent: "",              ← Orchestrator가 채움
    agent_response: {},      ← 하위 Agent가 채움
    stream_mode: True,
    document_id: None,
    document_content: None,
    template_type: None,
    ...
}
```

---

## 3단계: Agent별 맥락 사용

```
[사용자 입력]
    |
    v
[Orchestrator]
    |  intent 분류: user_input만 사용 (ONNX 분류기)
    |  schedule followup 감지: chat_history 사용
    |  일반 대화 응답: chat_summary를 시스템 프롬프트에 포함
    |
    |--- intent: judgment -------> [Judgment Agent]
    |--- intent: doc_retrieve ---> [Document Agent]
    |--- intent: schedule_add ---> [Schedule Agent]
    |--- intent: general --------> [General Response]
```

### 각 Agent의 맥락 사용

| Agent | chat_history 사용 | chat_summary | prev_agent_context |
|-------|:-----------------:|:------------:|:------------------:|
| **Orchestrator** | schedule followup 감지 | 일반 대화 시스템 프롬프트 | X |
| **Judgment** | 이전 판단 이력 추출 (`_extract_judgment_history`) + LLM 프롬프트에 최근 3턴 포함 | X | 이전 문서/일정 맥락을 `## 이전 대화에서 참조한 문서` 섹션으로 프롬프트에 포함 |
| **Document** | 이전 `doc_retrieve` 결과에서 document_id/title 추출 (`_extract_doc_from_history`) + sLLM 리라이팅 + QA 프롬프트에 최근 대화 포함 | X | schedule/judgment 맥락으로 검색 쿼리 보강 |
| **Schedule** | 이전 일정/clarify 정보 추출 (`_extract_clarify_from_history`, `_extract_last_schedule_from_history`) | X | X |
| **General** | LLM messages 배열에 직접 포함 | 시스템 프롬프트에 포함 | X |

---

## 4단계: Document Agent sLLM 리라이팅 (상세)

regex로 잡지 못하는 표현("위에 문서", "두 번째 거", "아까 그 내용")을 sLLM(Kanana)이 구체적 문서명으로 변환합니다.

```
[사용자: "네 번째 문서 내용 자세히 알려줘"]
    |
    v
[1단계: regex fast-path] (0ms)
    |  _FOLLOWUP_RE 매칭? -> "네 번째"는 패턴에 없음 -> 미매칭
    |
    v
[조건 체크: sLLM 호출 필요?]
    |  prev_doc 있음? -> Yes
    |  regex 미매칭? -> Yes
    |  구체적 문서명 없음? -> Yes
    |  -> sLLM 호출!
    |
    v
[2단계: sLLM(Kanana) 리라이팅] (~1-3초)
    |
    |  프롬프트:
    |  [이전 검색 결과]
    |  1. 보안사고_긴급대응_TF_회의록
    |  2. 사내_정보보안_관리규정_v3.0
    |  3. 긴급_보안사고_대응회의록
    |  4. 개인정보_처리위탁_계약서
    |  5. IT_시스템_구축_용역_계약서
    |
    |  현재 질문: 네 번째 문서 내용 자세히 알려줘
    |
    |  sLLM 응답: REWRITE: 개인정보_처리위탁_계약서 내용 자세히 알려줘
    |
    v
[3단계: title 매칭 검증]
    |  "개인정보_처리위탁_계약서" <- sources[3].title 매칭 성공
    |  -> document_id=100 확보
    |
    v
[4단계: DB에서 문서 전문 로드]
    |  _get_document(100) -> 4927자 content
    |  -> RAG 검색 스킵!
    |
    v
[5단계: QA/Summary]
    |  리라이팅된 쿼리 + document_content -> LLM 답변
    |
    v
[응답: "개인정보 처리 위탁 계약서의 주요 내용은..."]
```

### sLLM 호출 조건 (3가지 AND)

| 조건 | 미충족 시 |
|------|----------|
| prev_doc 있음 (이전에 문서 검색한 적 있음) | sLLM 안 탐 — 참조할 이전 문서 없음 |
| regex 미매칭 (기존 패턴으로 잡지 못함) | sLLM 안 탐 — regex fast-path로 처리 |
| 구체적 문서명 없음 (쿼리가 모호함) | sLLM 안 탐 — 이미 명확한 쿼리 |

### 안전장치

| 상황 | 동작 |
|------|------|
| VLLM_BASE_URL 미설정 | 즉시 fallback (sLLM 호출 안 함) |
| sLLM 타임아웃 (8초) | 원본 쿼리로 일반 RAG 검색 |
| sLLM 응답 파싱 실패 | 원본 쿼리로 일반 RAG 검색 |
| title 매칭 실패 | 쿼리만 교체, 일반 RAG 검색 |
| 할루시네이션 (응답 3배 초과) | 원본 쿼리로 fallback |

---

## 5단계: Cross-Agent 맥락 공유 (상세)

`prev_agent_context`를 통해 다른 Agent의 결과를 참조합니다.

### Document -> Judgment

```
사용자: "보안 문서 찾아줘"        -> Document Agent (검색)
사용자: "이걸로 판단해줘"         -> Judgment Agent
    |
    v
prev_agent_context = {
    agent_type: "document",
    document: {title: "보안사고_회의록", summary: "..."}
}
    |
    v
Judgment Agent의 LLM 프롬프트:
    "## 이전 대화에서 참조한 문서
     - 제목: 보안사고_회의록
     - 내용 요약: ..."
```

### Schedule -> Document

```
사용자: "보안 TF 회의 잡아줘"     -> Schedule Agent (일정 등록)
사용자: "관련 회의록 찾아줘"       -> Document Agent
    |
    v
prev_agent_context = {
    agent_type: "schedule",
    schedule: {title: "보안 TF 회의", date: "2026-03-27"}
}
    |
    v
Document Agent: "보안 TF 회의" 키워드로 쿼리 보강
```

---

## 전체 맥락 공유 구조도

```
               [chat.py (중앙 허브)]
                   |
          DB에서 로드:
          |- chat_history (10턴)
          |- chat_summary (10턴 초과분 요약)
          |- prev_agent_context (직전 Agent 결과)
                   |
                   v
             [AgentState]
                   |
    +--------------+--------------+
    |              |              |
    v              v              v
[Orchestrator] [Document]   [Judgment]
    |          [Agent]       [Agent]
    |              |              |
    |         history에서     prev_ctx에서
    |         이전 doc 추출   이전 doc 참조
    |              |              |
    |         regex or         LLM 프롬프트에
    |         sLLM 리라이팅    맥락 포함
    |              |              |
    v              v              v
 [intent      [follow-up     [이전 문서
  분류]        QA/요약]       기반 판단]
    |              |              |
    +--------------+--------------+
                   |
                   v
              [DB 저장]
           다음 턴에서 재활용
```

---

## 핵심 메커니즘 요약

| 메커니즘 | 역할 | 사용 Agent |
|---------|------|-----------|
| **chat_history** | 최근 10턴 원문 전달 | 전체 |
| **chat_summary** | 10턴 초과분 sLLM 요약 | Orchestrator (일반 대화) |
| **prev_agent_context** | 직전 Agent 결과 압축 (cross-agent) | Judgment, Document |
| **_extract_doc_from_history** | 이전 doc_retrieve의 sources 추출 | Document |
| **_extract_judgment_history** | 이전 judgment 결과 추출 | Judgment |
| **_extract_clarify_from_history** | 이전 schedule_clarify 추출 | Schedule |
| **sLLM 리라이팅** | 모호한 표현 -> 구체적 문서명 변환 | Document |
| **title 매칭 검증** | 리라이팅 결과 -> document_id 연결 | Document |

---

## 부가 경로 (핵심 흐름에는 포함하지 않음)

| 경로 | 설명 |
|------|------|
| **프론트 document_id 직접 전달** | 문서 상세 페이지에서 "요약" 버튼 → chat.py가 DB에서 content 로드 |
| **force_intent** | 프론트에서 intent 강제 지정 → ONNX 분류 스킵 |
| **복합 질문 분해** | "출장 규정 알려주고 회의도 잡아줘" → sub_query 분해 → 순차 실행 |
| **규정 검증** | Agent 응답 후 자동 규정 위반 체크 → 경고 표시 |
| **스트리밍** | `stream_pending=True` → chat.py에서 SSE 토큰 단위 실시간 전송 |
