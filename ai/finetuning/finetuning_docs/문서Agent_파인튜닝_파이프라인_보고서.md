# 문서 Agent LoRA v2 파인튜닝 파이프라인 보고서

## 1. 개요

### 1.1 목적
문서 Agent의 3가지 핵심 기능(요약, QA, 문서생성)을 sLLM으로 전환하기 위한 LoRA 파인튜닝 파이프라인.
LLM API(GPT/Claude) 기반으로 구현된 기능을 **Qwen3-8B + QLoRA 어댑터**로 교체하여 비용 절감 및 자체 서빙 실현.

### 1.2 어댑터 구성

| 어댑터 | 기능 | 입력 | 출력 |
|--------|------|------|------|
| **v2_summary** | 문서 요약 | 원문 텍스트 | 마크다운 (핵심요약 + 주요포인트 + 키워드) |
| **v2_qa** | 문서 QA | Context 청크 + Question | JSON (answer + citations) |
| **v2_generate** | 문서 생성 | 필드 명세 + 자연어 지시 | JSON (동적 필드 명세 기반, 양식 확장 가능) |

### 1.3 기술 스택

| 항목 | 선택 |
|------|------|
| 베이스 모델 | Qwen/Qwen3-8B |
| 비교 모델 | EXAONE-3.5-7.8B, Kanana-1.5-8B |
| 양자화 | QLoRA 4-bit (bitsandbytes) |
| 학습 프레임워크 | HuggingFace TRL SFTTrainer |
| GPU | NVIDIA RTX 5090 (32GB VRAM) |
| 서빙 | vLLM + LoRA 어댑터 핫스왑 |

---

## 2. 데이터 수집

### 2.1 데이터 소스

#### AI Hub 공공 데이터셋

| 데이터셋 | ID | 규모 | 용도 |
|----------|:--:|-----:|------|
| 요약문 및 레포트 생성 데이터 | SN 582 | 201,671건 | v2_summary, v2_generate, v2_qa 공통 |
| 행정 문서 대상 기계독해 | SN 569 | 155,000+ QA쌍 | v2_qa MRC 변환 |

#### SN 582 카테고리별 데이터 현황

| 카테고리 | 학습 건수 | 문서 특성 |
|----------|----------:|-----------|
| 회의록 (minute) | 27,200 | 국회 속기록 (발언자별 대화체) |
| 연설문 (speech) | 32,000 | 공식 연설, 축사, 기념사 |
| 뉴스 (news_r) | 21,600 | 경제/사회/정치 뉴스 기사 |
| 보도자료 (briefing) | 16,000 | 정부/기관 보도자료 |
| 보고서 (paper) | 8,000 | 정책/연구 보고서 |
| 간행물 (public) | 8,000 | 정기 간행물, 백서 |
| 사설 (edit) | 8,000 | 신문 사설, 칼럼 |
| 역사기록물 (his_cul) | 8,000 | 역사 문서, 문화재 기록 |
| 나레이션 (narration) | 8,371 | 다큐멘터리 나레이션 |
| 문학 (literature) | 9,600 | 소설, 수필 |

#### SN 569 MRC 데이터 현황

| 유형 | 건수 | 설명 |
|------|-----:|------|
| span_extraction | 108,684 QA | 정답 경계 추출형 (qa_type=1) |
| span_extraction_how | 46,518 QA | 절차형 (qa_type=2) |
| 기타 (미사용) | ~100,000+ | multiple_choice, tableqa, text_entailment, unanswerable |

### 2.2 데이터 구조

#### SN 582 (개별 JSON 파일, 파일 1건 = 문서 1건)
```json
{
  "Meta(Acqusition)": {
    "doc_type": "minute",
    "doc_source_type": "국회회의록시스템"
  },
  "Meta(Refine)": {
    "passage": "원문 텍스트 (300~3000자)"
  },
  "Annotation": {
    "summary1": "1문장 생성요약",
    "summary2": "2~3문장 추출요약",
    "summary3": "20% 추출요약"
  }
}
```

#### SN 569 (대용량 JSON 1건, SQuAD 형식)
```json
{
  "data": [
    {
      "doc_title": "문서 제목",
      "paragraphs": [
        {
          "context": "지문 텍스트 (150~800자)",
          "qas": [
            {
              "question": "질문",
              "answers": {"text": "답변", "answer_start": 210},
              "qa_type": 1
            }
          ]
        }
      ]
    }
  ]
}
```

---

## 3. 데이터 변환

### 3.1 학습 데이터 형식 (SFTTrainer messages)

모든 어댑터 공통으로 아래 JSONL 형식 사용:

```json
{
  "messages": [
    {"role": "system", "content": "프로덕션 시스템 프롬프트 (100% 일치)"},
    {"role": "user", "content": "사용자 입력"},
    {"role": "assistant", "content": "모델 출력 (학습 타겟)"}
  ]
}
```

> **핵심 원칙**: v2_summary/v2_qa는 프로덕션 `document_agent.py`의 프롬프트와 100% 동일, v2_generate는 **동적 필드 명세 방식**으로 범용 system prompt + 필드 명세를 user prompt에 포함하여 새로운 문서 양식에도 대응 가능.

### 3.2 어댑터별 변환 전략

#### v2_summary (문서 요약)

| 항목 | 내용 |
|------|------|
| 소스 | SN 582 선별 카테고리 (5종: 뉴스, 보도자료, 보고서, 간행물, 사설) |
| 변환 방식 | AI Hub passage → GPT-4o 요약 생성 (DOC_SUMMARY_SLLM_PROMPT) |
| 원문 필터 | 300~3,000자 |
| 비용 | ~$7 (GPT-4o 700건) |

> **카테고리 선별 이유**: 회의록(국회 속기록), 연설문, 역사기록물, 문학, 나레이션은 기업 문서 도메인과 부적합하여 제외. 정보 밀도가 높고 구조화된 텍스트만 선별.

**변환 로직:**
```
AI Hub 원본                    →  학습 데이터
─────────────────────────────────────────────
passage (원문)                 →  user: "다음 문서를 요약해주세요.\n\n사용자 요청: {랜덤}\n\n문서 내용:\n{passage}"
GPT-4o 요약 생성               →  assistant: 핵심 요약 + ## 주요 포인트 + ## 키워드
```

