# 문서 Agent LoRA v2 파인튜닝 파이프라인 보고서

## 1. 개요

### 1.1 목적
문서 Agent의 3가지 핵심 기능(요약, QA, 문서생성)을 sLLM으로 전환하기 위한 LoRA 파인튜닝 파이프라인.
LLM API(GPT/Claude) 기반으로 구현된 기능을 **Qwen3-8B + QLoRA 어댑터**로 교체하여 비용 절감 및 자체 서빙 실현.

### 1.2 어댑터 구성

| 어댑터 | 기능 | 입력 | 출력 |
|--------|------|------|------|
| **v2_summary** | 문서 요약 | 원문 텍스트 | 마크다운 (핵심요약 + 주요포인트 + 키워드) |
| **v2_qa** | 문서 QA | Context 청크 + Question | JSON (answer + citations + confidence) |
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
| 소스 | SN 582 전 카테고리 (10종) |
| 변환 방식 | 규칙 기반 (API 불필요) + GPT-4o-mini 키워드 보강 |
| 원문 필터 | 300~3,000자 |
| 비용 | ~$0.7 (키워드 보강만) |

**변환 로직:**
```
AI Hub 원본                    →  학습 데이터
─────────────────────────────────────────────
passage (원문)                 →  user: "다음 문서를 요약해주세요.\n\n사용자 요청: {랜덤}\n\n문서 내용:\n{passage}"
summary2 (2~3문장 추출요약)    →  assistant 핵심 요약 파트
summary3 (20% 추출요약)        →  주요 포인트 불릿 추출
GPT-4o-mini 키워드 추출        →  ## 키워드 파트
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

| 카테고리 | 건수 | 비율 |
|----------|:----:|:----:|
| 회의록 | 180 | 25.7% |
| 보고서 | 100 | 14.3% |
| 뉴스 | 100 | 14.3% |
| 보도자료 | 90 | 12.9% |
| 간행물 | 80 | 11.4% |
| 연설문 | 60 | 8.6% |
| 사설 | 50 | 7.1% |
| 역사기록물 | 20 | 2.9% |
| 나레이션 | 15 | 2.1% |
| 문학 | 5 | 0.7% |

**키워드 품질 개선:**

| 방법 | 예시 결과 | 비용 |
|------|-----------|------|
| TF 기반 (초기) | `씨는, 시스템에, 전표, 사내, 하지만` | $0 |
| 형태소 분석 (Okt) | `전표, 시스템, 사무실, 챗봇, 사내` | $0 |
| **GPT-4o-mini (채택)** | **`RPA, 챗봇, 업무자동화, KT, 딥러닝`** | **$0.7** |

→ GPT-4o-mini가 **의미적 핵심 키워드**를 정확하게 추출하여 채택.

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
answers.text                   →  {"answer": "...", "citations": [...], "confidence": 0.95}
```

- span_extraction (추출형) 60% + span_extraction_how (절차형) 40% 비율 혼합
- context 150~800자, answer 5자 이상 필터링

**소스 2: SN 582 → GPT-4o QA 생성**
```
SN 582 passage                 →  GPT-4o가 질문+답변 쌍 생성
─────────────────────────────────────────────
passage (원문)                 →  Context 청크 분할
GPT-4o 생성 question           →  Question
GPT-4o 생성 answer + citation  →  {"answer": "...", "citations": [...], "confidence": 0.90}
```

- 보고서, 회의록, 간행물, 보도자료, 뉴스 카테고리 혼합
- 500~1,500자 원문 필터링

**assistant 출력 형식 (JSON):**
```json
{
  "answer": "질문에 대한 답변",
  "citations": [
    {"source": "문서명", "content": "인용 내용", "relevance": "높음"}
  ],
  "confidence": 0.95
}
```

---

#### v2_generate (문서 생성) — 동적 필드 명세 방식

| 항목 | 내용 |
|------|------|
| 소스 | SN 582 passage → GPT-4o가 JSON 문서 생성 |
| 변환 방식 | 반자동 (AI Hub 원문 + GPT-4o JSON 생성) → **동적 필드 변환** |
| 비용 | ~$31.3 |

**핵심 설계: 동적 필드 명세 방식**

기존 고정 템플릿 방식(템플릿별 system prompt 고정)에서 **동적 필드 명세 방식**으로 전환.
새로운 문서 양식(DOCX)이 추가되어도 sLLM 재학습 없이 대응 가능.

