# 문서 Agent LoRA v2 파인튜닝 계획

> 최종 수정: 2026-03-04
> 담당: 신지용 (PM, 승언 업무 인수, 데이터 수집 단독 진행)

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
| **doc_qa** | O | **P1** | 일반 업무 문서(회의록/보고서/기획서) 기반 QA. 인용 정확도 중요. 규정 QA는 v1_judgment |
| **doc_summary** | O | P2 | 마크다운 출력. 수집 확정 |
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

VRAM 예상: Kanana ~5GB + Qwen3 ~5GB + LoRA 어댑터 + KV Cache = ~25GB → RTX 5090 32GB 가능

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

→ 3개 모델 동일 eval 셋으로 비교 후 **1개 모델로 통일** (v2_generate/v2_qa/v2_summary 동일 베이스)

---

## 5. 학습 데이터 설계

### v2_generate (P0) — 총 1,500개

| 템플릿 | 수량 | AI Hub | 합성 | 변형 | 비고 |
|--------|:----:|:------:|:----:|:----:|------|
| 회의록 | 600개 | 60개 (10%) | 420개 (70%) | 120개 (20%) | **합성 중심** (기업 회의록 공개 데이터 없음) |
| 보고서 | 450개 | 315개 (70%) | 90개 (20%) | 45개 (10%) | AI Hub 보고서/간행물 원문 활용 |
| 제안서 | 450개 | 315개 (70%) | 90개 (20%) | 45개 (10%) | AI Hub 보도자료/간행물 원문 활용 |

빈 필드 규칙: 합성 데이터의 ~30% (타입당 60건, 전체 180건)를 부분 누락으로 생성 — 할루시네이션 방지 (긴 입력에서 없는 정보를 지어내서 다른 필드에 채우는 현상 방지)

> **meeting_minutes 합성 중심 이유**: AI Hub 회의록 = 국회 속기록(발언자 대화 형식)으로
> 기업 회의록과 도메인/스타일이 다름. 공개 기업 회의록 데이터셋이 존재하지 않아
> GPT-4o/Claude로 기업 도메인(마케팅, 개발, 인사, 예산 회의 등) 직접 생성.
> AI Hub 국회회의록은 40개만 다양성 확보용으로 소량 활용.
> 회의록이 사용 빈도 최고이므로 400개로 가장 많이 배분.

소스 비율 (전체):

| 소스 | 비율 | 개수 | 역할 |
|------|:----:|:----:|------|
| AI Hub 원문 + GPT-4o 변환 | 46% | 690개 | report 315 + proposal 315 + meeting 60 |
| GPT-4o/Claude 합성 | 40% | 600개 | meeting 420 + report 90 + proposal 90 (부분 누락 180건 포함) |
| 변형(구어체/오타) | 14% | 210개 | meeting 120 + report 45 + proposal 45 |

### v2_qa (P1) — 총 1,000개

> **중요**: 일반 업무 문서(회의록/보고서/기획서) 기반 QA. 규정 QA는 v1_judgment가 담당.
> context는 프로덕션 동일하게 RAG 검색 결과 3~5개 청크를 JSON 배열로 제공.

| 소스 | 비율 | 개수 | 역할 |
|------|:----:|:----:|------|
| 행정 문서 기계독해 MRC 변환 (SN 569) | 30% | 300개 | MRC → DOC_QA 형식 변환 (비용 $0) |
| 요약문 레포트 기반 QA 생성 (SN 582) | 30% | 300개 | passage → GPT-4o로 QA쌍 생성 |
| GPT-4o/Claude 합성 | 30% | 300개 | 기업 업무 문서 context + Q&A 쌍 |
| 변형 | 10% | 100개 | 구어체 질문, 답 없는 경우, 모호한 질문 |

### v2_summary (P2) — 총 1,000개

| 소스 | 비율 | 개수 | 역할 |
|------|:----:|:----:|------|
| AI Hub 문서요약 변환 (SN 582) | 70% | 700개 | 10개 카테고리에서 고품질 선별 |
| GPT-4o/Claude 합성 | 20% | 200개 | 추상형 마크다운 모범답안 + 문체 다양성 |
| 변형 | 10% | 100개 | 짧은/긴 문서, 표 많은 문서 등 엣지케이스 |

