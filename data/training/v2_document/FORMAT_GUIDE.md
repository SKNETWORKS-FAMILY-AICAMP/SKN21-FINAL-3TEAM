# v2 Document 학습 데이터 형식 가이드

> 어댑터 분리 전략: 기능별 별도 LoRA 어댑터로 학습

## 디렉토리 구조

```
data/training/
├── v2_generate/          # doc_generate 전용 (380개)
│   ├── train.jsonl
│   └── eval.jsonl
├── v2_qa/                # doc_qa 전용 (300개)
│   ├── train.jsonl
│   └── eval.jsonl
├── v2_summary/           # doc_summary 전용 (200개)
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

### 1. v2_generate (380개) — JSON 출력

assistant 응답은 반드시 **순수 JSON** (마크다운 코드블록 없이).

| 템플릿 | 필수 키 | 목표 |
|--------|---------|------|
| meeting_minutes | title, date, attendees, summary, decisions, action_items, risks | 150개 |
| report | title, author, date, department, report_type, overview, main_content, tasks, issues, next_plan | 130개 |
| proposal | title, submit_date, submit_to, company, manager, proposal_name, background, purpose, content, schedule, budget, budget_total, expected_effect | 100개 |

소스 비율:

| 소스 | 비율 | 개수 |
|------|:----:|:----:|
| AI Hub 실제 데이터 | 40% | ~150개 |
| GPT-4o 합성 | 30% | ~115개 |
| Claude 합성 | 15% | ~55개 |
| 변형(구어체/오타) | 15% | ~60개 |

### 2. v2_qa (300개) — JSON 출력

```json
{
  "answer": "답변 텍스트",
  "citations": [
    {"source": "조항/문서명", "content": "인용 내용", "relevance": "높음/보통/낮음"}
  ],
  "confidence": 0.0~1.0
}
```

소스 비율:

| 소스 | 비율 | 개수 |
|------|:----:|:----:|
| AI Hub 기계독해 | 50% | 150개 |
| GPT-4o 합성 | 25% | 75개 |
| Claude 합성 | 15% | 45개 |
| 변형 | 10% | 30개 |

### 3. v2_summary (200개) — 마크다운 출력

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
| AI Hub 문서요약 | 50% | 100개 |
| GPT-4o 합성 | 25% | 50개 |
| Claude 합성 | 15% | 30개 |
| 변형 | 10% | 20개 |

## 전체 총량

| 어댑터 | 데이터 | AI Hub | 합성 | 변형 |
|--------|:------:|:------:|:----:|:----:|
| v2_generate | **380개** | 150 (40%) | 170 (45%) | 60 (15%) |
| v2_qa | **300개** | 150 (50%) | 120 (40%) | 30 (10%) |
| v2_summary | **200개** | 100 (50%) | 80 (40%) | 20 (10%) |
| **합계** | **880개** | **400** | **370** | **110** |

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

## 검증

```bash
python ai/finetuning/validate_v2_data.py --dir data/training/v2_generate
python ai/finetuning/validate_v2_data.py --dir data/training/v2_qa
python ai/finetuning/validate_v2_data.py --dir data/training/v2_summary
python ai/finetuning/validate_v2_data.py --dir data/training/v2_generate --split --eval_ratio 0.1
```
