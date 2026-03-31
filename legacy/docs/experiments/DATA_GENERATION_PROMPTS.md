# Intent 데이터 생성 프롬프트 모음

> **사용법**: 각 프롬프트를 Claude/GPT/Gemini 웹에 복붙 → 출력을 JSONL 파일로 저장
> **작성일**: 2026-02-22

---

## 작업 순서

```
Step 1. Seed 문장 확인 (아래 Section 0)
Step 2. 기본 데이터 생성 — Section 1 프롬프트 × 8 intent × 3 LLM
Step 3. 경계 쌍 생성 — Section 2 프롬프트 × 10쌍 × 3 LLM
Step 4. 적대적 테스트 생성 — Section 3 프롬프트 × 8 intent × 3 LLM
Step 5. 경계 쌍/적대적 교차 검증 — Section 4 프롬프트
Step 6. 시나리오 테스트 — Section 5 (수동 작성)
Step 7. 파일 합치기 + QA — 스크립트 실행
```

### LLM 분업표

| 작업 | Claude | GPT | Gemini |
|------|:------:|:---:|:------:|
| 기본 데이터 (intent별 100개) | O | O | O |
| 경계 쌍 생성 | O | O | O |
| 적대적 테스트 생성 | O | O | O |
| 경계 쌍 라벨 검증 | 다른 2개가 검증 | 다른 2개가 검증 | 다른 2개가 검증 |

### 파일 저장 규칙

```
data/training/intent_v2/
├── raw/                          ← 원본 (LLM별)
│   ├── claude_judgment.jsonl
│   ├── gpt_judgment.jsonl
│   ├── gemini_judgment.jsonl
│   ├── claude_doc_search.jsonl
│   ├── ...
│   ├── claude_boundary_01_doc_search_doc_qa.jsonl
│   ├── gpt_boundary_01_doc_search_doc_qa.jsonl
│   ├── ...
│   ├── claude_adversarial.jsonl
│   ├── gpt_adversarial.jsonl
│   └── gemini_adversarial.jsonl
└── (합친 파일들은 Step 7에서 스크립트가 생성)
```

---

## Section 0. Seed 문장 (앵커)

> 각 intent별 10개 핵심 예시. 프롬프트에 포함되어 스타일 기준점 역할.

### judgment (규정 기반 판단)
```
1. 인턴에게 서버 접근 권한 줘도 돼?
2. 연차 3일 연속으로 써도 되나요?
3. 재택근무 중에 카페에서 일해도 괜찮아?
4. 경쟁사 이직 시 위약금 있어?
5. 야근 수당 안 주면 규정 위반이야?
6. 개인 노트북으로 사내 시스템 접속해도 돼?
7. 수습 기간에 연차 쓸 수 있나?
8. 회사 차량 주말에 개인 용도로 써도 되나요?
9. 보안 구역에 외부인 데리고 들어가도 돼?
10. 퇴직금 중간 정산 신청 가능한가요?
```

### doc_search (문서/규정 검색)
```
1. 연차 규정 몇 조에 나와있어?
2. 출장비 지급 기준 문서 찾아줘
3. 보안 규정 전문 보여줘
4. 복리후생 관련 규정 있어?
5. 인사평가 기준 문서 어디 있지?
6. 재택근무 가이드라인 찾아줘
7. 경조사 휴가 규정 알려줘
8. 직급별 결재 한도 문서 있나?
9. 성과급 지급 기준 규정 찾아봐
10. 신입사원 온보딩 매뉴얼 있어?
```

### doc_generate (문서 생성)
```
1. 이 내용으로 보고서 만들어줘
2. 오늘 회의 내용으로 회의록 작성해줘
3. 프론트엔드 개발자 JD 만들어줘
4. AI 도입 제안서 작성해줘
5. 주간 업무 보고서 써줘
6. 이 데이터로 분석 보고서 만들어
7. 인턴 채용 공고 만들어줘
8. 프로젝트 기획서 작성해줘
9. 미팅 결과 정리해서 회의록 만들어
10. 퇴사자 인수인계 문서 작성해줘
```

### doc_summary (문서 요약)
```
1. 이 문서 요약해줘
2. 핵심만 정리해줘
3. 이 보고서 3줄로 요약해줘
4. 긴 문서인데 핵심 포인트만 뽑아줘
5. 이 회의록 요약 좀
6. 첨부한 파일 간단히 정리해줘
7. 이 제안서 핵심이 뭐야?
8. 문서 내용 한눈에 보게 정리해줘
9. 이거 읽기 귀찮은데 요약 좀
10. 이 규정 문서 주요 조항만 정리해줘
```

