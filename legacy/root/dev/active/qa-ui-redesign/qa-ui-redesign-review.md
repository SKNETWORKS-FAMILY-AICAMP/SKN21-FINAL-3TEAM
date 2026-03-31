# QA 카드 UI/UX 리디자인 플랜 검토

**검토일**: 2026-03-25
**검토 대상 파일**:
- `frontend/src/pages/ChatPage.jsx` (L170-232: QA 카드, L234-264: 검색 카드, L780-791: QA 스켈레톤)
- `frontend/src/components/chat/SourceItem.jsx` (L1-30)
- `ai/agents/document/_qa.py` (L135, L151: 0.85 캡)
- `ai/agents/document/_common.py` (L225-268: `filter_and_build_citations`)
- `ai/agents/document/_stream.py` (L158-168: 스트리밍 후처리)

---

## 1. 완전성 검토

### 1-1. 누락 사항: QA 스켈레톤 (ChatPage.jsx L780-791)

**누락됨.** L785에서 스트리밍 중 QA 스켈레톤을 렌더링할 때 `confidence: null`로 설정하고 있다:
```js
agentResponse: { sub_type: 'qa', confidence: null },
```
이 부분은 confidence bar를 제거하면 자연스럽게 해결되지만, **인용/출처 병합 후에도 스켈레톤 안의 `renderCardMessage` 호출이 새 레이아웃과 호환되는지 확인 필요**. 스켈레톤에서는 `sources`/`citations`가 아직 없는 상태(빈 배열)로 렌더되므로, "참고 문서 (0건)" 섹션이 보이지 않도록 조건 분기를 해야 한다.

**권장**: 스켈레톤 렌더링 시 "참고 문서" 섹션을 숨기는 조건(`sources.length > 0`)을 명시적으로 플랜에 추가할 것.

### 1-2. 누락 사항: 스트리밍 후처리 (_stream.py L158-168)

`_stream.py` L158-168에서 `filter_and_build_citations`를 호출하여 `citations`를 생성하고 `agent_response`에 주입한다. 플랜에서 `_common.py`의 citations 구조를 변경하면 (relevance 뱃지 -> score 숫자), 이 스트리밍 경로도 자동으로 영향을 받는다. 이것 자체는 문제없지만, **`_stream.py`가 수정 대상 파일 목록에 빠져 있다**. 명시적으로 포함시킬 것.

### 1-3. 누락 사항: SSE result 이벤트의 데이터 구조

`chat.py`에서 최종 `agent_response`를 SSE `result` 이벤트로 전송할 때, 프론트엔드가 `data.citations`와 `data.sources`를 별도로 파싱한다 (ChatPage.jsx L120-125 부근). 인용/출처 병합 시 프론트엔드의 파싱 로직도 수정해야 하는데, 플랜에 프론트엔드 데이터 파싱 레이어 변경이 언급되지 않았다.

**권장**: `citations` 필드를 아예 제거하고 `sources`만 보낼지, 아니면 `citations`를 유지하되 프론트에서 무시할지 방향을 정할 것.

---

## 2. 호환성 검토: 검색 카드 (L234-264)와의 UI 일관성

### 현재 상태
- **검색 카드** (L234-264): `SourceItem` 컴포넌트 사용, `score` 퍼센티지 표시, "전체 보기 ->" 링크
- **QA 카드** (L203-219): 인라인 인용 렌더링 (SourceItem 미사용), relevance 뱃지 (높음/중간/낮음)

### 플랜 적용 후
QA 카드에서 `SourceItem`을 재사용하면 검색 카드와 동일한 레이아웃이 되므로 **일관성이 향상된다**. 이 점은 긍정적.

### 주의 사항
QA 카드의 "참고 문서"와 검색 카드의 "출처"가 같은 `SourceItem`을 쓰되, 섹션 타이틀만 다르게 된다. 이는 의도된 것이고 문제없다.

---

## 3. 프론트 영향: SourceItem.jsx 수정 범위

### 현재 SourceItem 사용처 (2곳)
1. **QA 카드** L225: `sources.map(...)` — 검색 출처 섹션
2. **검색 카드** L257: `sources.map(...)` — 출처 섹션

### 분석
플랜에서 SourceItem 자체의 수정은 언급되지 않았다. 현재 SourceItem은 이미 `score` 퍼센티지를 표시하고 있으므로 (L2-5), 플랜의 "score percentage 사용" 의도와 이미 일치한다.

**문제 없음.** QA 카드에서 기존 인라인 인용(L206-218)을 제거하고 `SourceItem`으로 대체하면 되며, SourceItem 자체를 수정할 필요는 없다.

단, 한 가지 고려: SourceItem은 `onClick`으로 `onSelect`를 호출하여 문서 상세 보기로 이동한다. QA 카드에서도 동일 동작이 바람직한지 확인. (현재 인용 섹션에는 클릭 동작이 없다.)

---

## 4. 백엔드 영향: confidence 캡 제거

### 현재 구조
- `_qa.py` L135: `confidence: round(min(rag_top_score, 0.85), 2)` (스트리밍)
- `_qa.py` L151: 동일 (비스트리밍)
- 프론트 `confColor` (L174): threshold 0.7 / 0.4로 색상 분기

### 캡 제거 시 영향

**핵심 질문: 0.85 캡을 제거하면 RAG score가 0.85 이상으로 올라갈 수 있는가?**

`_retrieve_context` (L135-180)에서 `search_results`의 `score`는 Qdrant + BM25 hybrid search 또는 reranker 점수이다. 이 점수는 0~1 범위이며, reranker 사용 시 0.9+ 가능하다.