**assistant 출력 형식 (마크다운):**
```markdown
핵심 요약 2~3문장

## 주요 포인트
- 포인트 1
- 포인트 2
- 포인트 3

## 키워드
키워드1, 키워드2, 키워드3, 키워드4, 키워드5
```

**카테고리별 배분 (700건):**

| 카테고리 | 건수 | 비율 | 선별 이유 |
|----------|:----:|:----:|-----------|
| 뉴스 | 180 | 25.7% | 육하원칙 구조, 핵심→세부 전개 |
| 보도자료 | 160 | 22.9% | 팩트 중심, 정보 밀도 높음 |
| 보고서 | 160 | 22.9% | 실적/현황/이슈 구조, 기업 문서와 유사 |
| 간행물 | 100 | 14.3% | 분석/데이터 중심, 긴 문서 요약 |
| 사설 | 100 | 14.3% | 주장+논거 구조, 논점 파악 |

---

#### v2_qa (문서 QA)

| 항목 | 내용 |
|------|------|
| 소스 1 | SN 569 기계독해 → MRC 형식 변환 (300건) |
| 소스 2 | SN 582 원문 → GPT-4o QA쌍 생성 (300건) |
| 변환 방식 | 소스1: 규칙 변환 / 소스2: GPT-4o 반자동 |
| 비용 | ~$7.5 (소스2만) |

**소스 1: MRC → DOC_QA 변환 (API 불필요)**
```
SN 569 MRC                     →  학습 데이터
─────────────────────────────────────────────
context (지문)                 →  Context: ["청크1", "청크2", ...] (250자씩 분할)
question                       →  Question: {question}
answers.text                   →  {"answer": "...", "citations": [{"content": "..."}]}
```

- span_extraction (추출형) 60% + span_extraction_how (절차형) 40% 비율 혼합
- context 150~800자, answer 5자 이상 필터링
- **단답 보강 (2026-03-05)**: 15자 미만 단답(152건, 34%)을 GPT-4o로 서술형 답변으로 재생성 (150건 성공)

**소스 2: SN 582 → GPT-4o QA 생성**
```
SN 582 passage                 →  GPT-4o가 질문+답변 쌍 생성
─────────────────────────────────────────────
passage (원문)                 →  Context 청크 분할
GPT-4o 생성 question           →  Question
GPT-4o 생성 answer + citation  →  {"answer": "...", "citations": [{"content": "..."}]}
```

- 보고서, 회의록, 간행물, 보도자료, 뉴스 카테고리 혼합
- 500~1,500자 원문 필터링

**assistant 출력 형식 (JSON):**
```json
{
  "answer": "질문에 대한 답변",
  "citations": [
    {"content": "답변의 근거가 되는 원문 인용"}
  ]
}
```

> **v2 변경 (2026-03-04)**: `source`, `relevance`, `confidence` 필드를 sLLM 학습 데이터에서 제거.
> 이 필드들은 sLLM 서빙 시 백엔드가 RAG score 기반으로 계산하여 채움.
> - `confidence`: `avg(search_scores) * 0.7 + min(citation_count/3, 1.0) * 0.3`, not-found 시 0.1 고정
> - `relevance`: citation과 RAG 청크의 reranker score로 산출
> - `source`: RAG 청크 메타데이터에서 문서명 추출

**not-found 예시 (10~15%)**:
- 카테고리 교차 매칭 (경제 문서 context + 교육 질문 등)으로 자연스러운 불일치 생성
- `{"answer": "제공된 문서에서 해당 내용을 찾을 수 없습니다.", "citations": []}`
- 감지 방식: `citations == []` (문구 매칭보다 안정적)

---

#### v2_generate (문서 생성) — 동적 필드 풀 방식

| 항목 | 내용 |
|------|------|
| 소스 | SN 582 passage + 합성 시나리오 → GPT-4o가 JSON 문서 생성 |
| 변환 방식 | 반자동 (원문 + **필드 풀 랜덤 조합** + GPT-4o JSON 생성) |
| 비용 | ~$37.5 |

**핵심 설계: 동적 필드 풀 + 랜덤 조합**

기존 고정 필드 방식의 문제: sLLM이 "회의록 = 이 7개 필드"로 외워버려, 사용자가 다른 필드 조합의 커스텀 템플릿을 올리면 대응 불가.

**해결**: 문서유형별 **필드 풀**(15~20개)을 정의하고, 매 학습 샘플마다 풀에서 **랜덤 조합**을 선택. sLLM이 특정 필드 조합을 외울 수 없고, "필드 명세를 읽고 따르는 능력" 자체를 학습.



**필드 풀 설계 (3계층: 필수 / 메타 / 내용):**

매 학습 샘플: **필수 전부 + 내용 풀 2~4개 + 메타 풀 1~3개 = 총 6~10개 필드**
내용 풀 최소 2개 보장 — 메타데이터만 뽑히는 무의미한 샘플 방지.

| 문서유형 | 필수 (항상 포함) | 메타 풀 (1~3개 선택) | 내용 풀 (2~4개 선택) |
|----------|-----------------|---------------------|---------------------|
| **회의록** (19개) | title, date, attendees | time, location, meeting_type, author, moderator, department, duration | summary, content, agenda, meeting_purpose, decisions, action_items, risks, next_meeting, notes |
| **보고서** (18개) | title, date, author | department, position, report_to, report_type, period, audience | overview, main_content, tasks, achievements, issues, kpi_results, conclusion, recommendations, next_plan |
| **제안서** (20개) | title, submit_date, purpose | submit_to, company, manager, contact, proposer, period | background, current_situation, content, scope, schedule, budget, budget_total, expected_effect, resources, risks, deliverables |

**새 양식 대응 플로우:**


> **핵심**: 학습 데이터에서 수백 가지 필드 조합을 경험한 모델은, 처음 보는 양식도 필드 명세만 있으면 대응 가능.

**변환 로직:**


**문서유형별 배분 (1,500건):**

| 문서유형 | AI Hub | 합성 | 합계 |
|----------|:------:|:----:|:----:|
| 회의록 | 100 | 400 | **500** |
| 보고서 | 300 | 200 | **500** |
| 제안서 | 300 | 200 | **500** |
| **합계** | **700** | **800** | **1,500** |

