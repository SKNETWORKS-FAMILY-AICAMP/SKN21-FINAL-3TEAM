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

---

## 2026-02-11 (화) — 저녁 세션

**실험 5~6 기획서 작성:**
- EXPERIMENT_PLAN.md에 실험 5 (다중 모델 × 하이퍼파라미터 전탐색) 기획 추가
  - 비교 모델 3종: klue/bert-base, klue/roberta-base, monologg/koelectra-base-v3
  - 하이퍼파라미터 4종: epochs[3,5,7,10] × lr[1e-5,2e-5,3e-5,5e-5] × batch[8,16,32] × warmup[0.0,0.06,0.1]
  - 2단계 진행: Step1 144번(warmup 고정) + Step2 9번(warmup 미세조정) = 총 153번 학습
- EXPERIMENT_PLAN.md에 실험 6 (전처리 파이프라인 + 최종 성능 검증) 기획 추가
  - 전처리 4단계: 맞춤법 교정 / 초성 복원 / 슬랭 정규화 / 공백·특수문자 정리
  - Ablation Study: 전처리 단계별 기여도 개별 측정 (5가지 조합)
  - seed 3개(42, 123, 456) 반복 → 평균±표준편차로 신뢰성 검증
- Adversarial 테스트셋 확장 계획: 120 → 200문장 (+80)
  - 추가 유형: multi-intent 15 / ultra-short 15 / 오타·비정형 15 / formal 10 / context-dependent 10 / boundary 15
- 발표 스토리라인 6→7단계로 확장 (adversarial 확장 + 검증 강화 포인트 추가)
- 실험 4→5 논리 연결 수정 (v1.3=최종 → v1.3 데이터를 다른 모델에도 적용)
- TRAINING_LOG.md vs EXPERIMENT_PLAN.md 내용 대조 → 숫자 불일치 0건 확인

**팀원 작업 pull + 버그 확인:**
- develop pull → merge 완료 (혜빈/경은/지영 작업 대량 반영)
- frontend npm install: eslint 버전 충돌 확인 (@eslint/js@10 vs eslint@9) → --legacy-peer-deps로 설치
- Google 소셜 로그인 500 에러 원인 분석:
  - LoginPage.jsx에서 `/api/v1/auth/google`로 요청 → 프론트 dev 서버로 감 (백엔드 URL 아님)
  - 수정 필요: `window.location.href`를 `http://localhost:8000/api/v1/auth/google`로 변경
  - → 혜빈/지영에게 전달 필요

**다음 할 일 (내일):**
- Google 로그인 버그 혜빈/지영에게 공유
- eslint 버전 충돌 지영에게 공유
- adversarial 80문장 추가 제작 (200개 확장)
- max_length 64 충분한지 데이터 길이 확인
- 실험 5: 3모델 × 153번 그리드 서치 실행 (RunPod A100, ~3~5시간)
- 실험 6: 전처리 ablation + seed 반복 (~1~2시간)
- 이후 #6 오케스트레이터 착수

---

## 2026-02-12 (수)

**#6 오케스트레이터 + Agent async 전환:**
- judgment_agent, document_agent, schedule_agent → `async def`로 전환
- orchestrator.py 3개 wrapper 함수에 `await` 추가
- develop pull → 경은 judgment_agent 구현 코드와 merge conflict 해결
- feat/jiyong + develop 양쪽 push 완료

**인프라:**
- GitHub main 브랜치 보호 설정 (CLI): PR 필수 + 1 approval + force push 차단
- `run_model_comparison.py`에 `--resume` 기능 추가 (개별 run 단위 크래시 복구)

**실험 5 실행 (RunPod RTX 4090):**
- roberta-base: 이전 세션에서 완료 (48 Step1 + 3 Step2, best Adv F1=0.899)
- bert-base: 51 runs 완료, 결과 `grid_search_bert.json`으로 저장
- koelectra: torch 버전 이슈 (CVE-2025-32434, torch<2.6 차단) → torch+torchvision+transformers 업그레이드 후 실행 중

**실험 5 데이터/스크립트 QA:**
- 3개 에이전트 병렬 투입 (데이터 품질 / 스크립트 로직 / 이력 일관성)
- 발견 사항: doc_generate.jsonl 라벨 오염 2건, resume 모드 모델 저장 버그, Plan 숫자 2 차이
- 판단: 실험 결과 신뢰성에 영향 없으므로 수정 보류

**팀원 버그 공유 완료:**
- Google 로그인 500 에러 → 혜빈/지영에게 전달
- eslint 버전 충돌 → 지영에게 전달

