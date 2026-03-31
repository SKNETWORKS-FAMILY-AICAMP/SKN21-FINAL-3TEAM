# 발표자료 v2 작업 세션 (2026-03-27)

## 한 일

### 구조 개편
- 최종 구조 확정: 01~16 + Q&A + 데모 5분
- 삭제: 화면 구성(데모 커버), 성능 평가(성과 페이지 대체), 배포 아키텍처
- 추가: 왜 sLLM?(03), 개발 전략(05), Base 한계(10), 성과 3장(12~14)
- 스토리라인 C: Base 한계 → 파인튜닝 → 성과 → 데모

### 소스코드 검증
- 아키텍처: classify_intent 3분기 구조 확인 (compound/single/low_conf)
- 4중 보조장치 확인 (경은님은 3중이라 했으나 코드에 4개 함수 존재)
- top-3→top-2 수정 (gap 체크에서 2개만 세팅)
- DB 16테이블, 프론트 14페이지, RAG ~6초, E2E 6~10초
- orchestrator.py/config.py docstring 수정

### 경은님 자료 반영 (docs/ppt/)
- 11-3: 7회→3단계 실험 압축 + 인사이트 3칸
- 12: Base vs LoRA 상세 비교 + GPT vs sLLM + 프롬프트 설계 + 학습상세
- 10: 판단 Base 출력 JSON 예시로 교체

### 버그 수정
- AgentIndicator.jsx: clarify → "문서 생성 Agent"로 표시되도록 매핑 추가

### 커밋
- `feat: 발표자료 v2 (구조 개편 + 소스코드 검증)` — develop push 완료
- `feat: Base 한계/성과 섹션 추가 + 배포 삭제 + 지영님 TOC 병합` — develop push 완료
- `fix: orchestrator docstring top-2 수정 + AgentIndicator clarify 매핑` — feat/jiyong push (develop 미반영)

## 다음 할 일
- [ ] 코드 검증 미완: 06 기술스택, 08 Agent 구조+상세, 09 데이터+RAG, 15 한계점
- [ ] 데모 영상 5분 촬영
- [ ] 목차(TOC) 내용은 지영님 수정 후 최종 확인
- [ ] 발표 리허설