- 회의록은 AI Hub가 국회 속기록이라 기업 도메인과 차이 → 합성 비중 높임
- 합성 800건 중 30% (240건)는 **부분 누락** — 입력에 없는 정보를 빈 필드로 두도록 학습 (할루시네이션 방지)
- **변형 카테고리 삭제** — 필드 변형이 모든 샘플에 내장되므로 별도 불필요

---

## 4. 데이터 전체 수량

### 4.1 어댑터별 데이터 구성 (최종 확정)

| 어댑터 | 총량 | AI Hub | 합성 (GPT-4o) |
|--------|:----:|:------:|:------------------:|
| v2_summary | **1,007** | 702 (70%) | 305 (30%) |
| v2_qa | **1,000** | 600 (60%) | 400 (40%) |
| v2_generate | **1,501** | 700 (47%) | 801 (53%) |
| **합계** | **3,508** | **2,002 (57%)** | **1,506 (43%)** |

### 4.2 비율 설계 근거

**v2_summary — AI Hub 70% + 합성 30%:**
- AI Hub 5개 카테고리(뉴스/보도자료/보고서/간행물/사설) passage → GPT-4o가 요약
- 실제 문서 원문 기반이라 문체/구조 다양성이 합성보다 우월
- 합성 30%로 기업 도메인(이메일, 사내공지, 계약서 등) 보완
- 요약 태스크는 도메인에 덜 민감 → 7:3 비율 적절

**v2_qa — AI Hub 60%:**
- SN 569 MRC 300건 (정형화된 QA, 품질 안정적)
- SN 582 기반 GPT-4o 생성 300건 (업무 문서 도메인 QA)
- 합성 40%로 다양한 질문 패턴 + 기업 도메인 보충

**v2_generate — 1,500건 (필드 풀 방식):**
- 3개 문서 유형(회의록/보고서/제안서) 균등 배분 → 타입당 500건
- 매 샘플마다 필드 풀에서 랜덤 조합 선택 (6~10개 필드) → 명세 따르기 능력 학습
- 합성 800건 중 30% (240건)는 부분 누락 — 할루시네이션 방지
- 회의록은 AI Hub 국회 속기록 도메인 차이로 합성 비중 높임 (합성 400 / AI Hub 100)

### 4.3 예상 비용

| 항목 | 모델 | 건수 | 비용 |
|------|------|-----:|-----:|
| v2_summary AI Hub 요약 생성 | GPT-4o | 700 | ~$7.0 |
| v2_qa Report QA 생성 | GPT-4o | 300 | ~$7.5 |
| v2_generate JSON 생성 | GPT-4o | 1,500 | ~$37.5 |
| v2_summary 합성 데이터 | GPT-4o | 300 | ~$6.0 |
| v2_qa 합성 데이터 | GPT-4o | 400 | ~$4.0 |
| **합계** | | | **~$62.0** |

---

## 5. 데이터 검증

### 5.1 자동 검증 항목 (validate_v2_data.py)

