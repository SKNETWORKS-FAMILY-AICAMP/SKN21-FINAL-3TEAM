#!/usr/bin/env python3
"""화면 설계서 PDF Generator for DUDE (WorkFlow Agent)"""
import os
import textwrap
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, black, white
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

PAGE_W, PAGE_H = landscape(A4)
ML, MR, MT, MB = 30, 30, 25, 25
DARK_GRAY = HexColor('#4A4A4A')
MED_GRAY = HexColor('#707070')
LIGHT_GRAY = HexColor('#F5F5F5')
BLUE = HexColor('#3B5BDB')
RED = HexColor('#E03131')

FONT = 'AppleGothic'
FONT_EN = 'Helvetica'
FONT_EN_B = 'Helvetica-Bold'

def setup_fonts():
    pdfmetrics.registerFont(TTFont('AppleGothic', '/System/Library/Fonts/Supplemental/AppleGothic.ttf'))

def make_styles():
    return {
        'desc_title': ParagraphStyle('dt', fontName=FONT, fontSize=8.5, leading=11, textColor=black, spaceAfter=1),
        'desc_bullet': ParagraphStyle('db', fontName=FONT, fontSize=7.5, leading=10, textColor=black, leftIndent=8),
        'cp_title': ParagraphStyle('ct', fontName=FONT, fontSize=8, leading=10.5, textColor=black, spaceAfter=1),
        'cp_bullet': ParagraphStyle('cb', fontName=FONT, fontSize=7.5, leading=10, textColor=black, leftIndent=8),
    }

STYLES = None

