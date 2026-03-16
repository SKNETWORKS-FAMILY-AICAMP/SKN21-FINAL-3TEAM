# 문서 생성 시스템 개선 — 최종 실행 계획

## 한 줄 요약

> 시스템 템플릿은 **LoRA 재학습(데이터 정제)**으로, 커스텀 템플릿은 **프롬프트 추출(description 기반)**로 개선한다.

---

## 확정된 설계

### 전체 구조

```
[시스템 템플릿] 회의록/보고서/제안서
  → LoRA가 전체 필드 생성 (현재 v2 방식 유지, 데이터 정제 후 재학습)
  → 사용자 입력 필드(title, date, attendees 등)는 폼 값으로 덮어쓰기

[커스텀 템플릿] 사용자 업로드 양식
  → 1단계: LoRA가 content/summary 생성 (학습된 키)
  → 2단계: content에서 커스텀 필드 프롬프트 추출 (description이 힌트)
  → 사용자 입력 필드(role="input")는 폼 값으로 덮어쓰기
```

### 필드 역할 구분

```
role="input"     : 사용자가 폼에서 입력 (title, date, attendees, author 등)
role="generated" : AI가 생성 (content, summary, decisions, 커스텀 필드 등)

최종 문서 = input 필드 + generated 필드 합산 → DOCX 빌더
```

### 시스템 vs 커스텀 분기

```python
if is_system_template:
    # LoRA 1회 호출로 전체 필드 생성 (기존 방식 유지)
    data = await _call_llm(...)  # task="generate", LoRA
    # 시스템 템플릿은 재학습으로 품질 개선

else:  # 커스텀 템플릿
    # 1단계: content/summary (학습된 키)
    data = await _call_llm(...)  # task="generate", LoRA

    # 2단계: 커스텀 필드 (role="generated" 중 1단계에서 안 만든 것)
    #        description 기반 프롬프트 추출, LoRA 안 태움
    custom_data = await _extract_structured_fields(
        data["content"], custom_fields  # task="extract"
    )
    data.update(custom_data)
```

---

## 할 일 (우선순위 순)

### Step 1. 커스텀 템플릿 2단계 추출 구현 (1일)

> 커스텀 템플릿의 role="generated" 필드를 content에서 프롬프트로 추출

**수정 파일:**

| 파일 | 변경 |
|------|------|
| `ai/agents/document_agent.py` | `_extract_structured_fields()` 신규, 커스텀 템플릿 경로에 2단계 추가 |
| `ai/llm/prompts.py` | `DOC_EXTRACT_PROMPT` 추가 |

**`_extract_structured_fields()`:**

```python
async def _extract_structured_fields(content, generated_fields):
    """
    content에서 role="generated" 커스텀 필드를 description 기반으로 추출.
    fields_to_prompt()로 description을 프롬프트에 동적 주입.
    """
    field_spec = fields_to_prompt(generated_fields)
    # 예시:
    #   - 회의결과: 회의에서 최종 합의된 결론을 배열로 작성
    #   - 추진전략: 향후 추진 방향을 구체적으로 기술

    user_prompt = f"[추출 필드]\n{field_spec}\n\n[문서 내용]\n{content}"
    result_str = await _call_llm(DOC_EXTRACT_PROMPT, user_prompt,
                                  json_mode=True, task="extract")
    return json.loads(result_str)
```

**`DOC_EXTRACT_PROMPT`:**

```python
DOC_EXTRACT_PROMPT = """\
주어진 문서 내용에서 아래 [추출 필드]에 해당하는 정보를 JSON으로 추출하세요.

규칙:
- 입력 내용에 명시적으로 언급된 내용만 추출하세요.
- 추측하거나 새로운 내용을 만들지 마세요.
- 정보가 없으면 빈 문자열("") 또는 빈 배열([])로 두세요.
- 반드시 JSON만 출력하세요.\
"""
```

**`_call_llm()` 라우팅 추가:**
- `task="extract"` → LoRA 없이 base 모델 또는 API 사용
- 기존 `task="generate"` → LoRA v2_generate 유지

**기존 회의록 fallback(`_extract_decisions_actions`):**
- 시스템 템플릿용이므로 **데이터 재학습 전까지 유지**
- 재학습 후 필요 없어지면 제거

---

### Step 2. 커스텀 템플릿 — role 스키마 + 필드 편집 UI (3~4일)

> 사용자가 DOCX 업로드 후 필드를 확인/수정할 수 있게 함

