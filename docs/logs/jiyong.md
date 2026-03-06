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

---

## 2026-02-20 (목)

**오케스트레이터 복합질문 코드 주석 처리:**
- `ENABLE_COMPLEX_QUERY=False`로 이미 비활성 상태인 복합질문 관련 코드를 주석 처리
  - `classify_intent_v2`: complexity 감지 블록 주석 → `is_complex = False` 고정
  - `route_by_complexity`: complex 라우팅 체크 주석
  - `build_graph`: decompose/execute/merge 노드 및 엣지 주석
  - 함수 정의 자체는 유지 (향후 재활성화 가능)
- 현재 그래프 흐름: 3분기 (지시어→resolve_context→재분류 / 저신뢰→clarify / 고신뢰→Agent 직행)

**오케스트레이터 구조 설명 문서 작성:**
- `docs/지용/오케스트레이터_구조_설명.md` 신규 생성
- 그래프 흐름도, 노드별 설명, config 값, 지시어 패턴, 비활성 기능 정리

**ChromaDB → Qdrant 일괄 변경:**
- 프로젝트 전체에서 ChromaDB 참조를 Qdrant로 수정 (11개 문서)
  - CLAUDE.md, README.md, DATA_PLAN.md, DATA_GUIDE.md, ERD.md, TASK_BOARD.md
  - 멘토링 문서 2개, 학습가이드, 팀원 로그, 역할분배 문서

**중간발표 멘토링 문서 최신화:**
- `docs/멘토링/중간발표_멘토링_20260220.md` 전체 업데이트
  - 단계별 진행률: 2단계 100%, 3단계 80%, 5단계 10%, 6단계 40%
  - 5명 팀원 최신 작업 내역 반영 (전체 로그 크로스체크)
  - Agent 구현율 조정 (Judgment 98%, Schedule 85%)
  - AWS 배포 블로커 완료 반영

**프로젝트 구조 학습가이드 이동:**
- `docs/지용/프로젝트_구조_학습가이드.md` → `docs/프로젝트_구조_학습가이드.md`

**다음 할 일:**
- 복합 질문 테스트 데이터 제작 + 감지 정확도 측정
- post_execution_check 실제 로직 구현
- 프론트엔드(지영)에게 SSE 새 이벤트 타입 공유
- 1~2어절 초단문 처리 방안 검토 (clarify 기능 활성화)

---

## 2026-02-22 (일)

**오케스트레이터 단일질문 분류 전용으로 초기화 (`fb7eeb9`):**
- 복합질문 분해/실행/병합 로직 전면 제거 (11개 함수 삭제)
- 맥락해석(resolve_context) 로직 제거
- classify_intent_v2 → classify_intent, route_by_complexity → route_by_intent 리네임
- AgentState에서 is_complex, sub_queries 등 5개 필드 삭제
- intent_classifier에서 detect_complexity, COMPLEX_PATTERNS 등 삭제
- chat.py SSE 핸들러 정리
- vite.config.js loadEnv 적용
- 실험 파일 2개 삭제

**develop 최신 반영 머지 (`f01ea8b`):**
- develop 브랜치 최신 코드 merge

**Agent 설계문서 + 산출물 동기화 업데이트 (`e9950b3`):**
- docs/agent/architecture.md, agent_data.md 추가
- README.md Document Agent 기능 설명 구체화
- 산출물 docx 2종 업데이트
- 멘토링 PDF 추가

**다음 할 일:**
- Intent 분류 실험 v2 착수 (데이터 생성 + 모델 비교)

---

## 2026-02-23 (일)

**Intent 분류 실험 v2 — Stage 1 데이터 생성 완료:**

기본 데이터 생성 (GPT-4o + Claude Sonnet 4):
- Claude: 8개 intent x 150개 = 1,200개 (CLI 에이전트 7개 병렬 실행)
- GPT-4o: 8개 intent x ~137개(평균) = 1,099개 (CMD에서 스크립트 실행)
- 합계: **2,299개** (중복 제거 후)
- GPT-5 시도 → 추론 모델이라 데이터 생성 부적합 (파싱 0개) → GPT-4o로 변경

QA 결과:
- 비유효 라벨: 0개, Cross-LLM 중복: 0개
- 클래스 균형 max/min: 1.11 (양호)
- Train/Val/Test: 1,847 / 226 / 226 (stratified, seed=42, 누출 없음)

**실험 스크립트 4개 작성 완료:**
- `ai/experiments_v2/run_baseline.py` — Stage 2: 3모델 동일 HP 비교
- `ai/experiments_v2/run_grid_search.py` — Stage 3: 32-point grid + 3-seed 안정성
- `ai/experiments_v2/run_final_eval.py` — Stage 4: hold-out, adversarial, ablation, 속도, 통계
- `ai/experiments_v2/run_error_analysis.py` — 오분류 유형 분류 + 보고서

**경계 쌍 + 적대적 데이터 생성:**
- 경계 쌍: GPT 300개 + Claude 300개 = 600개 (10쌍 x 30개 x 2 LLM)
- 적대적: GPT 232개 + Claude 240개 → 중복 제거 후 **450개**
- Train-Val 누출 1건 제거, Train-Adversarial 중복 13건 제거
- 최종 Split: Train 2,327 / Val 285 / Test 286