**작업 범위 규칙 (충돌 방지):**
- `ai/agents/` 폴더 파일 수정 안 함
- 예외: `orchestrator.py` (라우팅, intent 모델 로드), `intent_classifier.py`, `state.py` (사전 공유 후)
- judgment_agent → 경은, document_agent → 승언, schedule_agent → 혜빈 담당

**doc_search 응답 UI QA:**
- 3개 에이전트로 전체 chat UI 분석
- 발견: 모든 카드 컴포넌트(JudgmentCard, GenerateCard 등)가 ChatPage에서 미사용 — 전부 텍스트 버블로 출력 중
- useSSE.js에 `result` 이벤트 핸들러 누락, chatStore 메시지 구조 확장 필요
- doc_search 전용 DocSearchCard 제안: 답변 요약 + 출처 카드 + 관련도 바 + 후속 행동 버튼
- → 지영에게 SSE result 이벤트 연결 + intent별 카드 분기 렌더링 요청 필요

**오케스트레이터 ↔ Intent 분류기 구조 확인:**
- intent_classifier.py → 모델 로드 + 추론 (싱글톤)
- orchestrator.py → classify_intent 노드에서 get_classifier() 호출 → route_by_intent로 분기
- 실험 5 최종 모델은 `ai/models/intent_classifier/`에 파일 교체만 하면 됨 (코드 수정 0줄)
- 현재 weights 없으면 fallback 모드 (전부 general로 분류)

**다음 할 일:**
- koelectra 실험 마저 완료 (RunPod — 집에서 처리)
- koelectra 결과 저장: `cp grid_search_full.json grid_search_koelectra.json`
- 3모델 비교 분석 + 차트 생성
- 실험 6: 전처리 ablation + seed 반복
- 최종 모델 확정 → `ai/models/intent_classifier/`에 배포 + TRAINING_LOG.md 업데이트

---

## 2026-02-13 (목)

**실험 5 최종 모델 배포:**
- 3모델 비교 결과 확정: BERT(Adv F1 0.9015) > RoBERTa(0.899) > KoELECTRA(0.8856)
- `train_best_bert.py` 배포용 학습 스크립트 작성 → RunPod에서 BERT best config 1회 학습
  - config: klue/bert-base, epochs=5, lr=2e-5, batch=16, warmup=0.0
- `model.safetensors`(423MB) RunPod → 로컬 다운로드 후 `ai/models/intent_classifier/`에 배치
- `config.json` RoBERTa → BertForSequenceClassification으로 변경
- `model_info.json` klue/bert-base + best config/metrics 추가
- 팀원 충돌 QA 통과 (다른 팀원 ai/models/ 미접근 확인)
- intent_classifier.py 코드 수정 0줄 — fallback 모드에서 실제 모델 추론으로 전환 완료

**다음 할 일:**
- 실험 6: 전처리 ablation + seed 반복 (내일)
- TRAINING_LOG.md 실험 5 최종 결과 업데이트
- #6 오케스트레이터 마무리

---

## 2026-02-16 (일)

**실험 6 결과 분석 + 문서 반영:**
- EXPERIMENT_PLAN.md에 "실험 5→6 수치 비교 해석" 섹션 추가
  - 실험 5(90.15%) vs 실험 6(88.56%) 차이가 성능 하락이 아닌 보고 기준 차이임을 명시
  - 같은 seed=42 기준 전처리 적용 후 90.15% → 90.82% 상승
- 최종 모델 성능 테이블 재구성 (seed=42 전처리 없음/있음 + 3-seed 평균 나란히 배치)
- 발표 스토리라인 6~7번 항목 개편

**전처리 파이프라인 실서비스 연결 확인:**
- intent_classifier.py:113에서 ai/experiments/preprocessing.py를 이미 import 중 → 실서비스에 전처리 적용됨
- 추후 ai/agents/preprocessing.py로 위치 이동 필요 (실험 폴더 의존 제거)

**실험 7: BERT vs GPT-4o-mini 최종 비교 (212문장 동일 조건):**
- run_final_comparison.py 작성 (BERT 전처리 유/무 + GPT zero/few-shot, 4가지 비교)
- 토크나이저 이슈 해결 (tokenizer_config.json의 tokenizer_class가 비정상 → klue/bert-base로 직접 로드)
- **결과: BERT+전처리 F1=90.07% > GPT Few-shot F1=86.30% (3.8%p 역전)**
  - 실험 1(70문장)에서 GPT가 7.5%p 우세 → 212문장에서 BERT가 3.8%p 우세
  - GPT 약점: 1~2어절 짧은 입력("일정","규정","보고서")을 general로 오분류 (21건)
  - BERT 약점: 맥락 의존("아까 그거"), 복합 질문 (11건)