플랜에서 confidence bar를 **제거**한다고 했으므로, 프론트 `confColor` 로직(L174)은 아예 삭제될 예정이다. 따라서 **threshold 충돌 문제는 발생하지 않는다.**

다만 플랜에서 "등급별 한 줄 안내"를 하단에 표시한다고 했는데, 이 안내문의 등급 기준이 무엇인지 명확하지 않다. RAG `top_score`를 그대로 쓴다면:

| top_score 범위 | 안내문 |
|---|---|
| >= 0.7 | "문서 기반 답변입니다" |
| >= 0.4 | "관련 문서를 참고했지만 정확하지 않을 수 있습니다" |
| < 0.4 | "관련도가 낮은 문서를 참고했습니다" |

이 threshold는 기존과 동일하므로 문제없다. **단, 캡을 제거한 raw score를 사용하면 0.7 이상이 더 자주 나와서 "높음" 안내가 늘어날 수 있다.** 이것이 의도한 것인지 확인 필요.

### `_common.py` citations 구조 변경

현재 (L259-266):
```python
citations = [{
    "source": s.get("title", ""),
    "content": s.get("content", "")[:200],
    "relevance": "높음" if s.get("score", 0) >= 0.7 else ...
}]
```

플랜: `relevance` 텍스트 -> `score` 숫자로 변경. 이 변경은 `_stream.py` L167에서도 반영되므로 스트리밍/비스트리밍 모두 일관된다. **문제없음.**

다만 `citations` 필드와 `sources` 필드를 프론트에서 병합하려면, 백엔드에서도 `citations`를 별도로 보내지 않고 `sources`에 통합하는 것이 깔끔하다. **`citations` 필드 자체를 폐기할지 결정 필요.**

---

## 5. 리스크

### 5-1. (중간) 인용 내용 문장 경계 truncate

플랜: "content를 200자 하드컷 대신 문장 경계에서 자르겠다"

`_common.py` L262의 `s.get("content", "")[:200]`을 문장 경계로 바꾸면, content 길이가 200자보다 **길어질 수 있다**. SSE 전송 크기가 커져 프론트 렌더링 성능에 영향 가능. 최대 길이 상한(e.g., 400자)을 두는 것이 안전하다.

또한, `_build_sources` (L199)에서도 `full_content[:300]`으로 자르고 있다. sources와 citations 모두 문장 경계 truncate를 적용하려면 `_build_sources`도 함께 수정해야 한다. **플랜에서 `_build_sources` 수정이 누락되었다.**

### 5-2. (낮음) JudgmentCard와의 confidence 혼동

`ChatPage.jsx` L110에서 `JudgmentCard`도 `data.confidence`를 사용한다. QA와 Judgment는 `resultIntent`로 분기되므로 서로 영향 없다. **리스크 없음.**

### 5-3. (낮음) DB 저장 영향

`chat.py` L562에서 `intent_confidence`로 저장하는 값은 intent 분류 confidence (L331)이지 QA confidence가 아니다. `agent_response` JSON에 포함된 QA confidence는 `agent_response` 컬럼에 그대로 직렬화되므로, 캡 제거해도 DB 스키마 변경 불필요. **리스크 없음.**

### 5-4. (중간) 기존 채팅 히스토리와의 호환

이미 저장된 채팅에서 `citations`에 `relevance: "높음"` 형태로 저장된 데이터가 있다. 프론트를 새 구조(score 숫자)로 바꾸면 기존 데이터 렌더링 시 score가 `undefined`가 된다. **프론트에서 fallback 처리 필요**: score가 없으면 relevance 텍스트를 표시하거나 숨기는 분기.

### 5-5. (낮음) 인용/출처 병합 시 데이터 중복

현재 citations = sources 상위 3건의 subset이다 (L265). 병합하면 sources만 표시하게 되므로 중복 자체가 해소된다. **리스크 없음, 오히려 개선.**

---

## 6. 종합 판정

| 항목 | 판정 | 비고 |
|------|------|------|
| 완전성 | **부분 누락** | 스켈레톤(L780-791), `_stream.py`, `_build_sources`, 프론트 파싱 레이어 |
| 검색 카드 호환성 | **양호** | SourceItem 재사용으로 일관성 향상 |
| SourceItem 영향 | **안전** | 수정 불필요, 기존 score 표시 로직 그대로 사용 |
| confidence 캡 제거 | **안전** | bar 자체를 제거하므로 threshold 충돌 없음 |
| 리스크 | **관리 가능** | 기존 데이터 fallback, 문장 경계 truncate 상한, _build_sources 누락 |

### 플랜 보완 체크리스트

- [ ] **수정 대상에 `_stream.py` (L158-168) 추가** — citations 구조 변경 자동 반영 확인
- [ ] **수정 대상에 `_build_sources` (L183-202) 추가** — 문장 경계 truncate 일관 적용
- [ ] **QA 스켈레톤 (L780-791) 렌더링 조건 명시** — "참고 문서" 섹션 숨김 처리
- [ ] **`citations` 필드 폐기 여부 결정** — 백엔드에서 보내지 않거나 프론트에서 무시
- [ ] **문장 경계 truncate에 max_chars 상한 추가** (e.g., 400자)
- [ ] **기존 채팅 히스토리 fallback** — relevance 텍스트 데이터에 대한 프론트 방어 코드
- [ ] **"등급별 한 줄 안내" threshold 기준 명시** — 캡 제거 후 raw score 사용 시 분포 변화 인지
