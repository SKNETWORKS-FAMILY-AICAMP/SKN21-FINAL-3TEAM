# v2 Document 학습 데이터 형식 가이드

> 어댑터 분리 전략: 기능별 별도 LoRA 어댑터로 학습

## 디렉토리 구조

```
data/training/
├── v2_generate/          # doc_generate 전용 (1,000개)
│   ├── aihub_generate.jsonl    # AI Hub 변환 (460개)
│   ├── synth_generate.jsonl    # 합성 데이터 (400개)
│   ├── augmented_generate.jsonl # 변형 데이터 (140개)
│   ├── train.jsonl             # 최종 학습용 (분할 후)
│   └── eval.jsonl              # 최종 평가용 (분할 후)
├── v2_qa/                # doc_qa 전용 (1,000개)
│   ├── aihub_qa.jsonl          # AI Hub 변환 (600개)
│   ├── synth_qa.jsonl          # 합성 데이터 (300개)
│   ├── augmented_qa.jsonl      # 변형 데이터 (100개)
│   ├── train.jsonl
│   └── eval.jsonl
├── v2_summary/           # doc_summary 전용 (1,000개)
│   ├── aihub_summary.jsonl     # AI Hub 변환 (700개)
│   ├── synth_summary.jsonl     # 합성 데이터 (200개)
│   ├── augmented_summary.jsonl # 변형 데이터 (100개)
│   ├── train.jsonl
│   └── eval.jsonl
└── v2_document/          # 공통 가이드 + 샘플
    └── FORMAT_GUIDE.md
```

## JSONL 포맷 (SFTTrainer용 messages 형식)

모든 데이터는 `{"messages": [...]}` 형식의 JSONL 파일입니다.

```jsonl
{"messages": [
  {"role": "system", "content": "태스크별 시스템 프롬프트"},
  {"role": "user", "content": "사용자 입력"},
  {"role": "assistant", "content": "모델이 학습할 출력"}
]}
```

## 어댑터별 데이터 설계

### 1. v2_generate (1,000개) — JSON 출력

assistant 응답은 반드시 **순수 JSON** (마크다운 코드블록 없이).

| 템플릿 | 필수 키 | 총량 | AI Hub | 합성 | 변형 |
|--------|---------|:----:|:------:|:----:|:----:|
| meeting_minutes | title, date, attendees, summary, decisions, action_items, risks | 400 | 40 (10%) | 280 (70%) | 80 (20%) |
| report | title, author, date, department, report_type, overview, main_content, tasks, issues, next_plan | 300 | 210 (70%) | 60 (20%) | 30 (10%) |
| proposal | title, submit_date, submit_to, company, manager, proposal_name, background, purpose, content, schedule, budget, budget_total, expected_effect | 300 | 210 (70%) | 60 (20%) | 30 (10%) |

**빈 필드 규칙**: 전체 데이터의 ~30%는 일부 선택 필드를 빈 문자열(`""`)이나 빈 배열(`[]`)로 포함.
실제 사용자 입력이 불완전한 경우를 학습하기 위함.

**meeting_minutes 참고**: 기업 회의록은 공개 데이터셋이 존재하지 않아 합성 중심으로 구성.
AI Hub 국회 회의록은 소량(40개)만 다양성 확보용으로 활용.

소스 비율 (템플릿별 차이 있음):

| 소스 | 비율 | 개수 | 비고 |
|------|:----:|:----:|------|
| AI Hub 원문 + GPT-4o 변환 | 46% | 460개 | report 210 + proposal 210 + meeting 40 |
| GPT-4o/Claude 합성 | 40% | 400개 | meeting 280 + report 60 + proposal 60 |
| 변형(구어체/오타) | 14% | 140개 | meeting 80 + report 30 + proposal 30 |

### 2. v2_qa (1,000개) — JSON 출력

> **중요**: v2_qa는 **일반 업무 문서**(회의록/보고서/기획서 등) 기반 QA입니다.
> 규정 QA는 v1_judgment 어댑터가 담당하므로 여기서 다루지 않습니다.

context는 프로덕션과 동일하게 **RAG 검색 결과 3~5개 청크**를 JSON 배열로 제공합니다.

```json
{
  "answer": "답변 텍스트",
  "citations": [
    {"source": "문서명", "content": "인용 내용", "relevance": "높음/중간/낮음"}
  ],
  "confidence": 0.0~1.0
}
```

소스 비율:

| 소스 | 비율 | 개수 |
|------|:----:|:----:|
| 행정 문서 기계독해 MRC 변환 (SN 569) | 30% | 300개 |
| 요약문 레포트 기반 QA 생성 (SN 582) | 30% | 300개 |
| GPT-4o/Claude 합성 | 30% | 300개 |
| 변형 (구어체 질문, 답 없는 경우) | 10% | 100개 |

