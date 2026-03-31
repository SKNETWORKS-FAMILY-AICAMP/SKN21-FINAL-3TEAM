# QA Baseline 실험 설계

**날짜**: 2026-02-21
**담당**: 진승언 (AI 리드)
**목적**: QA Agent 파인튜닝 전 baseline 성능 측정

---

## 배경

프로젝트의 QA Agent 기능 구현을 위해 두 한국어 sLLM의 QA 능력을 사전 평가한다.
성능이 더 우수한 모델을 선정하여 이후 파인튜닝에 활용한다.

---

## 대상 모델

| 모델 | 파라미터 | 양자화 방식 |
|------|----------|------------|
| `K-intelligence/Midm-2.0-Base-Instruct` | 11.5B | bitsandbytes 4-bit (NF4) |
| `skt/A.X-3.1-Light` | 7B | bitsandbytes 4-bit (NF4) |

실행 환경: Google Colab L4 (24GB VRAM), 모델 순차 실행

---

## 데이터

**파일**: `ai/data/qa_samples.json`
**총 40건**: 일반 도메인 20건 + 회사 업무 20건

### 포맷
```json
{
  "id": "biz_001",
  "domain": "business",
  "context": "...",
  "question": "...",
  "answer": "..."
}
```

### 도메인 구성
- **general (20건)**: 한국 시사, 상식, 과학, 역사 등 짧은 지문 기반 QA
- **business (20건)**: 회의록, 프로젝트 보고서, 업무 이메일 맥락의 QA

---

## 실험 코드

**파일**: `ai/experiments/run_qa_baseline.py`

### 실행 방식
```bash
python ai/experiments/run_qa_baseline.py           # 두 모델 모두
python ai/experiments/run_qa_baseline.py --model midm
python ai/experiments/run_qa_baseline.py --model ax
```

### 프롬프트 템플릿
```
[지문]
{context}

[질문]
{question}

[답변]
```
→ `tokenizer.apply_chat_template()` 사용

### 평가 지표 (정량)
| 지표 | 설명 |
|------|------|
| ROUGE-L | 예측/정답 간 최장 공통 부분 수열 F1 |
| Token F1 | SQuAD 방식 토큰 overlap F1 |

→ 도메인별(general / business) + 전체 평균 모두 산출

---

## 출력 파일

| 파일 | 내용 |
|------|------|
| `results/qa_quantitative.json` | 모델별 정량 지표 요약 |
| `results/qa_qualitative.json` | 전체 예측 답변 저장 (정성 검토용) |

---

## 이후 단계

1. 두 모델 결과 비교 → 더 우수한 모델 선정
2. 선정 모델 기반 QA 데이터 수집 (파인튜닝용)
3. LoRA/QLoRA 파인튜닝 적용 (4단계)