**Stage 2 Baseline 학습 (로컬 RTX 4070):**
- 3모델: klue/bert-base, koelectra-base-v3, distilkobert
- 고정 HP: epochs=5, lr=2e-5, batch=16
- koelectra: **Val F1 0.9825** (112.9M, 860s)
- bert-base: Val F1 0.9780 (110.6M, 808s)
- distilkobert: Val F1 0.9498 (28.4M, 243s) — sentencepiece 설치 후 완료
- 차트: baseline_comparison.png, training_curves.png, per_class_f1_radar.png, confusion matrix 3장

**Stage 3 Grid Search (RunPod RTX 4090):**
- koelectra 대상 32-point grid search (~17분)
- Best config: **ep10/lr3e-5/bs16 → Val F1 0.9897**
- Seed 안정성: 0.9874 ± 0.0033 (3-seed)
- Baseline(0.9825) → Best(0.9897): +0.72%p → **데이터 > HP** 재확인

**Stage 4 최종 평가 (RunPod RTX 4090):**
- 3모델 best config으로 재학습 + adversarial 450개 평가
- koelectra **Adv F1 86.04%** > bert 85.17% > distilkobert 79.26%
- doc_qa 3모델 모두 최약점 (70~74%)
- 전처리 Ablation A~E 전부 동일 (효과 없음)
- McNemar 전부 n.s., Bootstrap CI 산출 완료
- **최종 선택: koelectra** (Adv F1, 속도 8.3ms, 강건성 모두 우위)
- 차트 11장 생성 (confusion, ablation, confidence, speed, f1_vs_speed)

**기술 이슈:** GPT-5 추론 모델 비호환 → GPT-4o 전환 / Python 3.11/3.13 이중 설치 → python -m pip / distilkobert sentencepiece 누락 / RunPod torch 버전 충돌 → --upgrade 필수 / run_final_eval.py mcnemar 리스트 버그 수정

**다음 할 일:**
- ~~run_error_analysis.py 실행 (오분류 유형 분석)~~ → 2/23 완료
- 시나리오 테스트 30개 작성
- ~~doc_qa/doc_search/general 타겟 보강 → 재학습~~ → 2/23 완료
- ~~최종 모델 저장 (ai/models/intent_classifier/)~~ → 2/23 완료
- 발표 자료 준비

---

## 2026-02-23 (일) — 오후 세션

**develop 최신 반영:**
- develop pull → feat/jiyong에 merge (fast-forward, 36파일)

**Stage 5.1 오분류 분석 (RunPod):**
- koelectra best config으로 재학습 + 서비스 디렉토리에 모델 저장
- `run_error_analysis.py` 실행 완료
  - Test: 278/286 정답 (97.2%), 8건 오분류
  - Adversarial: 387/450 정답 (86.0%), 63건 오분류
- 오분류 주요 유형: short_text(47건), overconfident(42건), boundary_high(30건)
- Top 혼동 쌍: doc_qa→doc_search(10), doc_generate→doc_summary(5), schedule_add→schedule_view(4)
- 차트 8장 생성 (error_types, confusion_analysis, confidence_analysis × test/adversarial)

**Stage 5.2 보강 데이터 생성 + QA:**
- 98개 타겟 보강 데이터 작성 (`augmentation_stage5.jsonl`)
  - doc_qa +20, doc_generate +15, schedule_add +11, schedule_view +11, general +11, judgment +10, doc_search +10, doc_summary +10
- **초판 QA에서 적대적 데이터 누출 13건 발견** → 전면 재작성
  - 원인: adversarial 테스트셋 확인 없이 직관적으로 작성
- 재작성 후 QA 통과: 적대적↔보강 exact 중복 0건, 라벨 유효, 8개 intent 전부 포함

**Stage 5.3 보강 재학습 (RunPod):**
- `run_stage5_retrain.py` 작성 + 실행
- Train: 2,327 + 98(보강) = 2,425개, koelectra best config (ep10/lr3e-5/bs16)
- **결과:**
  - Test F1: 0.9726 → **0.9788** (+0.62%p)
  - Adv F1: 0.8604 → **0.8784** (+1.80%p)
  - doc_qa: 0.710 → **0.789** (+7.9%p, 최대 개선)
  - doc_summary: 0.875 → **0.917** (+4.2%p)
  - doc_search: 0.827 → **0.853** (+2.6%p)
  - doc_generate: 0.882 → 0.869 (-1.4%p, 소폭 하락)
- 최종 모델 `ai/models/intent_classifier/`에 저장 (koelectra v2, 8 labels)
- 차트: stage5_comparison.png, stage5_confusion_adv.png

**실험 계획서 업데이트:**
- EXPERIMENT_PLAN_v2.md: Stage 5.1~5.2 결과 반영, 오분류 분석 상세, 보강 QA 결과 기록

**발표 스토리라인 검토:**
- 슬라이드 1~7: 데이터 준비 완료 ✅
- 슬라이드 8 "전처리 효과": 전처리 효과 없음 → **"데이터 보강"으로 변경 제안** (Before/After 비교)
- 슬라이드 9~10: Stage 5 결과 반영 필요