```
[기존 - 고정 템플릿]
system: "당신은 회의록 작성 전문가입니다. title, date, attendees..."
user: "다음 회의 내용을 바탕으로 회의록 JSON을 작성해주세요."

[변경 - 동적 필드]
system: "당신은 기업 문서 작성 전문가입니다.
        주어진 [필드 명세]에 따라 JSON을 생성하세요."
user: "[문서 유형] 회의록
      [필드 명세]
      - title: 회의 주제를 반영한 구체적인 제목
      - date: 회의 날짜 (YYYY-MM-DD)
      ...
      [회의 내용]
      보건복지부장관 문형표..."
```

**새 양식 대응 플로우:**
```
1. 관리자가 새 문서 양식 DOCX 업로드
2. 시스템이 DOCX 파싱 → 필드 자동 추출
3. 관리자가 추출된 필드 명세 확인/수정
4. 확정된 필드 명세 저장
5. 사용자 요청 시 → 저장된 필드 명세를 sLLM 프롬프트에 동적 삽입 → JSON 생성
```

> **장점**: system prompt가 범용이므로, 학습 시 다양한 필드 조합을 경험한 모델은 처음 보는 양식도 필드 명세만 있으면 대응 가능.

**변환 로직:**
```
AI Hub passage                 →  GPT-4o가 JSON 생성 → 동적 필드 프롬프트로 재구성
─────────────────────────────────────────────
system                         →  범용: "당신은 기업 문서 작성 전문가입니다. [필드 명세]에 따라 JSON을 생성하세요."
passage (원문)                 →  user: "[문서 유형] 회의록\n[필드 명세]\n- title: ...\n[회의 내용]\n{passage}"
GPT-4o 생성 JSON               →  assistant: {"title": "...", "summary": "...", ...} (그대로 유지)
```

**템플릿별 배분 (783건):**

| 템플릿 | 건수 | JSON 필드 수 | 소스 카테고리 |
|--------|:----:|:------------:|---------------|
| meeting_minutes | 39 | 7필드 | 회의록 |
| report | 342 | 12필드 | 보고서, 간행물 |
| proposal | 402 | 19필드 | 보도자료, 간행물 |

> **참고**: 회의록은 AI Hub 회의록이 국회 속기록이라 기업 회의록과 도메인 차이가 있어, 나머지 217건 중 합성으로 보충 예정.

---

## 4. 데이터 전체 수량

### 4.1 어댑터별 데이터 구성

| 어댑터 | 총량 | AI Hub | 합성 (GPT/Claude) | 변형 |
|--------|:----:|:------:|:------------------:|:----:|
| v2_summary | **1,000** | 700 (70%) | 200 (20%) | 100 (10%) |
| v2_qa | **1,000** | 600 (60%) | 300 (30%) | 100 (10%) |
| v2_generate | **1,000** | 783 (78%) | 150 (15%) | 67 (7%) |
| **합계** | **3,000** | **2,083 (69%)** | **650 (22%)** | **267 (9%)** |

### 4.2 비율 설계 근거

**v2_summary — AI Hub 70%로 높은 이유:**
- SN 582에 summary2/summary3가 직접 제공되어 변환 품질이 높음
- 단, 80%→70%로 낮춘 이유: 추출요약(extractive) 편향 방지
- 합성 20%로 추상형(abstractive) 마크다운 모범답안 보충

**v2_qa — AI Hub 60%:**
- SN 569 MRC 300건 (정형화된 QA, 품질 안정적)
- SN 582 기반 GPT-4o 생성 300건 (업무 문서 도메인 QA)
- 합성 30%로 다양한 질문 패턴 보충

**v2_generate — AI Hub 78%로 높아진 이유:**
- 이전 세션 병렬 실행으로 report/proposal이 계획보다 많이 확보됨
- AI Hub 원문을 input으로 사용, output은 GPT-4o가 생성 (반합성)
- 동적 필드 방식으로 전환하여 다양한 필드 조합 학습 효과
- 나머지 217건은 합성+변형으로 보충 (회의록 도메인 보강 포함)

### 4.3 예상 비용