# ===== SCREEN DATA =====
SCREENS = [
    {
        'name': '로그인 페이지',
        'path': '/login',
        'req_id': 'R-001',
        'screen_id': 'SC-01-001',
        'placeholder': '중앙 카드 레이아웃의 로그인 폼\n그라데이션 배경 위 로고 + 탭(로그인/회원가입)\n이메일/비밀번호 입력 + Google OAuth 버튼',
        'descs': [
            (1, '로고 및 브랜딩', ['WorkFlow Agent (듀드) 로고 표시', '그라데이션 배경 위 중앙 카드 레이아웃']),
            (2, '이메일/비밀번호 입력', ['이메일 입력 필드', '비밀번호 입력 필드 (8자 이상)', '"아이디 저장" 체크박스']),
            (3, '로그인 버튼', ['클릭 시 JWT 토큰 발급 후 대시보드 이동', '실패 시 에러 메시지 표시']),
            (4, 'Google OAuth 버튼', ['클릭 시 Google 인증 프로세스 시작', '인증 완료 시 대시보드로 리다이렉트']),
            (5, '비밀번호 찾기 링크', ['클릭 시 비밀번호 재설정 뷰로 전환']),
        ],
        'cps': [('인증 방식', ['JWT + Google OAuth 2.0 지원', '로그인 상태 유지 시 토큰 자동 갱신'])],
    },
    {
        'name': '회원가입 페이지',
        'path': '/login > 회원가입 탭',
        'req_id': 'R-002',
        'screen_id': 'SC-01-002',
        'placeholder': '회원가입 탭 활성화 상태\n이름/이메일/비밀번호/확인/팀 선택 폼\n가입 완료 시 성공 모달 표시',
        'descs': [
            (1, '이름 입력', ['사용자 실명 입력']),
            (2, '이메일 입력', ['회사 이메일 형식 검증']),
            (3, '비밀번호 입력', ['8자 이상, 비밀번호 확인 필드와 일치 검증']),
            (4, '팀 선택 드롭다운', ['소속 팀 선택 (DB에서 팀 목록 조회)']),
            (5, '가입 버튼', ['폼 검증 후 계정 생성', '성공 시 축하 모달 → 로그인 탭 자동 전환']),
        ],
        'cps': [('입력 검증', ['필수 필드 미입력 시 에러 표시', '중복 이메일 체크'])],
    },
    {
        'name': '비밀번호 재설정',
        'path': '/login > 비밀번호 재설정',
        'req_id': 'R-003',
        'screen_id': 'SC-01-003',
        'placeholder': '비밀번호 재설정 뷰\n이메일 입력 + 재설정 안내 문구\n뒤로가기 버튼',
        'descs': [
            (1, '이메일 입력', ['가입된 이메일 주소 입력']),
            (2, '재설정 요청 버튼', ['입력된 이메일로 재설정 링크 발송']),
            (3, '뒤로가기 버튼', ['로그인 탭으로 복귀']),
        ],
        'cps': [],
    },
    {
        'name': '대시보드',
        'path': '/dashboard',
        'req_id': 'R-010',
        'screen_id': 'SC-02-001',
        'placeholder': '2단 그리드 레이아웃\n좌측: 위젯 영역 (일정/활동/문서/AI챗)\n우측: 캘린더 + 팀 정보 사이드바\n상단: 인사말 배너 + 액션 카운트',
        'descs': [
            (1, '인사말 배너', ['사용자명 + 오늘 회의/액션 수 표시', '스크롤 시 접히는 애니메이션']),
            (2, '일정 타임라인 위젯', ['오늘의 일정을 시간순 표시', 'Google Calendar + DB 일정 통합']),
            (3, '활동 타임라인 위젯', ['최근 활동 피드 (문서 업로드, 일정 등)']),
            (4, 'AI 챗 위젯', ['빠른 AI 질문 입력 영역', '클릭 시 챗 페이지로 이동']),
            (5, '캘린더 위젯', ['월간 달력에 일정 표시']),
            (6, '최근 문서 위젯', ['최근 업로드 문서 5건 표시']),
            (7, '팀 멤버 위젯', ['팀원 현황 및 상태 표시']),
        ],
        'cps': [('위젯 시스템', ['드래그앤드롭 위젯 배치 (편집 모드)', '위젯 추가/제거/순서 변경 가능'])],
    },
    {
        'name': '대시보드 편집 모드',
        'path': '/dashboard > 편집 모드',
        'req_id': 'R-011',
        'screen_id': 'SC-02-002',
        'placeholder': '위젯 편집 UI 활성화 상태\n위젯 드래그앤드롭 핸들 표시\n숨겨진 위젯 미리보기 + 추가 버튼\n초기화 버튼',
        'descs': [
            (1, '편집 모드 토글', ['대시보드 상단 편집 버튼 클릭으로 활성화']),
            (2, '위젯 드래그앤드롭', ['위젯 카드에 드래그 핸들 표시', '자유롭게 순서 변경 가능']),
            (3, '위젯 추가/제거', ['숨겨진 위젯 목록 미리보기', '+ 버튼으로 추가, × 버튼으로 제거']),
            (4, '초기화 버튼', ['기본 레이아웃으로 리셋']),
        ],
        'cps': [('레이아웃 저장', ['변경 사항 LocalStorage에 자동 저장', '브라우저 재시작 시에도 유지'])],
    },
    {
        'name': '대시보드 - 하단 바 출현',
        'path': '/dashboard > 하단 영역',
        'req_id': 'R-013',
        'screen_id': 'SC-02-003',
        'placeholder': '대시보드 하단 영역\nTask Pipeline + 팀원 아바타\nNeeds Attention 위젯',
        'descs': [
            (1, 'Task Pipeline 영역', ['담당자별 프로필 아이콘 표시', '일정 관리/태스크 바로가기']),
            (2, '팀원 아바타 바', ['팀원 프로필 아이콘 일렬 배치', '클릭 시 해당 팀원 업무 현황']),
            (3, 'Needs Attention 위젯', ['긴급 처리 필요 항목 표시', 'View All 클릭 시 전체 목록']),
            (4, '일정 상세 표시', ['오늘 일정에 실제 미팅 정보 표시', '시간대별 이벤트 블록']),
        ],
        'cps': [('실시간 업데이트', ['팀원 상태 변경 시 자동 갱신', '긴급 항목 알림 뱃지'])],
    },
    {
        'name': 'AI 챗봇',
        'path': '/chat',
        'req_id': 'R-020',
        'screen_id': 'SC-03-001',
        'placeholder': '3패널 레이아웃\n좌측: 세션 사이드바 (세션 목록)\n중앙: 채팅 창 (메시지 버블)\n우측: 규정 패널 / 문서 뷰어\n하단: 메시지 입력 + 추천 질문',
        'descs': [
            (1, '세션 사이드바', ['채팅 세션 목록', '새 세션 생성(+) 버튼', '세션 전환/삭제']),
            (2, '채팅 메시지 영역', ['사용자/봇 메시지 버블 구분', 'SSE 스트리밍 실시간 응답', '마크다운 렌더링 지원']),
            (3, '추천 질문', ['빈 채팅 시 추천 질문 카드 표시', '클릭 시 자동 전송']),
            (4, '메시지 입력', ['텍스트 입력 필드', '파일 첨부 버튼', '전송 버튼']),
            (5, '규정 패널 토글', ['우측 규정 패널 열기/닫기', '새로운 규정 판단 시 알림 뱃지']),
        ],
        'cps': [('실시간 응답', ['SSE(Server-Sent Events) 스트리밍', '응답 중 상태 표시 (타이핑 인디케이터)'])],
    },
    {
        'name': 'AI 챗봇 - 규정 판단 응답',
        'path': '/chat > 규정 판단',
        'req_id': 'R-021',
        'screen_id': 'SC-03-002',
        'placeholder': '규정 판단 결과 카드 표시\n판단 결과 뱃지 (가능/불가/조건부)\n신뢰도 바 + 근거 규정 목록\n우측 규정 패널에 상세 내용',
        'descs': [
            (1, '판단 결과 뱃지', ['가능(초록), 불가(빨강), 조건부(노랑), 규정없음(회색)', '한눈에 결과 파악 가능']),
            (2, '신뢰도 표시', ['신뢰도 퍼센트 + 시각적 바', '각 판단 근거별 가중치 표시']),
            (3, '근거 규정 목록', ['관련 규정 조항 번호 및 제목', '클릭 시 규정 패널에서 상세 확인']),
            (4, '경고 사항', ['위반 가능성 또는 주의사항 표시']),
        ],
        'cps': [('규정 패널 연동', ['판단 결과 클릭 시 우측 패널에 규정 상세 표시', 'RAG 기반 하이브리드 검색 결과'])],
    },
    {
        'name': 'AI 챗봇 - 문서 관련 응답',
        'path': '/chat > 문서 응답',
        'req_id': 'R-022',
        'screen_id': 'SC-03-003',
        'placeholder': '문서 관련 응답 카드들\n- 문서 검색: 출처 + 관련도 목록\n- 문서 생성: 템플릿 + 프리뷰 + 다운로드\n- 문서 Q&A: 신뢰도 + 인용 목록\n- 문서 요약: 마크다운 요약',
        'descs': [
            (1, '문서 검색 결과', ['쿼리 응답 텍스트', '출처 문서 목록 + 관련도 점수']),
            (2, '문서 생성 프리뷰', ['템플릿 유형 표시', '생성된 내용 필드별 미리보기', 'DOCX/PDF 다운로드 버튼']),
            (3, '문서 Q&A 응답', ['신뢰도 점수 + 시각적 바', '인용 목록 + 검색 출처']),
            (4, '문서 요약', ['마크다운 형식 요약 텍스트']),
        ],
        'cps': [],
    },
    {
        'name': 'AI 챗봇 - 일정 관리 응답',
        'path': '/chat > 일정 응답',
        'req_id': 'R-023',
        'screen_id': 'SC-03-004',
        'placeholder': '일정 추가 결과 카드\n제목, 날짜, 시간 표시\nGoogle Meet 링크 생성 상태\n이메일 초대 발송 상태',
        'descs': [
            (1, '일정 생성 결과', ['생성된 일정 제목/날짜/시간 표시']),
            (2, 'Google Meet 링크', ['자동 생성된 화상회의 링크', '클릭 시 Meet 접속']),
            (3, '이메일 알림 상태', ['참석자 초대 이메일 발송 여부', '발송 성공/실패 표시']),
            (4, '명확화 요청', ['정보 부족 시 추가 질문 카드', '클릭 가능한 선택지 버튼']),
        ],
        'cps': [('Google 연동', ['Calendar + Meet + Gmail 통합', 'OAuth 2.0 인증 필요'])],
    },
    {
        'name': '문서 생성 - 템플릿 선택',
        'path': '/document-generate',
        'req_id': 'R-040',
        'screen_id': 'SC-04-001',
        'placeholder': '템플릿 선택 화면\n시스템 템플릿: 회의록, 보고서, 제안서 카드\n커스텀 템플릿 목록\n템플릿 업로드 버튼',
        'descs': [
            (1, '시스템 템플릿', ['회의록(meeting_minutes) 카드', '보고서(report) 카드', '제안서(proposal) 카드']),
            (2, '커스텀 템플릿 목록', ['사용자가 업로드한 DOCX 템플릿', '각 템플릿 삭제 버튼']),
            (3, '템플릿 업로드 버튼', ['DOCX 파일 업로드 다이얼로그', '업로드 후 목록에 자동 추가']),
        ],
        'cps': [('템플릿 종류', ['시스템 3종 + 사용자 커스텀 무제한', 'DOCX 형식만 지원'])],
    },
    {
        'name': '문서 생성 - 폼 입력',
        'path': '/document-generate > 폼 입력',
        'req_id': 'R-041',
        'screen_id': 'SC-04-002',
        'placeholder': '동적 폼 영역\n템플릿에 따라 필드 자동 생성\n회의록: 팀/참석자 선택 + 내용 입력\n보고서/제안서: 제목/내용/날짜 등',
        'descs': [
            (1, '동적 폼 필드', ['텍스트, 텍스트에어리어, 날짜, 리스트 타입', '템플릿에 따라 자동 생성']),
            (2, '팀/참석자 선택 (회의록)', ['팀 드롭다운 선택', '멀티 셀렉트 참석자 선택', '선택된 참석자 칩 표시']),
            (3, '기본값 자동 설정', ['날짜: 오늘, 작성자: 현재 사용자', '부서: 소속 팀']),
            (4, '생성 버튼', ['AI 문서 생성 요청', '로딩 중 버튼 비활성화']),
        ],
        'cps': [],
    },
    {
        'name': '문서 생성 - 결과 미리보기',
        'path': '/document-generate > 결과',
        'req_id': 'R-042',
        'screen_id': 'SC-04-003',
        'placeholder': '생성된 문서 미리보기\n회의록: 액션아이템 파이프라인 포함\n보고서/제안서: 필드별 내용 표시\nDOCX/PDF 다운로드 버튼',
        'descs': [
            (1, '회의록 미리보기', ['회의 정보 + 내용 + 결정사항', '액션아이템 파이프라인 시각화']),
            (2, '보고서/제안서 미리보기', ['필드별 생성 내용 표시', '마크다운 렌더링']),
            (3, '다운로드 버튼', ['DOCX 다운로드', 'PDF 다운로드']),
        ],
        'cps': [('AI 생성', ['GPT/Claude API 기반 콘텐츠 생성', '템플릿 구조에 맞춰 자동 채움'])],
    },
    {
        'name': '문서 관리',
        'path': '/documents',
        'req_id': 'R-050',
        'screen_id': 'SC-05-001',
        'placeholder': '2단 레이아웃\n상단: 검색바 + 필터 + 업로드 영역\n좌측: 문서 목록 (제목, 상태, 날짜)\n우측: 선택된 문서 상세',
        'descs': [
            (1, '검색 컨트롤', ['검색 유형: 제목 / 제목+내용 / 날짜', '텍스트 입력 또는 날짜 선택기']),
            (2, '범위 필터', ['회사 전체 / 우리 팀 전환']),
            (3, '문서 업로드', ['드래그앤드롭 업로드 영역', 'PDF, DOCX, TXT 지원', '범위(회사/팀) 선택']),
            (4, '문서 목록', ['문서명, 상태 뱃지(완료/처리중/실패)', '클릭 시 우측 상세 패널 표시']),
        ],
        'cps': [('AI 분석', ['업로드 시 자동 요약/카테고리/태그 생성', '분석 완료까지 "처리중" 상태 표시'])],
    },
    {
        'name': '문서 상세 보기',
        'path': '/documents > 문서 상세',
        'req_id': 'R-051',
        'screen_id': 'SC-05-002',
        'placeholder': '문서 상세 패널 (우측)\n문서 메타데이터 (이름, 유형, 버전, 날짜)\n카테고리 뱃지 + 태그 목록\nAI 요약 내용 표시\n삭제 버튼',
        'descs': [
            (1, '문서 메타데이터', ['파일명, 문서 유형, 버전', '업로드 날짜, 업로더 정보']),
            (2, '카테고리 및 태그', ['AI가 자동 분류한 카테고리 뱃지', '관련 태그 목록']),
            (3, '문서 내용 미리보기', ['추출된 텍스트 내용 표시', 'AI 요약 포함']),
            (4, '삭제 버튼', ['문서 삭제 (확인 다이얼로그)']),
        ],
        'cps': [],
    },
    {
        'name': '일정 관리 - 캘린더',
        'path': '/schedules > 캘린더 탭',
        'req_id': 'R-060',
        'screen_id': 'SC-06-001',
        'placeholder': 'FullCalendar 컴포넌트\n월/주/일 뷰 전환\n이벤트 색상별 구분 (타입/Google)\n일정 추가(+) 버튼\n연동 뱃지 (Google/Slack)',
        'descs': [
            (1, '캘린더 뷰', ['FullCalendar 기반 월/주/일 뷰', 'Google Calendar + DB 일정 통합 표시']),
            (2, '이벤트 유형 구분', ['색상 범례로 일정 타입 구분', '개인/팀/Google 이벤트 식별']),
            (3, '일정 추가 버튼', ['일정 생성 모달 열기', '제목, 설명, 날짜, 시간, 타입 입력']),
            (4, 'Google 연동 뱃지', ['Google Calendar 연동 상태 표시', '새로고침 버튼']),
            (5, '일정 타입 관리', ['커스텀 일정 타입 생성/편집/삭제']),
        ],
        'cps': [('Google Calendar 동기화', ['양방향 동기화 지원', 'OAuth 2.0 인증 필요'])],
    },
    {
        'name': '일정 관리 - Google 연동',
        'path': '/schedules > Google 연동',
        'req_id': 'R-062',
        'screen_id': 'SC-06-003',
        'placeholder': 'Google Integration 모달',
        'descs': [
            (1, 'Google 계정 연결', ['Google 계정 연결 상태 표시', '연결 해제 버튼']),
            (2, 'Google Calendar 연동', ['캘린더 일정 양방향 동기화', '연동 완료 시 체크 표시']),
            (3, 'Google Tasks 연동', ['태스크 동기화 연결', 'Pipeline 태스크와 연동']),
            (4, 'Gmail 연동', ['이벤트 알림 이메일 발송', '참석자 초대 메일 연동']),
            (5, 'Google Sheets 연동', ['Google Sheets 목록 조회', 'Sheets 탭에서 확인 가능']),
        ],
        'cps': [('OAuth 2.0 인증', ['Synced via OAuth 2.0', '토큰 자동 갱신'])],
    },
    {
        'name': '일정 관리 - Slack 연동',
        'path': '/schedules > Slack 연동',
        'req_id': 'R-063',
        'screen_id': 'SC-06-004',
        'placeholder': 'Slack Integration 모달',
        'descs': [
            (1, 'Slack 알림 연결', ['Slack 워크스페이스 연동', '알림 토글 ON/OFF']),
            (2, '알림 설정', ['일정 알림 메시지 자동 전송', '새 이벤트 시 Slack 채널 알림']),
            (3, 'OAuth 2.0 인증', ['Slack OAuth 2.0 인증 플로우', 'Done 버튼으로 설정 완료']),
        ],
        'cps': [('실시간 알림', ['일정 변경 시 Slack 채널 자동 알림', '멘션 및 리마인더 지원'])],
    },
    {
        'name': '일정 관리 - 파이프라인 프로젝트',
        'path': '/schedules > Pipeline 탭',
        'req_id': 'R-061',
        'screen_id': 'SC-06-002',
        'placeholder': '프로젝트 목록 화면',
        'descs': [
            (1, '프로젝트 카드', ['프로젝트명 + 진행률 퍼센트 바 표시', '태스크 수 + D-day 카운트 (D-20, D-14 등)', '멤버 아바타 아이콘 표시']),
            (2, '탭 네비게이션', ['Calendar / Pipeline / Approvals / Sheets 탭', 'Pipeline 탭 선택 시 프로젝트 목록 표시']),
            (3, '연동 상태 뱃지', ['Google Connected / Slack Connected 뱃지', '연동 상태 실시간 표시']),
            (4, '새 프로젝트 생성', ['+ 새 프로젝트 버튼', '프로젝트명, 멤버, 마감일 설정']),
        ],
        'cps': [('프로젝트 관리', ['프로젝트별 태스크 그룹핑', 'Google/Slack 연동 상태 표시'])],
    },
    {
        'name': '업무 관리 (칸반)',
        'path': '/schedules > Pipeline > 프로젝트 상세',
        'req_id': 'R-070',
        'screen_id': 'SC-07-001',
        'placeholder': '칸반 보드',
        'descs': [
            (1, '칸반 컬럼', ['To Do / In Progress / Review / Done', '각 컬럼 카운트 뱃지']),
            (2, '태스크 카드', ['우선순위 뱃지 (HIGH/MEDIUM/LOW)', '제목, 설명, 태그 (Backend, API 등)', '담당자 아바타 + 마감일 D-day']),
            (3, '드래그앤드롭', ['카드를 컬럼 간 드래그 이동', '낙관적 업데이트(Optimistic Update)']),
            (4, 'Google Tasks 연동', ['Google Tasks 바로가기 버튼', 'Google Tasks 확인 버튼']),
            (5, '새 태스크 버튼', ['+ 새 태스크 클릭 시 생성 모달']),
        ],
        'cps': [('D-day 표시', ['In Progress/Review: D-1 빨강, D-2~7 주황', 'Done: 일반 날짜 표시'])],
    },
    {
        'name': '업무 관리 - 태스크 생성',
        'path': '/schedules > Pipeline > New Task',
        'req_id': 'R-071',
        'screen_id': 'SC-07-002',
        'placeholder': '태스크 생성 모달',
        'descs': [
            (1, '제목 입력', ['태스크 제목 텍스트 입력']),
            (2, '설명 입력', ['태스크 상세 설명 입력']),
            (3, '담당자 선택', ['팀원 아바타 + 이름 목록 표시', '멀티 셀렉트로 복수 담당자 지정']),
            (4, '우선순위 설정', ['Low / Medium / High 선택']),
            (5, '마감일 설정', ['날짜 선택기 (Due Date)', 'D-day 자동 계산']),
        ],
        'cps': [('자동 연동', ['생성 즉시 칸반 보드에 반영', 'Google Tasks 동기화'])],
    },
    {
        'name': '결재 관리',
        'path': '/schedules > Approvals 탭',
        'req_id': 'R-080',
        'screen_id': 'SC-08-001',
        'placeholder': '결재 관리 화면',
        'descs': [
            (1, 'Process 컬럼', ['결재 요청 목록 표시', '연차/반차 신청 등 결재 항목', '승인됨/거절됨 상태 뱃지']),
            (2, 'Schedule 컬럼', ['일정 관련 결재 항목', '진행 상황 업데이트 카드']),
            (3, 'New Tasks 컬럼', ['결재 관련 신규 태스크', 'PR 리뷰, 배포 승인 요청 등']),
            (4, '새 요청 버튼', ['+ 새 요청 클릭 시 결재 생성']),
        ],
        'cps': [('결재 프로세스', ['3단 칸반 형태 결재 흐름 시각화', '승인/거절 상태 실시간 반영'])],
    },
    {
        'name': '결재 상세 및 생성',
        'path': '/schedules > Approvals > 상세/생성',
        'req_id': 'R-081',
        'screen_id': 'SC-08-002',
        'placeholder': '결재 상세 및 생성 모달',
        'descs': [
            (1, '결재 유형', ['연차/반차, 재택근무, PR리뷰 등 10종', '유형별 아이콘 + 라벨']),
            (2, '요청자 정보', ['아바타, 이름, 팀, 요청 일시']),
            (3, '상세 내용', ['결재 제목 및 상세 내용 표시', '첨부파일 미리보기/다운로드']),
            (4, '승인/거절 버튼', ['대기중 항목에 승인/거절 처리', '처리 시 즉시 상태 변경']),
        ],
        'cps': [],
    },
    {
        'name': '쪽지',
        'path': '/dashboard > 쪽지함',
        'req_id': 'R-090',
        'screen_id': 'SC-09-001',
        'placeholder': '쪽지함 팝업',
        'descs': [
            (1, '쪽지함 팝업', ['대시보드 우측에 쪽지함 오버레이', '받은 쪽지 / 보낸 쪽지 탭']),
            (2, '쪽지 카드', ['발신자 아바타 + 이름', '메시지 미리보기 + 발송 시간', '읽지 않음 표시']),
            (3, '쪽지 보내기', ['+ 쪽지 보내기 버튼', '수신자 선택 + 내용 입력']),
        ],
        'cps': [('실시간 알림', ['새 쪽지 수신 시 알림 뱃지', '캘린더 뷰 위 오버레이 표시'])],
    },
    {
        'name': 'AI 어시스턴트 팝업',
        'path': '/dashboard > AI 어시스턴트',
        'req_id': 'R-091',
        'screen_id': 'SC-09-002',
        'placeholder': 'AI 어시스턴트 팝업',
        'descs': [
            (1, 'AI 어시스턴트 패널', ['대시보드 우측에 슬라이드 팝업 표시', '추천 질문 목록 제공']),
            (2, '추천 질문', ['클릭 시 해당 질문 바로 전송', '규정 판단, 문서 검색 등 다양한 질문 예시']),
            (3, '최근 대화 히스토리', ['이전 대화 세션 목록 표시', '클릭 시 해당 대화로 이동']),
            (4, '메시지 입력', ['하단 텍스트 입력 필드', '전송 버튼으로 AI 질문']),
            (5, '새 스토리 / Assigned', ['+ 새 스토리 버튼으로 새 대화 시작', 'Assigned 버튼으로 할당된 항목 확인']),
        ],
        'cps': [('빠른 접근', ['대시보드에서 바로 AI 질문 가능', '전체 챗 페이지 이동 없이 간편 사용'])],
    },
    {
        'name': '마이페이지',
        'path': '/mypage',
        'req_id': 'R-095',
        'screen_id': 'SC-10-001',
        'placeholder': '마이페이지',
        'descs': [
            (1, '프로필 섹션', ['아바타 + 이름, 이메일, 팀, 역할', '프로필 수정 버튼']),
            (2, '통계 카드', ['AI 대화 수 / 최근 문서 수 / 보관 일정 수', '클릭 시 상세 목록 이동']),
            (3, '계정 보안', ['이메일, 계정 권한 (ADMINISTRATOR)', '비밀번호 변경 버튼']),
            (4, '최근 작업 히스토리', ['최근 AI 대화 목록', '최근 사용 문서 목록']),
            (5, '개인 메모', ['메모 추가/수정/삭제', '메모 카드 목록']),
        ],
        'cps': [('아바타', ['프로필 이미지 업로드 가능', 'Dicebear API 기본 아바타'])],
    },
    {
        'name': '마이페이지 - 프로필 수정',
        'path': '/mypage > 프로필 수정',
        'req_id': 'R-096',
        'screen_id': 'SC-10-002',
        'placeholder': '프로필 수정 모달',
        'descs': [
            (1, '프로필 수정 모달', ['마이페이지 위 오버레이 모달 표시', '프로필 이미지 변경 가능']),
            (2, '이름 입력', ['현재 이름 표시 및 수정 가능']),
            (3, '소속팀 입력', ['소속 팀 표시 및 수정 가능']),
            (4, '연락처 입력', ['전화번호 입력 필드']),
            (5, '주소 입력', ['주소 텍스트 입력 필드']),
            (6, '취소/저장하기 버튼', ['취소 클릭 시 모달 닫기', '저장하기 클릭 시 변경사항 DB 반영']),
        ],
        'cps': [('입력 검증', ['필수 필드 미입력 시 저장 불가', '변경사항 즉시 프로필에 반영'])],
    },
    {
        'name': '마이페이지 - AI 대화 목록',
        'path': '/mypage > AI 대화 탭',
        'req_id': 'R-097',
        'screen_id': 'SC-10-003',
        'placeholder': 'AI 대화 목록',
        'descs': [
            (1, 'AI 대화 목록', ['과거 AI 대화 세션 목록 표시', '대화 제목 + 날짜 + 시간 표시']),
            (2, '통계 카드', ['AI 대화 29건 / 최근 문서 14건 / 남은 일정 1건', '각 카드 클릭 시 해당 탭으로 전환']),
            (3, '대화 항목', ['재택근무 규정 알아줘, 인턴 관련 문서 찾아줘 등', '클릭 시 해당 대화 상세로 이동']),
            (4, '계정 보안', ['이메일, 계정 권한(ADMINISTRATOR) 표시', '비밀번호 변경 버튼']),
        ],
        'cps': [('대화 관리', ['대화 이력 전체 조회', '대화별 날짜/시간 기록'])],
    },
    {
        'name': '마이페이지 - 문서 목록',
        'path': '/mypage > 최근 문서 탭',
        'req_id': 'R-098',
        'screen_id': 'SC-10-004',
        'placeholder': '문서 목록',
        'descs': [
            (1, '문서 목록', ['사용자가 업로드/생성한 문서 목록', '문서 제목 + 파일 형식(pdf) 표시']),
            (2, '통계 카드', ['AI 대화 / 최근 문서 / 남은 일정 카운트', '최근 문서 탭 활성 상태']),
            (3, '문서 항목', ['최종프로젝트_아이디어(수정후) pdf 등', '클릭 시 문서 미리보기 팝업']),
            (4, '계정 보안', ['이메일, 계정 권한 표시', '비밀번호 변경 버튼']),
        ],
        'cps': [('문서 접근', ['마이페이지에서 내 문서 바로 확인', '문서 관리 페이지 이동 없이 조회'])],
    },
    {
        'name': '마이페이지 - 남은 일정',
        'path': '/mypage > 남은 일정 탭',
        'req_id': 'R-099',
        'screen_id': 'SC-10-005',
        'placeholder': '남은 일정 목록',
        'descs': [
            (1, '남은 일정 목록', ['예정된 일정 목록 표시', '일정 제목 + 날짜/시간 표시']),
            (2, '통계 카드', ['AI 대화 / 최근 문서 / 남은 일정 카운트', '남은 일정 탭 활성 상태']),
            (3, '최근 작업 및 히스토리', ['최근 AI 대화 + 최근 사용 문서 통합 표시', '전체 보기 버튼']),
        ],
        'cps': [('일정 관리', ['마이페이지에서 남은 일정 빠르게 확인', '일정 클릭 시 상세 정보 표시'])],
    },
    {
        'name': '마이페이지 - 문서 미리보기',
        'path': '/mypage > 문서 미리보기',
        'req_id': 'R-099-1',
        'screen_id': 'SC-10-006',
        'placeholder': '문서 미리보기 모달',
        'descs': [
            (1, '문서 미리보기 모달', ['마이페이지 위 오버레이 다이얼로그', '문서 제목 + 파일 형식 아이콘 표시']),
            (2, '문서 내용 표시', ['문서 텍스트 내용 스크롤 가능 영역', '마크다운/텍스트 형식 렌더링']),
            (3, '문서 메타 정보', ['파일명, 유형(pdf) 표시', '닫기(X) 버튼으로 모달 닫기']),
        ],
        'cps': [('미리보기', ['문서 관리 페이지 이동 없이 내용 확인', '모달 형태로 빠른 조회'])],
    },
    {
        'name': '관리자 설정',
        'path': '/admin',
        'req_id': 'R-100',
        'screen_id': 'SC-11-001',
        'placeholder': '관리자 설정 페이지',
        'descs': [
            (1, '팀 필터', ['전체/개발/QA기획/UI/UX/영업/마케팅/CS', '선택 시 데이터 자동 갱신']),
            (2, '통계 카드', ['전체 사용자 수, 오늘 질의 수, 등록 규정 수']),
            (3, '사용자 관리', ['사용자 목록 테이블 (이름, 이메일, 팀, 권한)', '+ 사용자 추가 버튼', '권한 수정/삭제 버튼']),
            (4, '인기 질의', ['자주 묻는 질의 목록 + 횟수 바 차트']),
            (5, '최근 질의 로그', ['질의 내용 + 타임스탬프', '시간대별 질의 기록']),
        ],
        'cps': [('접근 제어', ['관리자 권한(is_admin) 필수', '비관리자 접근 시 대시보드로 리다이렉트'])],
    },
    {
        'name': '관리자 설정 - 질의 상세',
        'path': '/admin > 질의 검색',
        'req_id': 'R-101',
        'screen_id': 'SC-11-002',
        'placeholder': '질의 상세 모달',
        'descs': [
            (1, '질의 검색 모달', ['관리자 설정 페이지 위 오버레이 팝업', '질의 상세 내용 표시']),
            (2, '질의 내용', ['사용자 질의 텍스트 전체 표시', 'RAG 파이프라인 처리 과정 설명']),
            (3, '처리 정보', ['질의 날짜/시간 표시', 'RAG 검색 방식 (bge-v2, Qdrant 등) 상세']),
            (4, '사용자 관리 테이블', ['모달 뒤 사용자 목록 테이블 표시', '이름, 이메일, 팀, 권한 컬럼']),
            (5, 'RAG 통계', ['오늘 RAG 질의 통계 바 차트', '최근 질의 로그 타임라인']),
        ],
        'cps': [('관리자 모니터링', ['질의별 RAG 파이프라인 상세 확인', '사용자별 질의 패턴 분석 가능'])],
    },
    {
        'name': '다크 모드',
        'path': '/dashboard (다크 모드)',
        'req_id': 'R-110',
        'screen_id': 'SC-12-001',
        'placeholder': '다크 모드 대시보드',
        'descs': [
            (1, '다크 모드 테마', ['전체 UI 다크 배경(#1A1A2E 계열) 적용', '텍스트/아이콘 밝은 색상 자동 전환']),
            (2, '인사말 배너', ['사용자명 + 오늘 회의/일정 수 표시', '다크 배경 위 흰색 텍스트']),
            (3, 'Today Schedule', ['오늘 일정 타임라인 다크 테마 적용', '이벤트 블록 색상 유지 (가독성 확보)']),
            (4, '캘린더 위젯', ['월간 캘린더 다크 배경 적용', '오늘 날짜 하이라이트 유지']),
            (5, 'Task Pipeline', ['칸반 보드 카드 다크 스타일', '우선순위 뱃지 색상 유지 (MEDIUM/HIGH/LOW)']),
            (6, 'Needs Attention', ['긴급 항목 위젯 다크 테마', '알림 뱃지 및 버튼 색상 유지']),
        ],
        'cps': [('테마 전환', ['설정에서 라이트/다크 모드 전환', '사용자 선호 테마 LocalStorage 저장'])],
    },
]