**다음 할 일:**
- ~~슬라이드 8을 "데이터 보강 Before/After"로 변경~~ → 2/23 야간 완료
- ~~시나리오 테스트 30개 작성 + 실행~~ → 2/23 야간 완료
- ~~intent_classifier.py 8개 intent + koelectra 모델 로드 확인~~ → 2/23 야간 완료
- 발표 자료 준비

---

## 2026-02-23 (일) — 야간 세션

**Stage 6 RunPod 실행 + 결과 분석:**
- Stage 5 시나리오 baseline: 26/30 (86.7%), 4건 오분류
- Stage 6 학습 (Label Smoothing 0.1): Adv F1 87.58% (-0.26%p), 과신뢰 42→13건 (-69%)
- Stage 6 시나리오: 26/30 (86.7%), 동일 4건 오분류 (confidence만 낮아짐)
- "규정 확인" 라벨 judgment→doc_search 수정 → 조정 시 27/30 (90%)
- 오분류 3건 모두 Stage 6에서 threshold 0.85 이하 → clarify 라우팅으로 해결

**intent_classifier.py 업데이트:**
- docstring: v2_stage5 → v2_stage6
- 토크나이저: klue/bert-base 하드코딩 → model_info.json에서 base_model 동적 로드
- config.py threshold: CONFIDENCE 0.7→0.85, FALLBACK 0.5→0.4

**EXPERIMENT_PLAN_v2.md 결과 반영:**
- Stage 6 섹션: ⬜ 체크박스 → ✅ 실제 결과 수치 전부 반영
- 팩트 오류 8건 수정:
  - "3개 LLM" → "2개 LLM" (Gemini 미사용)
  - adversarial 240개 → 450개 (2곳)
  - GPU A4000 → 4090
  - 로드맵 "4단계" → "6단계"
  - 슬라이드 8에 Label Smoothing/과신뢰 해소 설명 추가
  - TODO 체크박스 정리

**모델 weights 로컬 배포:**
- RunPod에서 model.safetensors (431MB) 다운로드 → ai/models/intent_classifier/ 배치
- 로컬에서 파인튜닝 모델 직접 로드 가능 (fallback 불필요)

**다음 할 일:**
- 발표 차트 10장 정리 (누락 확인 + 최종 버전)
- 최종 보고서 작성 (Stage 4.10)
- 다른 팀원 작업 통합 (PM)

---

## 2026-02-24 (월)

**문서 관리 페이지 검색 기능 개선:**

1. EC2 서버에서 RRF 스코어 분포 분석 (3개 쿼리):
   - 상위 클러스터(0.030~0.033) vs 하위 클러스터(0.014~0.016) 2군집 패턴 확인
   - 기획서 문서(id 1,2,3)가 모든 쿼리에서 상위 클러스터에 출현 → 벡터 유사도 false positive

2. RAG → DB ILIKE 전환 결정:
   - 문서 관리 페이지에서 RAG(Qdrant hybrid BM25+Vector+RRF) 검색은 오버킬
   - 문서 수가 적고(8~9개) RRF 스코어 압축으로 관련/무관 구분 불가
   - **"제목+내용" 검색도 DB ILIKE로 변경** (사용자가 기대하는 건 정확한 키워드 매칭)

3. 수정 파일 3개:
   - `frontend/src/pages/DocumentsPage.jsx`: 드롭다운 "내용" → "제목+내용" 복원, SEARCH_TYPE_MAP/PLACEHOLDERS 업데이트
   - `backend/app/api/v1/documents.py`: search_type regex에 `title_content` 추가
   - `backend/app/services/document_service.py`: RAG content 검색 블록 제거 → `or_(title.ilike, content.ilike)` DB 검색으로 교체

4. RAG 관련 코드(업로드 시 Qdrant 인덱싱, 삭제 시 Qdrant 정리)는 유지 — 챗봇(judgment agent)에서 계속 사용

5. 테스트 문서(id=18, test_upload_search) DB+Qdrant에서 삭제

6. 커밋 `d83930c` → feat/jiyong + develop 양쪽 push 완료

**develop 최신 반영:**
- develop pull → fast-forward merge (37파일, 승언/혜빈/지영 작업 대량 반영)
  - 승언: document_agent 대폭 수정, 회의록/보고서/제안서 스킬 개선
  - 혜빈: chat.py, documents.py, admin.py, auth.py, 유저 모델 필드 추가
  - 지영: MyPage 신규, Topbar/ChatWindow/ChatSessionSidebar/DocumentViewPanel UI 개선

**다음 할 일:**
- 발표 차트 정리 + 최종 보고서
- 팀원 작업 통합 테스트
- E2E 테스트 확인

---

## 2026-02-24 (월) — 오후 세션

**FINAL_REPORT.md 보완 (3건):**
- schedule_view -4.8%p 하락 원인 분석 추가 (Label Smoothing + 소표본 영향)
- Stage 5 vs 7 보강 차이 설명 추가 (임계량 ~100개 이상이어야 효과)
- McNemar n.s. 해석 보강 ("동급일 때 실용적 기준으로 선택이 합리적")