> summary2(추출형 요약)를 seed로 활용하되, GPT-4o mini로 마크다운 구조(핵심요약 + 주요포인트 + 키워드)로 변환
> AI Hub 80%→70%로 낮춘 이유: summary2가 추출형이라 비율이 너무 높으면 모델이 추출형 습관을 학습할 위험. 합성 20%로 추상형 모범답안 확보

### 전체 총량

| 어댑터 | 데이터 | AI Hub | 합성 | 변형 | 예상 비용 |
|--------|:------:|:------:|:----:|:----:|:---------:|
| v2_generate | **1,500개** | 690 (46%) | 600 (40%) | 210 (14%) | ~$27 + $12 |
| v2_qa | **1,000개** | 600 (60%) | 300 (30%) | 100 (10%) | ~$7.5 + $6 |
| v2_summary | **1,000개** | 700 (70%) | 200 (20%) | 100 (10%) | ~$0.7 + $4 |
| **합계** | **3,500개** | **1,990 (57%)** | **1,100 (31%)** | **410 (12%)** | **~$57.2** |

> 비용 = AI Hub 변환 + 합성 데이터 생성. 변형 데이터는 규칙 기반($0).

### 데이터 포맷 (JSONL, SFTTrainer messages 형식)

```jsonl
{"messages": [
  {"role": "system", "content": "태스크별 시스템 프롬프트"},
  {"role": "user", "content": "사용자 입력"},
  {"role": "assistant", "content": "모델이 학습할 출력 (JSON 또는 마크다운)"}
]}
```

- doc_generate → assistant가 **순수 JSON** 출력 (영문 필드명 필수)
- doc_qa → assistant가 **JSON** 출력 (answer + citations[].content만 — confidence/source/relevance는 백엔드가 RAG score 기반 계산)
- doc_summary → assistant가 **마크다운** 출력 (요약 + 주요포인트 + 키워드)

샘플 데이터: `data/training/v2_*/sample_*.jsonl` 참고

### AI Hub 데이터셋 (확정)

| 데이터셋 | URL | 용량 | 용도 | 저장 경로 |
|----------|-----|:----:|------|-----------|
| 요약문 및 레포트 생성 데이터 (SN 582) | https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=582 | 495MB | v2_summary + v2_generate + v2_qa | `data/raw/aihub/summary_report/` |
| 행정 문서 대상 기계독해 (SN 569) | https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=569 | 271MB | v2_qa (MRC 180개) | `data/raw/aihub/admin_mrc/` |

> 원본 데이터는 `data/raw/` 에 저장 (.gitignore 등록됨, 대용량)

**SN 582 구조** (중첩 JSON, 파일 1건 = passage 1건):
```
{
  "Meta(Acqusition)": {"doc_type": "보고서", ...},
  "Meta(Refine)": {"passage": "원문 텍스트", ...},
  "Annotation": {
    "summary1": "한 줄 생성요약",
    "summary2": "2-3문장 추출요약"  // 2~3sent 폴더
    // 또는 "summary3": "20% 추출요약"  // 20per 폴더
  }
}
```

카테고리별 학습용 건수: 회의록 27,200 / 보고서 8,000 / 간행물 8,000 / 뉴스 21,600 / 보도자료 16,000 / 사설 8,000

### 합성 데이터 생성 프롬프트

별도 작성 예정. `ai/finetuning/finetuning_docs/` 디렉토리에 프롬프트 파일 추가할 것.

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
| batch_size | 4 | 동일 | RTX 5090 32GB 기준 |
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

### 완료 (2026-03-04)

| 작업 | 파일 | 상태 |
|------|------|:----:|
| AI Hub 데이터 다운로드 (SN 582 + SN 569) | `data/raw/aihub/` | ✅ |
| AI Hub 데이터 탐색/분석 스크립트 | `ai/finetuning/scripts/aihub_explore.py` | ✅ |
| v2_summary 변환 스크립트 | `ai/finetuning/scripts/convert_aihub_summary.py` | ✅ |
| v2_generate 변환 스크립트 | `ai/finetuning/scripts/convert_aihub_generate.py` | ✅ |
| v2_qa 변환 스크립트 | `ai/finetuning/scripts/convert_aihub_qa.py` | ✅ |
| .gitignore에 data/raw/ 추가 | `.gitignore` | ✅ |
| FORMAT_GUIDE.md 업데이트 | `data/training/v2_document/FORMAT_GUIDE.md` | ✅ |
| v2_generate/qa/summary config 수량 업데이트 | `ai/finetuning/configs/v2_*.yaml` | ✅ |

