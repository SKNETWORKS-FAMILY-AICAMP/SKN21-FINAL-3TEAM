# 작업 로그 — 신지용 (PM)

> 세션 종료 시 Claude가 자동으로 업데이트합니다.

---

## 2026-02-10 (월)

**GitHub 전면 정비:**
- 라벨 설명 수정 2개 (3단계/4단계 description 뒤바뀜 교정)
- 마일스톤 이름 수정 3개 (2/3/4단계 → TASK_BOARD 기준)
- 이슈 마일스톤 재배치 14개
- 이슈 제목 수정 4개 (#9, #10, #14, #16)
- 신규 이슈 생성: #39 LLM API 모듈, #40 doc LLM 연동, #41 추가 데이터 수집
- 이슈 본문 수정: #12, #17 — "LLM API 먼저" 전략 반영

**문서 정비:**
- TASK_BOARD.md, README.md, CLAUDE.md, .gitignore 업데이트

**인프라:**
- Discord 웹훅 연동 (push/PR/이슈 → push-log 채널)
- WORK_LOG → 팀원별 개별 로그 체계로 변경

**다음 할 일:**
- TASK_BOARD 1단계 이슈부터 실제 개발 시작
- 팀원들에게 GitHub 정비 내용 공유

---

## 2026-02-11 (화)

**1단계 완료 확인 + 이슈 종료:**
- #2 API 스키마 정의 → 7개 스키마 파일 확인 후 Closed
- #3 AgentState 필드 확정 → 12개 필드 확인 후 Closed
- 1단계 체크리스트 7항목 전부 완료 확인

**2단계: #4 Intent 학습 데이터 구축:**
- 7개 카테고리 × 200문장 = 1,405개 JSONL 생성 (Claude 에이전트 6개 병렬)
- QA 완료: 중복0, JSON유효성통과, 라벨정확성통과
- general→judgment 5문장 재분류 (규정 관련 질문 경계 정리)
- train/eval 분할 (85:15): 1,194 / 211

**3단계: #5 Intent 분류 모델 파인튜닝:**
- RunPod GPU(On-Demand)에서 klue/bert-base 파인튜닝
- v1.0 결과: Eval F1 99.08%, Adversarial 72% (25문장)
  - 문제: judgment↔general 경계 오분류 5건
  - 원인: judgment 92%가 격식체, 길이 편향 (judgment 25.8자 vs general 10.4자)
- v1.1: judgment 캐주얼 데이터 +50건 증강 후 재학습
  - Eval F1 98.80%, Adversarial 88% (25문장) → judgment 오분류 0건 해결
- Adversarial 테스트 70개로 확장: 85.7% (60/70)
  - 남은 오분류: 오타/축약어 4건 + 짧은입력 3건 + 맥락의존 2건 + 경계모호 1건
  - → 모델이 아닌 전처리/오케스트레이터 레벨에서 처리 예정
- TRAINING_LOG.md 생성 (버전별 성능 기록)
- test_intent.py 생성 (대화형/단일/adversarial 테스트)

**ERD 검토 (혜빈 작업):**
- develop 브랜치 `docs/ERD.md` 확인 (11개 테이블)
- ERD vs ORM 모델 대조: 불일치 0건
- 개선 제안 3건: ①chat_logs에 session_id 추가 ②action_items.assignee FK 검토 ③TEXT→JSONB 검토

**ML 비교 실험 (발표용):**
- 실험 기획서 작성: `ai/experiments/EXPERIMENT_PLAN.md`
- adversarial 70문장 JSON 분리 (`adversarial_test.json`)
- test_intent.py 하드코딩 → JSON 로드로 리팩토링
- 실험 스크립트 3개 작성 + QA (run_method_comparison, run_gpt_comparison, run_visualize)
- RunPod GPU에서 실험 실행 (v1.1 재학습 + 6가지 방법론 비교)
- 결과: GPT Few-shot F1 97.5% > BERT Fine-tuned 90.0% (adversarial)
  - 단, BERT가 68배 빠르고 (6.7ms vs 457ms) 비용 $0
  - 일반 입력에서는 BERT Eval F1 98.8%
- 차트 4장 생성: method_comparison, confusion_eval, confusion_adv, improvement_v1
- TRAINING_LOG.md에 EXP 섹션 추가

**데이터 증강 + 버전별 학습 (v1.2~v1.4):**
- v1.2: 비정형 데이터 +300건 (6카테고리×50, 인터넷 슬랭/초성/축약어)
  - adversarial 70→120 확장 (multi-intent, ultra-short, formal, 경계쌍)
  - 결과: Eval F1 98.07%, Adversarial 85.0% (120개 기준)
- v1.3: boundary 타겟 증강 +163건 (7파일, v1.2 오분류 패턴 분석 기반)
  - judgment↔general, doc_search↔doc_generate, multi-intent, ultra-short, meeting, formal
  - adversarial 라벨 QA → 3건 수정 (multi-intent 최종의도 규칙 일관성)
  - seed 고정 추가 (재현성)
  - **최종 결과: Eval F1 98.63%, Adversarial 91.67% (10건 오분류)**
- v1.4: 하이퍼파라미터 그리드 서치 (6가지 조합)
  - best=epochs10/lr2e-5 → Eval은 미세 향상, Adversarial은 하락
  - **결론: 데이터 품질 > 하이퍼파라미터 (v1.3이 최종 모델)**
- 버전별 학습 파이프라인: `run_train_versioned.py`
- TRAINING_LOG.md 전체 업데이트 (v1.2~v1.4 + 전체 비교 요약)
- 차트: `improvement_all_versions.png` (4패널 버전 비교)

**후반 세션: 문서 QA + 마무리:**
- EXPERIMENT_PLAN.md 최종 정리: 실험 4개 완료 반영 + 차트 이미지 참조 6장 추가
  - adversarial 기준 차이 주석 추가 (실험2 25문장 vs 실험4 120문장 직접 비교 불가 명시)
- 차트 QA: v1.3 Eval F1 수치 오류 수정 + 요약 테이블 adversarial 셋 정확도 보정
- TRAINING_LOG.md: v1.4 혼동행렬 설명 주석 추가 (v1.3과 동일 데이터 기준)
- state.py: Intent 분류 담당자 주석 수정 (경은→지용)
- `upload_to_runpod.sh` 스크립트 추가 (학습 데이터 업로드용)

**다음 할 일:**
- #6 LangGraph 오케스트레이터 + SSE 구현
- 전처리 파이프라인 추가 (초성복원, 맞춤법교정) → adversarial 추가 개선
- 팀 진도 확인 (경은/승언/혜빈/지영)