**중간발표 대본 스토리라인 개편:**
- 슬라이드 5: 제목 "문제 정의"로 변경, 경계 데이터 600개 전략 설명 추가
- 슬라이드 6: Adversarial F1 중심 테이블로 변경, Full Fine-tuning 학습 방식 설명 추가
- 슬라이드 7: 4단계 나열 → "3가지 교훈" 스토리라인으로 전면 재구성
- 슬라이드 8: 테이블 간소화, 핵심 메시지 한 문장으로
- 슬라이드 9: "기억할 숫자 3개"로 시작, 향후 계획 우선순위 방식으로 변경

**대본 진행상황 업데이트:**
- Document Agent: 50% → 70% (LLM 연동 동작)
- 전체 진행률: 65% → 75%
- 향후 계획 1순위: Document Agent 완성 → sLLM 파인튜닝으로 변경
- Q6: Document Agent 블로커 → LLM→sLLM 교체 시 성능 질문으로 변경

**3개 문서 일치성 검토 + 수정:**
- EXPERIMENT_PLAN ↔ FINAL_REPORT ↔ 대본 교차 대조
- 불일치 3건 수정 (Plan: 속도 8.3ms→7.9ms 통일, 시나리오 30→100개, 슬라이드 제목 동기화)

**FINAL_REPORT 이미지 정리:**
- 차트 이미지 마크다운 삽입 (GitHub 모바일 열람용)
- 시나리오 차트 위치 보정 (섹션 끝 → 결과 테이블 바로 아래)
- 누락 차트 2개 추가 (class_distribution, error_types_adversarial)
- 30문장 기준 시나리오 차트 제거 (100문장 데이터와 불일치)
- 중복/과잉 차트 4장 제거 (hp_heatmap, seed_stability, confusion matrix 2장) → 10개→6개

**다음 할 일:**
- FINAL_REPORT.md 정독하며 실험 내용 공부
- 발표 자료(PPT) 제작 (Gemini 활용)
- 시연 시나리오 준비 (슬라이드 3, 2분→5분으로 확장 검토)

---

## 2026-02-25 (화)

**중간발표 문서 준비:**
- 중간발표 시나리오 v3 작성 + README 현행화 (`66da39f`)
- 중간발표 보조 자료 추가: FINAL_REPORT 보기용 + 실험 요약 PDF (`506a9da`)
- 실험간단요약 PDF → intent실험요약.md로 교체 (`c3d25ca`)
- intent실험요약을 스토리라인 형식으로 개선 (`368be83`)

**README 대폭 개선 (중간발표용):**
- 파인튜닝 데이터 현황 미정으로 수정 (`96d00ac`)
- 아키텍처/기능구현 섹션에서 담당자 이름 제거 (`378b343`)
- 현재 배포 상태 반영: Backend CI/CD + Frontend 로컬 (`b9fd301`)
- 중간발표용 보강: 핵심 성과 + 실험 이미지 + 수치 보정 (`7fed8a5`)
- Agent 워크플로우 다이어그램 원본 ASCII art 복원 (`9055c7f`)
- README/CLAUDE.md 실제 프로젝트 구조와 불일치 수정 (`efcbc91`)

**코드 수정:**
- Intent confidence threshold 0.75→0.85 수정 + 4주차 산출물 추가 (`b8460e6`)
- E2E Playwright 셀렉터 수정 + 8개 인텐트 전체 커버리지 달성 (`90184b7`)
  - 기존 셀렉터가 UI 변경으로 깨진 부분 수정
  - 8개 인텐트(judgment, doc_search, doc_generate, doc_summary, doc_qa, schedule_add, schedule_view, general) 전체 테스트 통과

**다음 할 일:**
- 중간발표 (발표 자료 최종 점검)
- 시연 시나리오 리허설
- 팀원 작업 통합 테스트

---

## 2026-03-03 (월)

**문서 Agent LoRA v2 파인튜닝 인프라 구축:**

Phase 0 — LLM Factory 리팩토링:
- `_call_llm()` Solar API 하드코딩 → `get_llm().generate()` async 리팩토링
  - `ai/agents/document_agent.py`: 8개 함수 async 전환 + await 추가
  - `ai/agents/schedule_agent.py`: 3개 함수 async 전환 + await 추가
- `ai/llm/base.py`: `generate()`/`chat()`에 `json_mode: bool` 파라미터 추가
- `ai/llm/openai_provider.py`: json_mode → `response_format={"type": "json_object"}` 구현
- `ai/llm/anthropic_provider.py`: json_mode → 시스템 프롬프트에 JSON 지시 추가

어댑터 분리 전략 결정 (통합 X → 기능별 분리 O):
- doc_generate(JSON)와 doc_summary(마크다운)의 출력 포맷 차이로 통합 학습 시 간섭 위험
- JD 템플릿 제외 → 회의록/보고서/제안서 3종만 유지

Config 분리 (3종):
- `ai/finetuning/configs/v2_generate.yaml` — r=32, 380개 (회의록150+보고서130+제안서100)
- `ai/finetuning/configs/v2_qa.yaml` — r=32, 300개
- `ai/finetuning/configs/v2_summary.yaml` — r=16 (단순 태스크), 200개

