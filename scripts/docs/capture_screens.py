#!/usr/bin/env python3
"""Capture all frontend screens using Playwright with API mocking"""
import asyncio, json, os, jwt
from datetime import datetime, timedelta, timezone
from playwright.async_api import async_playwright

BASE = 'http://localhost:5173'
API_BASE = 'http://localhost:8000'
OUT_DIR = '/Users/anhyebin/Documents/SKN21/SKN21-FINAL-3TEAM/docs/screenshots'
JWT_SECRET = 'change-this-secret-key'
JWT_ALG = 'HS256'

def make_token(user_id=1):
    exp = datetime.now(timezone.utc) + timedelta(hours=24)
    return jwt.encode({'sub': str(user_id), 'exp': exp}, JWT_SECRET, algorithm=JWT_ALG)

FAKE_USER_OBJ = {
    'id': 1, 'name': '안혜빈', 'email': 'hyebin@example.com',
    'team': 'Backend', 'is_admin': True, 'avatar': None,
    'phone': '010-1234-5678', 'address': '서울시 강남구', 'role': 'Backend Developer',
    'is_active': True, 'slack_enabled': False
}

FAKE_TEAMS = [
    {'id': 1, 'name': '개발팀'}, {'id': 2, 'name': '기획팀'},
    {'id': 3, 'name': 'AI팀'}, {'id': 4, 'name': '디자인팀'}
]
FAKE_MEMBERS = [
    {'id': 1, 'name': '안혜빈', 'email': 'hyebin@example.com', 'team': 'Backend', 'avatar': None, 'is_admin': True},
    {'id': 2, 'name': '신지용', 'email': 'jiyong@example.com', 'team': 'PM', 'avatar': None, 'is_admin': True},
    {'id': 3, 'name': '문지영', 'email': 'jiyoung@example.com', 'team': 'Frontend', 'avatar': None, 'is_admin': False},
    {'id': 4, 'name': '윤경은', 'email': 'kyungeun@example.com', 'team': 'AI', 'avatar': None, 'is_admin': False},
    {'id': 5, 'name': '진승언', 'email': 'seungeon@example.com', 'team': 'AI', 'avatar': None, 'is_admin': False},
]
FAKE_DOCS = [
    {'id': 1, 'filename': '프로젝트_기획서_v2.pdf', 'doc_type': 'pdf', 'status': 'completed', 'scope': 'company', 'category': '기획', 'tags': ['프로젝트', '기획'], 'summary': 'WorkFlow Agent 프로젝트 기획서', 'version': '2.0', 'uploaded_by': 1, 'uploader_name': '안혜빈', 'created_at': '2025-03-10T09:00:00'},
    {'id': 2, 'filename': '회의록_20250310.docx', 'doc_type': 'docx', 'status': 'completed', 'scope': 'team', 'category': '회의록', 'tags': ['회의', '주간'], 'summary': '주간 회의 내용 정리', 'version': '1.0', 'uploaded_by': 2, 'uploader_name': '신지용', 'created_at': '2025-03-10T14:00:00'},
    {'id': 3, 'filename': 'API_설계서.pdf', 'doc_type': 'pdf', 'status': 'processing', 'scope': 'company', 'category': '기술문서', 'tags': ['API', 'Backend'], 'summary': None, 'version': '1.0', 'uploaded_by': 1, 'uploader_name': '안혜빈', 'created_at': '2025-03-11T10:30:00'},
]
FAKE_SCHEDULES = [
    {'id': 1, 'title': '주간 스프린트 회의', 'description': '스프린트 진행상황 리뷰', 'start_date': '2025-03-11T10:00:00', 'end_date': '2025-03-11T11:00:00', 'schedule_type': 'meeting', 'is_all_day': False, 'user_id': 1, 'source': 'local'},
    {'id': 2, 'title': 'AI 모델 테스트', 'description': 'LoRA 모델 성능 평가', 'start_date': '2025-03-12T14:00:00', 'end_date': '2025-03-12T16:00:00', 'schedule_type': 'work', 'is_all_day': False, 'user_id': 1, 'source': 'local'},
    {'id': 3, 'title': '프로젝트 마감일', 'description': '최종 발표 준비', 'start_date': '2025-03-20T00:00:00', 'end_date': '2025-03-20T23:59:00', 'schedule_type': 'deadline', 'is_all_day': True, 'user_id': 1, 'source': 'local'},
]
FAKE_TASKS = [
    {'id': 1, 'title': 'JWT 인증 구현', 'description': 'Access/Refresh 토큰 구현', 'status': 'done', 'priority': 'high', 'assignee_id': 1, 'assignee_name': '안혜빈', 'due_date': '2025-03-08', 'tags': 'Backend,API', 'project_id': None},
    {'id': 2, 'title': 'RAG 파이프라인 구축', 'description': 'Qdrant + BM25 하이브리드 검색', 'status': 'in_progress', 'priority': 'high', 'assignee_id': 4, 'assignee_name': '윤경은', 'due_date': '2025-03-15', 'tags': 'AI,RAG', 'project_id': None},
    {'id': 3, 'title': '대시보드 UI 구현', 'description': '위젯 드래그앤드롭 기능', 'status': 'review', 'priority': 'medium', 'assignee_id': 3, 'assignee_name': '문지영', 'due_date': '2025-03-13', 'tags': 'Frontend,UI/UX', 'project_id': None},
    {'id': 4, 'title': '문서 파서 개발', 'description': 'Docling + PaddleOCR 통합', 'status': 'todo', 'priority': 'medium', 'assignee_id': 5, 'assignee_name': '진승언', 'due_date': '2025-03-18', 'tags': 'AI,Document', 'project_id': None},
    {'id': 5, 'title': '일정 Google 연동', 'description': 'Google Calendar API 양방향 동기화', 'status': 'in_progress', 'priority': 'high', 'assignee_id': 1, 'assignee_name': '안혜빈', 'due_date': '2025-03-14', 'tags': 'Backend,API', 'project_id': None},
    {'id': 6, 'title': 'E2E 테스트 작성', 'description': '주요 플로우 테스트', 'status': 'todo', 'priority': 'low', 'assignee_id': 2, 'assignee_name': '신지용', 'due_date': '2025-03-22', 'tags': 'QA,PM', 'project_id': None},
]
FAKE_APPROVALS_PENDING = [
    {'id': 1, 'type': 'leave', 'title': '연차 신청 (3/15)', 'detail': '개인 사유로 연차 신청합니다.', 'status': 'pending', 'requester_id': 3, 'requester_name': '문지영', 'requester_team': 'Frontend', 'file_url': None, 'created_at': '2025-03-10T09:00:00'},
    {'id': 2, 'type': 'review', 'title': 'PR #45 리뷰 요청', 'detail': '챗봇 스트리밍 기능 PR 리뷰 부탁드립니다.', 'status': 'pending', 'requester_id': 4, 'requester_name': '윤경은', 'requester_team': 'AI', 'file_url': None, 'created_at': '2025-03-11T11:00:00'},
]
FAKE_APPROVALS_APPROVED = [
    {'id': 3, 'type': 'remote', 'title': '재택근무 신청 (3/12)', 'detail': '집중 개발을 위한 재택근무 신청', 'status': 'approved', 'requester_id': 1, 'requester_name': '안혜빈', 'requester_team': 'Backend', 'file_url': None, 'created_at': '2025-03-09T08:30:00'},
]
FAKE_MESSAGES_INBOX = [
    {'id': 1, 'sender_id': 2, 'sender_name': '신지용', 'sender_team': 'PM', 'receiver_id': 1, 'content': '오늘 스프린트 회의 10시에 시작합니다. 참석 부탁드려요!', 'is_read': False, 'created_at': '2025-03-11T09:00:00'},
    {'id': 2, 'sender_id': 3, 'sender_name': '문지영', 'sender_team': 'Frontend', 'receiver_id': 1, 'content': 'API 스키마 변경사항 확인해주세요.', 'is_read': True, 'created_at': '2025-03-10T16:30:00'},
]
FAKE_CHAT_SESSIONS = [
    {'id': 1, 'title': '규정 판단 질문', 'created_at': '2025-03-11T09:30:00'},
    {'id': 2, 'title': '문서 요약 요청', 'created_at': '2025-03-10T14:00:00'},
]
FAKE_REGULATIONS = [
    {'id': 1, 'article_number': '제1조', 'title': '목적', 'content': '이 규정은 회사의 근무 관련 사항을 정함을 목적으로 한다.', 'created_at': '2025-01-01'},
    {'id': 2, 'article_number': '제10조', 'title': '연차휴가', 'content': '직원은 연간 15일의 유급 연차휴가를 사용할 수 있다.', 'created_at': '2025-01-01'},
    {'id': 3, 'article_number': '제15조', 'title': '재택근무', 'content': '부서장의 승인을 받아 주 2일 이내 재택근무가 가능하다.', 'created_at': '2025-01-01'},
]
FAKE_QUERY_LOGS = [
    {'id': 1, 'user_id': 1, 'user_name': '안혜빈', 'query': '연차 사용 규정 알려줘', 'intent': 'regulation', 'response_time': 1.2, 'created_at': '2025-03-11T10:00:00'},
    {'id': 2, 'user_id': 3, 'user_name': '문지영', 'query': '프로젝트 기획서 요약해줘', 'intent': 'doc_summary', 'response_time': 2.5, 'created_at': '2025-03-11T09:30:00'},
]