### schedule_add (일정 추가)
```
1. 내일 3시에 팀미팅 잡아줘
2. 금요일 오후 2시 면접 일정 추가해줘
3. 다음주 월요일 10시 스프린트 리뷰 등록해줘
4. 3월 5일에 워크숍 일정 넣어줘
5. 오늘 5시에 1:1 미팅 추가
6. 다음주 수요일 점심에 팀 회식 잡아
7. 매주 화요일 9시 스탠드업 미팅 등록
8. 이번주 목요일 4시에 고객 미팅 추가해줘
9. 내일 오전에 코드 리뷰 일정 잡아줘
10. 3월 말에 분기 회고 일정 넣어줘
```

### schedule_view (일정 조회)
```
1. 이번주 일정 보여줘
2. 내일 미팅 몇 시야?
3. 다음주 스케줄 확인해줘
4. 오늘 남은 일정 있어?
5. 3월 일정 전체 보여줘
6. 이번달 회의 일정 알려줘
7. 금요일에 뭐 있지?
8. 다음주 빈 시간 언제야?
9. 이번주 목요일 일정 확인
10. 오후에 약속 있었나?
```

### general (일반 질문/인사)
```
1. 안녕하세요
2. 고마워
3. 오늘 날씨 어때?
4. 너 이름이 뭐야?
5. 잘 부탁해
6. 뭘 할 수 있어?
7. 도움 좀 줄래?
8. 아 그렇구나
9. 다음에 또 물어볼게
10. 수고했어
```

### doc_qa (문서 내용 기반 Q&A)
```
1. 지난 회의 결정사항이 뭐야?
2. 예산이 얼마로 잡혀있어?
3. 이 보고서에서 핵심 이슈가 뭐야?
4. 지난달 매출이 얼마였어?
5. 회의에서 누가 담당자로 정해졌어?
6. 이 문서에 기한이 언제라고 되어있어?
7. 프로젝트 목표가 뭐라고 써있어?
8. 지난 분기 성과 지표 알려줘
9. 이 계약서 해지 조건이 뭐야?
10. 보안 감사 결과 어떻게 나왔어?
```

---

## Section 1. 기본 데이터 생성 프롬프트

> **사용법**: `{INTENT}`, `{DEFINITION}`, `{SEED_SENTENCES}` 자리에 해당 intent 정보를 넣고 복붙
> **각 LLM에 1번씩** = intent 8개 × LLM 3개 = **24번 실행**
> **출력**: intent당 100개 JSONL

### 프롬프트 (복사용)

```
한국어 직장인 챗봇의 intent 분류 학습 데이터를 생성해주세요.

## Intent 정보
- **라벨**: {INTENT}
- **정의**: {DEFINITION}

## 전체 Intent 목록 (다른 intent와 혼동하지 말 것)
- judgment: 규정상 해도 되는지/안 되는지 판단 요청
- doc_search: 문서/규정을 찾거나 검색하는 요청
- doc_generate: 새 문서를 만들어달라는 요청 (보고서, 회의록, JD, 제안서)
- doc_summary: 기존 문서의 내용을 요약/정리해달라는 요청
- schedule_add: 일정을 새로 추가/등록하는 요청
- schedule_view: 기존 일정을 확인/조회하는 요청
- general: 인사, 감사, 잡담 등 업무 외 일반 대화
- doc_qa: 문서 내용에서 특정 정보를 질문하는 요청

## Seed 예시 (이런 스타일 참고)
{SEED_SENTENCES}

## 생성 규칙
1. **100개** 고유 문장 생성 (중복 없음)
2. 모든 문장은 반드시 **{INTENT}** intent에만 해당해야 함
3. 다른 intent로 해석될 수 있는 애매한 문장은 제외
4. 길이 분포:
   - 초단문 (2~4어절): 20개
   - 단문 (5~8어절): 30개
   - 중문 (9~15어절): 30개
   - 장문 (16어절 이상): 20개
5. 스타일 분포:
   - 반말/구어체: 40개 ("~해줘", "~있어?", "~해봐")
   - 존댓말: 30개 ("~해주세요", "~있나요?", "~부탁드립니다")
   - 격식체: 15개 ("~요청합니다", "~확인 바랍니다")
   - 오타/줄임말 포함: 15개 ("ㅂㄱㅅ", "회이록", "일졍")
6. 주제를 다양하게: 연차, 출장, 보안, 인사평가, 급여, 복리후생, 프로젝트, 회의 등

## 출력 형식
JSONL 형식으로만 출력 (설명 없이 데이터만):
{"text": "문장", "label": "{INTENT}"}
{"text": "문장", "label": "{INTENT}"}
...
(100줄)
```

