# 문서 Agent LoRA v2 파인튜닝 계획

> 최종 수정: 2026-03-03
> 담당: 신지용 (PM, 승언 업무 인수)

---

## 1. 목표

현재 문서 Agent는 LLM API(Solar → LLM Factory로 리팩토링 완료)로 4가지 기능을 수행 중.
sLLM + LoRA로 전환하여 **비용 절감 + 자체 모델 확보**.

- LoRA v1(판단 Agent, Kanana-1.5-8B) → 이미 완료
- **LoRA v2(문서 Agent) → 이번 작업**

---

## 2. 핵심 결정사항

### 어댑터 분리 전략 (통합 X → 기능별 분리 O)

**기능별로 별도 LoRA 어댑터로 학습한다.**

이유:
- doc_generate(JSON 출력)와 doc_summary(마크다운 출력)의 포맷이 완전히 다름
- 통합 학습 시 JSON 정확도가 마크다운 학습에 의해 저하될 위험
- doc_generate의 핵심 목적이 **정확한 필드명 출력**인데, 다른 태스크가 이를 방해하면 파인튜닝 의미 없음
- 분리하면 태스크별 독립 최적화 + 개별 디버깅 가능

### 문서 템플릿 3종 (JD 제외)

| 템플릿 | DOCX 생성 코드 | 필드 수 |
|--------|---------------|:-------:|
| 회의록 (meeting_minutes) | `create_meeting_minutes.py` | 7개 |
| 보고서 (report) | `create_report.py` | 12개 |
| 제안서 (proposal) | `create_proposal.py` | 15+개 |

JD는 현재 불필요하여 제외.

### 파인튜닝 대상 기능

| 기능 | 파인튜닝? | 우선순위 | 이유 |
|------|:---------:|:--------:|------|
| **doc_generate** | O | **P0** | JSON 스키마 준수가 핵심. 필드명 정규화 코드 200줄+ 제거 가능 |
| **doc_qa** | O | **P1** | 인용(citation) 정확도 중요. JSON 출력 |
| **doc_summary** | △ | P2 | 마크다운 출력, 프롬프트로 충분할 수 있음. 여유 있으면 진행 |
| **doc_search** | X | - | LLM 역할은 검색 결과 종합뿐. RAG 품질이 핵심 |

---

## 3. 어댑터 구성

### 전체 모델 구조

| # | 어댑터 | 베이스 모델 | 용도 | 상태 |
|---|--------|-----------|------|:----:|
| 1 | `v1_judgment` | Kanana-1.5-8B | 규정 판단 | 완료 |
| 2 | `v2_generate` | Qwen3-8B (예정) | 문서 생성 | **P0** |
| 3 | `v2_qa` | Qwen3-8B (예정) | 문서 QA | **P1** |
| 4 | `v2_summary` | Qwen3-8B (예정) | 문서 요약 | P2 |

### vLLM 서버 구성

```
서버1 (Kanana-1.5-8B, port 8000) → v1_judgment 어댑터
서버2 (Qwen3-8B, port 8001)      → v2_generate / v2_qa / v2_summary 어댑터 스위칭
```

VRAM 예상: Kanana ~5GB + Qwen3 ~5GB + LoRA 어댑터 + KV Cache = ~30GB → A100 40GB 가능

---

## 4. 베이스 모델 선정

### 1차 추천: Qwen3-8B

선정 근거:
1. 이전 세대 Qwen2.5-14B(2배 크기)와 동등한 성능 → 8B로 14B급 효율
2. 코드/JSON 생성에 특화된 학습 → 구조화 출력 강점
3. Thinking Mode로 복잡한 문서 추론 가능
4. 118+ 언어 지원 (한영 혼용 대응)
5. HuggingFace 8B 모델 중 최고 인기, QLoRA/vLLM/PEFT 호환 검증 완료

### 비교 테스트 (3개 모델)

| 모델 | 강점 | 약점 |
|------|------|------|
| **Qwen3-8B** | JSON/코드 생성, 세대 도약 | 한국어 특화는 아님 |
| EXAONE-3.5-7.8B | 한국어 대화 최강 (KoMT 7.96) | 상업적 제약, JSON 약할 수 있음 |
| Kanana-1.5-8B | 한국어 자연스러움, IFEval 80.11 | MT-Bench 낮음, 코드 학습 약함 |

→ 3개 모델 동일 eval 셋으로 테스트 후 최종 선정