| 항목 | 모델 | 건수 | 비용 |
|------|------|-----:|-----:|
| v2_summary 키워드 보강 | GPT-4o-mini | 700 | ~$0.7 |
| v2_qa Report QA 생성 | GPT-4o | 300 | ~$7.5 |
| v2_generate JSON 생성 | GPT-4o | 783 | ~$31.3 |
| 합성 데이터 생성 (예정) | GPT-4o / Claude | 650 | ~$13.0 |
| **합계** | | | **~$52.5** |

---

## 5. 데이터 검증

### 5.1 자동 검증 (validate_v2_data.py)

| 검증 항목 | v2_summary | v2_qa | v2_generate |
|-----------|:----------:|:-----:|:-----------:|
| JSONL 파싱 | ✅ | ✅ | ✅ |
| messages 구조 (system/user/assistant) | ✅ | ✅ | ✅ |
| content 비어있는지 | ✅ | ✅ | ✅ |
| 반복 패턴 탐지 | ✅ | ✅ | ✅ |
| 마크다운 구조 (## 주요 포인트, ## 키워드) | ✅ | - | - |
| 키워드 품질 (조사/어미 포함 여부) | ✅ | - | - |
| JSON 파싱 (assistant 응답) | - | ✅ | ✅ |
| 필수 필드 존재 | - | ✅ | ✅ |
| 한국어 키 혼입 방지 | - | ✅ | ✅ |
| confidence 범위 (0.0~1.0) | - | ✅ | - |
| relevance 값 (높음/중간/낮음) | - | ✅ | - |
| citations 배열 검증 | - | ✅ | - |
| 템플릿별 필수 필드 | - | - | ✅ |

### 5.2 품질 기준

| 지표 | 기준 | 조치 |
|------|:----:|------|
| 에러율 < 5% | ✅ PASS | 그대로 사용 |
| 에러율 5~15% | ⚠️ REVIEW | 에러 샘플 수동 검수 후 수정/제거 |
| 에러율 > 15% | ❌ FAIL | 변환 로직 재점검 필요 |

### 5.3 중복 검사

- **소규모** (< 2,000건): Jaccard trigram similarity (threshold ≥ 0.95)
- **대규모** (≥ 2,000건): 해시 기반 exact duplicate 체크
- 어댑터 간 교차 중복도 검사 (같은 passage가 다른 어댑터에 사용된 경우)

### 5.4 수동 검수

각 어댑터별 랜덤 샘플 30건 (약 3~5%) 수동 검수:
- 답변이 원문에 근거하는지
- JSON 필드 값이 의미적으로 정확한지
- 마크다운 형식이 일관적인지

---

## 6. 학습 데이터 분할

| 어댑터 | Train | Eval | Eval 비율 |
|--------|------:|-----:|:---------:|
| v2_summary | 850 | 150 | 15% |
| v2_qa | 900 | 100 | 10% |
| v2_generate | 900 | 100 | 10% |

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

> **주의**: 학습 데이터의 system prompt와 프로덕션(`document_agent.py`)의 system prompt가 일부 불일치.
> vLLM으로 교체할 때 반드시 아래 수정을 함께 진행해야 sLLM이 학습한 패턴대로 동작함.

#### 9.3.1 v2_generate: 고정 템플릿 → 동적 필드 방식 전환

**현재 프로덕션 (고정 템플릿 — 템플릿별 system prompt 별도)**
```python
# _generate_meeting_minutes() — document_agent.py:398
sys_prompt = "당신은 회의록 작성 전문가입니다.\n아래 [작성 지침]을 참고하여..."

# _generate_report() — document_agent.py:521
sys_prompt = "당신은 업무보고서 작성 전문가입니다.\n아래 [작성 지침]을 참고하여..."

# _generate_proposal() — document_agent.py:636
sys_prompt = "당신은 제안서 작성 전문가입니다.\n아래 [작성 지침]을 참고하여..."
```

**학습 데이터 (동적 필드 — 범용 system prompt 1개)**
```python
sys_prompt = (
    "당신은 기업 문서 작성 전문가입니다.\n"
    "사용자가 제공하는 [필드 명세]에 따라 문서 내용을 JSON으로 생성하세요.\n\n"
    "규칙:\n"
    "- [필드 명세]에 정의된 필드만 JSON 키로 사용하세요.\n"
    "- 각 필드의 설명을 참고하여 적절한 값을 생성하세요.\n"
    "- 입력 내용에 해당 정보가 없으면 빈 문자열 또는 빈 배열로 두세요.\n"
    "- 배열 필드는 반드시 JSON 배열 형태로 출력하세요.\n"
    "- 반드시 JSON만 출력하세요. 설명 텍스트나 마크다운을 포함하지 마세요."
)
```

**수정 방법**: `_generate_meeting_minutes`, `_generate_report`, `_generate_proposal` 3개 함수의 system prompt를 위 범용 프롬프트로 통일하고, 기존 필드 지침은 user prompt의 `[필드 명세]` 섹션으로 이동.

#### 9.3.2 v2_qa: 스트리밍 모드 프롬프트 통일

**현재 프로덕션 (스트리밍 모드에서 별도 프롬프트 사용)**
```python
# _handle_doc_qa() 스트리밍 모드 — document_agent.py:861
sys_prompt = """당신은 기업 문서 기반 질의응답 전문가입니다.
주어진 문서 내용을 근거로 사용자의 질문에 정확하게 답변하세요.
...
"""
# → 자연어 답변용 (JSON 아님), 학습 데이터와 불일치
```

**학습 데이터 (DOC_QA_SYSTEM_PROMPT — JSON 출력)**
```python
# ai/llm/prompts.py:122
DOC_QA_SYSTEM_PROMPT = """당신은 기업 문서 기반 질의응답 전문가입니다.
...
결과는 반드시 아래 JSON 형식으로만 응답하세요:
{"answer": "...", "citations": [...], "confidence": 0.0~1.0}
"""
```

**수정 방법**: 스트리밍 모드에서도 `DOC_QA_SYSTEM_PROMPT`를 사용하도록 통일. 스트리밍 시 JSON 응답을 받아서 `answer` 필드만 토큰 전송하고, `sources`/`citations`는 `result` 이벤트로 별도 전달.

#### 9.3.3 v2_summary: 수정 불필요

프로덕션과 학습 데이터 모두 `DOC_SUMMARY_SYSTEM_PROMPT` (`ai/llm/prompts.py:110`) 사용. 100% 일치.

#### 9.3.4 수정 체크리스트

| 파일 | 수정 내용 | 어댑터 |
|------|-----------|--------|
| `ai/agents/document_agent.py` | `_generate_meeting_minutes()` system prompt → 동적 필드 | v2_generate |
| `ai/agents/document_agent.py` | `_generate_report()` system prompt → 동적 필드 | v2_generate |
| `ai/agents/document_agent.py` | `_generate_proposal()` system prompt → 동적 필드 | v2_generate |
| `ai/agents/document_agent.py` | `_handle_doc_qa()` 스트리밍 프롬프트 → `DOC_QA_SYSTEM_PROMPT` 통일 | v2_qa |
| `ai/llm/prompts.py` | 동적 필드 범용 system prompt 상수 추가 (`DOC_GENERATE_SYSTEM_PROMPT`) | v2_generate |

---

## 10. 변환 스크립트

| 스크립트 | 용도 | API 필요 |
|----------|------|:--------:|
| `ai/finetuning/scripts/convert_aihub_summary.py` | SN 582 → v2_summary 변환 | GPT-4o-mini (키워드만) |
| `ai/finetuning/scripts/convert_aihub_qa.py` | SN 569 + SN 582 → v2_qa 변환 | GPT-4o (Report QA만) |
| `ai/finetuning/scripts/convert_aihub_generate.py` | SN 582 → v2_generate 변환 (고정 프롬프트) | GPT-4o |
| `ai/finetuning/scripts/convert_to_dynamic_fields.py` | v2_generate 프롬프트를 동적 필드 방식으로 변환 | 불필요 |
| `ai/finetuning/validate_v2_data.py` | 3개 어댑터 데이터 통합 검증 | 불필요 |

### 실행 명령어

```bash
# 1. v2_summary (700건, 키워드 GPT 보강)
python ai/finetuning/scripts/convert_aihub_summary.py --total 700 --llm-enhance

# 2. v2_qa MRC (300건, API 불필요)
python ai/finetuning/scripts/convert_aihub_qa.py --source mrc --mrc-count 300

# 3. v2_qa Report QA (300건, GPT-4o)
python ai/finetuning/scripts/convert_aihub_qa.py --source report --report-count 300

# 4. v2_generate (783건, GPT-4o)
python ai/finetuning/scripts/convert_aihub_generate.py

# 5. 동적 필드 방식으로 프롬프트 변환
python ai/finetuning/scripts/convert_to_dynamic_fields.py

# 6. 검증
python ai/finetuning/validate_v2_data.py --deduplicate

# 7. Train/Eval 분할
python ai/finetuning/validate_v2_data.py --split
```

---

## 11. 진행 현황

### AI Hub 데이터 변환 (2026-03-04 기준)

| 어댑터 | AI Hub 목표 | 완료 | 상태 |
|--------|:-----------:|:----:|:----:|
| v2_summary | 700 | 700 | ✅ |
| v2_qa (MRC) | 300 | 300 | ✅ |
| v2_qa (Report QA) | 300 | 300 | ✅ |
| v2_generate | 783 | 783 | ✅ (동적 필드 변환 완료) |

### 검증 결과 (2026-03-04)

| 어댑터 | 건수 | 에러 | 경고 | 판정 |
|--------|:----:|:----:|:----:|:----:|
| v2_summary | 700 | 0 | 235 | ✅ PASS |
| v2_qa | 600 | 0 | 1 | ✅ PASS |
| v2_generate | 783 | 0 | 0 | ✅ PASS |
| **합계** | **2,083** | **0** | **236** | **✅ PASS** |

### 전체 데이터 파이프라인

| 단계 | 내용 | 상태 |
|:----:|------|:----:|
| 1 | AI Hub 데이터 다운로드 (SN 582 + SN 569) | ✅ |
| 2 | AI Hub → 학습 형식 변환 (2,083건) | ✅ |
| 3 | v2_generate 동적 필드 프롬프트 변환 | ✅ |
| 4 | AI Hub 데이터 검증 (에러 0건) | ✅ |
| 5 | 합성 데이터 생성 (650건) | ⏳ |
| 6 | 변형 데이터 생성 (267건) | ⏳ |
| 7 | 전체 데이터 검증 + 중복 제거 | ⏳ |
| 8 | Train/Eval 분할 | ⏳ |
| 9 | QLoRA 파인튜닝 (3개 어댑터) | ⏳ |
| 10 | 모델 평가 | ⏳ |
| 11 | vLLM 배포 | ⏳ |

---

## 부록

### A. 데이터 디렉토리 구조

```
data/
├── raw/aihub/                              ← AI Hub 원본 (git 미추적)
│   ├── 022.요약문 및 레포트 생성 데이터/   ← SN 582
│   └── 016.행정 문서 대상 기계독해 데이터/ ← SN 569
├── training/
│   ├── v2_summary/
│   │   ├── aihub_summary.jsonl             ← AI Hub 변환 (700건)
│   │   ├── synthetic_summary.jsonl         ← 합성 (200건) [예정]
│   │   ├── variant_summary.jsonl           ← 변형 (100건) [예정]
│   │   ├── train.jsonl                     ← 학습용 (850건) [분할 후]
│   │   └── eval.jsonl                      ← 검증용 (150건) [분할 후]
│   ├── v2_qa/
│   │   ├── aihub_qa.jsonl                  ← AI Hub 변환 (600건)
│   │   ├── synthetic_qa.jsonl              ← 합성 (300건) [예정]
│   │   ├── variant_qa.jsonl                ← 변형 (100건) [예정]
│   │   ├── train.jsonl
│   │   └── eval.jsonl
│   └── v2_generate/
│       ├── aihub_generate.jsonl            ← AI Hub 변환 (783건, 동적 필드 방식)
│       ├── aihub_generate_fixed_prompt_backup.jsonl  ← 고정 프롬프트 백업
│       ├── synthetic_generate.jsonl        ← 합성 (150건) [예정]
│       ├── variant_generate.jsonl          ← 변형 (67건) [예정]
│       ├── train.jsonl
│       └── eval.jsonl
```

### B. 관련 문서

- `ai/finetuning/finetuning_docs/문서Agent_LoRA_v2_파인튜닝_계획.md` — 상세 계획서
- `ai/finetuning/finetuning_docs/AI_Hub_데이터_적합성_검토.md` — AI Hub 데이터 적합성 분석
- `data/training/v2_document/FORMAT_GUIDE.md` — 데이터 형식 가이드
- `ai/finetuning/configs/v2_summary.yaml` — v2_summary 학습 설정
- `ai/finetuning/configs/v2_qa.yaml` — v2_qa 학습 설정
- `ai/finetuning/configs/v2_generate.yaml` — v2_generate 학습 설정
