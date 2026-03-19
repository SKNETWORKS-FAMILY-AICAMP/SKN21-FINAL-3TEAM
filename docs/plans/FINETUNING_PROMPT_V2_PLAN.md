# 파인튜닝 System Prompt 수정 + 데이터 재생성 플랜

> 작성일: 2026-03-04
> 상태: 코드 수정 완료 ([1]~[4]) / 데이터 재생성 미실행 ([5]~[6])

## 배경

sLLM 파인튜닝(v2_summary, v2_qa, v2_generate) 전 프롬프트 + 데이터 품질 전수 검토 결과, **3개 어댑터 모두 prompt 수정 필요**. 기존 데이터는 초기화하고 수정된 스크립트로 전량 재생성.

## 해결한 이슈 11개

1. v2_qa citations 복수 케이스 0건 → 스크립트에서 복수 생성 로직 추가
2. v2_summary 포인트 2개 이하 128건 → 필터 추가 (3개 이상만 통과)
3. prompts.py 변경이 현 LLM API에 영향 → **sLLM 전용 상수 분리** (기존 건드리지 않음)
4. v2_generate 프로덕션 리팩토링 → sLLM 전환 시 동적 필드로 변경
5. `<출력 형식>` 태그 혼동 위험 → 태그 없이 직접 구조만 제시
6. v2_summary 괄호 설명 `(2~3문장)` leak 위험 → 괄호 제거, 규칙 섹션으로 이동
7. v2_qa citation 매칭 부정확 (substring) → 퍼지 매칭 + 매칭 실패 시 샘플 제외
8. v2_qa 부정 예시 품질 낮음 (단순 rotation) → 카테고리 교차 매칭으로 개선
9. 스크립트에 sys.path 없어 import 불가 → `sys.path.insert(0, str(BASE_DIR))` 추가
10. not-found 문구 불일치 (프롬프트 vs 스크립트) → 프롬프트 기준 통일
11. convert_aihub_qa.py에 not-found 로직 없음 → 카테고리 교차 not-found 추가

## 아키텍처: sLLM 프롬프트 분리 전략

```python
# ai/llm/prompts.py

# === 기존 LLM API용 (GPT/Claude — 프로덕션, 수정 안 함) ===
DOC_QA_SYSTEM_PROMPT = """..."""
DOC_SUMMARY_SYSTEM_PROMPT = """..."""
DOCUMENT_SYSTEM_PROMPT = """..."""

# === sLLM 파인튜닝/서빙용 (vLLM + LoRA — 신규 추가) ===
DOC_QA_SLLM_PROMPT = """...(간소화: answer + citations[].content만)..."""
DOC_SUMMARY_SLLM_PROMPT = """...(태그/괄호 제거, 형식 직접 제시)..."""
DOC_GENERATE_SLLM_PROMPT = """...(복사 금지 규칙 추가)..."""
```

## 어댑터별 최종 프롬프트

### v2_qa — `DOC_QA_SLLM_PROMPT`
- JSON: `{"answer": "...", "citations": [{"content": "..."}]}`
- confidence/source/relevance 제거 (백엔드가 RAG score 기반으로 채움)
- not-found: `"제공된 문서에서 해당 내용을 찾을 수 없습니다."` + `citations: []`
- sLLM 서빙: **비스트리밍(JSON) 전용**, not-found 감지는 `citations == []`

### v2_summary — `DOC_SUMMARY_SLLM_PROMPT`
- `<출력 형식>` 태그 제거 (Qwen3 `<|im_start|>` 혼동 방지)
- 괄호 설명 제거 → 규칙 섹션으로 이동
- 포인트 3~5개, 키워드 3~7개 (규칙으로 명시)

### v2_generate — `DOC_GENERATE_SLLM_PROMPT`
- "필드 설명이나 지침 문장을 그대로 값으로 출력하지 마세요" 규칙 추가
- "적절한 값을 생성하세요" → "입력 내용을 바탕으로 구체적인 문서 내용을 작성하세요"

## 수정된 파일 8개 (완료)

| 파일 | 수정 내용 |
|------|-----------|
| `ai/llm/prompts.py` | sLLM 전용 상수 3개 추가 (기존 유지) |
| `ai/finetuning/scripts/convert_aihub_qa.py` | JSON 간소화 + citations 복수 + 퍼지 매칭 + not-found(카테고리 교차) |
| `ai/finetuning/scripts/convert_to_dynamic_fields.py` | SYSTEM_PROMPT 교체 |
| `ai/finetuning/scripts/convert_aihub_summary.py` | SYSTEM_PROMPT 교체 + 포인트 3개 미만 필터 |
| `ai/finetuning/scripts/synthesize_qa.py` | JSON 간소화 + 카테고리 교차 not-found + 비율 12% |
| `ai/finetuning/scripts/synthesize_generate.py` | SYSTEM_PROMPT 교체 |
| `ai/finetuning/scripts/synthesize_summary.py` | SYSTEM_PROMPT 교체 |
| `ai/finetuning/validate_v2_data.py` | QA 스키마 업데이트 + citations 분포 리포트 |

## 미실행: 데이터 재생성 [5]~[6]

```bash
# [5] 기존 데이터 삭제 후 재생성
rm -f data/training/v2_qa/*.jsonl
rm -f data/training/v2_summary/*.jsonl
rm -f data/training/v2_generate/*.jsonl

# v2_qa MRC (API 불필요)
python ai/finetuning/scripts/convert_aihub_qa.py --source mrc

# v2_qa Report (GPT-4o ~$12)
python ai/finetuning/scripts/convert_aihub_qa.py --source report

# v2_summary (API 불필요 / --llm-enhance 시 ~$0.7)
python ai/finetuning/scripts/convert_aihub_summary.py
python ai/finetuning/scripts/convert_aihub_summary.py --llm-enhance

# v2_generate (기존 백업 데이터 변환)
python ai/finetuning/scripts/convert_to_dynamic_fields.py

# [6] 검증 + 분할
python ai/finetuning/validate_v2_data.py --deduplicate
python ai/finetuning/validate_v2_data.py --split
```

**예상 비용**: ~$13 (v2_qa Report $12 + v2_summary 키워드 $0.7)

## 검증 기준

1. `validate_v2_data.py` → 에러 0건
2. v2_qa: JSON에 `answer` + `citations[].content`만 존재
3. v2_qa: citations 길이 분포 — 1개 70~80%, 2개 15~20%, 3개 5~10%
4. v2_qa: not-found 10~15%
5. v2_generate: 476건 유지
6. v2_summary: 포인트 3개 미만 0건
7. 학습 데이터 `messages[0]["content"]`와 `prompts.py` sLLM 상수가 byte-for-byte 일치

## 후속 작업 (sLLM 전환 시 — 이번 범위 밖)

- `document_agent.py`: provider 타입 분기 → sLLM이면 `_SLLM_PROMPT` 사용
- `document_agent.py`: `_handle_doc_qa()`에서 confidence를 RAG score 기반 계산
  - `avg(search_scores) * 0.7 + min(citation_count/3, 1.0) * 0.3`
  - not-found (`citations == []`) → confidence = 0.1 고정
- `document_agent.py`: `_generate_*()` 3개 함수 → 동적 필드 방식으로 리팩토링
- vLLM json_mode + LoRA 호환성 테스트 필요
