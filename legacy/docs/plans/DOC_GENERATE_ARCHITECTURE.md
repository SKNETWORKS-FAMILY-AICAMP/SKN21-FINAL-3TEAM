# 문서 생성 아키텍처 정리

## 날짜: 2026-03-25

---

## 1. 전체 파이프라인

```
사용자 입력 (자연어)
       │
       ▼
┌──────────────────┐
│  fill-fields API │  sLLM(LoRA) 1회 호출
│  데이터 생성      │  자연어 → 구조화된 JSON
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  DOCX 채우기      │  sLLM 호출 없음
│                  │
│  기본템플릿:      │  → create 빌더 (python-docx)
│  커스텀템플릿:    │  → placeholder 치환 (docxtpl)
└────────┬─────────┘
         │
         ▼
    완성된 DOCX
```

---

## 2. 기본 템플릿 (시스템 빌더)

### 대상
- 기본 회의록 (`create_meeting_minutes.py`)
- 기본 보고서 (`create_report.py`)
- 기본 제안서 (`create_proposal.py`)

### 흐름
1. 사용자 폼 입력 → `_build_narrative_input()`으로 서술형 변환
2. sLLM 호출 → 구조화된 JSON 생성
3. 시스템 빌더가 python-docx로 DOCX 생성
4. 배열 필드(action_items, tasks, schedule, budget)는 **동적 행 추가**

### 동적 행 추가
- `max(len(data), 3)` — 데이터 수만큼 행 생성, 최소 3행 유지
- `table.add_row()`로 동적 확장

---

## 3. 커스텀 템플릿 (placeholder 방식)

### 대상
- 사용자가 업로드한 모든 DOCX 양식

### 흐름

#### 업로드 시 (1회)
```
원본 DOCX
    │
    ▼
template_extractor.py
  - 라벨|빈칸 패턴 감지
  - 배열 테이블 감지 (패턴 A: 병합헤더+No. / 패턴 B: C0 라벨 반복)
  - sub_keys 추출 (컬럼 헤더)
  - description 생성 (JSON 예시 형태 — LoRA 학습 형식과 동일)
    │
    ▼
parsed_structure → DB 저장
    │
    ▼
placeholder_inject.py
  - 빈 셀에 {{key}} 삽입
  - 배열 테이블에 {%tr for/endfor%} XML 행 삽입
  - 빈 데이터 행 제거 (루프가 자동 생성하므로)
    │
    ▼
_tpl.docx 저장
```

#### 문서 생성 시 (매번)
```
fill-fields API (sLLM 1회)
  - DB에서 parsed_structure의 description 읽기
  - 프롬프트 조립: [필드 명세] + [내용]
  - sLLM → JSON 데이터 반환
    │
    ▼
fill_with_placeholder.py (docxtpl)
  - _tpl.docx 로드
  - {{key}} → 데이터 치환
  - {%tr for%} → 배열 행 자동 복제
  - sLLM 호출 없음, 단순 치환
    │
    ▼
완성된 DOCX
```

### placeholder_inject.py 감지 패턴

| 패턴 | 구조 | 처리 |
|------|------|------|
| 라벨\|빈칸 (가로) | `회의 제목 \| (빈)` | `{{key}}` 삽입 |
| 라벨 위+값 아래 (세로) | `작성 \| 검토 \| 승인` 아래 빈 행 | `{{key}}` 삽입 |
| 1열 섹션 | `결정 사항` 헤더 + 아래 빈 셀 | `{{key}}` 삽입 |
| 배열 패턴 A | 병합 헤더 + No. + 컬럼 헤더 | `{%tr for/endfor%}` + `{{item.sub_key}}` |
| 배열 패턴 B | C0 같은 라벨 3회+ 반복 | `{%tr for/endfor%}` + `{{item.sub_key}}` |

### fill_with_placeholder.py sub_key 매핑

- data key(영문)와 placeholder key(한글 컬럼 헤더)가 다를 수 있음
- `_SUB_KEY_ALIASES` 이름 기반 매핑으로 자동 변환
- 예: `amount` → `금액`, `task` → `Action Item`