SCREENS = [
    ('SC-01-001_login', '/login', False, None),
    ('SC-01-002_register', '/login', False, 'register'),
    ('SC-02-001_dashboard', '/dashboard', True, None),
    ('SC-03-001_chat', '/chat', True, None),
    ('SC-04-001_doc_generate', '/document-generate', True, None),
    ('SC-05-001_documents', '/documents', True, None),
    ('SC-06-001_schedules', '/schedules', True, None),
    ('SC-07-001_tasks', '/tasks', True, None),
    ('SC-08-001_approvals', '/approvals', True, None),
    ('SC-09-001_messages', '/messages', True, None),
    ('SC-10-001_mypage', '/mypage', True, None),
    ('SC-11-001_admin', '/admin', True, None),
    ('SC-12-001_meetings', '/meetings', True, None),
]

async def setup_api_mocks(page):
    """Intercept all API calls and return mock data"""
    async def handle_route(route):
        url = route.request.url
        path = url.split('/api/v1')[-1] if '/api/v1' in url else ''
        method = route.request.method

        # Auth
        if '/auth/me' in path:
            await route.fulfill(status=200, content_type='application/json', body=json.dumps(FAKE_USER_OBJ))
            return
        # Teams
        if '/teams' in path or '/auth/teams' in path:
            await route.fulfill(status=200, content_type='application/json', body=json.dumps(FAKE_TEAMS))
            return
        # Members
        if '/members' in path or '/users' in path:
            await route.fulfill(status=200, content_type='application/json', body=json.dumps(FAKE_MEMBERS))
            return
        # Documents
        if '/documents' in path and 'search' not in path:
            if method == 'GET':
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(FAKE_DOCS))
                return
        if '/documents/search' in path:
            await route.fulfill(status=200, content_type='application/json', body=json.dumps(FAKE_DOCS))
            return
        # Schedules
        if '/schedules' in path and 'type' not in path:
            await route.fulfill(status=200, content_type='application/json', body=json.dumps(FAKE_SCHEDULES))
            return
        if '/schedule-types' in path or '/schedules/types' in path:
            await route.fulfill(status=200, content_type='application/json', body=json.dumps([
                {'id': 1, 'name': 'meeting', 'color': '#3B82F6', 'label': '회의'},
                {'id': 2, 'name': 'work', 'color': '#10B981', 'label': '업무'},
                {'id': 3, 'name': 'deadline', 'color': '#EF4444', 'label': '마감'},
            ]))
            return
        # Tasks / Pipeline
        if '/tasks' in path or '/pipeline' in path:
            await route.fulfill(status=200, content_type='application/json', body=json.dumps(FAKE_TASKS))
            return
        # Approvals
        if '/approvals' in path:
            if 'pending' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(FAKE_APPROVALS_PENDING))
            elif 'approved' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(FAKE_APPROVALS_APPROVED))
            elif 'rejected' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps([]))
            else:
                all_approvals = FAKE_APPROVALS_PENDING + FAKE_APPROVALS_APPROVED
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(all_approvals))
            return
        # Messages
        if '/messages' in path:
            if 'inbox' in path or 'received' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(FAKE_MESSAGES_INBOX))
            elif 'sent' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps([]))
            else:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps(FAKE_MESSAGES_INBOX))
            return
        # Chat sessions
        if '/chat/sessions' in path or '/chat' in path:
            await route.fulfill(status=200, content_type='application/json', body=json.dumps(FAKE_CHAT_SESSIONS))
            return
        # Meetings
        if '/meetings' in path:
            await route.fulfill(status=200, content_type='application/json', body=json.dumps([]))
            return
        # Google
        if '/google' in path:
            await route.fulfill(status=200, content_type='application/json', body=json.dumps({'connected': False}))
            return
        # Regulations
        if '/regulations' in path:
            await route.fulfill(status=200, content_type='application/json', body=json.dumps(FAKE_REGULATIONS))
            return
        # Admin stats / query logs
        if '/admin' in path:
            if 'stats' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps({
                    'total_users': 5, 'today_queries': 12, 'total_regulations': 3
                }))
            elif 'logs' in path or 'queries' in path:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps({
                    'items': FAKE_QUERY_LOGS, 'total': 2, 'page': 1, 'pages': 1
                }))
            else:
                await route.fulfill(status=200, content_type='application/json', body=json.dumps({}))
            return
        # Calendar
        if '/calendar' in path:
            await route.fulfill(status=200, content_type='application/json', body=json.dumps(FAKE_SCHEDULES))
            return
        # Sheets
        if '/sheets' in path:
            await route.fulfill(status=200, content_type='application/json', body=json.dumps([]))
            return
        # Gmail
        if '/gmail' in path:
            await route.fulfill(status=200, content_type='application/json', body=json.dumps([]))
            return
        # Templates
        if '/templates' in path:
            await route.fulfill(status=200, content_type='application/json', body=json.dumps([]))
            return
        # Default: return empty success
        await route.fulfill(status=200, content_type='application/json', body=json.dumps([]))

    await page.route(f'{API_BASE}/**', handle_route)
    await page.route('**/api/v1/**', handle_route)

