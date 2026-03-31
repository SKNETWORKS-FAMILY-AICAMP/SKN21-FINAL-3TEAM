# [공지] Document Agent 리팩토링 완료 + Intent 파인튜닝 예정

## 배포 완료 (develop → EC2)

Document Agent 리팩토링이 develop에 머지 & EC2 배포되었습니다.

### 변경 요약

| Before (7개 intent) | After (8개 intent) |
|---|---|
| judgment | judgment |
| doc_search | doc_search |
| doc_generate | doc_generate (회의록 포함) |
| ~~meeting_generate~~ (삭제) | **doc_summary** (신규) |
| schedule_add | schedule_add |
| schedule_view | schedule_view |
| general | general |
| - | **doc_qa** (신규) |

- `meeting_generate` 제거 → `doc_generate`의 meeting_minutes 템플릿으로 통합
- `doc_summary` 신규 — 문서 요약 (document_content 기반)
- `doc_qa` 신규 — 문서 내용 기반 질의응답 (RAG + LLM)

### 수정 파일 (15개)

AI 6개 / Backend 2개 / Frontend 3개 / Tests 2개 / 기타 2개

---

## E2E 테스트 결과 (EC2 배포 후)

| 테스트 | Intent | AgentIndicator | 결과 |
|--------|--------|----------------|------|
| 보고서 작성해줘 | `doc_generate` | 문서 생성 Agent | PASS |
| 회의록 만들어줘 | `doc_generate` | 문서 생성 Agent | PASS |
| 마케팅 문서 찾아줘 | `doc_search` | (검색 결과 표시) | PASS |
| 이 문서 요약해줘 | `doc_summary` | 문서 요약 Agent | PASS |
| 지난 회의 결정사항이 뭐야? | `doc_qa` | 문서 QA Agent | PASS |
| 연차 규정 알려줘 | `judgment` | 규정 판단 Agent | PASS |
| 오늘 일정 알려줘 | `schedule_view` | 일정 조회 Agent | PASS |

---

## 알아둘 점

### doc_summary — 빈 응답 나오는 건 정상
- 채팅에서 "이 문서 요약해줘"만 보내면 요약할 문서가 없어서 빈 응답
- 프론트에서 `document_id`를 채팅 요청에 포함하는 UI 필요 (지영님 작업)
- 작업 상세: `docs/지용/DOC_SUMMARY_FRONTEND_TASK.md` 참고

### BERT 현재 비활성화
- 8개 라벨 재학습 전까지 Solar LLM + 임베딩 유사도 fallback으로 분류 중
- 기존 7라벨 weights는 `.bak_7label`로 백업됨

---

## 다음 작업: Intent 분류 파인튜닝

8개 intent 기준 BERT 재학습을 진행합니다.

- 비교 모델 3개: `klue/bert-base`, `koelectra-base-v3`, `distilkobert`
- 데이터 생성: 멀티 LLM 혼합형 (Claude·GPT·Gemini 분업 + 교차 검증)
- 기본 300개/intent → 총 2,400개 + 경계 쌍/적대적 데이터
- 실험 스크립트: `ai/experiments_v2/`
- 계획 문서: `docs/지용/EXPERIMENT_PLAN_v2.md`

파인튜닝 완료되면 현재 Solar LLM fallback → BERT 모델로 교체 예정입니다.

---

관련 커밋: `c6bc62f` (refactor: Document Agent 리팩토링)
변경 기록: `docs/지용/REFACTORING_DOC_AGENT_v2.md`
