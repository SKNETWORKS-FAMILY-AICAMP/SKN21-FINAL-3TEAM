"""
WorkFlow Agent (듀듀) 시스템 구성도 v3
- 흑백 기반 깔끔한 디자인 (참고 PDF 스타일)
- 최소한의 색상 사용
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import os

plt.rcParams['font.family'] = 'AppleGothic'
plt.rcParams['axes.unicode_minus'] = False

# ── 색상 (모노톤) ──
WHITE = '#FFFFFF'
BG = '#F9F9F9'
BLACK = '#1a1a1a'
DARK = '#333333'
GRAY = '#777777'
LIGHT = '#E8E8E8'
BORDER = '#CCCCCC'
HEADER_BG = '#2D2D2D'
HEADER_TX = '#FFFFFF'
BOX_BG = '#FAFAFA'
ACCENT = '#4A90D9'  # 화살표용 포인트 컬러 하나만


def box(ax, x, y, w, h, fc=WHITE, ec=BORDER, lw=1.2):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.006",
                        facecolor=fc, edgecolor=ec, linewidth=lw,
                        transform=ax.transAxes, zorder=2)
    ax.add_patch(p)


def header(ax, x, y, w, h=0.035, title='', fs=10):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.005",
                        facecolor=HEADER_BG, edgecolor=HEADER_BG, linewidth=0,
                        transform=ax.transAxes, zorder=3)
    ax.add_patch(p)
    ax.text(x + w/2, y + h/2, title, ha='center', va='center',
            fontsize=fs, fontweight='bold', color=HEADER_TX,
            transform=ax.transAxes, zorder=4)


def item(ax, x, y, w, h, text, fs=7.5, fw='normal', fc=WHITE, ec=BORDER):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.004",
                        facecolor=fc, edgecolor=ec, linewidth=0.8,
                        transform=ax.transAxes, zorder=5)
    ax.add_patch(p)
    ax.text(x + w/2, y + h/2, text, ha='center', va='center',
            fontsize=fs, fontweight=fw, color=BLACK,
            transform=ax.transAxes, zorder=6)


def label(ax, x, y, text, fs=9, color=DARK, fw='bold'):
    ax.text(x, y, text, ha='left', va='center',
            fontsize=fs, fontweight=fw, color=color,
            transform=ax.transAxes, zorder=7)


def arrow(ax, x1, y1, x2, y2, color=DARK, lw=1.3):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=color, lw=lw),
                transform=ax.transAxes, zorder=10)


def arrow_lbl(ax, x1, y1, x2, y2, text, color=DARK, lw=1.3, fs=7):
    arrow(ax, x1, y1, x2, y2, color=color, lw=lw)
    mx, my = (x1+x2)/2, (y1+y2)/2
    ax.text(mx, my + 0.013, text, ha='center', va='bottom',
            fontsize=fs, color=color, fontweight='bold',
            transform=ax.transAxes, zorder=11)


def create():
    fig, ax = plt.subplots(1, 1, figsize=(24, 15))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    fig.patch.set_facecolor(WHITE)

    # ── 타이틀 ──
    ax.text(0.5, 0.975, 'WorkFlow Agent (듀듀) - 시스템 구성도',
            ha='center', va='center', fontsize=20, fontweight='bold', color=BLACK,
            transform=ax.transAxes)
    ax.text(0.5, 0.955, 'SK Networks Family AI Camp 21기 3팀',
            ha='center', va='center', fontsize=10, color=GRAY,
            transform=ax.transAxes)
    ax.plot([0.03, 0.97], [0.945, 0.945], color=LIGHT, lw=1, transform=ax.transAxes, zorder=1)

    # ═══════════════════════════════════
    # 상단: USER | FRONTEND | BACKEND | DATABASE | EXTERNAL
    # ═══════════════════════════════════
    ty = 0.55
    th = 0.375
    g = 0.012

    # ── USER ──
    ux, uw = 0.03, 0.12
    box(ax, ux, ty, uw, th, fc=BG)
    header(ax, ux, ty + th - 0.035, uw, title='USER')

    label(ax, ux + 0.01, ty + th - 0.065, '회원가입', fs=8.5)
    for i, f in enumerate(['e-mail', 'name', 'password', 'team (부서)']):
        item(ax, ux + 0.01, ty + th - 0.095 - i*0.03, uw - 0.02, 0.024, f, fs=7.5)

    label(ax, ux + 0.01, ty + th - 0.225, '로그인', fs=8.5)
    for i, f in enumerate(['e-mail', 'password']):
        item(ax, ux + 0.01, ty + th - 0.255 - i*0.03, uw - 0.02, 0.024, f, fs=7.5)

    ax.text(ux + uw/2, ty + 0.025, '직원 사용자', ha='center', va='center',
            fontsize=8.5, fontweight='bold', color=GRAY, transform=ax.transAxes, zorder=5)

    # ── FRONTEND ──
    fx, fw = ux + uw + g, 0.19
    box(ax, fx, ty, fw, th, fc=BG)
    header(ax, fx, ty + th - 0.035, fw, title='FRONTEND')

    label(ax, fx + 0.01, ty + th - 0.065, 'homepage 화면', fs=8.5)
    pages = ['대시보드', 'AI 챗봇 (SSE 스트리밍)', '문서 관리 / 문서 생성',
             '회의록 생성', '일정 관리 (캘린더/칸반)',
             '태스크 파이프라인', '결재 요청 / 쪽지함',
             '마이페이지', '관리자 페이지', '로그인 / 회원가입']
    for i, p in enumerate(pages):
        item(ax, fx + 0.01, ty + th - 0.095 - i*0.03, fw - 0.02, 0.024, p, fs=7.5)

    ax.text(fx + fw/2, ty + 0.025, 'React + Vite + Tailwind + Zustand', ha='center', va='center',
            fontsize=7, color=GRAY, transform=ax.transAxes, zorder=5)

    # ── BACKEND ──
    bx, bw = fx + fw + g, 0.21
    box(ax, bx, ty, bw, th, fc=BG)
    header(ax, bx, ty + th - 0.035, bw, title='BACKEND')

    label(ax, bx + 0.01, ty + th - 0.065, 'API Routers (18개)', fs=8.5)

    rw = 0.062
    r1 = ['/chat (SSE)', '/auth (JWT)', '/documents', '/meetings', '/schedules', '/calendar']
    r2 = ['/google (OAuth)', '/tasks', '/gmail', '/sheets', '/pipeline', '/approvals']
    r3 = ['/messages', '/admin', '/regulations', '/slack', '', '']

    for i, r in enumerate(r1):
        if r: item(ax, bx + 0.007, ty + th - 0.095 - i*0.03, rw, 0.024, r, fs=6.5)
    for i, r in enumerate(r2):
        if r: item(ax, bx + 0.007 + rw + 0.004, ty + th - 0.095 - i*0.03, rw, 0.024, r, fs=6.5)
    for i, r in enumerate(r3):
        if r: item(ax, bx + 0.007 + (rw + 0.004)*2, ty + th - 0.095 - i*0.03, rw + 0.008, 0.024, r, fs=6.5)

    ax.text(bx + bw/2, ty + 0.025, 'FastAPI + SSE + JWT + SQLAlchemy', ha='center', va='center',
            fontsize=7, color=GRAY, transform=ax.transAxes, zorder=5)

    # ── DATABASE ──
    dx, dw = bx + bw + g, 0.16
    box(ax, dx, ty, dw, th, fc=BG)
    header(ax, dx, ty + th - 0.035, dw, title='DATABASE')

    label(ax, dx + 0.008, ty + th - 0.065, 'PostgreSQL (AWS RDS)', fs=8)
    tw = 0.068
    t1 = ['users', 'documents', 'regulations', 'meetings', 'action_items', 'schedules', 'judgments', 'chat_sessions']
    t2 = ['chat_logs', 'oauth_tokens', 'sheet_trackers', 'pipeline_tasks', 'approval_reqs', 'messages', 'projects', 'doc_templates']
    for i, t in enumerate(t1):
        item(ax, dx + 0.007, ty + th - 0.09 - i*0.028, tw, 0.022, t, fs=6)
    for i, t in enumerate(t2):
        item(ax, dx + 0.007 + tw + 0.004, ty + th - 0.09 - i*0.028, tw, 0.022, t, fs=6)

    label(ax, dx + 0.008, ty + 0.055, 'Qdrant (벡터 DB)', fs=7.5)
    item(ax, dx + 0.007, ty + 0.018, tw, 0.028, '문서 임베딩', fs=6.5)
    item(ax, dx + 0.007 + tw + 0.004, ty + 0.018, tw, 0.028, '규정 임베딩', fs=6.5)

    # ── EXTERNAL ──
    ex, ew = dx + dw + g, 0.145
    box(ax, ex, ty, ew, th, fc=BG)
    header(ax, ex, ty + th - 0.035, ew, title='EXTERNAL')

    label(ax, ex + 0.008, ty + th - 0.065, 'Google API (OAuth 2.0)', fs=8)
    gsvcs = ['Google Calendar\n(일정 + Meet 링크)', 'Google Tasks\n(할 일 양방향 동기화)',
             'Gmail\n(초대 메일 / 알림)', 'Google Sheets\n(프로젝트 내보내기)']
    for i, gs in enumerate(gsvcs):
        item(ax, ex + 0.007, ty + th - 0.10 - i*0.05, ew - 0.014, 0.04, gs, fs=7)

    label(ax, ex + 0.008, ty + 0.1, 'Slack Webhook', fs=7.5)
    item(ax, ex + 0.007, ty + 0.065, ew - 0.014, 0.028, '마감 알림 발송', fs=7)

    label(ax, ex + 0.008, ty + 0.04, 'LLM API', fs=7.5)
    item(ax, ex + 0.007, ty + 0.008, 0.06, 0.025, 'OpenAI', fs=6.5)
    item(ax, ex + 0.007 + 0.065, ty + 0.008, 0.065, 0.025, 'Anthropic', fs=6.5)

    # ── 상단 화살표 ──
    ay = ty + th/2
    arrow_lbl(ax, ux + uw, ay + 0.015, fx, ay + 0.015, '요청', color=DARK, fs=7)
    arrow_lbl(ax, fx + fw, ay + 0.025, bx, ay + 0.025, 'REST API', color=ACCENT, fs=7)
    arrow_lbl(ax, bx, ay - 0.015, fx + fw, ay - 0.015, 'SSE Stream', color=ACCENT, fs=7)
    arrow_lbl(ax, bx + bw, ay, dx, ay, 'CRUD', color=DARK, fs=7)
    arrow_lbl(ax, dx + dw, ay + 0.015, ex, ay + 0.015, 'API 호출', color=DARK, fs=7)

    # ═══════════════════════════════════
    # 하단 왼쪽: AI ENGINE
    # ═══════════════════════════════════
    ax2, ay2, aw2, ah2 = 0.03, 0.03, 0.60, 0.48
    box(ax, ax2, ay2, aw2, ah2, fc=BG)
    header(ax, ax2, ay2 + ah2 - 0.035, aw2, title='AI ENGINE  (LangGraph + RAG + LLM)')

    # Intent
    label(ax, ax2 + 0.015, ay2 + ah2 - 0.07, 'Intent Classification', fs=9.5)
    item(ax, ax2 + 0.015, ay2 + ah2 - 0.11, 0.57, 0.032,
         'klue/roberta-large 앙상블 (5-seed, 93.3% 정확도)  -->  8개 Intent 분류',
         fs=8.5, fw='bold', fc='#F0F0F0', ec=BORDER)

    # Agents
    label(ax, ax2 + 0.015, ay2 + ah2 - 0.155, 'Agent (조건부 라우팅)', fs=9.5)
    agents = [
        'Judgment Agent\n규정 판단 / RAG + 신뢰도',
        'Document Agent\n문서 검색 / 생성 / 요약 / QA',
        'Schedule Agent\n일정 등록 / Google 서비스 연동',
        'General Response\n일반 질문 / LLM 직접 응답',
    ]
    aw_e = 0.135
    for i, a in enumerate(agents):
        item(ax, ax2 + 0.015 + i*(aw_e + 0.007), ay2 + ah2 - 0.22, aw_e, 0.055, a, fs=7, fw='bold')

    # RAG
    label(ax, ax2 + 0.015, ay2 + ah2 - 0.255, 'RAG Pipeline (Hybrid Search)', fs=9.5)
    rags = ['Query Refiner\n(한국어 최적화)', 'BM25 검색\n(키워드 기반)', 'Vector 검색\n(의미 기반)',
            'RRF 합산\n(점수 통합)', 'Cross-Encoder\nReranker']
    rw_e = 0.108
    for i, r in enumerate(rags):
        rx = ax2 + 0.015 + i*(rw_e + 0.005)
        item(ax, rx, ay2 + ah2 - 0.32, rw_e, 0.05, r, fs=7)
        if i < 4:
            arrow(ax, rx + rw_e + 0.001, ay2 + ah2 - 0.295,
                  rx + rw_e + 0.006, ay2 + ah2 - 0.295, color=GRAY, lw=1)

    # LLM
    label(ax, ax2 + 0.015, ay2 + ah2 - 0.355, 'LLM Factory (Provider 패턴)', fs=9.5)
    llms = ['GPT-4o / GPT-4o-mini  (OpenAI)', 'Claude Sonnet  (Anthropic)', 'vLLM + LoRA  (RunPod A100)']
    lw_e = 0.185
    for i, l in enumerate(llms):
        item(ax, ax2 + 0.015 + i*(lw_e + 0.007), ay2 + ah2 - 0.405, lw_e, 0.04, l, fs=7.5)

    # Parser
    label(ax, ax2 + 0.015, ay2 + 0.06, 'Document Parser', fs=9.5)
    parsers = ['Docling (PDF)', 'PaddleOCR (스캔)', 'python-docx (DOCX)', 'PyMuPDF (PDF)']
    pw_e = 0.135
    for i, p in enumerate(parsers):
        item(ax, ax2 + 0.015 + i*(pw_e + 0.007), ay2 + 0.015, pw_e, 0.035, p, fs=7.5)

    # ═══════════════════════════════════
    # 하단 오른쪽: INFRASTRUCTURE
    # ═══════════════════════════════════
    ix, iy, iw, ih = 0.645, 0.03, 0.335, 0.48
    box(ax, ix, iy, iw, ih, fc=BG)
    header(ax, ix, iy + ih - 0.035, iw, title='INFRASTRUCTURE')

    # AWS
    label(ax, ix + 0.015, iy + ih - 0.07, 'AWS', fs=9.5)
    aws = [
        'EC2 (t3.medium)  -  FastAPI 백엔드 서버',
        'RDS (PostgreSQL 16)  -  프로덕션 데이터베이스',
        'S3  -  문서 파일 저장소',
        'CloudFront  -  CDN / 프론트엔드 배포',
    ]
    for i, a in enumerate(aws):
        item(ax, ix + 0.012, iy + ih - 0.105 - i*0.04, iw - 0.024, 0.032, a, fs=7.5)

    # GPU
    label(ax, ix + 0.015, iy + ih - 0.275, 'GPU / 컨테이너', fs=9.5)
    gpus = [
        'RunPod (A100 GPU)  -  vLLM 서빙 / LoRA 핫스왑',
        'Docker Compose  -  PostgreSQL + Redis + Qdrant',
        'GitHub Actions  -  CI/CD 자동 배포',
    ]
    for i, g in enumerate(gpus):
        item(ax, ix + 0.012, iy + ih - 0.31 - i*0.04, iw - 0.024, 0.032, g, fs=7.5)

    # Auth
    label(ax, ix + 0.015, iy + 0.1, '인증 체계', fs=9.5)
    auths = [
        'JWT (HS256)  -  Bearer Token / 60분 만료',
        'Google OAuth 2.0  -  소셜 로그인 + API 인증',
        'AES-256 (Fernet)  -  OAuth 토큰 암호화 저장',
    ]
    for i, a in enumerate(auths):
        item(ax, ix + 0.012, iy + 0.06 - i*0.035, iw - 0.024, 0.028, a, fs=7.5)

    # ── 세로 화살표 ──
    arrow_lbl(ax, bx + bw*0.35, ty, ax2 + aw2*0.35, ay2 + ah2,
              'Agent 호출', color=ACCENT, lw=1.8, fs=8)
    arrow_lbl(ax, ax2 + aw2*0.65, ay2 + ah2, bx + bw*0.65, ty,
              '응답 반환', color=ACCENT, lw=1.8, fs=8)

    ax.text(0.48, 0.535, 'Generate', ha='center', va='center',
            fontsize=11, fontweight='bold', color=ACCENT,
            transform=ax.transAxes, zorder=15)

    # ── 하단 정보 ──
    ax.text(0.97, 0.007, '작성일 : 2026.03.17  |  작성자 : 안혜빈',
            ha='right', va='bottom', fontsize=8, color=GRAY, transform=ax.transAxes)
    ax.text(0.03, 0.007, 'SK Networks Family AI Camp 21기 - WorkFlow Agent (듀듀)',
            ha='left', va='bottom', fontsize=8, color=GRAY, transform=ax.transAxes)

    # ── 저장 ──
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                       'docs', '시스템_구성도_DUDE.pdf')
    plt.tight_layout(pad=0.3)
    fig.savefig(out, format='pdf', dpi=300, bbox_inches='tight', facecolor=WHITE, edgecolor='none')
    plt.close()
    print(f"시스템 구성도 생성 완료: {out}")


if __name__ == '__main__':
    create()