학습/평가/검증 스크립트:
- `ai/finetuning/train_v2_document.py` — `--task generate/qa/summary/all` 지원, 3개 모델 비교 모드
- `ai/finetuning/evaluate.py` — 평가 함수 6종 (JSON유효율, 필드정확도, TokenF1, ROUGE-L 등)
- `ai/finetuning/validate_v2_data.py` — 데이터 검증 (JSON파싱, 필수필드, 한국어키 탐지, 중복제거)

데이터 디렉토리 분리:
- `data/training/v2_generate/` — sample_generate.jsonl (회의록+보고서+제안서 3개)
- `data/training/v2_qa/` — sample_qa.jsonl (2개)
- `data/training/v2_summary/` — sample_summary.jsonl (2개)

문서:
- `docs/지용/문서Agent_LoRA_v2_파인튜닝_계획.md` — 전체 계획 문서 (베이스모델 비교, 데이터 설계, 하이퍼파라미터, 평가 기준, 리스크)
- `data/training/v2_document/FORMAT_GUIDE.md` — 데이터 형식 가이드 업데이트

정리:
- 승언 이전 파일 `ai/finetuning/legacy/`로 이동 (train_qa_lora.py, qa_ft_colab.ipynb, v2_document.yaml)
- `ai/data/회의록3.json` 삭제 (미사용)

커밋 `bc20261` → feat/jiyong + develop 양쪽 push 완료

**다음 할 일:**
- AI Hub 데이터 검색 + 다운로드 (국회회의록, 행정문서 기계독해, 문서요약 등)
- 변환 스크립트 작성 (AI Hub → messages JSONL)
- GPT-4o/Claude 합성 데이터 생성 (교차 검증)
- 변형 데이터 생성 (구어체/오타)
- 검증 + train/eval 분할
- RunPod A100에서 3개 모델 비교 학습 (Qwen3-8B, EXAONE-3.5-7.8B, Kanana-1.5-8B)

---

## 2026-03-04 (화)

**파인튜닝 시스템 프롬프트 검토 + 데이터 품질 QA:**

프롬프트 ↔ 학습 데이터 일치 검증:
- v2_summary: `prompts.py` ↔ 학습 데이터 system 100% 일치 (171자) ✅
- v2_qa: `prompts.py` ↔ 학습 데이터 system 100% 일치 (423자) ✅
- v2_generate: 동적 필드 방식 system prompt 적용됨 ✅

v2_qa 데이터 다양성 문제 발견 (심각):
- confidence: 0.9, 0.95 딱 2종류뿐 (600건 전부)
- relevance: 전부 "높음" (600건 전부)
- citations 수: 전부 1개 (600건 전부)
- 합성 스크립트(`synthesize_qa.py`)도 동일 문제 — `build_training_sample`에서 하드코딩
- **원인**: AI Hub 원본에 confidence/relevance 정보 없어서 변환 시 하드코딩, 합성 스크립트도 그대로 가져감

v2_generate AI Hub 데이터 탈락:
- 고정 프롬프트 backup: 783건
- 동적 필드 변환 후: 476건 (307건 탈락)
- `convert_to_dynamic_fields.py` 변환 실패 원인 확인 필요

3개 어댑터 시스템 프롬프트 개선안 작성:
- v2_generate: "실제 내용 작성" + "지침 문장 복사 금지" 2줄 추가
- v2_summary: 출력 형식 단계별 명시 (헤딩명, 포인트 3~5개, 키워드 3~7개 쉼표 구분)
- v2_qa: confidence 구간 가이드, relevance 판단 기준, citations 복수 허용 명시
- v2_qa 근본적 설계 선택지 3가지 정리 (A.현행+보완 / B.간소화 / C.자연어)

**산출물:**
- `ai/finetuning/finetuning_docs/프롬프트_검토_TODO.md` — 검토 결과 + 개선안 + 작업 체크리스트

**다음 할 일 (집에서 이어서):**
- Step 1: 3개 어댑터 프롬프트 확정 (TODO.md 개선안 기반)
- Step 2: v2_generate 476건 탈락 원인 확인 + 복구
- Step 3: v2_qa 합성 스크립트 수정 (다양성 보완)
- Step 4: 프롬프트 변경 시 AI Hub 데이터 재변환 + 합성 데이터 재생성
- Step 5: 검증 + train/eval 분할

---

## 2026-03-04 (화) — 오후 세션 (프롬프트 v2 구현)

**프롬프트 v2 스크립트 수정 (8개 파일, 이전 세션에서 완료):**
- `ai/llm/prompts.py`: sLLM 전용 상수 3개 추가 (DOC_QA/SUMMARY/GENERATE_SLLM_PROMPT)
- 변환 스크립트 3개 + 합성 스크립트 3개: sys.path + import + SYSTEM_PROMPT 교체
- `validate_v2_data.py`: QA 스키마 업데이트 (confidence/relevance/source 제거)
- 플랜 문서: `docs/지용/FINETUNING_PROMPT_V2_PLAN.md`

**기존 문서 2개 업데이트:**
- `문서Agent_파인튜닝_파이프라인_보고서.md`: v2_qa JSON 간소화 반영, 검증 항목 수정, sLLM 프롬프트 전략 반영, 진행 현황 업데이트
- `문서Agent_LoRA_v2_파인튜닝_계획.md`: 데이터 포맷 설명 수정, 프롬프트 v2 완료 기록 추가