| 검증 항목 | v2_summary | v2_qa | v2_generate |
|-----------|:----------:|:-----:|:-----------:|
| JSONL 파싱 | ✅ | ✅ | ✅ |
| messages 구조 (system/user/assistant) | ✅ | ✅ | ✅ |
| content 비어있는지 | ✅ | ✅ | ✅ |
| 반복 패턴 탐지 | ✅ | ✅ | ✅ |
| 마크다운 구조 (## 주요 포인트, ## 키워드) | ✅ | - | - |
| 포인트 개수 검증 (3~5개) | ✅ | - | - |
| 키워드 개수 검증 (3~7개) | ✅ | - | - |
| 키워드 품질 (조사/어미 포함 여부) | ✅ | - | - |
| 메타지시문 복사 감지 (5패턴) | ✅ | - | - |
| JSON 파싱 (assistant 응답) | - | ✅ | ✅ |
| 동적 필드 명세 기반 누락/과잉 검증 | - | - | ✅ |
| 한국어 키 혼입 방지 | - | ✅ | ✅ |
| deprecated 필드 거부 (confidence 등) | - | ✅ | - |
| citations 배열 구조 검증 (content 필드) | - | ✅ | - |
| citations 길이 분포 리포트 | - | ✅ | - |
| not-found 비율 (10~15%) | - | ✅ | - |

### 5.2 검증 결과 (2026-03-05 최종)

```
총 샘플: 3,508건 | 에러: 0건 | 경고: 178건 | 판정: ✅ PASS
```

#### v2_generate (1,501건)

| 파일 | 건수 | JSON유효 | 에러 | 경고 |
|------|:----:|:--------:|:----:|:----:|
| aihub_generate.jsonl | 700 | 100% | 0 | 0 |
| synthetic_generate.jsonl | 801 | 100% | 0 | 0 |

- 템플릿 분포: 회의록 655 / 보고서 423 / 제안서 423
- 동적 필드 명세 기반 누락/과잉 필드: 0건
- 한국어 키 혼입: 0건
- user 평균 길이: aihub 1,167자 / synthetic 1,698자
- assistant 평균 길이: aihub 725자 / synthetic 867자

#### v2_qa (1,000건)

| 파일 | 건수 | JSON유효 | not-found | 에러 |
|------|:----:|:--------:|:---------:|:----:|
| aihub_qa.jsonl | 300 | 100% | 36건 (12.0%) | 0 |
| report_qa.jsonl | 300 | 100% | 36건 (12.0%) | 0 |
| synthetic_qa.jsonl | 400 | 100% | 48건 (12.0%) | 0 |

- citations 길이 분포: 0개=120건(12%), 1개=847건, 2개=29건, 3개=4건
- deprecated 필드 (confidence/relevance/source): 0건
- 단답(20자 미만): 3건 (고유명사/수치, 정상)

#### v2_summary (1,007건)

| 파일 | 건수 | 형식적합 | 에러 | 경고 |
|------|:----:|:--------:|:----:|:----:|
| aihub_summary.jsonl | 702 | 100% | 0 | 137 |
| synthetic_summary.jsonl | 305 | 100% | 0 | 41 |

- 경고 178건: 전부 **조사 포함 키워드 오탐** (예: "김정은"→"은", "제도"→"도")
  - 정상 키워드를 정규식이 과탐한 것으로, 실제 품질 문제 아님
- 포인트 개수 위반 (3~5개 범위 밖): 0건
- 키워드 개수 위반 (3~7개 범위 밖): 0건
- 메타지시문 복사: 0건

### 5.3 중복 검사 결과

- **방식**: user + assistant 쌍 기준 해시 비교 (3,508건)
- **완전 중복: 0건**
- 참고: assistant만 비교 시 not-found 응답 120건이 동일하나, user prompt(Context+Question)는 전부 다름 → 정상

### 5.4 품질 기준

| 지표 | 기준 | 결과 | 조치 |
|------|:----:|:----:|------|
| 에러율 < 5% | ✅ PASS | **0.0%** | 그대로 사용 |
| 에러율 5~15% | ⚠️ REVIEW | - | - |
| 에러율 > 15% | ❌ FAIL | - | - |

---

## 6. 학습 데이터 분할

| 어댑터 | 총량 | Train | Eval | Eval 비율 |
|--------|-----:|------:|-----:|:---------:|
| v2_summary | 1,007 | 857 | 150 | 14.9% |
| v2_qa | 1,000 | 900 | 100 | 10.0% |
| v2_generate | 1,501 | 1,351 | 150 | 10.0% |

```bash
# 분할 실행
python ai/finetuning/validate_v2_data.py --split
```

---

## 7. 파인튜닝

### 7.1 공통 하이퍼파라미터

| 파라미터 | 값 |
|----------|:--:|
| Quantization | 4-bit (QLoRA) |
| LoRA dropout | 0.05 |
| Target modules | q_proj, v_proj, k_proj, o_proj, gate_proj, up_proj |
| Epochs | 5 |
| Batch size | 4 |
| Gradient accumulation | 4 (effective batch = 16) |
| Learning rate | 1e-4 |
| Warmup ratio | 0.1 |
| Max length | 2,048 tokens |
| Early stopping patience | 3 |
| alpha/r ratio | 2.0 |

### 7.2 어댑터별 LoRA 설정

| 어댑터 | LoRA rank (r) | LoRA alpha | 이유 |
|--------|:-------------:|:----------:|------|
| v2_summary | 16 | 32 | 비교적 단순한 태스크 → rank 축소 |
| v2_qa | 32 | 64 | citation 추출 정확도 위한 표현력 |
| v2_generate | 32 | 64 | 복잡한 JSON 스키마(15+ 필드) 표현력 |

### 7.3 학습 환경

```
GPU: NVIDIA RTX 5090 (32GB VRAM)
QLoRA 4-bit → 모델 메모리: ~6GB
학습 시 최대 메모리: ~18GB (batch_size=4, max_length=2048)
여유 VRAM: ~14GB
```

---

## 8. 평가

### 8.1 어댑터별 평가 지표 및 목표

#### v2_summary

| 지표 | 목표 | 측정 방법 |
|------|:----:|-----------|
| ROUGE-L | > 0.45 | eval set 대비 생성 요약의 ROUGE-L F1 |
| 포맷 준수율 | > 95% | `## 주요 포인트` + `## 키워드` 존재 여부 |

#### v2_qa

| 지표 | 목표 | 측정 방법 |
|------|:----:|-----------|
| Token F1 | > 0.80 | 정답 토큰과 생성 토큰 간 F1 |
| 인용 정확도 | > 90% | citation이 실제 context에 존재하는지 |

#### v2_generate

| 지표 | 목표 | 측정 방법 |
|------|:----:|-----------|
| JSON 유효율 | > 98% | json.loads() 성공 비율 |
| 필드 완전성 | > 95% | 필수 필드 존재 비율 |
| 필드명 정확도 | > 99% | 영문 키 정확도 (한국어 키 0%) |

### 8.2 비교 실험 계획

| 비교 항목 | 모델 A | 모델 B | 모델 C |
|-----------|--------|--------|--------|
| 베이스 모델 | Qwen3-8B | EXAONE-3.5-7.8B | Kanana-1.5-8B |
| 한국어 성능 | ★★★★ | ★★★★★ | ★★★★★ |
| 라이선스 | Apache 2.0 | 비상업 주의 | 상업 가능 |
| 학습 비용 | 동일 | 동일 | 동일 |

→ 3개 모델 중 평가 결과 최고 성능 모델을 프로덕션 채택

---

## 9. 배포

### 9.1 vLLM 서빙 구조

```
vLLM Server (RTX 5090)
├── Base Model: Qwen3-8B (4-bit)
├── LoRA Adapter: v2_summary
├── LoRA Adapter: v2_qa
└── LoRA Adapter: v2_generate
    → 요청별로 어댑터 핫스왑 (추가 메모리 최소)
```

### 9.2 전환 방식

```python
# 기존 (LLM API)
response = await openai_client.chat.completions.create(
    model="gpt-4o", messages=[...]
)

# 전환 후 (vLLM + LoRA)
response = await vllm_client.chat.completions.create(
    model="v2_summary",  # LoRA 어댑터 이름
    messages=[...]        # 동일한 messages 형식
)
```

→ `ai/llm/factory.py`에서 provider만 변경하면 Agent 코드 수정 불필요

### 9.3 프로덕션 프롬프트 수정 (vLLM 교체 시 필수)

> **2026-03-04 업데이트**: sLLM 전용 프롬프트 상수가 `ai/llm/prompts.py`에 추가됨.
> - `DOC_QA_SLLM_PROMPT` — JSON 간소화 (answer + citations[].content만)
> - `DOC_SUMMARY_SLLM_PROMPT` — 태그/괄호 제거, 규칙 섹션 분리
> - `DOC_GENERATE_SLLM_PROMPT` — 복사 금지 규칙 추가, 동적 필드
>
> **기존 LLM API 프롬프트(`DOC_QA_SYSTEM_PROMPT` 등)는 수정 없이 유지.**
> vLLM으로 교체할 때 `document_agent.py`에서 provider 타입 분기 → sLLM이면 `_SLLM_PROMPT` 사용.

#### 9.3.1 v2_generate: 고정 템플릿 → 동적 필드 방식 전환

- **프로덕션**: 템플릿별 고정 system prompt 3개 (`_generate_meeting_minutes`, `_generate_report`, `_generate_proposal`)
- **sLLM**: 범용 system prompt 1개 (`DOC_GENERATE_SLLM_PROMPT`) + 동적 `[필드 명세]`
- **교체 방법**: 3개 함수의 system prompt를 통일, 기존 필드 지침은 user prompt의 `[필드 명세]`로 이동
- v2 변경: 복사 방지 규칙 추가 ("필드 설명을 그대로 값으로 출력하지 마세요")
- 프롬프트 전문 → **부록 C.1** 참조

#### 9.3.2 v2_qa: sLLM 비스트리밍 전용 + 프롬프트 교체

- **sLLM**: `DOC_QA_SLLM_PROMPT` — JSON 출력, confidence/source/relevance 제거 (백엔드가 RAG score로 계산)
- **운용**: 비스트리밍(JSON) 전용. vLLM 8B ~50 tok/s 기준 ~5초
- `citations == []`이면 not-found로 감지
- 프롬프트 전문 → **부록 C.2** 참조

#### 9.3.3 v2_summary: sLLM 전용 프롬프트로 교체

- **sLLM**: `DOC_SUMMARY_SLLM_PROMPT` — 태그/괄호 제거 버전
- 기존 `DOC_SUMMARY_SYSTEM_PROMPT`는 LLM API용으로 유지
- 프롬프트 전문 → **부록 C.3** 참조

#### 9.3.4 수정 체크리스트

| 파일 | 수정 내용 | 어댑터 |
|------|-----------|--------|
| `ai/agents/document_agent.py` | `_generate_meeting_minutes()` system prompt → 동적 필드 | v2_generate |
| `ai/agents/document_agent.py` | `_generate_report()` system prompt → 동적 필드 | v2_generate |
| `ai/agents/document_agent.py` | `_generate_proposal()` system prompt → 동적 필드 | v2_generate |
| `ai/agents/document_agent.py` | `_handle_doc_qa()` → `DOC_QA_SLLM_PROMPT` (비스트리밍 JSON) | v2_qa |
| `ai/llm/prompts.py` | ✅ sLLM 전용 상수 3개 추가 완료 (`DOC_*_SLLM_PROMPT`) | 전체 |

---

## 10. 변환 스크립트

| 스크립트 | 용도 | API 필요 |
|----------|------|:--------:|
| `convert_aihub_summary.py` | SN 582 → v2_summary 700건 (GPT-4o 요약 생성) | GPT-4o |
| `convert_aihub_qa.py` | SN 569 MRC 300건 + SN 582 Report QA 300건 + 단답 보강 | GPT-4o |
| `convert_aihub_generate.py` | SN 582 → v2_generate 700건 (동적 필드) | GPT-4o |
| `synthesize_generate.py` | v2_generate 합성 800건 | GPT-4o |
| `synthesize_qa.py` | v2_qa 합성 400건 | GPT-4o |
| `synthesize_summary.py` | v2_summary 합성 300건 | GPT-4o |
| `merge_training_data.py` | 소스별 병합 → merged_*.jsonl | 불필요 |
| `validate_v2_data.py` | 3개 어댑터 데이터 통합 검증 | 불필요 |

> 스크립트 경로: `ai/finetuning/scripts/`

### 실행 명령어

```bash
# Phase 1: AI Hub 변환
python ai/finetuning/scripts/convert_aihub_summary.py --total 700
python ai/finetuning/scripts/convert_aihub_qa.py --source mrc --mrc-count 300
python ai/finetuning/scripts/convert_aihub_qa.py --source report --report-count 300 --output data/training/v2_qa/report_qa.jsonl
python ai/finetuning/scripts/convert_aihub_generate.py

# Phase 2: 합성 데이터
python ai/finetuning/scripts/synthesize_generate.py
python ai/finetuning/scripts/synthesize_qa.py
python ai/finetuning/scripts/synthesize_summary.py

# Phase 3: 변형 데이터 (규칙 기반, 예정)

# Phase 4: 병합 + 검증 + 분할
python ai/finetuning/scripts/merge_training_data.py
python ai/finetuning/validate_v2_data.py --deduplicate
python ai/finetuning/validate_v2_data.py --split
```

---

## 11. 진행 현황 (2026-03-05 최종)

### 데이터 수집 현황

| 어댑터 | 소스 | 목표 | 완료 | 상태 |
|--------|------|:----:|:----:|:----:|
| v2_summary | AI Hub + GPT-4o 요약 | 700 | 702 | ✅ |
| v2_summary | 합성 (GPT-4o) | 300 | 305 | ✅ |
| v2_qa | AI Hub MRC | 300 | 300 | ✅ |
| v2_qa | AI Hub Report QA | 300 | 300 | ✅ |
| v2_qa | 합성 (GPT-4o) | 400 | 400 | ✅ (12% not-found 포함) |
| v2_generate | AI Hub 변환 (필드 풀) | 700 | 700 | ✅ |
| v2_generate | 합성 (필드 풀) | 800 | 801 | ✅ |

### 전체 파이프라인

| 단계 | 내용 | 상태 |
|:----:|------|:----:|
| 1 | AI Hub 데이터 다운로드 (SN 582 + SN 569) | ✅ |
| 2 | AI Hub → 학습 형식 변환 (v2_summary 702 + v2_qa 600 + v2_generate 700) | ✅ |
| 3 | 프롬프트 v2 수정 + sLLM 상수 분리 | ✅ |
| 4 | 스크립트 QA + 계획서 수치 일관성 검증 | ✅ |
| 5 | v2_generate 필드 풀 방식 재설계 (고정필드 폐기) | ✅ |
| 6 | 합성 데이터 생성 (v2_generate 801 + v2_summary 305 + v2_qa 400) | ✅ |
| 7 | validate_summary() 검증 강화 (포인트/키워드/메타지시문) | ✅ |
| 8 | 전체 데이터 검증 (3,508건, 에러 0건, 중복 0건) | ✅ |
| 9 | Train/Eval 분할 | ⏳ |
| 10 | QLoRA 파인튜닝 (3개 어댑터) | ⏳ |
| 11 | 3개 모델 비교 → 1개 모델 선정 | ⏳ |
| 12 | vLLM 배포 + Agent 연동 | ⏳ |

### 구현 완료 이력

<details>
<summary>2026-03-03 (인프라 구축)</summary>

| 작업 | 파일 |
|------|------|
| `_call_llm()` Solar→LLM Factory 리팩토링 | `document_agent.py`, `schedule_agent.py` |
| BaseLLM에 json_mode 파라미터 추가 | `base.py`, `openai_provider.py`, `anthropic_provider.py` |
| v2_document.yaml 하이퍼파라미터 설정 | `ai/finetuning/configs/v2_document.yaml` |
| train_v2_document.py 학습 스크립트 | `ai/finetuning/train_v2_document.py` |
| evaluate.py 평가 함수 6개 구현 | `ai/finetuning/evaluate.py` |
| validate_v2_data.py 검증 스크립트 | `ai/finetuning/validate_v2_data.py` |
| 어댑터별 yaml config 3개 | `ai/finetuning/configs/v2_*.yaml` |
| 데이터 디렉토리 분리 | `data/training/v2_generate/`, `v2_qa/`, `v2_summary/` |

</details>

<details>
<summary>2026-03-04 (데이터 변환 + 프롬프트 v2)</summary>

| 작업 | 파일 |
|------|------|
| AI Hub 데이터 다운로드 (SN 582 + SN 569) | `data/raw/ai_hub/` |
| AI Hub 탐색/분석 스크립트 | `aihub_explore.py` |
| v2_summary 700건 변환 | `convert_aihub_summary.py` |
| v2_qa MRC 300건 변환 | `convert_aihub_qa.py` |
| v2_qa Report QA 300건 생성 | `convert_aihub_qa.py` |
| sLLM 전용 프롬프트 상수 3개 | `ai/llm/prompts.py` |
| 합성 스크립트 3개 프롬프트 교체 | `synthesize_qa/generate/summary.py` |

</details>

<details>
<summary>2026-03-05 오전 (스크립트 QA + 정합성 수정)</summary>

| 작업 | 파일 |
|------|------|
| convert_aihub_generate.py 하드코딩 프롬프트 → DOC_GENERATE_SLLM_PROMPT 동적 필드 | `convert_aihub_generate.py` |
| 전 스크립트 dotenv override=True 통일 | 6개 스크립트 |
| v2_generate 1500건 수치 일관성 (yaml/merge/가이드) | 4개 파일 |
| merge output → merged_*.jsonl (base 덮어쓰기 방지) | `merge_training_data.py` |
| synthesize_qa 400→300건, synthesize_summary 300→200건 | 2개 스크립트 |
| v2_qa not-found 목표 건수 안에 포함하도록 로직 수정 | `convert_aihub_qa.py` |
| v2_qa 데이터 트리밍 (324→300, 336→300) | `aihub_qa.jsonl`, `report_qa.jsonl` |
| 문서 통합: 보고서를 정본으로, 계획서 deprecated | 보고서, 계획서 |

</details>

<details>
<summary>2026-03-05 오후 (데이터 품질 검증 + 스크립트 재설계)</summary>

| 작업 | 파일 |
|------|------|
| 3개 어댑터 데이터 품질 심층 검증 (JSON, 필드, 길이분포, 도메인 오염) | 전체 데이터 파일 |
| v2_summary 스크립트 전면 재설계: 규칙기반→GPT-4o 요약 생성 | `convert_aihub_summary.py` |
| v2_summary 카테고리 선별: 10종→5종 (뉴스/보도/보고서/간행물/사설) | `convert_aihub_summary.py` |
| v2_summary 합성 프롬프트: SUMMARY_GENERATION_SYSTEM→DOC_SUMMARY_SLLM_PROMPT | `synthesize_summary.py` |
| v2_summary 메타지시문 복사 감지 validate_summary() 추가 | `synthesize_summary.py` |
| aihub_qa 단답 보강: 15자 미만 152건→GPT-4o 서술형 재생성 (150건 성공) | `convert_aihub_qa.py` |
| synthetic_qa 400건 조정 + not-found 12% 정확 매칭 (48/400) | `synthetic_qa.jsonl` |

</details>

<details>
<summary>2026-03-05 야간 (데이터 생성 완료 + 검증 최종)</summary>

| 작업 | 파일 |
|------|------|
| validate_summary() 검증 강화: 포인트 3~5개, 키워드 3~7개, 메타지시문 5패턴 | `convert_aihub_summary.py`, `synthesize_summary.py` |
| convert_aihub_summary.py에 --append 옵션 추가 | `convert_aihub_summary.py` |
| v2_summary aihub 702건 생성 완료 | `aihub_summary.jsonl` |
| v2_summary synthetic 305건 생성 완료 | `synthetic_summary.jsonl` |
| v2_generate synthetic 801건 생성 완료 | `synthetic_generate.jsonl` |
| validate_v2_data.py 검증 스크립트 전면 개선 | `validate_v2_data.py` |
| - v2_generate: 고정 필드 → 동적 [필드 명세] 파싱 기반 검증 | |
| - v2_summary: 포인트/키워드 개수 + 메타지시문 감지 추가 | |
| - _detect_task: 동적 필드 프롬프트 감지 추가 | |
| - 중복 체크: assistant만 → user+assistant 쌍 비교 | |
| 전체 검증 실행: 3,508건, 에러 0건, 중복 0건, ✅ PASS | 전체 |
| 데이터 생성 과정 기록 문서 작성 | `데이터_생성_과정_기록.md` |

</details>

---

## 12. TODO

### 전처리 + 분할

| STEP | 작업 | 상태 |
|------|------|:----:|
| 1 | Train/Eval 분할 (`--split`) | ⏳ |
| 2 | 토큰 길이 분석 (max_length 설정 확인) | ⏳ |

### 학습 + 평가

| STEP | 작업 | 상태 |
|------|------|:----:|
| 3 | GPU 환경 준비 (RTX 5090 or RunPod) | ⏳ |
| 4 | 3개 모델 비교 학습 (Qwen3-8B / EXAONE / Kanana) | ⏳ |
| 5 | 평가 결과 비교 → **1개 모델로 통일** 선정 | ⏳ |
| 6 | 선정 모델로 v2_qa, v2_summary, v2_generate 학습 | ⏳ |
| 7 | vLLM 서버 배포 + Agent 연동 + E2E 테스트 | ⏳ |

---

## 13. 리스크 및 대응

| 리스크 | 대응 |
|--------|------|
| 제안서(6~10 랜덤필드) JSON 깨짐 | 10개 샘플 선행 테스트. 실패 10%+ 시 rank→48 또는 EXAONE 전환 |
| AI Hub 데이터 도메인 불일치 (국회 회의록 등) | meeting_minutes는 합성 중심으로 전환 완료. report/proposal은 적합 확인 |
| LLM API보다 성능 하락 | LLM API(GPT/Claude)를 fallback으로 유지. factory.py provider 전환으로 즉시 복구 |
| RTX 5090 32GB VRAM 부족 | batch_size 2로 축소 + grad_accum 8로 조정. 또는 A100 전환 |
| 합성 데이터 품질 부족 | 3단계 검증: 자동검증 → LLM 교차검증 → 수동 샘플링(150개) |
| AI Hub summary 카테고리 부적합 | 10종→5종 선별 (회의록/연설문/역사/문학/나레이션 제외), GPT-4o로 요약 재생성 |

---

## 부록

### A. 데이터 디렉토리 구조

```
data/
├── raw/ai_hub/                             ← AI Hub 원본 (git 미추적)
│   ├── 022.요약문 및 레포트 생성 데이터/   ← SN 582
│   └── 016.행정 문서 대상 기계독해 데이터/ ← SN 569
├── training/
│   ├── v2_summary/
│   │   ├── aihub_summary.jsonl             ← AI Hub + GPT-4o 요약 (702건) ✅
│   │   ├── synthetic_summary.jsonl         ← 합성 (305건) ✅
│   │   ├── merged_summary.jsonl            ← 병합 (분할 전) [예정]
│   │   ├── train.jsonl                     ← 학습용 (857건) [분할 후]
│   │   └── eval.jsonl                      ← 검증용 (150건) [분할 후]
│   ├── v2_qa/
│   │   ├── aihub_qa.jsonl                  ← AI Hub MRC (300건) ✅
│   │   ├── report_qa.jsonl                 ← AI Hub Report QA (300건) ✅
│   │   ├── synthetic_qa.jsonl              ← 합성 (400건, 12% not-found) ✅
│   │   ├── merged_qa.jsonl                 ← 병합 (분할 전) [예정]
│   │   ├── train.jsonl                     ← 학습용 (900건) [분할 후]
│   │   └── eval.jsonl                      ← 검증용 (100건) [분할 후]
│   └── v2_generate/
│       ├── aihub_generate.jsonl            ← AI Hub 변환 (700건, 필드 풀) ✅
│       ├── synthetic_generate.jsonl        ← 합성 (801건, 필드 풀 + 부분 누락 240건) ✅
│       ├── merged_generate.jsonl           ← 병합 (분할 전) [예정]
│       ├── train.jsonl                     ← 학습용 (1,351건) [분할 후]
│       └── eval.jsonl                      ← 검증용 (150건) [분할 후]
```

### B. 관련 문서

- `ai/finetuning/finetuning_docs/AI_Hub_데이터_적합성_검토.md` — AI Hub 데이터 적합성 분석
- `ai/finetuning/configs/v2_*.yaml` — 어댑터별 학습 설정
- `docs/지용/FINETUNING_PROMPT_V2_PLAN.md` — 프롬프트 v2 변경 상세

---

### C. sLLM 학습용 프롬프트 전문

> 출처: `ai/llm/prompts.py` — 학습 데이터 생성 + vLLM 서빙 시 동일하게 사용

#### C.1 DOC_GENERATE_SLLM_PROMPT (문서 생성)

```
당신은 기업 문서 작성 전문가입니다.
사용자가 제공하는 [필드 명세]에 따라 문서 내용을 JSON으로 생성하세요.

규칙:
- [필드 명세]에 정의된 필드만 JSON 키로 사용하세요.
- 각 필드의 설명을 참고하여, 입력 내용을 바탕으로 구체적인 문서 내용을 작성하세요.
- 필드 설명이나 지침 문장을 그대로 값으로 출력하지 마세요.
- 입력 내용에 해당 정보가 없으면 빈 문자열 또는 빈 배열로 두세요.
- 배열 필드는 반드시 JSON 배열 형태로 출력하세요.
- 반드시 JSON만 출력하세요. 설명 텍스트나 마크다운을 포함하지 마세요.
```

> system prompt 1개로 회의록/보고서/제안서를 모두 처리. 필드 풀에서 매 샘플마다 6~10개 랜덤 선택.
> 문서 유형별 필드 명세는 user prompt의 `[필드 명세]` 섹션에 동적으로 삽입됨. 커스텀 템플릿도 동일 방식으로 대응.

#### C.2 DOC_QA_SLLM_PROMPT (문서 QA)

```
당신은 기업 문서 기반 질의응답 전문가입니다.
주어진 문서 내용을 근거로 사용자의 질문에 정확하게 답변합니다.

결과는 반드시 아래 JSON 형식으로만 응답하세요:
{
    "answer": "질문에 대한 답변",
    "citations": [
        {"content": "답변의 근거가 되는 원문 인용"}
    ]
}

규칙:
- 반드시 제공된 문서 내용만을 근거로 답변하세요.
- 답변의 근거가 되는 문서 원문을 citations에 1~3개 포함하세요.
- 문서에서 답을 찾을 수 없으면 answer에 "제공된 문서에서 해당 내용을 찾을 수 없습니다."라고 작성하고 citations는 빈 배열([])로 두세요.
- 추측이나 외부 지식으로 답변을 보충하지 마세요.
- JSON 외의 텍스트를 포함하지 마세요.
```

> LLM API용 `DOC_QA_SYSTEM_PROMPT`에서 `source`, `relevance`, `confidence` 필드를 제거한 간소화 버전.
> 해당 필드들은 서빙 시 백엔드가 RAG score 기반으로 계산하여 채움.

#### C.3 DOC_SUMMARY_SLLM_PROMPT (문서 요약)

```
당신은 기업 문서 요약 전문가입니다.
주어진 문서를 분석하여 핵심 내용을 정리합니다.

반드시 아래 형식으로 출력하세요:

핵심 요약

## 주요 포인트
- 포인트

## 키워드
키워드들

규칙:
- 핵심 요약은 2~3문장으로 작성하세요.
- 주요 포인트는 불릿(-)으로 3~5개 작성하세요.
- 키워드는 명사/명사구 3~7개를 쉼표로 구분하세요.
- 원문에 없는 내용을 추가하지 마세요.
- 한국어로 답변하세요.
```

---

### D. 어댑터별 실제 학습 데이터 예시

> 실제 생성된 JSONL에서 발췌. sLLM은 이 messages 형식을 그대로 학습함.

#### D.1 v2_generate — 문서 생성 (회의록)

```json
{
  "messages": [
    {
      "role": "system",
      "content": "(C.1 DOC_GENERATE_SLLM_PROMPT 전문)"
    },
    {
      "role": "user",
      "content": "다음 내용을 바탕으로 문서를 JSON 형식으로 작성해주세요.\n\n[문서 유형] 회의록\n\n[필드 명세]\n- title: 회의 주제를 반영한 구체적인 제목\n- date: 회의 날짜 (YYYY-MM-DD 형식, 없으면 오늘 날짜)\n- attendees: 참석자 이름 배열 (없으면 빈 배열)\n- summary: 회의에서 논의된 주요 내용을 파트별로 3~5문장으로 요약\n- decisions: 결정된 사항 목록 (배열, 없으면 빈 배열)\n- action_items: 후속 조치 목록 배열. 각 항목은 {\"content\", \"assignee\", \"due_date\"} 형태\n- risks: 리스크 목록 배열. 각 항목은 {\"description\", \"level\"(상/중/하), \"regulation\"} 형태\n\n[회의 내용]\n인천국제공항공사 3단계 사업 진행 상황 회의..."
    },
    {
      "role": "assistant",
      "content": "{\n  \"title\": \"인천공항 3단계 사업 진행 상황 및 국고지원 관련 논의\",\n  \"date\": \"2023-10-06\",\n  \"attendees\": [\"최홍열\", \"황영철\"],\n  \"summary\": \"회의에서는 인천국제공항공사의 3단계 사업 진행 상황에 대한 논의가 이루어졌다...\",\n  \"decisions\": [],\n  \"action_items\": [],\n  \"risks\": [{\"description\": \"국고지원 없이 3단계 사업을 진행할 경우 재정적 부담 증가\", \"level\": \"상\", \"regulation\": \"국가 재정 지원 확보 필요\"}]\n}"
    }
  ]
}
```

> `decisions`, `action_items`가 빈 배열 — 원문에 해당 내용이 없어 GPT-4o가 비워둔 정상 케이스.

#### D.2 v2_qa — 문서 QA (정상 응답)

```json
{
  "messages": [
    {
      "role": "system",
      "content": "(C.2 DOC_QA_SLLM_PROMPT 전문)"
    },
    {
      "role": "user",
      "content": "Context:\n[\"기술력 우수한 창업기업, 벤처기업 인증 쉬워진다...\", \"벤처투자기관: 창투사, 신기술사업금융업자...\", \"투자 기업과 같이 벤처확인 기회를 부여...\"]\n\nQuestion: 이번 벤처확인 제도 개선의 목적은?"
    },
    {
      "role": "assistant",
      "content": "{\"answer\": \"벤처확인 제도 개선\", \"citations\": [{\"content\": \"이번 벤처확인 제도 개선을 통해 우수한 기술력을 갖춘 기업들이 보다 수월하게 벤처기업으로 확인을 받을 수 있을 것으로 예상된다.\"}]}"
    }
  ]
}
```

#### D.3 v2_qa — 문서 QA (not-found 응답, ~12%)

```json
{
  "messages": [
    {
      "role": "system",
      "content": "(C.2 DOC_QA_SLLM_PROMPT 전문)"
    },
    {
      "role": "user",
      "content": "Context:\n[\"2021 사회적 고립가구 지원 사업 자문운영 관련 사전 간담회. 일시: 2021년 4월 1일...\"]\n\nQuestion: 2014년 지방공기업 경영평가는 어떤 방법의 평가를 통해 지방공기업의 개혁을 이끌어낼 계획일까"
    },
    {
      "role": "assistant",
      "content": "{\"answer\": \"제공된 문서에서 해당 내용을 찾을 수 없습니다.\", \"citations\": []}"
    }
  ]
}
```

> Context는 2021년 사회적 고립가구 문서인데, 질문은 2014년 지방공기업 경영평가 — 의도적 카테고리 교차 매칭으로 생성된 not-found 샘플.

#### D.4 v2_summary — 문서 요약

```json
{
  "messages": [
    {
      "role": "system",
      "content": "(C.3 DOC_SUMMARY_SLLM_PROMPT 전문)"
    },
    {
      "role": "user",
      "content": "다음 문서를 요약해주세요.\n\n사용자 요청: 회의 결과 요약\n\n문서 내용:\n회의 제목: 2023년 3분기 전략 계획 회의\n일시: 2023년 10월 25일 오후 2시\n참석자: 박준형(대표이사), 이민정(전략기획팀장)...\n\n회의 안건:\n1. 2023년 3분기 성과 분석\n2. 2024년 사업 계획 수립..."
    },
    {
      "role": "assistant",
      "content": "2023년 10월 25일에 열린 3분기 전략 계획 회의에서는 3분기 성과 분석, 2024년 사업 계획 수립, 신규 프로젝트 추진 방안이 논의되었다. 3분기 매출이 15% 증가하였으나 고객 유치 목표 달성 미흡, 2024년 매출 20% 증가 목표 설정 등이 주요 이슈로 다뤄졌다.\n\n## 주요 포인트\n- 3분기 매출 15% 증가 보고\n- 2024년 매출 목표 20% 증가 설정\n- 중국 및 동남아시아 시장 진출 검토\n- AI 기반 컨설팅 솔루션 시범 프로젝트 제안\n- 고객 유치 프로그램 개선 필요성 제기\n\n## 키워드\n3분기 성과, 2024년 사업 계획, 신규 프로젝트, 고객 유치, AI 솔루션"
    }
  ]
}
```