---

## 5. 학습 데이터 설계

### v2_generate (P0) — 총 380개

| 템플릿 | 수량 | 비고 |
|--------|:----:|------|
| 회의록 | 150개 | 사용 빈도 최고, 7필드 JSON |
| 보고서 | 130개 | 12필드, tasks 배열 구조 |
| 제안서 | 100개 | 15+필드로 가장 복잡 |

소스 비율:

| 소스 | 비율 | 개수 | 역할 |
|------|:----:|:----:|------|
| AI Hub 실제 데이터 | 40% | ~150개 | 실제 한국어 문서 패턴 |
| GPT-4o 합성 | 30% | ~115개 | 정확한 JSON 스키마 학습 |
| Claude 합성 | 15% | ~55개 | 문체 다양성 + 교차 검증 |
| 변형(구어체/오타) | 15% | ~60개 | 실사용 환경 대응력 |

### v2_qa (P1) — 총 300개

| 소스 | 비율 | 개수 | 역할 |
|------|:----:|:----:|------|
| AI Hub 기계독해 | 50% | 150개 | context→question→answer 실제 패턴 |
| GPT-4o 합성 | 25% | 75개 | citation 포맷 학습 |
| Claude 합성 | 15% | 45개 | 교차 검증 |
| 변형 | 10% | 30개 | 애매한 질문, 답 없는 경우 |

### v2_summary (P2) — 총 200개 (또는 안 함)

| 소스 | 비율 | 개수 | 역할 |
|------|:----:|:----:|------|
| AI Hub 문서요약 | 50% | 100개 | 원문→요약 실제 쌍 |
| GPT-4o 합성 | 25% | 50개 | 마크다운 포맷 학습 |
| Claude 합성 | 15% | 30개 | 문체 다양성 |
| 변형 | 10% | 20개 | 짧은/긴 문서 대응 |

### 전체 총량

| 어댑터 | 데이터 | AI Hub | 합성 | 변형 |
|--------|:------:|:------:|:----:|:----:|
| v2_generate | **380개** | 150 (40%) | 170 (45%) | 60 (15%) |
| v2_qa | **300개** | 150 (50%) | 120 (40%) | 30 (10%) |
| v2_summary | **200개** | 100 (50%) | 80 (40%) | 20 (10%) |
| **합계** | **880개** | **400** | **370** | **110** |

### 데이터 포맷 (JSONL, SFTTrainer messages 형식)

```jsonl
{"messages": [
  {"role": "system", "content": "태스크별 시스템 프롬프트"},
  {"role": "user", "content": "사용자 입력"},
  {"role": "assistant", "content": "모델이 학습할 출력 (JSON 또는 마크다운)"}
]}
```

- doc_generate → assistant가 **순수 JSON** 출력 (영문 필드명 필수)
- doc_qa → assistant가 **JSON** 출력 (answer + citations + confidence)
- doc_summary → assistant가 **마크다운** 출력 (요약 + 주요포인트 + 키워드)

샘플 데이터: `data/training/v2_document/sample_*.jsonl` 참고

### AI Hub 데이터셋 후보

직접 검색하여 우리 포맷에 맞는지 확인 필요:
- 회의록 관련: "국회 회의록", "회의 기록" 키워드 검색
- 보고서/제안서: "레포트 생성", "요약문" 키워드 검색
- QA: "기계독해", "행정문서" 키워드 검색
- 요약: "문서요약", "대화요약" 키워드 검색

> AI Hub 데이터는 우리 JSON 스키마와 직접 매칭되지 않으므로 변환 스크립트 필요

---

## 6. LoRA 하이퍼파라미터

### v2_generate / v2_qa 공통

| 파라미터 | 값 | v1 대비 | 이유 |
|----------|:--:|:-------:|------|
| r (rank) | 32 | 16→32 | 복잡한 JSON 스키마 표현력 |
| lora_alpha | 64 | 32→64 | alpha/r = 2.0 유지 |
| lora_dropout | 0.05 | 동일 | |
| target_modules | q,v,k,o,gate,up_proj | +gate,up | Qwen3 아키텍처, MLP 중요 |
| num_epochs | 5 | 3→5 | early stopping 적용 |
| learning_rate | 1e-4 | 2e-4→1e-4 | rank 증가에 따른 안정화 |
| max_length | 2048 | 동일 | 제안서 JSON도 ~1500토큰 |
| batch_size | 4 | 동일 | A100 40GB 기준 |
| grad_accum | 4 | 동일 | effective batch = 16 |