### 3. v2_summary (1,000개) — 마크다운 출력

```markdown
핵심 요약 문장 (2~3문장)

## 주요 포인트
- 포인트 1
- 포인트 2

## 키워드
키워드1, 키워드2, 키워드3
```

소스 비율:

| 소스 | 비율 | 개수 |
|------|:----:|:----:|
| AI Hub 문서요약 변환 | 70% | 700개 |
| GPT-4o/Claude 합성 | 20% | 200개 |
| 변형 | 10% | 100개 |

## 전체 총량

| 어댑터 | 총량 | AI Hub | 합성 (GPT+Claude) | 변형 |
|--------|:----:|:------:|:------------------:|:----:|
| v2_generate | **1,000** | 460 (46%) | 400 (40%) | 140 (14%) |
| v2_qa | **1,000** | 600 (60%) | 300 (30%) | 100 (10%) |
| v2_summary | **1,000** | 700 (70%) | 200 (20%) | 100 (10%) |
| **합계** | **3,000** | **1,760 (59%)** | **900 (30%)** | **340 (11%)** |

> meeting_minutes만 합성 비율이 높은 이유: 기업 회의록 공개 데이터셋이 없어 GPT-4o/Claude로 직접 생성.

## AI Hub 데이터셋

| 데이터셋 | URL | 용도 | 저장 경로 |
|----------|-----|------|-----------|
| 요약문 및 레포트 생성 데이터 (SN 582) | https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=582 | v2_summary + v2_generate + v2_qa | `data/raw/aihub/summary_report/` |
| 행정 문서 대상 기계독해 (SN 569) | https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=569 | v2_qa (MRC 300개) | `data/raw/aihub/admin_mrc/` |

> 원본 데이터는 `data/raw/` 에 저장 (.gitignore 등록됨, 대용량)

## 파일 명명 규칙 (각 디렉토리 내)

- `aihub_*.jsonl` — AI Hub 변환 데이터
- `synth_*.jsonl` — GPT/Claude 합성 데이터
- `augmented_*.jsonl` — 변형 데이터
- `train.jsonl` — 최종 학습 데이터 (분할 후)
- `eval.jsonl` — 최종 평가 데이터 (분할 후)

## 학습 실행

```bash
# 기능별 학습
python ai/finetuning/train_v2_document.py --task generate --mode all
python ai/finetuning/train_v2_document.py --task qa --mode all
python ai/finetuning/train_v2_document.py --task summary --mode all

# 3개 모델 비교
python ai/finetuning/train_v2_document.py --task generate --mode compare

# 전체 일괄 학습
python ai/finetuning/train_v2_document.py --task all --mode all
```

## 품질 검증 (3단계 파이프라인)

### STEP 1: 자동 검증
```bash
python ai/finetuning/validate_v2_data.py --dir data/training/v2_generate
python ai/finetuning/validate_v2_data.py --dir data/training/v2_qa
python ai/finetuning/validate_v2_data.py --dir data/training/v2_summary
```
- JSON 유효성, 필수 필드 존재, 포맷 규칙 자동 검사

### STEP 2: LLM 교차 검증
- GPT-4o로 생성한 데이터 → Claude로 검증 (자연스러움, 정확성)
- Claude로 생성한 데이터 → GPT-4o로 검증
- 점수 하위 10%는 수정 또는 제거

### STEP 3: 수동 샘플링 검수
- 전체 3,000개 중 ~150개 (약 5%) 무작위 추출하여 직접 확인
- 어댑터별 50개씩: generate 50 + qa 50 + summary 50

## 변환 스크립트

```
ai/finetuning/scripts/
  aihub_explore.py              # AI Hub 데이터 탐색/분석
  convert_aihub_summary.py      # summary 700개 변환
  convert_aihub_generate.py     # generate report/proposal 420개 변환 (GPT-4o API 필요)
  convert_aihub_qa.py           # qa 600개 변환 (SN 569 MRC 300 + SN 582 레포트 QA 300)
```

```bash
# 데이터 탐색
python ai/finetuning/scripts/aihub_explore.py --dataset all

# 변환 실행 (순서대로)
python ai/finetuning/scripts/convert_aihub_summary.py
python ai/finetuning/scripts/convert_aihub_generate.py
python ai/finetuning/scripts/convert_aihub_qa.py
```

### Train/Eval 분할
```bash
python ai/finetuning/validate_v2_data.py --dir data/training/v2_generate --split --eval_ratio 0.1
python ai/finetuning/validate_v2_data.py --dir data/training/v2_qa --split --eval_ratio 0.1
python ai/finetuning/validate_v2_data.py --dir data/training/v2_summary --split --eval_ratio 0.15
```
