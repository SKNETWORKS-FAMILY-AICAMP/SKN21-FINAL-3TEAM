"""
API v1 라우터 (팀원 A 관리)
각 팀원이 만든 엔드포인트를 여기서 통합합니다.
"""
from fastapi import APIRouter

from app.api.v1 import (
    chat, auth, documents, meetings, schedules, calendar, admin,
    google_connect, tasks, gmail, sheets, regulations, slack, pipeline,
    approvals, messages,
)

api_router = APIRouter()

# 팀원 A: 챗봇 + SSE 스트리밍
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])

# 팀원 D: 인증
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])

# 팀원 C/D: 문서 관리
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])

# 팀원 C/D: 회의 관리
api_router.include_router(meetings.router, prefix="/meetings", tags=["Meetings"])

# 팀원 D: 일정 관리
api_router.include_router(schedules.router, prefix="/schedules", tags=["Schedules"])

# 팀원 D: Google Calendar
api_router.include_router(calendar.router, prefix="/calendar", tags=["Google Calendar"])

# 팀원 D: Google 통합 OAuth
api_router.include_router(google_connect.router, prefix="/google", tags=["Google OAuth"])

# 팀원 D: Google Tasks
api_router.include_router(tasks.router, prefix="/tasks", tags=["Google Tasks"])

# 팀원 D: Gmail
api_router.include_router(gmail.router, prefix="/gmail", tags=["Gmail"])

# 팀원 D: Google Sheets
api_router.include_router(sheets.router, prefix="/sheets", tags=["Google Sheets"])

# 팀원 D: 관리자
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])

# 팀원 D: Slack 연동
api_router.include_router(slack.router, prefix="/slack", tags=["Slack"])

# 팀원 D: Pipeline Task (프로젝트 칸반)
api_router.include_router(pipeline.router, prefix="/pipeline", tags=["Pipeline Tasks"])

# 팀원 D: 결재/승인 요청
api_router.include_router(approvals.router, prefix="/approvals", tags=["Approvals"])

# 팀원 D: 쪽지(메시지)
api_router.include_router(messages.router, prefix="/messages", tags=["Messages"])

# 공개 규정 API
api_router.include_router(regulations.router, prefix="/regulations", tags=["Regulations"])