def draw_cover_page(c):
    c.setFillColor(white)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(black)
    c.setFont(FONT, 20)
    c.drawString(ML + 10, PAGE_H - 100, 'SKN21-Final-3Team')
    c.setFont(FONT, 11)
    c.drawString(ML + 10, PAGE_H - 125, 'WorkFlow Agent (듀드): 자체 sLLM 개발을 통한 기업 업무 활용 생성형 AI 플랫폼')
    c.setFont(FONT, 42)
    c.drawString(ML + 10, PAGE_H - 250, 'Workflow Agent 화면설계서')
    c.setFont(FONT_EN_B, 12)
    right_x = PAGE_W / 2 + 50
    c.drawString(right_x, PAGE_H - 400, 'Date')
    c.drawString(right_x, PAGE_H - 425, 'Writer')
    c.setFont(FONT, 12)
    c.drawString(right_x + 80, PAGE_H - 400, '2025.03.11')
    c.drawString(right_x + 80, PAGE_H - 425, '안혜빈')


def draw_header_table(c, name, path, req_id, screen_id):
    y_top = PAGE_H - MT
    row_h = 22
    label_w = 85
    col2_w = (PAGE_W - ML - MR - label_w * 2) * 0.62
    col4_w = PAGE_W - ML - MR - label_w * 2 - col2_w
    cols = [label_w, col2_w, label_w, col4_w]

    # Top right: Confidential + team
    c.setFont(FONT_EN_B, 8)
    c.setFillColor(RED)
    c.drawRightString(PAGE_W - MR - 120, y_top + 5, 'Confidential')
    c.setFillColor(black)
    c.drawRightString(PAGE_W - MR, y_top + 5, 'SKN21-Final-3Team')

    x = ML
    for row_i, row_data in enumerate([(name, req_id), (path, screen_id)]):
        y = y_top - row_i * row_h
        labels = ['화면명', '요구사항 ID'] if row_i == 0 else ['화면 경로', '화면 ID']
        cx = x
        for col_i in range(4):
            w = cols[col_i]
            if col_i % 2 == 0:
                c.setFillColor(DARK_GRAY)
                c.rect(cx, y - row_h, w, row_h, fill=1, stroke=0)
                c.setFillColor(white)
                c.setFont(FONT, 9)
                c.drawCentredString(cx + w / 2, y - row_h + 7, labels[col_i // 2])
            else:
                c.setStrokeColor(DARK_GRAY)
                c.setLineWidth(0.5)
                c.rect(cx, y - row_h, w, row_h, fill=0, stroke=1)
                c.setFillColor(black)
                c.setFont(FONT, 9)
                val = row_data[0] if col_i == 1 else row_data[1]
                c.drawString(cx + 8, y - row_h + 7, str(val))
            cx += w

    return y_top - 2 * row_h


def draw_description_section(c, screen_id, descs, cps, content_top):
    desc_x = 545
    desc_w = PAGE_W - MR - desc_x
    y = content_top - 8
    num_col_w = 20
    text_col_w = desc_w - num_col_w

    # Description header
    header_h = 20
    c.setFillColor(DARK_GRAY)
    c.rect(desc_x, y - header_h, desc_w, header_h, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont(FONT_EN_B, 9)
    c.drawCentredString(desc_x + desc_w / 2, y - header_h + 6, 'Description')
    y -= header_h

    # Screen ID row
    sid_h = 16
    c.setStrokeColor(DARK_GRAY)
    c.setLineWidth(0.5)
    c.rect(desc_x, y - sid_h, desc_w, sid_h, fill=0, stroke=1)
    c.setFillColor(black)
    c.setFont(FONT, 8)
    c.drawString(desc_x + 5, y - sid_h + 4, screen_id)
    y -= sid_h

    # Description items
    for num, title, bullets in descs:
        lines = [f'<b>{title}</b>']
        for b in bullets:
            lines.append(f'  \u2022 {b}')
        text = '\n'.join(lines)

        # Calculate height needed
        title_h = 13
        bullet_h = 11
        item_h = title_h + len(bullets) * bullet_h + 6
        if item_h < 26:
            item_h = 26

        if y - item_h < MB:
            break

        # Number cell
        c.setStrokeColor(DARK_GRAY)
        c.setLineWidth(0.5)
        c.rect(desc_x, y - item_h, num_col_w, item_h, fill=0, stroke=1)
        c.setFillColor(black)
        c.setFont(FONT, 8)
        c.drawCentredString(desc_x + num_col_w / 2, y - item_h / 2 - 3, str(num))

        # Text cell
        c.rect(desc_x + num_col_w, y - item_h, text_col_w, item_h, fill=0, stroke=1)
        ty = y - 4
        c.setFont(FONT, 8.5)
        c.setFillColor(black)
        c.drawString(desc_x + num_col_w + 4, ty - 9, title)
        ty -= 13
        c.setFont(FONT, 7.5)
        for b in bullets:
            c.drawString(desc_x + num_col_w + 10, ty - 8, f'\u2022 {b}')
            ty -= 11

        y -= item_h

    # Check Points
    if cps:
        cp_header_h = 18
        if y - cp_header_h > MB:
            c.setFillColor(MED_GRAY)
            c.rect(desc_x, y - cp_header_h, desc_w, cp_header_h, fill=1, stroke=0)
            c.setFillColor(white)
            c.setFont(FONT_EN_B, 8.5)
            c.drawCentredString(desc_x + desc_w / 2, y - cp_header_h + 5, 'Check Point')
            y -= cp_header_h

            for cp_title, cp_bullets in cps:
                title_h = 11
                bullet_h = 10
                cp_h = title_h + len(cp_bullets) * bullet_h + 6
                if cp_h < 22:
                    cp_h = 22
                if y - cp_h < MB:
                    break

                c.setStrokeColor(DARK_GRAY)
                c.setLineWidth(0.5)
                c.rect(desc_x, y - cp_h, desc_w, cp_h, fill=0, stroke=1)
                c.setFillColor(black)
                c.setFont(FONT, 8.5)
                c.drawString(desc_x + 5, y - 12, cp_title)
                c.setFont(FONT, 7.5)
                ty = y - 14
                for b in cp_bullets:
                    ty -= 10
                    c.drawString(desc_x + 11, ty, f'\u2022 {b}')
                y -= cp_h

    # Draw outer border for entire description section
    total_h = content_top - 8 - y
    c.setStrokeColor(DARK_GRAY)
    c.setLineWidth(1)
    c.rect(desc_x, y, desc_w, total_h, fill=0, stroke=1)


SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs', 'screenshots')

SCREENSHOT_MAP = {
    'SC-01-001': 'SC-01-001_login.png',
    'SC-01-002': 'SC-01-002_register.png',
    'SC-01-003': '비밀번호재설정.png',
    'SC-02-001': 'SC-02-001_dashboard.png',
    'SC-02-002': '대시보드_편집모드.png',
    'SC-02-003': '메뉴바출현.png',
    'SC-03-001': 'SC-03-001_chat.png',
    'SC-03-002': '챗봇_규정응답.png',
    'SC-03-003': 'SC-03-001_chat.png',
    'SC-03-004': '챗봇_일정생성.png',
    'SC-04-001': 'SC-04-001_doc_generate.png',
    'SC-04-002': '문서생성_문서필드.png',
    'SC-04-003': 'SC-04-001_doc_generate.png',
    'SC-05-001': '문서관리 .png',
    'SC-05-002': '문서관리_문서자세히.png',
    'SC-06-001': 'SC-06-001_schedules.png',
    'SC-06-002': 'pipeline_project.png',
    'SC-06-003': '일정관리_google.png',
    'SC-06-004': '일정관리_slack.png',
    'SC-07-001': 'pipeline.png',
    'SC-07-002': 'pipeline_추가 .png',
    'SC-08-001': 'approvals .png',
    'SC-08-002': 'approvals .png',
    'SC-09-001': '쪽지.png',
    'SC-09-002': '챗봇팝업.png',
    'SC-10-001': '마이페이지.png',
    'SC-10-002': '프로필수정.png',
    'SC-10-003': 'AI대화.png',
    'SC-10-004': '문서생성.png',
    'SC-10-005': '남은일정.png',
    'SC-10-006': '문서미리보기.png',
    'SC-11-001': '관리자설정.png',
    'SC-11-002': '관리자설정_질의자세히.png',
    'SC-12-001': '다크모드.png',
}

def draw_screenshot_area(c, content_top, placeholder_text, screen_id):
    sc_x = ML
    sc_w = 505
    sc_h = content_top - 8 - MB - 10
    sc_y = content_top - 8 - sc_h

    # Try to load actual screenshot
    img_file = SCREENSHOT_MAP.get(screen_id, '')
    img_path = os.path.join(SCREENSHOT_DIR, img_file) if img_file else ''

    if img_path and os.path.exists(img_path):
        # Draw border
        c.setStrokeColor(HexColor('#CCCCCC'))
        c.setLineWidth(0.5)
        c.rect(sc_x, sc_y, sc_w, sc_h, fill=0, stroke=1)
        # Draw screenshot fitted inside the area with padding
        pad = 4
        try:
            from reportlab.lib.utils import ImageReader
            img = ImageReader(img_path)
            iw, ih = img.getSize()
            avail_w = sc_w - 2 * pad
            avail_h = sc_h - 2 * pad
            scale = min(avail_w / iw, avail_h / ih)
            dw = iw * scale
            dh = ih * scale
            dx = sc_x + pad + (avail_w - dw) / 2
            dy = sc_y + pad + (avail_h - dh) / 2
            c.drawImage(img_path, dx, dy, width=dw, height=dh, preserveAspectRatio=True)
        except Exception:
            _draw_placeholder(c, sc_x, sc_y, sc_w, sc_h, placeholder_text)
    else:
        _draw_placeholder(c, sc_x, sc_y, sc_w, sc_h, placeholder_text)

def _draw_placeholder(c, sc_x, sc_y, sc_w, sc_h, placeholder_text):
    c.setStrokeColor(HexColor('#CCCCCC'))
    c.setLineWidth(1)
    c.setFillColor(LIGHT_GRAY)
    c.rect(sc_x, sc_y, sc_w, sc_h, fill=1, stroke=1)
    c.setFillColor(HexColor('#999999'))
    c.setFont(FONT, 14)
    c.drawCentredString(sc_x + sc_w / 2, sc_y + sc_h / 2 + 40, '[화면 캡처 영역]')
    c.setFont(FONT, 9)
    lines = placeholder_text.split('\n')
    ty = sc_y + sc_h / 2 + 10
    for line in lines:
        c.drawCentredString(sc_x + sc_w / 2, ty, line)
        ty -= 14
    c.setFont(FONT, 7)
    c.setFillColor(HexColor('#AAAAAA'))
    c.drawCentredString(sc_x + sc_w / 2, sc_y + 15, '* 실제 화면 스크린샷으로 교체 필요')


def draw_screen_page(c, screen):
    c.setFillColor(white)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    content_top = draw_header_table(c, screen['name'], screen['path'], screen['req_id'], screen['screen_id'])
    draw_screenshot_area(c, content_top, screen.get('placeholder', ''), screen['screen_id'])
    draw_description_section(c, screen['screen_id'], screen['descs'], screen.get('cps', []), content_top)


def main():
    setup_fonts()
    output = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs', '화면설계서_DUDE.pdf')
    c = canvas.Canvas(output, pagesize=landscape(A4))
    c.setTitle('Workflow Agent 화면설계서')
    c.setAuthor('SKN21-Final-3Team')

    draw_cover_page(c)

    for screen in SCREENS:
        c.showPage()
        draw_screen_page(c, screen)

    c.save()
    print(f'Generated: {output}')
    print(f'Total pages: {len(SCREENS) + 1} (1 cover + {len(SCREENS)} screens)')


if __name__ == '__main__':
    main()