async def inject_auth(page):
    token = make_token()
    fu = json.dumps(FAKE_USER_OBJ)
    await page.evaluate(f"""() => {{
        localStorage.setItem('access_token', '{token}');
        localStorage.setItem('cached_user', JSON.stringify({fu}));
    }}""")

async def capture_all():
    os.makedirs(OUT_DIR, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1440, 'height': 900})

        for filename, path, needs_auth, action in SCREENS:
            page = await context.new_page()
            try:
                if needs_auth:
                    await setup_api_mocks(page)
                    await page.goto(f'{BASE}/login', wait_until='domcontentloaded', timeout=8000)
                    await inject_auth(page)

                await page.goto(f'{BASE}{path}', wait_until='networkidle', timeout=15000)

                if action == 'register':
                    tab = await page.query_selector('button:has-text("회원가입"), [role="tab"]:has-text("회원가입")')
                    if tab:
                        await tab.click()
                        await page.wait_for_timeout(800)

                await page.wait_for_timeout(2000)

                cur_url = page.url
                if needs_auth and '/login' in cur_url:
                    print(f'REDIRECT: {filename} -> still on login. Retrying...')
                    await inject_auth(page)
                    await page.goto(f'{BASE}{path}', wait_until='networkidle', timeout=15000)
                    await page.wait_for_timeout(2000)

                out = os.path.join(OUT_DIR, f'{filename}.png')
                await page.screenshot(path=out, full_page=False)
                final_url = page.url
                print(f'OK: {filename} (url: {final_url})')
            except Exception as e:
                print(f'FAIL: {filename} - {e}')
                try:
                    out = os.path.join(OUT_DIR, f'{filename}.png')
                    await page.screenshot(path=out, full_page=False)
                    print(f'  (saved partial)')
                except:
                    pass
            finally:
                await page.close()

        await browser.close()
    print(f'\nDone. Screenshots in: {OUT_DIR}')

if __name__ == '__main__':
    asyncio.run(capture_all())