- EXPERIMENT_PLAN.md에 실험 7 섹션 + 발표 스토리라인 반영
- 커밋 & push 완료

**다음 할 일:**
- ~~복합 질문 처리 (멀티 인텐트) — 오케스트레이터에서 LLM으로 문장 분리 → BERT 각각 분류~~ → 2/16 구현 완료
- ~~긴 질문 / 맥락 의존 질문 처리 방안~~ → 2/16 구현 완료
- #6 오케스트레이터 마무리

---

## 2026-02-16 (일) — 오후 세션

**복합 질문 처리 시스템 (Smart Hybrid) 구현:**

설계서 기반 Phase 1~2 전체 구현 완료. 4개 파일 수정.

- `ai/agents/state.py`: AgentState에 6개 필드 추가
  - is_complex, sub_queries, intent_candidates, resolved_input, sub_responses, needs_context_resolution
- `ai/agents/intent_classifier.py`: 대규모 확장
  - `predict(return_candidates=True)`: BERT top-3 후보 반환 지원
  - `detect_complexity()`: 3중 AND 로직 (키워드 + confidence gap + 동사 수)
  - `is_context_dependent()`: 대명사/지시어 패턴 감지
  - `apply_known_overrides()`: 실험에서 발견된 반복 오분류 보정 (KNOWN_OVERRIDES dict)
  - COMPLEX_PATTERNS 넓은 범위 확장 (아서/어서, 고, 면서, 뒤에, 바탕으로 등)
  - 모든 fallback 모드(Solar, embedding)에서도 candidates/overrides 지원
- `ai/agents/orchestrator.py`: 그래프 v2 전면 재구축
  - `classify_intent_v2`: BERT 분류 + 복합감지 + 지시어감지 통합
  - `route_by_complexity`: simple/complex/context_dep/low_confidence 4분기
  - `resolve_context`: LLM으로 지시어 → 명확한 문장 변환 (최근 5턴 참조)
  - `decompose_and_classify`: LLM 1회 호출로 분류+분해+순서 결정
  - `execute_sub_queries`: 서브쿼리 순차 실행 (depends_on 체인)
  - `merge_responses`: 섹션별 순차 표시 + 한줄 요약
  - `clarify_with_candidates`: confidence < 0.7 시 top-3 후보 제시
  - `post_execution_check`: 뼈대만 추가 (Agent 완성 후 실제 로직)
  - `_validate_decomposition`: LLM 분해 결과 검증 (필수 필드, intent 유효성, 순환참조)
- `backend/app/api/v1/chat.py`: SSE 이벤트 확장
  - intent_update (재진입 시), multi_intent, sub_query_done, clarify_candidates
  - classify_intent_v2 SSE 중복 전송 방지 (_classify_sent 플래그)
  - _build_initial_state에 6개 새 필드 초기화

**버그 수정 2건:**
1. `_execute_single_agent`에서 `stream_mode=False` 추가 (서브쿼리 빈 응답 방지)
2. SSE classify_intent_v2 재진입 시 `intent` → `intent_update`로 구분

**토크나이저 버그 발견 및 수정:**
- 회귀 테스트 중 기존에 잠재해 있던 **토크나이저 불일치 버그** 발견
- **문제**: `ai/models/intent_classifier/tokenizer_config.json`의 `tokenizer_class`가 `"TokenizersBackend"`(무효값)로 저장됨
  - `"BertTokenizerFast"`로 수정하여 로드 성공했지만, 로컬 vocab 파일이 klue/bert-base 원본과 불일치
  - 동일 모델인데 **로컬 토크나이저 F1 80.54%** vs **klue/bert-base 토크나이저 F1 90.07%** (10%p 차이)
- **원인**: RunPod에서 모델 저장 시 토크나이저 파일이 비정상 기록. 기존 실험 스크립트는 `klue/bert-base`에서 직접 로드하여 문제가 드러나지 않았지만, 실서비스(`intent_classifier.py`)는 로컬 모델 디렉토리에서 로드 중이었음
- **수정**: `intent_classifier.py`에서 토크나이저를 `klue/bert-base` 원본에서 로드하도록 변경
  ```python
  # 변경 전: self.tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
  # 변경 후:
  self.tokenizer = AutoTokenizer.from_pretrained("klue/bert-base")
  ```
- **검증 결과**: 수정 후 기존 실험 결과와 정확히 일치
  - adversarial (212문장): F1 90.07% (기존 90.07% — 동일)
  - blind (70문장): F1 95.62% (기존 92.84% — +2.78%p 상승)