### v2_summary (수행 시)

- rank 16으로 축소 가능 (단순 태스크)
- 나머지 동일

---

## 7. 평가 기준

| 어댑터 | 메트릭 | 목표 |
|--------|--------|:----:|
| **v2_generate** | JSON 유효율 | >98% |
| | 필드 완전성 (필수 필드 존재) | >95% |
| | 필드명 정확도 (정규화 불필요) | >99% |
| **v2_qa** | Token F1 | >0.80 |
| | 인용 정확도 (context에 존재) | >90% |
| **v2_summary** | ROUGE-L | >0.45 |
| | 포맷 준수율 | >95% |

**베이스라인**: Solar API / GPT-4o / base 모델(LoRA 없음)과 비교
**최소 조건**: Solar API 이상이어야 배포 가치 있음

---

## 8. 구현 현황

### 완료 (2026-03-03)

| 작업 | 파일 | 상태 |
|------|------|:----:|
| `_call_llm()` Solar→LLM Factory 리팩토링 | `document_agent.py`, `schedule_agent.py` | ✅ |
| BaseLLM에 json_mode 파라미터 추가 | `base.py`, `openai_provider.py`, `anthropic_provider.py` | ✅ |
| v2_document.yaml 하이퍼파라미터 설정 | `ai/finetuning/configs/v2_document.yaml` | ✅ |
| train_v2_document.py 학습 스크립트 | `ai/finetuning/train_v2_document.py` | ✅ |
| evaluate.py 평가 함수 6개 구현 | `ai/finetuning/evaluate.py` | ✅ |
| validate_v2_data.py 검증 스크립트 | `ai/finetuning/validate_v2_data.py` | ✅ |
| 샘플 데이터 7개 | `data/training/v2_document/sample_*.jsonl` | ✅ |

### 완료 (2026-03-03 추가)

| 작업 | 파일 | 상태 |
|------|------|:----:|
| `v2_generate.yaml` config | `ai/finetuning/configs/v2_generate.yaml` | ✅ |
| `v2_qa.yaml` config | `ai/finetuning/configs/v2_qa.yaml` | ✅ |
| `v2_summary.yaml` config (r=16) | `ai/finetuning/configs/v2_summary.yaml` | ✅ |
| 데이터 디렉토리 분리 | `data/training/v2_generate/`, `v2_qa/`, `v2_summary/` | ✅ |
| 학습 스크립트 `--task` 지원 | `ai/finetuning/train_v2_document.py` | ✅ |
| FORMAT_GUIDE.md 업데이트 | `data/training/v2_document/FORMAT_GUIDE.md` | ✅ |
| JD 템플릿 제거 | REQUIRED_FIELDS, configs, FORMAT_GUIDE | ✅ |

### TODO: 데이터 수집

| 단계 | 작업 |
|------|------|
| STEP 1 | AI Hub 데이터 검색 + 다운로드 |
| STEP 2 | 변환 스크립트 작성 (AI Hub → messages JSONL) |
| STEP 3 | GPT-4o/Claude 합성 데이터 생성 |
| STEP 4 | 변형 데이터 생성 (구어체/오타) |
| STEP 5 | 검증 + train/eval 분할 |

### TODO: 학습 + 평가

| 단계 | 작업 |
|------|------|
| STEP 6 | RunPod A100에서 3개 모델 비교 학습 |
| STEP 7 | 평가 결과 비교 → 최종 모델 선정 |
| STEP 8 | vLLM 서버 배포 + Agent 연동 |
| STEP 9 | E2E 테스트 |

---

## 9. 리스크 및 대응

| 리스크 | 대응 |
|--------|------|
| 제안서(15+필드) JSON 깨짐 | 10개 샘플 선행 테스트. 실패 10%+ 시 rank→48 또는 EXAONE 전환 |
| AI Hub 데이터가 우리 포맷에 안 맞음 | 합성 데이터 비율 늘려서 보완 |
| Solar API보다 성능 하락 | Solar API를 fallback으로 유지. 설정 플래그로 전환 |
| doc_summary 200개로 부족 | 프롬프트만으로 충분하면 파인튜닝 생략 |
| 합성 데이터 품질 부족 | GPT 생성 → Claude 교차 검증, 자동 검증 파이프라인 |
