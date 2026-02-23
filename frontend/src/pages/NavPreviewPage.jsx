import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, MessageSquare, FilePlus, FileText,
  Users2, Calendar, Settings, Search, Bell,
  Command, LogOut, Moon, X,
} from 'lucide-react';

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: '대시보드', section: '메인' },
  { to: '/chat', icon: MessageSquare, label: 'AI 챗봇', section: '메인' },
  { to: '/document-generate', icon: FilePlus, label: '문서 생성', section: 'AI생성' },
  { to: '/documents', icon: FileText, label: '문서 관리', section: '관리' },
  { to: '/meetings', icon: Users2, label: '회의 관리', section: '관리' },
  { to: '/schedules', icon: Calendar, label: '일정 관리', section: '관리' },
  { to: '/admin', icon: Settings, label: '관리자 설정', section: '시스템' },
];

const mockUser = { name: '문지영' };

/* ───────────── Option 1: Topbar + Dropdown ───────────── */
function TopbarLayout({ children }) {
  return (
    <div className="flex flex-col h-full bg-surface-main">
      <header className="h-14 bg-sidebar-bg border-b border-sidebar-border flex items-center px-6 gap-6 flex-shrink-0 z-20">
        <a href="/nav-preview" className="flex items-center gap-2.5 flex-shrink-0">
          <div className="w-8 h-8 bg-accent-300 rounded-sm flex items-center justify-center text-base font-bold text-primary-900 font-display">W</div>
          <span className="font-display text-base font-bold text-sidebar-text tracking-tight">WorkFlow</span>
        </a>

        <nav className="flex items-center gap-1 flex-1">
          {navItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all whitespace-nowrap ${
                  isActive
                    ? 'bg-sidebar-active text-sidebar-text'
                    : 'text-sidebar-text-muted hover:text-sidebar-text hover:bg-white/[0.06]'
                }`
              }
            >
              <item.icon size={15} />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center gap-2 flex-shrink-0">
          <button className="w-8 h-8 flex items-center justify-center rounded-md text-sidebar-text-muted hover:text-sidebar-text hover:bg-white/[0.06] transition-all">
            <Moon size={16} />
          </button>
          <button className="w-8 h-8 flex items-center justify-center rounded-md text-sidebar-text-muted hover:text-sidebar-text hover:bg-white/[0.06] relative">
            <Bell size={16} />
            <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-accent-300 rounded-full" />
          </button>
          <div className="flex items-center gap-2 pl-3 border-l border-sidebar-border">
            <div className="w-7 h-7 rounded-full bg-accent-300 flex items-center justify-center text-xs font-bold text-primary-900">
              {mockUser.name[0]}
            </div>
            <span className="text-sm font-medium text-sidebar-text">{mockUser.name}</span>
          </div>
          <button className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs text-sidebar-text-muted hover:text-sidebar-text hover:bg-white/[0.06] border border-sidebar-border transition-all">
            <LogOut size={13} />
            로그아웃
          </button>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}

/* ───────────── Option 4: Command Palette ───────────── */
function CommandPaletteLayout({ children }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');

  const filtered = query
    ? navItems.filter(i => i.label.includes(query))
    : navItems;

  const close = () => { setOpen(false); setQuery(''); };

  return (
    <div className="flex flex-col h-full bg-surface-main">
      <header className="h-12 bg-sidebar-bg border-b border-sidebar-border flex items-center px-6 justify-between flex-shrink-0 z-20">
        <a href="/nav-preview" className="flex items-center gap-2.5">
          <div className="w-7 h-7 bg-accent-300 rounded-sm flex items-center justify-center text-sm font-bold text-primary-900 font-display">W</div>
          <span className="font-display text-sm font-bold text-sidebar-text tracking-tight">WorkFlow</span>
        </a>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setOpen(true)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-white/[0.04] border border-sidebar-border text-sidebar-text-muted hover:text-sidebar-text hover:border-accent-300/60 transition-all text-sm min-w-[200px]"
          >
            <Search size={14} />
            <span className="flex-1 text-left">메뉴 검색...</span>
            <kbd className="flex items-center gap-0.5 px-1.5 py-0.5 bg-white/10 rounded text-[0.625rem] font-mono">
              <Command size={9} />K
            </kbd>
          </button>
          <button className="w-8 h-8 flex items-center justify-center rounded-md text-sidebar-text-muted hover:text-sidebar-text hover:bg-white/[0.06]">
            <Moon size={15} />
          </button>
          <button className="w-8 h-8 flex items-center justify-center rounded-md text-sidebar-text-muted hover:text-sidebar-text hover:bg-white/[0.06] relative">
            <Bell size={15} />
            <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-accent-300 rounded-full" />
          </button>
          <div className="w-7 h-7 rounded-full bg-accent-300 flex items-center justify-center text-xs font-bold text-primary-900 ml-1">
            {mockUser.name[0]}
          </div>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto">{children}</main>

      {open && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-20" onClick={close}>
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
          <div
            className="relative w-full max-w-lg bg-sidebar-bg border border-sidebar-border rounded-lg shadow-2xl overflow-hidden"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 px-4 py-3 border-b border-sidebar-border">
              <Search size={16} className="text-sidebar-text-muted flex-shrink-0" />
              <input
                autoFocus
                value={query}
                onChange={e => setQuery(e.target.value)}
                placeholder="페이지나 기능 검색..."
                className="flex-1 bg-transparent text-sidebar-text text-sm outline-none placeholder:text-sidebar-text-muted"
              />
              <button onClick={close} className="text-sidebar-text-muted hover:text-sidebar-text">
                <X size={16} />
              </button>
            </div>

            <div className="py-2 max-h-80 overflow-y-auto">
              {!query && (
                <div className="px-4 pt-1 pb-2 text-[0.6875rem] font-semibold uppercase tracking-widest text-sidebar-text-muted opacity-60">
                  페이지 이동
                </div>
              )}
              {filtered.length === 0 ? (
                <div className="px-4 py-8 text-center text-sm text-sidebar-text-muted">검색 결과 없음</div>
              ) : (
                filtered.map(item => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    onClick={close}
                    className={({ isActive }) =>
                      `flex items-center gap-3 px-4 py-2.5 text-sm transition-all cursor-pointer ${
                        isActive
                          ? 'bg-sidebar-active text-sidebar-text'
                          : 'text-sidebar-text-muted hover:bg-white/[0.06] hover:text-sidebar-text'
                      }`
                    }
                  >
                    <item.icon size={16} className="flex-shrink-0" />
                    <div className="flex-1">
                      <div className="font-medium">{item.label}</div>
                      <div className="text-[0.6875rem] opacity-50 mt-0.5">{item.section}</div>
                    </div>
                  </NavLink>
                ))
              )}
            </div>

            <div className="px-4 py-2 border-t border-sidebar-border flex items-center gap-4 text-[0.6875rem] text-sidebar-text-muted">
              <span className="flex items-center gap-1"><kbd className="px-1.5 py-0.5 bg-white/10 rounded font-mono">↑↓</kbd> 이동</span>
              <span className="flex items-center gap-1"><kbd className="px-1.5 py-0.5 bg-white/10 rounded font-mono">↵</kbd> 선택</span>
              <span className="flex items-center gap-1"><kbd className="px-1.5 py-0.5 bg-white/10 rounded font-mono">esc</kbd> 닫기</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ───────────── Option 5: Tab Bar ───────────── */
function TabBarLayout({ children }) {
  return (
    <div className="flex flex-col h-full bg-surface-main">
      <header className="bg-sidebar-bg border-b border-sidebar-border flex-shrink-0">
        <div className="h-12 flex items-center justify-between px-6">
          <a href="/nav-preview" className="flex items-center gap-2.5">
            <div className="w-7 h-7 bg-accent-300 rounded-sm flex items-center justify-center text-sm font-bold text-primary-900 font-display">W</div>
            <span className="font-display text-sm font-bold text-sidebar-text tracking-tight">WorkFlow</span>
          </a>

          <div className="flex items-center gap-2">
            <div className="flex items-center gap-2 border border-sidebar-border rounded-md px-3 py-1.5 bg-white/[0.04] min-w-[200px]">
              <Search size={13} className="text-sidebar-text-muted flex-shrink-0" />
              <input placeholder="규정 검색..." className="bg-transparent text-[0.8125rem] text-sidebar-text outline-none placeholder:text-sidebar-text-muted w-full" />
            </div>
            <button className="w-8 h-8 flex items-center justify-center rounded-md text-sidebar-text-muted hover:text-sidebar-text hover:bg-white/[0.06]">
              <Moon size={15} />
            </button>
            <button className="w-8 h-8 flex items-center justify-center rounded-md text-sidebar-text-muted hover:text-sidebar-text hover:bg-white/[0.06] relative">
              <Bell size={15} />
              <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-accent-300 rounded-full" />
            </button>
            <div className="flex items-center gap-2 pl-2 border-l border-sidebar-border ml-1">
              <div className="w-7 h-7 rounded-full bg-accent-300 flex items-center justify-center text-xs font-bold text-primary-900">
                {mockUser.name[0]}
              </div>
              <div>
                <div className="text-xs font-semibold text-sidebar-text leading-none">{mockUser.name}</div>
                <div className="text-[0.625rem] text-sidebar-text-muted mt-0.5">사용자</div>
              </div>
            </div>
            <button className="px-2 py-1 rounded-md text-xs text-sidebar-text-muted hover:text-sidebar-text border border-sidebar-border hover:bg-white/[0.06] transition-all ml-1">
              <LogOut size={13} />
            </button>
          </div>
        </div>

        {/* 탭 행 */}
        <div className="flex items-end px-4 overflow-x-auto">
          {navItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 transition-all ${
                  isActive
                    ? 'text-accent-300 border-accent-300'
                    : 'text-sidebar-text-muted border-transparent hover:text-sidebar-text hover:border-sidebar-border'
                }`
              }
            >
              <item.icon size={15} />
              {item.label}
            </NavLink>
          ))}
        </div>
      </header>

      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}