### Intent별 {DEFINITION} 값

| Intent | {DEFINITION} |
|--------|-------------|
| `judgment` | 회사 규정/정책에 따라 어떤 행위가 가능한지, 위반인지 판단을 요청하는 문장 |
| `doc_search` | 특정 문서나 규정의 존재, 위치, 전문을 검색하거나 찾아달라는 문장 |
| `doc_generate` | 보고서, 회의록, JD, 제안서 등 새 문서를 작성/생성해달라는 문장 |
| `doc_summary` | 이미 존재하는 문서의 내용을 요약하거나 핵심만 정리해달라는 문장 |
| `schedule_add` | 새로운 일정, 미팅, 이벤트를 캘린더에 추가/등록해달라는 문장 |
| `schedule_view` | 기존 일정을 확인하거나 조회해달라는 문장 |
| `general` | 인사, 감사, 잡담, 봇 기능 질문 등 업무 intent에 해당하지 않는 일반 대화 |
| `doc_qa` | 문서 내용에서 특정 사실, 숫자, 결정사항 등을 질문하는 문장 |

### 실행 예시

GPT 웹에서 `judgment` 데이터 생성 시:
1. 프롬프트의 `{INTENT}` → `judgment`
2. `{DEFINITION}` → `회사 규정/정책에 따라 어떤 행위가 가능한지, 위반인지 판단을 요청하는 문장`
3. `{SEED_SENTENCES}` → Section 0의 judgment seed 10개 복붙
4. 출력을 `data/training/intent_v2/raw/gpt_judgment.jsonl`로 저장

---

## Section 2. 경계 쌍 생성 프롬프트

> **사용법**: 10쌍 각각에 대해 3개 LLM에서 실행 = **30번 실행**
> **출력**: 쌍당 30개 (A라벨 15개 + B라벨 15개)

### 프롬프트 (복사용)

```
한국어 직장인 챗봇의 intent 분류 경계 테스트 데이터를 생성해주세요.

## 경계 쌍
- **Intent A**: {INTENT_A} — {DEF_A}
- **Intent B**: {INTENT_B} — {DEF_B}

## 핵심 규칙
이 두 intent는 **같은 주제**로 발화할 수 있지만 **사용자의 의도(화행)가 다릅니다**.
모델이 주제가 아니라 화행을 구분하도록 훈련하기 위한 데이터입니다.

## 생성 규칙
1. **{INTENT_A}** 라벨 15개 + **{INTENT_B}** 라벨 15개 = 총 30개
2. 같은 키워드/주제를 공유하되, 의도가 명확히 다른 문장
3. 사람이 봤을 때 라벨이 명확해야 함 (애매하면 제외)
4. 스타일: 반말/존댓말/오타 섞기
5. 주제 다양하게: 연차, 출장, 보안, 급여, 회의, 프로젝트 등

## 경계 구분 예시
{BOUNDARY_EXAMPLES}

## 출력 형식
JSONL 형식으로만 출력 (설명 없이):
{"text": "문장", "label": "intent_라벨"}
...
(30줄, A 15개 + B 15개 섞어서)
```

### 10쌍별 {BOUNDARY_EXAMPLES} 값

**쌍 1: `doc_search` ↔ `doc_qa`**
```
"출장비 규정 찾아줘" → doc_search (문서를 찾고 싶다)
"출장비 얼마야?" → doc_qa (문서 안의 금액을 알고 싶다)
"보안 규정 있어?" → doc_search (문서 존재 확인)
"보안 규정에 USB 관련 내용 뭐야?" → doc_qa (문서 내용 질문)
```

**쌍 2: `doc_search` ↔ `judgment`**
```
"연차 규정 알려줘" → doc_search (규정 내용을 보고 싶다)
"연차 써도 돼?" → judgment (쓸 수 있는지 판단해달라)
"보안 정책 찾아줘" → doc_search (정책 문서 검색)
"USB 써도 되나?" → judgment (규정 위반 여부 판단)
```

