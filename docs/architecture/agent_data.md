# Agent 데이터 수집 가이드

Judgment Agent와 Document Agent에 필요한 RAG 문서와 파인튜닝 데이터 정리.

---

## 1. 데이터 유형 요약

### Document Agent

| 기능 | RAG 문서 | 파인튜닝 데이터 | 비고 |
|------|---------|--------------|------|
| doc_search | O (전체 문서) | X | LLM은 결과 정리용만 |
| doc_generate | X | O (LoRA v2) | 템플릿 기반 생성 |
| doc_summary | X | O (LoRA v2) | 고정 포맷 요약 |
| doc_qa | O (비규정 문서) | O (LoRA v2) | 답변 + 인용 |

### Judgment Agent

| 기능 | RAG 문서 | 파인튜닝 데이터 | 비고 |
|------|---------|--------------|------|
| judgment (규정 판단) | O (규정 문서) | O (LoRA v1) | yes/no/conditional/no_regulation |
| regulation_qa (규정 QA) | O (규정 문서) | O (LoRA v1) | 규정 해석 답변 |

---

## 2. RAG 문서 수집

### 2-1. 수집 대상

| 분류 | 문서 종류 | 예시 | 사용 기능 |
|------|----------|------|----------|
| 규정 문서 (regulation) | 사내 규정/규칙/지침 | 인사규정, 보안규정, 복무규정, 출장규정, 급여규정 | doc_search, Judgment |
| 업무 문서 (business) | 업무 산출물 | 회의록, 보고서, 기획서, 제안서, 프로젝트 문서 | doc_search, doc_qa |

### 2-2. 수집 방식

- **규정 문서**: 관리자가 시스템에 사전 등록 (PDF, DOCX)
- **업무 문서**: 사용자가 직접 업로드

### 2-3. 인덱싱 요구사항

```
문서 파일 (PDF/DOCX)
      │
      ▼
 텍스트 추출 (Docling / python-docx)
      │
      ▼
 청킹 (의미 단위 — 조항별 or 단락별)
      │
      ▼
 임베딩 (현재: jhgan/ko-sbert-nli, 768dim) + 메타데이터
      │
      ├──→ Qdrant 저장 (벡터 검색)
      └──→ BM25 인덱스 (키워드 검색)
```

### 2-4. 메타데이터

각 청크에 필요한 메타데이터:

```json
{
  "source": "인사규정.pdf",
  "title": "인사규정",
  "chapter": "제3장 근로시간 및 휴가",
  "article": "제8조",
  "category": "regulation | business",
  "scope": "company | personal",
  "user_id": 123,
  "uploaded_at": "2026-02-22"
}
```

- `category: "regulation"` → Judgment, doc_search에서 사용
- `category: "business"` → doc_qa, doc_search에서 사용
- doc_search는 category 필터 없이 전체 검색

### 2-5. 최소 수집 목표

| 분류 | 문서 수 | 청크 수 (예상) |
|------|--------|--------------|
| 규정 문서 | 5~10개 | 200~500개 |
| 업무 문서 | 20~30개 | 500~1000개 |

---

## 3. Document Agent 파인튜닝 데이터

### 3-1. 공통 사항

- **수집 방식**: LLM API 호출 시 input/output을 chat_logs에 자동 저장
- **포맷**: JSON (LLM이 JSON mode로 출력하므로 그대로 학습 데이터로 사용)
- **목표 모델**: 미정 (현재 LLM API 사용, 추후 sLLM 교체 시 결정)
- **포맷**: JSONL (`instruction`, `input`, `output` 3필드) — Judgment Agent와 통일
- **최소 데이터 수**: 기능당 200~500쌍 (초기 목표)

### 3-2. doc_generate (문서 생성)

**학습 목표**: 사용자 요청 + 템플릿 타입 → 완성된 문서 JSON

| 항목 | 내용 |
|------|------|
| Input | `(user_request, template_type)` |
| Output | 템플릿 필드가 채워진 JSON |
| 템플릿 종류 | meeting_minutes, report, jd, proposal |

**데이터 예시**:

```jsonl
{
  "instruction": "사용자의 요청과 템플릿 타입을 참고하여 완성된 문서를 JSON 형태로 생성하세요.",
  "input": "template_type: meeting_minutes\nrequest: 2월 20일 마케팅팀 주간회의 회의록 작성해줘. 참석자는 김팀장, 이대리, 박사원. SNS 마케팅 예산 500만원 승인, 3월 캠페인 일정 확정.",
  "output": "{\"title\": \"마케팅팀 주간회의\", \"date\": \"2026-02-20\", \"attendees\": [\"김팀장\", \"이대리\", \"박사원\"], \"summary\": \"SNS 마케팅 예산 및 3월 캠페인 일정 논의\", \"decisions\": [\"SNS 마케팅 예산 500만원 승인\", \"3월 캠페인 일정 확정\"], \"action_items\": [{\"content\": \"캠페인 상세 기획안 작성\", \"assignee\": \"이대리\", \"due_date\": \"2026-02-27\"}]}"
}
```

**수집 방법**:
1. 실제 회의록/보고서/제안서 샘플 수집
2. 각 샘플에서 (요청문, 완성 JSON) 쌍 생성
3. LLM API로 생성한 결과를 chat_logs에서 추출

**템플릿별 목표**:

| 템플릿 | 데이터 수 | 수집 난이도 |
|--------|----------|-----------|
| meeting_minutes | 100~200 | 중 (회의록 샘플 필요) |
| report | 50~100 | 중 |
| jd | 50~100 | 하 (공개 JD 많음) |
| proposal | 50~100 | 중 |

### 3-3. doc_summary (문서 요약)

**학습 목표**: 문서 본문 → 고정 포맷 요약 JSON

| 항목 | 내용 |
|------|------|
| Input | `(document_text)` |
| Output | `{ title, core_summary, key_points, keywords }` |
| 고정 포맷 | title + core_summary(2~3문장) + key_points(3~7개) + keywords(3~5개) |

**데이터 예시**:

```jsonl
{
  "instruction": "문서 본문을 읽고 title, core_summary(2~3문장), key_points(3~7개), keywords(3~5개) 형태로 요약하세요.",
  "input": "2026년 1분기 마케팅 성과 보고서\n\n1. 개요\nSNS 채널 중심의 디지털 마케팅을 집중 운영하였으며...(생략)...",
  "output": "{\"title\": \"2026년 1분기 마케팅 성과 보고서\", \"core_summary\": \"1분기 SNS 중심 디지털 마케팅 결과 전년 대비 매출 15% 증가. 인스타그램 팔로워 2만명 증가, 전환율 3.2% 달성.\", \"key_points\": [\"SNS 마케팅 예산 대비 ROI 180% 달성\", \"인스타그램 채널 팔로워 2만명 증가\", \"전환율 3.2%로 목표(3.0%) 초과 달성\", \"2분기 예산 20% 증액 제안\"], \"keywords\": [\"마케팅\", \"SNS\", \"ROI\", \"전환율\"]}"
}
```

**수집 방법**:
1. 다양한 업무 문서(회의록, 보고서, 기획서) 본문 수집
2. LLM API로 고정 포맷 요약 생성 → chat_logs에서 추출
3. 사람이 품질 검수 (포맷 준수 여부)

**목표**: 200~300쌍

### 3-4. doc_qa (문서 QA)

**학습 목표**: 질문 + RAG 검색 컨텍스트 → 답변 + 인용

| 항목 | 내용 |
|------|------|
| Input | `(question, context_chunks[])` |
| Output | `{ answer, citations[{source, content, relevance}], confidence }` |
| 검색 대상 | 비규정 업무 문서 (회의록, 보고서, 기획서 등) |

**데이터 예시**:

```jsonl
{
  "instruction": "업무 문서 컨텍스트를 참고하여 질문에 답변하고, 인용 출처를 반드시 포함하세요.",
  "input": "[질문]\n지난 마케팅 회의에서 결정된 예산은?\n\n[컨텍스트]\n[1] (마케팅팀_주간회의_0220.md) SNS 마케팅 예산 500만원 승인...\n[2] (2분기_마케팅_기획서.md) 2분기 마케팅 예산 총 2000만원...",
  "output": "{\"answer\": \"지난 마케팅 회의에서 SNS 마케팅 예산 500만원이 승인되었습니다. 또한 2분기 마케팅 예산은 총 2000만원으로 편성되어 있습니다.\", \"citations\": [{\"source\": \"마케팅팀_주간회의_0220.md\", \"content\": \"SNS 마케팅 예산 500만원 승인\", \"relevance\": \"높음\"}, {\"source\": \"2분기_마케팅_기획서.md\", \"content\": \"2분기 마케팅 예산 총 2000만원\", \"relevance\": \"보통\"}], \"confidence\": 0.9}"
}
```