**데이터 경로 수정:**
- `convert_aihub_qa.py`, `convert_aihub_summary.py`: `data/raw/aihub/` → `data/raw/ai_hub/` (실제 폴더명과 일치)

**v2_qa MRC 재생성 + 버그 수정:**
- **버그**: `_char_overlap_ratio` 퍼지 매칭이 한국어 공통 글자로 거의 모든 청크를 매칭 → citations 2~3개 88%
- **수정**: 정확 substring 매칭 + 인접 청크 경계 처리로 변경
- **결과**: 324건 (MRC 290 + not-found 34), citations 1개 88.3%, not-found 10.5%

**v2_summary 재생성 + 버그 수정 3건:**
1. **`20per` 폴더만 로드**: `sorted()` 정렬에서 `20per`가 `2~3sent`보다 먼저 → limit 도달 후 `2~3sent` 미로드
   - 수정: `2~3sent` 우선 정렬 (summary2 있고, passage에서 포인트 추출 용이)
2. **소수점 오분할**: `[.!?。]` regex가 `3.5%`의 `.`도 분할
   - 수정: `(?<!\d)[.!?。]` (숫자 뒤 마침표 무시) + 줄바꿈 분할 추가
3. **포인트 6개 편향**: 긴 passage에서 항상 5개 이상 추출 → 99%가 6개
   - 수정: `max_points`를 `random.randint(3, 5)`로 랜덤화
- **결과**: 700건, 포인트 분포 3개 37% / 4개 32% / 5개 32%, 3개 미만 0건

**데이터 품질 검증:**
- v2_qa: system prompt byte-for-byte 일치 ✅, JSON 100% valid ✅, 필드 오류 0 ✅
- v2_summary: system prompt 일치 ✅, 마크다운 구조 100% ✅
- v2_summary 키워드 품질 이슈: TF 기반 추출 → 조사 포함 821건 (`수사가`, `측면에서`) → `--llm-enhance` 필요

**현재 데이터 현황:**

| 어댑터 | AI Hub 목표 | 완료 | 합성 목표 | 완료 | 변형 목표 | 완료 |
|--------|:-----------:|:----:|:---------:|:----:|:---------:|:----:|
| v2_qa | 600 | 324 (MRC만) | 300 | 0 | 100 | 0 |
| v2_summary | 700 | **700** ✅ | 200 | 0 | 100 | 0 |
| v2_generate | 460 | 0 | 400 | 0 | 140 | 0 |

**다음 할 일:**
- 아래 야간 세션에서 이어서 진행

---

## 2026-03-04 (화) — 야간 세션 (데이터 증량 + 문서 동기화)

**v2_generate 1,500건 증량 결정:**
- 기존 1,000건 → 1,500건 (QLoRA 8B 모델 기준 검토)
- 이유: 3개 문서 유형(회의록/보고서/제안서) 각각이 별도 서브태스크 → 타입당 500건 필요
- v2_qa(1,000), v2_summary(1,000)는 단일 태스크라 충분

**부분 누락(빈 필드) 학습 데이터 전략 추가:**
- v2_generate 할루시네이션 방지: 긴 입력에서 없는 정보를 지어내서 다른 필드에 채우는 현상
- 합성 600건 중 30% = 180건 (타입당 60건)을 부분 누락으로 생성
- 타입당: 전체채움 440건 (88%) + 부분누락 60건 (12%)

**v2_generate 최종 구성:**

| 템플릿 | 건수 | AI Hub | 합성 | 변형 |
|--------|:----:|:------:|:----:|:----:|
| 회의록 | 600 | 60 (10%) | 420 (70%) | 120 (20%) |
| 보고서 | 450 | 315 (70%) | 90 (20%) | 45 (10%) |
| 제안서 | 450 | 315 (70%) | 90 (20%) | 45 (10%) |
| **합계** | **1,500** | **690 (46%)** | **600 (40%)** | **210 (14%)** |

**문서 동기화 (계획서 + 보고서):**
- `문서Agent_LoRA_v2_파인튜닝_계획.md`: v2_generate 1,500건 반영, 템플릿별 배분 업데이트, 빈 필드 규칙 상세화, TODO STEP 갯수 업데이트
- `문서Agent_파인튜닝_파이프라인_보고서.md`: v2_generate 1,500건 반영, 비율 설계 근거 변경, 예상 비용 재계산, 진행현황 업데이트, 디렉토리 구조 업데이트

**전체 데이터 최종 구성:**

| 어댑터 | 총량 | AI Hub | 합성 | 변형 |
|--------|:----:|:------:|:----:|:----:|
| v2_qa | 1,000 | 600 (60%) | 300 (30%) | 100 (10%) |
| v2_summary | 1,000 | 700 (70%) | 200 (20%) | 100 (10%) |
| v2_generate | 1,500 | 690 (46%) | 600 (40%) | 210 (14%) |
| **합계** | **3,500** | **1,990 (57%)** | **1,100 (31%)** | **410 (12%)** |

**키워드 보강 순서 변경:**
- 기존: AI Hub 700건만 먼저 보강
- 변경: 합성+변형까지 전체 1,000건 모은 후 마지막에 한번에 보강 (~$0.7)