/* ───────────── 공통 더미 콘텐츠 ───────────── */
const HINTS = {
  1: '"관리" 버튼을 클릭하면 드롭다운이 열립니다.',
  4: '상단 [메뉴 검색...] 버튼을 클릭하면 Command Palette가 열립니다.',
  5: '헤더 아래 탭을 클릭해서 페이지를 이동해보세요.',
};

function PlaceholderContent({ variant }) {
  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-6 px-4 py-3 bg-accent-50 border border-accent-300/40 rounded-md text-sm text-accent-700">
        {HINTS[variant]}
      </div>
      <div className="grid grid-cols-3 gap-4 mb-6">
        {[['3', '오늘 회의'], ['12', '생성된 문서'], ['5', '처리 대기']].map(([num, label], i) => (
          <div key={i} className="bg-surface-card border border-neutral-border rounded-md p-5">
            <div className="text-2xl font-bold text-neutral-main">{num}</div>
            <div className="text-sm text-neutral-sub mt-1">{label}</div>
          </div>
        ))}
      </div>
      <div className="bg-surface-card border border-neutral-border rounded-md p-5">
        <div className="font-semibold text-neutral-main mb-3">최근 활동</div>
        {[
          '회의록 자동 생성 완료 — 기획팀 주간 회의',
          '보고서 초안 생성 — Q1 성과 보고서',
          '일정 등록 완료 — 팀 스프린트 리뷰',
        ].map((item, i) => (
          <div key={i} className="flex items-center gap-3 py-2.5 border-b border-neutral-divider last:border-0">
            <div className="w-1.5 h-1.5 rounded-full bg-accent-300 flex-shrink-0" />
            <span className="text-sm text-neutral-sub">{item}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ───────────── 메인 프리뷰 페이지 ───────────── */
const OPTIONS = [
  { id: 1, label: '1번 — Topbar + 드롭다운', Layout: TopbarLayout },
  { id: 4, label: '4번 — Command Palette', Layout: CommandPaletteLayout },
  { id: 5, label: '5번 — Tab Bar', Layout: TabBarLayout },
];

export default function NavPreviewPage() {
  const [selected, setSelected] = useState(1);
  const { Layout: SelectedLayout } = OPTIONS.find(o => o.id === selected);

  return (
    <div className="fixed inset-0 flex flex-col z-[9999]">
      {/* 프리뷰 컨트롤 바 */}
      <div className="flex-shrink-0 flex items-center justify-between px-5 py-2 bg-primary-900 z-[100]">
        <span className="text-sm font-semibold text-white/80">네비게이션 프리뷰</span>
        <div className="flex items-center gap-2">
          {OPTIONS.map(opt => (
            <button
              key={opt.id}
              onClick={() => setSelected(opt.id)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                selected === opt.id
                  ? 'bg-accent-300 text-primary-900'
                  : 'bg-white/10 text-white/60 hover:bg-white/20 hover:text-white'
              }`}
            >
              {opt.label}
            </button>
          ))}
          <a
            href="/dashboard"
            className="ml-2 px-3 py-1 rounded-md text-xs bg-white/10 text-white/60 hover:bg-white/20 hover:text-white transition-all flex items-center gap-1"
          >
            <X size={12} /> 닫기
          </a>
        </div>
      </div>

      {/* 선택된 레이아웃 */}
      <div className="flex-1 overflow-hidden">
        <SelectedLayout>
          <PlaceholderContent variant={selected} />
        </SelectedLayout>
      </div>
    </div>
  );
}