**수집 방법**:
1. RAG 인덱싱된 업무 문서 기반으로 질문 생성
2. LLM API에 (질문 + context_chunks) 입력 → (답변 + 인용) 출력
3. chat_logs에서 자동 추출
4. 인용 정확도 검수 (실제 context에 해당 내용 있는지)

**목표**: 200~500쌍

---

## 4. Judgment Agent 파인튜닝 데이터

### 4-1. 공통 사항

- **수집 방식**: Excel 데이터 확보 → JSONL 변환 + LLM API 호출 로그 추출
- **포맷**: JSONL (`instruction`, `input`, `output` 3필드)
- **목표 모델**: Kanana-1.5-8B 기반 LoRA v1
- **합계 목표**: 2,000쌍 (판단 1,000 + Q&A 1,000)

### 4-2. judgment (규정 판단)

**학습 목표**: 규정 컨텍스트 + 사용자 질문 → 판단 결과(yes/no/conditional/no_regulation) + 근거 + 대안

| 항목 | 내용 |
|------|------|
| Input | `(규정 조항 텍스트, 사용자 질문)` |
| Output | `결과 + 신뢰도 + 근거 + 조건(conditional일 때) + 대안` |
| 판단 카테고리 | `yes`, `no`, `conditional`, `no_regulation` |

**데이터 예시**:

```jsonl
{
  "instruction": "사내 규정을 기반으로 Yes/No/Conditional/No Regulation 중 하나로 판단하고, 근거 조항과 대안을 제시하세요.",
  "input": "[규정]\n제10조 복무의무\n직원은 회사 자산에 대한 무단 접근을 금지한다. 단, 업무상 필요 시 팀장 승인 하에 예외 접근이 가능하다.\n\n[질문]\n인턴에게 AWS 콘솔 접근 권한을 줘도 되나요?",
  "output": "결과: conditional\n신뢰도: 0.85\n근거: 제10조 복무의무에 따라 회사 자산(AWS 콘솔)에 대한 무단 접근은 금지되나, 업무상 필요 시 팀장 승인으로 예외 가능합니다.\n조건: 팀장 사전 승인 필요, 업무 범위 내 최소 권한 부여\n대안: 일일 임시 권한 발급, 테스트 환경 전용 계정 사용"
}
```

**수집 방법**:
1. 확보된 판단 데이터 1,000건 (Excel) → JSONL 변환
2. 각 건에 관련 규정 조항을 `[규정]` 섹션으로 매핑
3. LLM API 운영 중 chat_logs에서 추가 수집

**카테고리별 분포 목표**:

| 카테고리 | 데이터 수 | 비율 |
|----------|----------|------|
| yes | 250~300 | 25~30% |
| no | 250~300 | 25~30% |
| conditional | 250~300 | 25~30% |
| no_regulation | 100~200 | 10~20% |

**목표**: 1,000쌍

### 4-3. regulation_qa (규정 Q&A)

**학습 목표**: 규정 관련 질문 → 규정 해석 답변

| 항목 | 내용 |
|------|------|
| Input | `(규정 조항 텍스트, 사용자 질문)` |
| Output | 규정 해석 기반 답변 |
| 대상 규정 | 인사규정, 보안규정, 복무규정, 출장규정, 급여규정 등 |

**데이터 예시**:

```jsonl
{
  "instruction": "사내 규정을 참고하여 질문에 정확하게 답변하세요. 근거 조항을 반드시 포함하세요.",
  "input": "[규정]\n제15조 연차유급휴가\n1년간 80% 이상 출근한 직원에게 15일의 유급휴가를 부여한다. 3년 이상 근속자는 2년마다 1일씩 가산한다.\n\n[질문]\n5년차 직원인데 연차가 며칠인가요?",
  "output": "제15조 연차유급휴가에 따라, 5년차 직원의 연차는 16일입니다. 기본 15일에 3년 이상 근속 가산(2년마다 1일)으로 1일이 추가됩니다. (3년차 +1일, 5년차는 아직 2회차 가산 미도달)"
}
```

**수집 방법**:
1. 기존 Q&A 데이터 500건 검증
2. 규정 문서별 예상 질문 생성 (LLM 합성)
3. LLM API 운영 중 chat_logs에서 추가 수집

**목표**: 1,000쌍 (기존 500 + 추가 500)

### 4-4. Judgment Agent 데이터 현황

| 데이터 | 건수 | 상태 | 담당 |
|--------|:----:|------|------|
| 규정 판단 (judgment) | 1,000 | Excel 확보 → JSONL 변환 필요 (#9) | 경은 |
| 규정 Q&A (regulation_qa) | 500 | 기존 확보, 추가 500건 수집 필요 | 경은 |

### 4-5. Confidence 보정용 학습 참고

파인튜닝 시 output에 신뢰도(confidence)를 포함하되, 실제 서빙 시에는 아래 4중 보정이 적용됨:

| 보정 장치 | 설명 | 감점 방식 |
|-----------|------|---------|
| 환각 탐지 | LLM 인용 조항이 RAG에 존재하는지 확인 | `(0.5 - match_ratio) × 0.3` |
| 조항 검증 | 인용 조항명이 실제 존재하는지 검증 | `0.05 × missing_count` |
| 카테고리 제한 | 4가지 외 결과 자동 reject | confidence → `min(raw, 0.3)` |
| 일관성 모니터링 | 동일 질문 다른 답변 시 flag | flag만 (감점 X) |

→ 학습 데이터의 confidence는 "LLM raw 값"이며, 보정은 추론 시 코드에서 처리

---

## 5. 데이터 수집 우선순위

```
Phase 1 (3단계: Agent 개발 중)
 ├─ RAG 문서 인덱싱 (규정 5~10개 + 업무 20~30개)
 └─ LLM API 호출 시 chat_logs 자동 저장 시작

Phase 2 (4단계: 데이터 수집 + 파인튜닝)
 ├─ [Judgment] Excel 1,000건 → JSONL 변환 (LoRA v1 우선)
 ├─ [Judgment] Q&A 500건 추가 수집
 ├─ [Document] chat_logs에서 파인튜닝 데이터 추출
 ├─ 부족한 데이터는 LLM으로 합성 생성 (augmentation)
 └─ 품질 검수 후 학습 데이터셋 확정

Phase 3 (4단계: LoRA 학습)
 ├─ Kanana-1.5-8B 기반 LoRA v1 학습 (Judgment Agent) → sLLM 교체
 └─ LoRA v2 학습 (Document Agent, 베이스 모델 미정) → sLLM 교체
```

---

## 6. 데이터 품질 기준

### Document Agent

| 항목 | 기준 |
|------|------|
| JSONL 파싱 가능 | 모든 행이 valid JSON, 3필드(instruction/input/output) 필수 |
| 포맷 준수 | doc_summary: 4필드 필수 / doc_qa: citations 필수 |
| 인용 정확도 | doc_qa의 citation.content가 실제 context에 존재 |
| 한국어 품질 | 자연스러운 한국어, 존칭 통일 |
| 길이 제한 | core_summary: 2~3문장 / key_points: 3~7개 / keywords: 3~5개 |

### Judgment Agent

| 항목 | 기준 |
|------|------|
| JSONL 파싱 가능 | 모든 행이 valid JSON, 3필드(instruction/input/output) 필수 |
| 카테고리 정확성 | output의 결과가 yes/no/conditional/no_regulation 중 하나 |
| 근거 조항 존재 | output에 규정 조항 번호가 반드시 포함 |
| 카테고리 분포 | 4가지 결과가 편중 없이 균등 분포 (±10%) |
| 한국어 품질 | 자연스러운 한국어, 존칭 통일 |
| input 규정 매핑 | `[규정]` 섹션의 조항이 실제 규정 문서에 존재 |
