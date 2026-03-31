# 상호작용 멀티에이전트 전환 - Context & Decisions

## Status
- Phase: 플랜 작성 완료, 구현 대기
- Progress: 0 / 23 tasks complete
- Last Updated: 2026-03-26

---

## Key Files

### Modified (기존 파일 수정)
- `ai/agents/state.py` - AgentState에 체이닝 관련 5개 필드 추가
- `ai/agents/orchestrator.py` - agent_dispatcher 노드 추가, 그래프 재설계
- `backend/app/api/v1/chat.py` - agent_dispatcher SSE 핸들러 + chain 이벤트
- `ai/agents/document/_entry.py` - doc_generate 시 next_actions 생성
- `ai/agents/judgment_agent.py` - chain_context 읽어서 문서 기반 판단
- `ai/agents/schedule_agent.py` - chain_context 읽어서 일정 자동 등록

### New (신규 파일)
- `ai/agents/chain_config.py` - ALLOWED_CHAINS, MAX_CHAIN_DEPTH 등 체이닝 설정
- `ai/agents/chain_utils.py` - _build_chain_context, _summarize_chain 유틸

---

## Key Decisions

### 1. Dispatcher 패턴 선택 (2026-03-26)
- **결정**: 별도 `agent_dispatcher` 중간 노드 도입
- **대안 검토**:
  - (A) 각 에이전트 뒤에 직접 조건부 엣지 → 중복 코드 4벌
  - (B) format_response에서 체인 판단 → 역할 과부하
  - **(C) dispatcher 중간 노드 → 선택**: 단일 지점에서 체인 로직 관리
- **Trade-off**: 노드 하나 추가로 인한 미세한 지연 vs 코드 중앙 집중화

### 2. next_actions는 규칙 기반 (2026-03-26)
- **결정**: next_actions 생성은 LLM 판단이 아닌 코드 로직으로 결정
- **이유**: LLM에게 "다음 에이전트를 골라라"고 하면 비용 + 지연 + 예측 불가능성 증가
- **대안**: LLM 기반 planning agent → 비용/지연이 2배, 환각 리스크
- **Trade-off**: 유연성 ↓ (하드코딩) but 예측가능성 ↑, 비용 ↓

### 3. compound와 chain 공존 (2026-03-26)
- **결정**: compound(기존)과 chain(신규)을 별개 메커니즘으로 유지
- **이유**: compound는 "사용자 명시적 복합 요청", chain은 "에이전트 자율 후속 처리"로 목적이 다름
- **대안**: compound를 chain으로 통합 → 기존 코드 대대적 변경 필요, 리스크 높음

### 4. MAX_CHAIN_DEPTH = 3 (2026-03-26)
- **결정**: 최대 체인 깊이 3으로 제한
- **근거**: 실제 유스케이스 분석 (문서생성→규정→일정 = 3단계가 최대)
- **향후**: 사용 패턴 모니터링 후 조정 가능

---

## Database Schema
- 변경 없음 (AgentState는 인메모리 TypedDict, DB 스키마 무관)

## API Endpoints
- 변경 없음 (기존 POST /chat/stream 그대로 사용)
- SSE 이벤트 타입 추가:
  - `chain_progress`: 체인 진행 중 (depth, next_agent, reason)
  - `chain_complete`: 체인 완료 (total_agents, agents)

## Testing Notes

### 리그레션 테스트 (Phase 1 필수)
- 단일 judgment: "연차 규정 알려줘" → judgment_agent → format_response (기존과 동일)
- 단일 doc_retrieve: "매출 보고서 찾아줘" → document_agent → format_response (기존과 동일)
- 단일 schedule_add: "내일 2시 회의 잡아줘" → schedule_agent → format_response (기존과 동일)
- compound: "규정 확인하고 일정 잡아줘" → compound_pending → 순차 처리 (기존과 동일)
- clarify: 낮은 confidence → top-3 후보 제시 (기존과 동일)

### 체인 테스트 (Phase 2+)
- doc_generate → judgment: "사내 보고서 작성해줘" → 문서 생성 + 규정 체크
- doc_generate → schedule: "내일까지 보고서 만들어줘" → 문서 생성 + 마감 일정 등록
- 무한루프 방지: depth 3 초과 시 강제 종료 확인
- 이미 실행된 에이전트 재호출 방지 확인

---

## Known Issues / Open Questions

1. **compound 내 chain**: compound의 각 sub_query에서도 chain이 발생할 수 있는지?
   - 현재 방침: Phase 4에서 검토. 초기에는 compound 내 chain 비활성화.

2. **stream_mode와 chain**: 현재 스트리밍 모드에서 judgment_agent는 prepare_judgment_stream을 사용.
   chain의 두 번째 에이전트도 스트리밍해야 하는지?
   - 현재 방침: 후속 에이전트는 비스트리밍 모드로 실행 (첫 번째만 스트리밍)

3. **사용자 컨펌**: 자동 일정 등록 전 사용자에게 확인받아야 하는지?
   - 현재 방침: next_actions에 `confirm_required: true` 플래그로 제어. 프론트에서 컨펌 UI 표시.

4. **에이전트 부분 실패**: 체인 중 하나가 실패하면?
   - 현재 방침: 실패한 에이전트 결과를 chain_responses에 에러로 기록, 나머지는 계속 진행.