**쌍 3: `doc_qa` ↔ `judgment`**
```
"보안 규정에 뭐라고 써있어?" → doc_qa (사실 확인)
"USB 써도 돼?" → judgment (가능 여부 판단)
"연차 몇 일 남았어?" → doc_qa (정보 조회)
"연차 내일 써도 되나?" → judgment (허용 여부 판단)
```

**쌍 4: `doc_summary` ↔ `doc_qa`**
```
"이 문서 핵심이 뭐야?" → doc_summary (전체 요약)
"이 문서에서 예산이 얼마야?" → doc_qa (특정 사항 질문)
"회의록 요약해줘" → doc_summary (전체 정리)
"회의에서 누가 담당자야?" → doc_qa (특정 정보)
```

**쌍 5: `doc_generate` ↔ `doc_summary`**
```
"회의 내용으로 보고서 작성해줘" → doc_generate (새 문서 생성)
"회의 내용 정리해줘" → doc_summary (기존 내용 요약)
"제안서 만들어줘" → doc_generate (새로 만들기)
"제안서 핵심만 뽑아줘" → doc_summary (기존 것 요약)
```

**쌍 6: `schedule_add` ↔ `schedule_view`**
```
"다음주 미팅 잡아줘" → schedule_add (새 일정 등록)
"다음주 미팅 언제야?" → schedule_view (기존 일정 확인)
"금요일에 회의 넣어줘" → schedule_add (추가)
"금요일에 뭐 있지?" → schedule_view (조회)
```

**쌍 7: `doc_search` ↔ `doc_summary`**
```
"보안 규정 있어?" → doc_search (문서 존재/위치 확인)
"보안 규정 요약해줘" → doc_summary (내용 요약)
"인사 평가 기준 문서 찾아줘" → doc_search (검색)
"인사 평가 기준 핵심만 알려줘" → doc_summary (요약)
```

**쌍 8: `judgment` ↔ `general`**
```
"재택근무 해도 돼?" → judgment (규정 기반 판단)
"오늘 점심 뭐 먹을까?" → general (일상 질문)
"야근 수당 안 주면 위반이야?" → judgment (규정 판단)
"요즘 힘들다" → general (일상 대화)
```

**쌍 9: `doc_generate` ↔ `doc_qa`**
```
"JD 만들어줘" → doc_generate (새 문서 생성)
"JD에 필수 조건이 뭐야?" → doc_qa (기존 문서 질문)
"보고서 작성해줘" → doc_generate (생성)
"보고서에 결론이 뭐라고 써있어?" → doc_qa (내용 질문)
```

**쌍 10: `doc_search` ↔ `doc_generate`**
```
"제안서 양식 있어?" → doc_search (양식 검색)
"제안서 만들어줘" → doc_generate (새로 생성)
"회의록 템플릿 찾아줘" → doc_search (검색)
"회의록 작성해줘" → doc_generate (생성)
```

---

## Section 3. 적대적 테스트 생성 프롬프트

> **사용법**: 8개 intent 한 번에 생성, 3개 LLM에서 각각 실행 = **3번 실행**
> **출력**: 240개 (8 intent × 30개)

### 프롬프트 (복사용)

```
한국어 직장인 챗봇의 intent 분류 적대적(adversarial) 테스트 데이터를 생성해주세요.
모델이 틀리기 쉬운 어려운 문장들입니다.

## Intent 목록
- judgment: 규정상 해도 되는지/안 되는지 판단 요청
- doc_search: 문서/규정을 찾거나 검색
- doc_generate: 새 문서 작성/생성 요청
- doc_summary: 기존 문서 요약/정리 요청
- schedule_add: 새 일정 추가/등록
- schedule_view: 기존 일정 확인/조회
- general: 인사, 감사, 잡담 등 일반 대화
- doc_qa: 문서 내용에서 특정 정보 질문

## 생성 규칙
각 intent별로 30개씩, 총 240개 생성.
intent당 아래 7가지 유형을 골고루 포함 (유형별 ~4개):

1. **초단문** (2~3어절): "연차 되나?", "보고서 줘"
2. **오타/비표준**: "회이록 정리해조", "일졍 추가해줘어"
3. **격식체**: "연차 사용 가능 여부를 확인 요청드립니다"
4. **맥락 의존**: 문맥 없이는 애매하지만 의도는 명확 ("그거 돼?", "아까 그 문서")
5. **간접 표현**: 직접 요청 안 하고 돌려 말하기 ("연차 쓰고 싶은데...", "보고서가 필요한 상황이야")
6. **인터넷 언어**: "ㅂㄱㅅ 써줘", "일정 ㄱㄱ", "ㅎㅇㄹ 정리해줘"
7. **복합/긴 문장**: 여러 정보가 섞여있지만 핵심 intent는 하나 ("내일 미팅 전에 보고서 준비해야 하는데 양식 좀 만들어줘")

## 출력 형식
JSONL (설명 없이 데이터만):
{"text": "문장", "label": "intent_라벨"}
...
(240줄)
```