### 완료 (2026-03-04 추가 — 프롬프트 v2)

| 작업 | 파일 | 상태 |
|------|------|:----:|
| sLLM 전용 프롬프트 상수 3개 추가 | `ai/llm/prompts.py` | ✅ |
| v2_qa JSON 간소화 + 퍼지 매칭 + not-found | `ai/finetuning/scripts/convert_aihub_qa.py` | ✅ |
| v2_generate SYSTEM_PROMPT 교체 | `ai/finetuning/scripts/convert_to_dynamic_fields.py` | ✅ |
| v2_summary SYSTEM_PROMPT 교체 + 포인트 필터 | `ai/finetuning/scripts/convert_aihub_summary.py` | ✅ |
| 합성 스크립트 3개 SYSTEM_PROMPT 교체 | `synthesize_qa/generate/summary.py` | ✅ |
| validate_v2_data.py 스키마 업데이트 | `ai/finetuning/validate_v2_data.py` | ✅ |
| 프롬프트 v2 플랜 문서화 | `docs/지용/FINETUNING_PROMPT_V2_PLAN.md` | ✅ |

> 상세 내용: `docs/지용/FINETUNING_PROMPT_V2_PLAN.md` 참고

### TODO: 데이터 수집 (PM 단독 진행)

| 단계 | 작업 |
|------|------|
| STEP 1 | ~~AI Hub 데이터 다운로드~~ → 완료 (SN 582 + SN 569) |
| STEP 2 | 변환 스크립트 실행: summary 700 → generate 690 → qa 600 |
| STEP 3 | meeting_minutes 합성 데이터 420개 생성 (GPT-4o/Claude) |
| STEP 4 | 나머지 합성 데이터 생성 (report 90 + proposal 90 + qa 300 + summary 200, 부분 누락 180건 포함) |
| STEP 5 | 변형 데이터 생성 (구어체/오타) 410개 |
| STEP 6 | 3단계 품질 검증: 자동검증 → LLM 교차검증 → 수동 샘플링(150개) |
| STEP 7 | train/eval 분할 (generate/qa 10%, summary 15%) |

### TODO: 학습 + 평가

| 단계 | 작업 |
|------|------|
| STEP 8 | RunPod RTX 5090에서 3개 모델 비교 학습 (v2_generate 기준) |
| STEP 9 | 평가 결과 비교 → **1개 모델로 통일** 선정 |
| STEP 10 | 선정 모델로 v2_qa, v2_summary 추가 학습 |
| STEP 11 | vLLM 서버 배포 + Agent 연동 |
| STEP 12 | E2E 테스트 |

---

## 9. 리스크 및 대응

| 리스크 | 대응 |
|--------|------|
| 제안서(15+필드) JSON 깨짐 | 10개 샘플 선행 테스트. 실패 10%+ 시 rank→48 또는 EXAONE 전환 |
| AI Hub 데이터 도메인 불일치 (국회 회의록 등) | meeting_minutes는 합성 중심으로 전환 완료. report/proposal은 적합 확인 |
| Solar API보다 성능 하락 | Solar API를 fallback으로 유지. 설정 플래그로 전환 |
| RTX 5090 32GB VRAM 부족 | batch_size 2로 축소 + grad_accum 8로 조정. 또는 A100 전환 |
| 합성 데이터 품질 부족 | 3단계 검증: 자동검증 → LLM 교차검증 → 수동 샘플링(150개) |
| AI Hub summary2가 추출형 | GPT-4o mini로 마크다운 구조 변환 + 합성 20%로 추상형 모범답안 확보 |
| v2_summary max_length vs 프로덕션 gap | 학습 2048토큰 vs 프로덕션 8000글자. 추후 max_length 조정 검토 |