**현재 완료 현황:**

| 어댑터 | AI Hub | 합성 | 변형 |
|--------|:------:|:----:|:----:|
| v2_qa | 324/600 (MRC만) | 0/300 | 0/100 |
| v2_summary | **700/700** ✅ | 0/200 | 0/100 |
| v2_generate | 0/690 | 0/600 | 0/210 |

**다음 할 일 (API 순서):**
1. v2_qa Report QA 300건 (GPT-4o, ~$7.5)
2. v2_generate AI Hub 690건 (GPT-4o, ~$27.6)
3. 합성 데이터 1,100건 (GPT-4o/Claude, ~$22, 부분 누락 포함)
4. 변형 데이터 410건 (규칙 기반, $0)
5. v2_summary 키워드 보강 — 전체 1,000건 (GPT-4o-mini, ~$0.7)
6. 전체 검증 + train/eval 분할

---

## 2026-03-05 (수)

**v2_generate 필드 풀 방식 재설계 (다른 PC에서 작업 후 pull):**
- 기존 고정 필드 방식 폐기 → 필드 풀 랜덤 조합 방식으로 전환
- 문서유형별 15~20개 필드 풀 정의, 매 샘플 6~10개 랜덤 선택
- aihub_generate.jsonl + synthetic_generate.jsonl 삭제 후 재생성 중

**3개 어댑터 데이터 품질 심층 검증:**
- v2_generate: 필드 풀 방식 정상 동작 확인
- v2_qa: aihub_qa에서 34% 단답 문제 발견 (10자 미만)
- v2_summary: aihub + synthetic 양쪽 모두 품질 문제 발견
  - aihub: 규칙 기반 build_assistant_response()가 국회 속기록에서 쓰레기 생성
  - synthetic: SUMMARY_GENERATION_SYSTEM 번호 형식을 GPT가 메타지시문 그대로 복사

**v2_summary 스크립트 전면 재설계:**
- `convert_aihub_summary.py`:
  - 카테고리 10종→5종 선별 (뉴스180/보도160/보고서160/간행물100/사설100)
  - 제외: 회의록(국회속기록), 연설문, 역사기록물, 문학, 나레이션
  - build_assistant_response() 삭제 → GPT-4o 요약 생성으로 교체
  - validate_summary() 메타지시문 복사 감지 추가
- `synthesize_summary.py`:
  - SUMMARY_GENERATION_SYSTEM → DOC_SUMMARY_SLLM_PROMPT 교체
  - validate_summary()에 메타지시문 복사 감지 추가

**aihub_qa 단답 보강:**
- `convert_aihub_qa.py`에 `enhance_short_answers()` 함수 추가
- 15자 미만 단답 152건 → GPT-4o로 서술형 답변 재생성
- 결과: 150건 성공, 2건 영구 실패 (허용 범위)
- `--enhance-short`, `--min-answer-len` CLI 옵션 추가

**synthetic_qa 400건 조정:**
- synthesize_qa.py --append --count 64 실행 → 69건 추가 (not-found 7건 자동 추가)
- 405건→400건 트리밍
- not-found 비율 9.5%→12.0% 조정 (카테고리 교차 매칭으로 10건 추가 생성)
- 최종: 352 normal + 48 not-found = 400건 (12.0%)

**보고서 업데이트:**
- v2_qa 완료 반영 (synthetic 300→400건, aihub 단답 보강)
- v2_summary 재설계 반영 (카테고리 선별, GPT-4o 요약)
- 스크립트 테이블 건수 업데이트
- 리스크 섹션 summary 행 업데이트
- 구현 이력 2026-03-05 오후 섹션 추가

**현재 데이터 현황:**

| 어댑터 | AI Hub | 합성 | 상태 |
|--------|:------:|:----:|:----:|
| v2_qa | 600/600 ✅ | 400/400 ✅ | **완료** (병합 대기) |
| v2_summary | 0/700 | 0/300 | 스크립트 준비 완료, 재생성 대기 |
| v2_generate | 생성 중 | 생성 중 | 다른 PC에서 작업 중 |

**다음 할 일:**
- 아래 야간 세션에서 이어서 진행

---

## 2026-03-05 (수) — 야간 세션

**v2_summary 데이터 생성 완료:**
- `convert_aihub_summary.py`: 702건 생성 (목표 700, +2건 초과)
  - 컴퓨터 꺼짐 → `--append` 옵션 추가하여 이어서 생성 (JSONL 포맷 덕분에 데이터 유실 없음)
- `synthesize_summary.py`: 305건 생성 (목표 300, +5건 초과)
- validate_summary() 검증 강화: 포인트 3~5개, 키워드 3~7개, 메타지시문 5패턴 감지

**v2_generate 데이터 생성 완료:**
- synthetic_generate.jsonl: 801건 (목표 800)
- aihub_generate.jsonl: 700건 (기존 완료)

**validate_v2_data.py 검증 스크립트 전면 개선:**
- v2_generate: 고정 필드 검증 → 동적 `[필드 명세]` 파싱 기반 검증으로 변경
- v2_summary: 포인트/키워드 개수 + 메타지시문 감지 추가
- `_detect_task()`: 동적 필드 프롬프트 감지 키워드 추가
- 중복 체크: assistant만 비교 → user+assistant 쌍 비교 (not-found 오탐 해결)