---

## 4. 핵심 개선 사항 (이번 세션)

### 4-1. sLLM 프롬프트 description 통일
- **문제**: 기본템플릿은 JSON 예시 형태, 커스텀은 텍스트 나열 → sLLM이 문자열로 반환
- **해결**: `template_extractor._build_array_desc()`로 JSON 예시 형태 자동 생성
- **효과**: 커스텀 배열 필드도 dict 배열로 정확히 반환

```
이전: "각 항목은 업무 항목, 담당자, 진행률 필드를 가진 객체 배열"
이후: '목록 배열. 각 항목은 {"업무 항목": "업무 항목", "담당자": "담당자"} 형태'
```

### 4-2. placeholder 방식 도입
- **문제**: fill_with_llm이 매번 sLLM으로 셀 매핑 → 비결정적, 불안정
- **해결**: 업로드 시 1번 {{key}} 삽입, 생성 시 docxtpl 치환
- **효과**: 매핑 sLLM 호출 제거, 100% 결정적, 속도 향상

### 4-3. 기본 빌더 동적 행 추가
- **문제**: Action Item, tasks 등 고정 3~4행 → 데이터 많으면 잘림
- **해결**: `max(len(data), 3)` 행 + `table.add_row()` 동적 확장

### 4-4. 체크박스 텍스트 제거
- 시스템 빌더: `☐ 정기 ☐ 비정기 ☐ 긴급` → 텍스트만 (`정기`)
- 커스텀 DOCX: 체크박스 문자 제거

---

## 5. 파일 구조

```
ai/skills/
  placeholder_inject.py    — 원본 DOCX에 {{key}} 자동 삽입 (신규)
  fill_with_placeholder.py — docxtpl로 데이터 치환 (신규)
  fill_with_llm.py         — sLLM 매핑 방식 (기존, fallback용 유지)
  create_meeting_minutes.py — 기본 회의록 빌더
  create_report.py          — 기본 보고서 빌더
  create_proposal.py        — 기본 제안서 빌더

ai/document_parser/
  template_extractor.py    — DOCX 양식 필드 추출 + description 생성

backend/app/
  services/template_service.py — 기본 템플릿 정의 (parsed_structure)
  api/v1/documents.py          — fill-fields API, generate API
```

---

## 6. 테스트 결과 (sLLM 실데이터)

| 템플릿 | placeholder 삽입 | sLLM 데이터 | 최종 DOCX |
|--------|-----------------|------------|----------|
| 회의록(기본) | 11/11 | 7/11 (LoRA) | ✅ ActionItem 5행 |
| 보고서(기본) | 15/15 | 13/15 | ✅ 진행현황 3행 |
| 제안서(기본) | 18/18 | 14/18 | ✅ 추진일정 4행, 소요예산 4행 |
| 회의록양식2 | 8/8 | 7/8 | ✅ 결정사항 3행 |
| 회의록양식3 | 5/5 | 5/5 | ✅ |
| 보고서1 | 3/5 (실질3/3) | 4/5 | ✅ |

---

## 7. 한계 및 향후 개선

### 현재 한계
- sLLM이 일부 필드를 None으로 반환 (프롬프트 품질 아닌 모델 한계)
- 비정형 양식 (라벨 없는 빈칸, 2행 미만 배열)은 자동 감지 불가
- LoRA fallback 시 base 모델이 제대로 답변 못 함

### 향후 개선 방향
1. **UX 개선**: 업로드 후 "템플릿 검토" 화면 — 자동 감지 결과 확인 + 수동 수정
2. **LLM 보조 감지**: 규칙으로 못 잡는 10%를 업로드 시 LLM 1회로 보강
3. **사용자 가이드**: `{{key}}`, `{%tr for %}` 문법 안내 (고급 사용자용)
4. **_generate.py 연동**: placeholder 경로를 실제 서비스 파이프라인에 연결
