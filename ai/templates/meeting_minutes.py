"""
회의록 템플릿 (팀원 C 담당)

핵심 플로우:
  1. 사용자가 챗봇에서 "회의록 만들어줘"
  2. 사용자가 회의 요약/핵심 내용 입력
  3. sLLM이 템플릿에 맞춰 회의록 자동 생성
  4. 미리보기 표시 → DOCX/PDF 다운로드 가능

요구사항: FR-DOC-008
"""
from ai.templates.base import BaseTemplate


class MeetingMinutesTemplate(BaseTemplate):
    """회의록 템플릿"""

    template_type = "meeting_minutes"
    template_name = "회의록"

    # 회의록 필수 필드
    REQUIRED_FIELDS = [
        "title",        # 회의명
        "date",         # 일시
        "attendees",    # 참석자
        "agenda",       # 안건
        "content",      # 회의 내용 (사용자 입력 또는 sLLM 생성)
    ]

    # 회의록 마크다운 템플릿
    TEMPLATE = """# {title}

## 회의 정보
- **일시**: {date}
- **장소**: {location}
- **참석자**: {attendees}
- **작성자**: {author}

## 안건
{agenda}

## 회의 내용
{content}

## 결정사항
{decisions}

## Action Items
| 담당자 | 내용 | 기한 | 상태 |
|--------|------|------|------|
{action_items}

## 비고
{notes}
"""

    def render(self, data: dict) -> str:
        """
        회의록 렌더링

        Args:
            data: {
                "title": "2026 Q1 개발 스프린트 회의",
                "date": "2026-02-10 14:00",
                "location": "회의실 A",
                "attendees": ["김철수", "이영희"],
                "author": "김철수",
                "agenda": "스프린트 회고 및 다음 스프린트 계획",
                "content": "...(sLLM이 생성한 상세 내용)...",
                "decisions": ["결정사항1", "결정사항2"],
                "action_items": [
                    {"assignee": "이영희", "content": "API 문서 작성", "due_date": "2026-02-15"}
                ],
                "notes": ""
            }
        """
        # TODO: 팀원 C 구현
        # 1. data에서 필드 추출
        # 2. TEMPLATE에 데이터 삽입
        # 3. sLLM으로 content 보강 (사용자 입력이 간단할 경우)
        # 4. 렌더링된 마크다운 반환
        raise NotImplementedError("팀원 C: 회의록 템플릿 렌더링 구현 필요")