---

## Section 4. 교차 검증 프롬프트

> **사용법**: 경계 쌍/적대적 데이터를 다른 LLM에게 검증 요청
> **예시**: Claude가 생성한 경계 쌍 → GPT와 Gemini가 각각 검증

### 프롬프트 (복사용)

```
한국어 직장인 챗봇의 intent 분류 데이터를 검증해주세요.

## Intent 정의
- judgment: 규정상 해도 되는지/안 되는지 판단 요청
- doc_search: 문서/규정을 찾거나 검색
- doc_generate: 새 문서 작성/생성 요청
- doc_summary: 기존 문서 요약/정리 요청
- schedule_add: 새 일정 추가/등록
- schedule_view: 기존 일정 확인/조회
- general: 인사, 감사, 잡담 등 일반 대화
- doc_qa: 문서 내용에서 특정 정보 질문

## 검증 규칙
각 문장의 라벨이 올바른지 판단해주세요.
- **agree**: 라벨이 올바름
- **disagree**: 라벨이 틀림 → 올바른 라벨을 suggested_label에 기입
- **ambiguous**: 애매함 → 가장 가능성 높은 라벨을 suggested_label에 기입

## 검증 대상 데이터
(아래에 검증할 JSONL 데이터를 붙여넣기)

{여기에 데이터 붙여넣기}

## 출력 형식
JSONL로만 출력:
{"text": "원문", "original_label": "원래라벨", "vote": "agree/disagree/ambiguous", "suggested_label": "제안라벨_or_null"}
...
```

### 검증 후 처리 규칙

```
투표 결과 처리:
- 3/3 agree → 채택
- 2/3 agree → 채택
- 1/3 agree → 제거 (또는 suggested_label 중 다수결로 재라벨링)
- 0/3 agree → 제거
```

---

## Section 5. 시나리오 테스트 (수동 작성)

> 실제 업무 하루를 시뮬레이션하는 30개 문장. 이건 직접 작성 권장.