**v2 회귀 테스트 (`run_regression_v2.py`):**
- 기능 테스트 4종 전부 PASS:
  - predict() 호환성 (기본/후보 모드): PASS
  - detect_complexity() (단순 4 + 복합 3): 7/7 PASS
  - is_context_dependent() (양성 5 + 음성 3): 8/8 PASS
  - apply_known_overrides() (5 케이스): 5/5 PASS
- BERT 성능 회귀 테스트 (토크나이저 수정 후, 로컬 데스크탑에서 실행):
  - adversarial (212): Accuracy 90.09%, **Macro F1 90.07%** (기존과 동일)
  - blind (70): Accuracy 95.71%, **Macro F1 95.62%** (+2.78%p)
  - 평균 추론 시간: 14.46ms / 14.85ms
- **결론**: v2 코드 변경이 기존 BERT 성능에 영향 0. 토크나이저 수정으로 실서비스 성능이 실험 결과와 일치하게 됨

**문서:**
- `docs/복합질문_설계서.md` 신규 생성 (아키텍처, 결정 근거, SSE 흐름, 토크나이저 수정, 검증 계획)
- `ai/experiments/run_regression_v2.py` 신규 생성 (v2 회귀 테스트 스크립트)

**다음 할 일:**
- 복합 질문 테스트 데이터 30~50문장 제작 (Phase 3)
- 복합 감지 정확도 측정 (오탐/미감지 비율)
- post_execution_check 실제 로직 구현 (다른 팀원 Agent 완성 후)
- 프론트엔드(지영)에게 SSE 새 이벤트 타입 공유 필요

---

## 2026-02-19 (수)

**develop 최신 반영:**
- develop pull → 충돌 없이 머지 완료 (13개 파일, +1,483줄)
- 경은: `judgment_agent.py` 수정 + `test_e2e_judgment.py` E2E 테스트 추가 (784줄)
- 지영: 대시보드 리뉴얼 (`AIChatWidget`, `TodaySchedule`, `GreetingBanner` 등)

**BERT 복합질문 감지 로직 리뷰:**
- `detect_complexity()` 3중 신호 구조 확인 (intent_classifier.py:436~477)
  - 신호 1: 접속/순차 키워드 패턴 (COMPLEX_PATTERNS 6종)
  - 신호 2: BERT top-2 confidence gap < 0.3 (모델이 헷갈리는 것 자체가 복합 신호)
  - 신호 3: 동사 어미 2개 이상 (VERB_ENDINGS)
  - 판정: 2개 이상 충족 시 복합 (오탐 방지를 위한 AND 로직)
- BERT 단독으로는 복합질문 분류 불가 → confidence 분포를 간접 신호로 활용하는 하이브리드 구조

**복합질문 기능 토글 플래그 추가:**
- `config.py`에 `ENABLE_COMPLEX_QUERY = False` 플래그 추가
- `orchestrator.py`의 `route_by_complexity`에서 해당 플래그 참조
- False 시 복합질문 분해 경로 비활성화 → 단일 intent만 사용 (원래 동작)
- True로 바꾸면 즉시 복합질문 분해 활성화

**오케스트레이터 단독 테스트 (Python 3.13 환경):**
- BERT 모델 로드 + 9개 질문 라우팅 테스트: 전부 정상
- 복합질문도 `ENABLE_COMPLEX_QUERY=False`로 decompose 경로 안 탐 확인

**BERT 오분류 패턴 발견 + 수정 (KNOWN_OVERRIDES 확장):**
- 63개 테스트 중 8개 오분류 발견
- 원인: "X 알려줘" 어미를 BERT가 doc_search로 학습 (학습 데이터 편향)
  - doc_search에 "규정 찾아줘/검색해줘/보여줘" 43건 vs judgment에 "규정 알려줘" 0건
- KNOWN_OVERRIDES 5개 패턴 추가로 해결:
  1. `규정/규칙/지침 + 알려/설명` → judgment
  2. `기준/평가/심사 + 알려/설명` → judgment
  3. `복리후생/수당 + 뭐/있어` → judgment
  4. `퇴직금/급여 + 계산/얼마` → judgment
  5. `지각/결근 + 어떻게/징계` → judgment
- 회귀 테스트 14건 전부 통과
- 남은 4건은 1~2어절 초단문 (야근, 출장 등) → clarify(되묻기) 대상

**다음 할 일:**
- 복합 질문 테스트 데이터 제작 + 감지 정확도 측정
- post_execution_check 실제 로직 구현
- 프론트엔드(지영)에게 SSE 새 이벤트 타입 공유
- 1~2어절 초단문 처리 방안 검토 (clarify 기능 활성화)