**핵심 흐름:**

```
① DOCX 업로드 → 필드 자동 추출 (best effort)
② 필드 편집 화면 표시
   - 필드 추가/삭제/수정
   - 각 필드: key, label, description, role("내가 입력" vs "AI가 생성")
③ 확정 → DB 저장
④ 문서 생성 시:
   - role="input" → 폼에 표시, 사용자 입력값 그대로 사용
   - role="generated" → AI가 채움 (2단계 프롬프트 추출)
   - 합산 → DOCX 빌더
```

**필드 데이터 모델 (4개 속성):**

```json
{
  "key": "decisions",
  "label": "결정사항",
  "description": "회의에서 확정된 사항을 배열로 작성",
  "role": "generated"
}
```

**수정 파일:**

| 파일 | 변경 | 담당 |
|------|------|------|
| `backend/app/services/template_service.py` | 시스템 템플릿 `form` → `role` 전환 + 호환 로직 | 백엔드 |
| `backend/app/api/v1/documents.py` | 업로드 시 추출 결과 반환 (저장은 별도 확정 API) | 백엔드 |
| `ai/document_parser/template_extractor.py` | 추출 시 `role` 자동 판단 + FIELD_MAPPING에 없는 필드 처리 | AI |
| `frontend/src/components/documents/TemplateUploadDialog.jsx` | 필드 편집 UI (추가/삭제/role 토글/description 편집) | 프론트 |
| `frontend/src/pages/DocumentGeneratePage.jsx` | `form` → `role` 기반 폼 렌더링 | 프론트 |

**기존 호환:**
- `form: true` → `role: "input"`, `form: false` → `role: "generated"`
- `form`도 `role`도 없으면 기존 `FORM_KEYS` fallback 유지
- 서버 로드 시 자동 변환 (DB 마이그레이션 불필요)

**FIELD_MAPPING에 없는 커스텀 필드 처리:**
- 현재: 무시됨
- 변경: 추출하되 key는 한국어 레이블 그대로 (예: `"회의결과"`)
- description은 빈 문자열 → 사용자가 ②에서 직접 작성
- role 자동 판단: 짧은 필드(제목/날짜/이름) → input, 긴 필드 → generated

---

### Step 3. 시스템 템플릿 데이터 정제 + LoRA v3 재학습 (시간 남으면)

> 시스템 템플릿 3종의 구조화 필드 품질 향상. 현재 방식(전체 필드 생성) 유지, 데이터만 개선.

**정제 내용:**
- 구조화 필드(decisions/tasks/schedule) 채움률: 현재 14~34% → **80%**
- content/summary 포함률: 현재 32~34% → **100%**
- `data/training/v2_generate/clean_data.py` 작성

**재학습:**
- 현재 LoRA v2와 **같은 방식** (전체 필드 생성)
- 데이터만 정제된 버전으로 교체
- 재학습 후 기존 회의록 fallback 불필요해지면 제거

---

## 검증 체크리스트

### Step 1 완료 후
- [ ] 커스텀 템플릿: role="generated" 필드가 content에서 추출됨
- [ ] `task="extract"`에서 LoRA 안 태우는지 확인
- [ ] 시스템 템플릿: 기존 동작 변경 없음 (regression 없음)
- [ ] 챗봇 경로 정상 동작

### Step 2 완료 후
- [ ] DOCX 업로드 → 필드 추출 → 편집 UI 표시
- [ ] 필드 추가/삭제/수정 + role 지정 가능
- [ ] FIELD_MAPPING에 없는 필드도 추출
- [ ] description 편집 가능
- [ ] 문서 생성 시 role="input"만 폼 표시
- [ ] role="generated" 필드가 description 기반 추출됨
- [ ] 기존 form: true/false 템플릿 호환

### Step 3 완료 후
- [ ] 시스템 템플릿 decisions 채움률 80%+ (fallback 없이)
- [ ] 시스템 템플릿 tasks 채움률 80%+ (fallback 없이)
- [ ] content/summary 품질 개선 확인

---

## 일정

| 순서 | 작업 | 소요 | 담당 |
|------|------|------|------|
| Step 1 | 커스텀 템플릿 2단계 추출 구현 | 1일 | 지용 (AI) |
| Step 2 | role 스키마 + 필드 편집 UI | 3~4일 | 지용(백엔드/AI) + 지영(프론트) |
| Step 3 | 시스템 템플릿 데이터 정제 + LoRA v3 | 3~5일 | 시간 남으면 |