```json
[
  {"id": 1, "text": "안녕 듀듀", "expected_intent": "general", "scenario": "출근 인사"},
  {"id": 2, "text": "오늘 일정 뭐 있어?", "expected_intent": "schedule_view", "scenario": "아침 일정 확인"},
  {"id": 3, "text": "10시에 팀미팅 잡아줘", "expected_intent": "schedule_add", "scenario": "미팅 등록"},
  {"id": 4, "text": "연차 규정 찾아줘", "expected_intent": "doc_search", "scenario": "규정 검색"},
  {"id": 5, "text": "연차 내일 써도 돼?", "expected_intent": "judgment", "scenario": "규정 판단"},
  {"id": 6, "text": "연차 며칠 남았어?", "expected_intent": "doc_qa", "scenario": "문서 내용 질문"},
  {"id": 7, "text": "연차 규정 요약해줘", "expected_intent": "doc_summary", "scenario": "문서 요약"},
  {"id": 8, "text": "출장비 얼마까지 나와?", "expected_intent": "doc_qa", "scenario": "규정 내 금액 질문"},
  {"id": 9, "text": "출장비 지급 기준 문서 있어?", "expected_intent": "doc_search", "scenario": "문서 검색"},
  {"id": 10, "text": "출장 가도 되나요?", "expected_intent": "judgment", "scenario": "출장 승인 판단"},
  {"id": 11, "text": "지난 회의 결정사항이 뭐였지?", "expected_intent": "doc_qa", "scenario": "회의 내용 질문"},
  {"id": 12, "text": "회의록 작성해줘", "expected_intent": "doc_generate", "scenario": "회의록 생성"},
  {"id": 13, "text": "회의록 핵심만 정리해줘", "expected_intent": "doc_summary", "scenario": "회의록 요약"},
  {"id": 14, "text": "오후 3시에 고객 미팅 추가해줘", "expected_intent": "schedule_add", "scenario": "오후 일정 등록"},
  {"id": 15, "text": "내일 오전에 뭐 있지?", "expected_intent": "schedule_view", "scenario": "내일 일정 확인"},
  {"id": 16, "text": "프론트엔드 개발자 JD 만들어줘", "expected_intent": "doc_generate", "scenario": "JD 생성"},
  {"id": 17, "text": "이 보고서 요약 좀", "expected_intent": "doc_summary", "scenario": "보고서 요약"},
  {"id": 18, "text": "보고서에 예산이 얼마로 잡혀있어?", "expected_intent": "doc_qa", "scenario": "보고서 내용 질문"},
  {"id": 19, "text": "주간 업무 보고서 써줘", "expected_intent": "doc_generate", "scenario": "보고서 생성"},
  {"id": 20, "text": "재택근무 중 카페 가도 돼?", "expected_intent": "judgment", "scenario": "재택 규정 판단"},
  {"id": 21, "text": "재택근무 가이드라인 찾아줘", "expected_intent": "doc_search", "scenario": "가이드라인 검색"},
  {"id": 22, "text": "보안 규정 전문 보여줘", "expected_intent": "doc_search", "scenario": "규정 전문 검색"},
  {"id": 23, "text": "개인 노트북으로 접속해도 되나?", "expected_intent": "judgment", "scenario": "보안 규정 판단"},
  {"id": 24, "text": "이 계약서 해지 조건이 뭐야?", "expected_intent": "doc_qa", "scenario": "계약서 내용 질문"},
  {"id": 25, "text": "제안서 만들어줘", "expected_intent": "doc_generate", "scenario": "제안서 생성"},
  {"id": 26, "text": "다음주 금요일 퇴근 후 회식 잡아", "expected_intent": "schedule_add", "scenario": "회식 일정 등록"},
  {"id": 27, "text": "이번달 남은 일정 보여줘", "expected_intent": "schedule_view", "scenario": "월간 일정 확인"},
  {"id": 28, "text": "이 문서 3줄로 요약해줘", "expected_intent": "doc_summary", "scenario": "짧은 요약 요청"},
  {"id": 29, "text": "고마워 많이 도움됐어", "expected_intent": "general", "scenario": "감사 인사"},
  {"id": 30, "text": "내일 또 물어볼게", "expected_intent": "general", "scenario": "퇴근 인사"}
]
```

---

## 진행 체크리스트

### Step 2: 기본 데이터 (intent별 300개)

| Intent | Claude (100) | GPT (100) | Gemini (100) | 합계 |
|--------|:------:|:---:|:------:|:----:|
| judgment | [ ] | [ ] | [ ] | 300 |
| doc_search | [ ] | [ ] | [ ] | 300 |
| doc_generate | [ ] | [ ] | [ ] | 300 |
| doc_summary | [ ] | [ ] | [ ] | 300 |
| schedule_add | [ ] | [ ] | [ ] | 300 |
| schedule_view | [ ] | [ ] | [ ] | 300 |
| general | [ ] | [ ] | [ ] | 300 |
| doc_qa | [ ] | [ ] | [ ] | 300 |

### Step 3: 경계 쌍 (10쌍 × 30개)

| # | 쌍 | Claude | GPT | Gemini |
|:-:|-----|:------:|:---:|:------:|
| 1 | doc_search ↔ doc_qa | [ ] | [ ] | [ ] |
| 2 | doc_search ↔ judgment | [ ] | [ ] | [ ] |
| 3 | doc_qa ↔ judgment | [ ] | [ ] | [ ] |
| 4 | doc_summary ↔ doc_qa | [ ] | [ ] | [ ] |
| 5 | doc_generate ↔ doc_summary | [ ] | [ ] | [ ] |
| 6 | schedule_add ↔ schedule_view | [ ] | [ ] | [ ] |
| 7 | doc_search ↔ doc_summary | [ ] | [ ] | [ ] |
| 8 | judgment ↔ general | [ ] | [ ] | [ ] |
| 9 | doc_generate ↔ doc_qa | [ ] | [ ] | [ ] |
| 10 | doc_search ↔ doc_generate | [ ] | [ ] | [ ] |

### Step 4: 적대적 테스트 (240개)

| LLM | 생성 | 검증1 | 검증2 |
|-----|:----:|:-----:|:-----:|
| Claude | [ ] | GPT [ ] | Gemini [ ] |
| GPT | [ ] | Claude [ ] | Gemini [ ] |
| Gemini | [ ] | Claude [ ] | GPT [ ] |

### Step 5: 시나리오 테스트
- [ ] 30개 작성 완료 (위 Section 5 기반)