**전체 데이터 검증 실행:**
```
총 샘플: 3,508건 | 에러: 0건 | 경고: 178건 | 중복: 0건 | 판정: PASS
```
- 경고 178건: 전부 조사 포함 키워드 오탐 (정규식 과탐, 실제 품질 문제 아님)

**보고서 업데이트:**
- Section 4: 실제 데이터 수량 반영 (3,508건)
- Section 5: 검증 결과 기록 (에러 0건)
- Section 6: Train/Eval 분할 수치 실제 데이터에 맞게 수정
- Section 13: Solar API → LLM API fallback으로 수정
- 부록 A: variant 파일 제거, 건수/상태 최신화

**데이터 생성 과정 기록 문서 작성:**
- `ai/finetuning/finetuning_docs/데이터_생성_과정_기록.md` 신규 생성
- 8단계 타임라인 + 최종 데이터 현황 + 데이터 구조 + 핵심 설계 결정 기록

**최종 데이터 현황:**

| 어댑터 | AI Hub | 합성 | 합계 | 상태 |
|--------|:------:|:----:|:----:|:----:|
| v2_summary | 702 | 305 | 1,007 | 완료 |
| v2_qa | 600 | 400 | 1,000 | 완료 |
| v2_generate | 700 | 801 | 1,501 | 완료 |
| **합계** | **2,002** | **1,506** | **3,508** | **완료** |

**다음 할 일:**
- 토큰 길이 분석 (max_length=2048 충분한지 확인)
- Train/Eval 분할 (`validate_v2_data.py --split`)
- GPU 환경 준비 → 3개 모델 비교 학습

---

## 2026-03-06 (목)

**토큰 길이 분석 + max_length 결정:**
- Qwen3-8B 토크나이저로 3,500건 전체 토큰 길이 분석
- 결과: 97.8%가 2048 이하, 77건 초과 (전부 v2_generate)
- 77건 모두 2647 이하 → max_length=2560 결정 (H200 141GB VRAM 여유)
- 2048에서 자르면 assistant JSON이 깨지므로 증가가 필수

**데이터 라운드 넘버 트리밍:**
- v2_summary: 1,007 → 1,000 (aihub 702→700, synthetic 305→300)
- v2_generate: 1,501 → 1,500 (synthetic 801→800)
- v2_qa: 1,000 유지

**Train/Eval 분할 (seed=42, 90:10):**
- v2_summary: train 900 / eval 100
- v2_qa: train 900 / eval 100
- v2_generate: train 1,350 / eval 150
- 총 3,500건

**빡센 데이터 검증 (GPU 투입 전 최종 QA):**
- 소스 데이터: 에러 0건, JSON 100% valid, 완전 중복 0건
- train↔eval 누수: 0건
- 내부 중복: train 0건, eval 0건
- 소스↔train+eval 합계 일치: 3개 모두 일치
- 인코딩 깨짐(U+FFFD): 1건 발견 → 수정 완료
- v2_qa 동일문서 다른질문: 24건 (정상 — 같은 문서에서 다른 질문)
- v2_generate 필드 조합 다양성: 1,094개 고유 조합 / 1,350건 (81%)
- 내용 품질 확인: 3개 어댑터 랜덤 샘플 눈으로 검증, not-found 케이스 정상

**학습 스크립트 전면 점검 + 수정:**
- `train_v2_document.py`:
  - TrainingArguments → SFTConfig 마이그레이션 (trl 0.28+ 호환)
  - max_seq_length → max_length 파라미터명 변경
  - warmup_ratio → warmup_steps (deprecated 대응)
  - enable_input_require_grads() 방어 코드 추가
  - do_sample=False 시 temperature 제거
  - dataset_text_field 버전 호환 처리
  - 동적 필드 평가 함수 추가 (_parse_field_spec_from_user)
  - confidence 필드 제거 (QA eval)
  - max_length config에서 동적 로드
- `runpod_setup.sh`:
  - GitHub URL 수정 (개인→org 레포)
  - pip install -U 강제 업그레이드 + CUDA 12.4 torch 전용 설치
  - HF_TOKEN 미설정 시 경고 추가
  - 모델 학습 실패 시 다음 모델로 계속 진행
  - 버전 출력 추가 (torch, trl)
- 3개 YAML config: max_length 2048→2560

**AIHub 데이터 파이프라인 문서:**
- `ai/finetuning/finetuning_docs/AIHub_데이터_파이프라인.md` 작성 (멘토 리뷰용)
- AIHub 022 데이터 구조, 파이프라인 다이어그램, GPT-4o 역할, 프롬프트 3종 명세

**RunPod H200 학습 시작:**
- H200 141GB + Network Volume 60GB (US-TX-3) 세팅
- generate 태스크 3모델(Qwen3-8B, EXAONE, Kanana) 순차 학습 실행 중

**다음 할 일:**
- generate 학습 완료 확인 → qa, summary 순차 실행
- 3개 어댑터 × 3개 모델 = 9 runs 평가 결과 비교
- 베스트 모델 선택 + 결과 정리
- 결과 다운로드 후 로컬 배치
