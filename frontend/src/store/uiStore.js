/**
 * UI 상태 관리 (팀원 E 담당)
 */
import { create } from 'zustand'

const getInitialTheme = () => {
  const saved = localStorage.getItem('theme')
  if (saved === 'dark' || saved === 'light') return saved
  return 'light' // 기본값: 라이트 모드
}

// ── 대시보드 레이아웃 ──
const DASHBOARD_KEY = 'dashboard-layout'
const DEFAULT_DASHBOARD = {
  leftColumn: ['ScheduleTimelineWidget', 'TodaySchedule', 'TaskPipelineWidget'],
  rightColumn: ['CalendarWidget', 'ApprovalQueueWidget', 'TeamMembersWidget', 'WhatsOnWidget'],
  hidden: ['ActivityTimeline', 'RecentDocs', 'EmployeeTableWidget', 'AIChatWidget'],
  topbarScheduleHidden: false,
}

function loadDashboard() {
  try {
    const saved = JSON.parse(localStorage.getItem(DASHBOARD_KEY))
    if (!saved || !Array.isArray(saved.leftColumn) || !Array.isArray(saved.rightColumn) || !Array.isArray(saved.hidden)) {
      return DEFAULT_DASHBOARD
    }
    const all = [...saved.leftColumn, ...saved.rightColumn, ...saved.hidden]
    const expected = [...DEFAULT_DASHBOARD.leftColumn, ...DEFAULT_DASHBOARD.rightColumn, ...DEFAULT_DASHBOARD.hidden]
    if (expected.every(w => all.includes(w))) {
      if (saved.topbarScheduleHidden === undefined) {
        saved.topbarScheduleHidden = DEFAULT_DASHBOARD.topbarScheduleHidden
      }
      return saved
    }
  } catch { /* ignore */ }
  return DEFAULT_DASHBOARD
}

function saveDashboard(d) {
  localStorage.setItem(DASHBOARD_KEY, JSON.stringify(d))
}

// 위젯이 원래 어느 컬럼에 속하는지 판별
function defaultColumnFor(id) {
  if (DEFAULT_DASHBOARD.leftColumn.includes(id)) return 'leftColumn'
  return 'rightColumn'
}

// ── 메모 ──
const MEMOS_KEY = 'sidebar-memos'
function loadMemos() {
  try {
    const saved = JSON.parse(localStorage.getItem(MEMOS_KEY))
    if (Array.isArray(saved) && saved.length > 0) return saved
  } catch { /* ignore */ }
  // 기존 단일 메모 마이그레이션
  const old = localStorage.getItem('sidebar-memo')
  if (old) {
    const migrated = [{ id: Date.now().toString(), text: old, createdAt: Date.now() }]
    localStorage.setItem(MEMOS_KEY, JSON.stringify(migrated))
    localStorage.removeItem('sidebar-memo')
    return migrated
  }
  return []
}
function saveMemos(memos) {
  localStorage.setItem(MEMOS_KEY, JSON.stringify(memos))
}

// ── 개인화 설정 ──
const SETTINGS_KEY = 'user-settings'
const DEFAULT_SETTINGS = {
  aiStyle: 'detailed', // 'concise' | 'detailed'
  notifications: true,
}
function loadSettings() {
  try {
    const saved = JSON.parse(localStorage.getItem(SETTINGS_KEY))
    if (saved) return { ...DEFAULT_SETTINGS, ...saved }
  } catch { /* ignore */ }
  return DEFAULT_SETTINGS
}
function saveSettings(s) {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(s))
}

const useUIStore = create((set) => ({
  sidebarOpen: true,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

  // ── 메모 ──
  memos: loadMemos(),
  memoOpen: false,
  activeMemoId: null,
  toggleMemo: () => set((state) => ({ memoOpen: !state.memoOpen })),
  selectMemo: (id) => set({ activeMemoId: id }),
  addMemo: () => set((state) => {
    const existing = state.memos.find(m => !m.text.trim())
    if (existing) return { activeMemoId: existing.id }
    const newMemo = { id: Date.now().toString(), text: '', createdAt: Date.now() }
    const next = [newMemo, ...state.memos]
    saveMemos(next)
    return { memos: next, activeMemoId: newMemo.id }
  }),
  updateMemo: (id, text) => set((state) => {
    const next = state.memos.map(m => m.id === id ? { ...m, text } : m)
    saveMemos(next)
    return { memos: next }
  }),
  deleteMemo: (id) => set((state) => {
    const next = state.memos.filter(m => m.id !== id)
    saveMemos(next)
    return { memos: next, activeMemoId: state.activeMemoId === id ? null : state.activeMemoId }
  }),

  theme: getInitialTheme(),
  toggleTheme: () => set((state) => {
    const next = state.theme === 'dark' ? 'light' : 'dark'
    localStorage.setItem('theme', next)
    return { theme: next }
  }),

  // ── 대시보드 ──
  dashboard: loadDashboard(),
  editMode: false,

  toggleEditMode: () => set((state) => ({ editMode: !state.editMode })),

  toggleTopbarSchedule: () => set((state) => {
    const next = {
      ...state.dashboard,
      topbarScheduleHidden: !state.dashboard.topbarScheduleHidden
    }
    saveDashboard(next)
    return { dashboard: next }
  }),

  setLeftColumn: (order) => set((state) => {
    const next = { ...state.dashboard, leftColumn: order }
    saveDashboard(next)
    return { dashboard: next }
  }),

  setRightColumn: (order) => set((state) => {
    const next = { ...state.dashboard, rightColumn: order }
    saveDashboard(next)
    return { dashboard: next }
  }),

  // dragId를 targetCol의 targetId 앞에 삽입 (targetId=null이면 끝에)
  moveWidget: (dragId, targetId, targetCol) => set((state) => {
    const d = state.dashboard
    let left = d.leftColumn.filter(w => w !== dragId)
    let right = d.rightColumn.filter(w => w !== dragId)
    let hidden = d.hidden.filter(w => w !== dragId)

    if (targetCol === 'leftColumn') {
      const idx = targetId != null ? left.indexOf(targetId) : -1
      left = idx === -1 ? [...left, dragId] : [...left.slice(0, idx), dragId, ...left.slice(idx)]
    } else {
      const idx = targetId != null ? right.indexOf(targetId) : -1
      right = idx === -1 ? [...right, dragId] : [...right.slice(0, idx), dragId, ...right.slice(idx)]
    }

    const next = { ...d, leftColumn: left, rightColumn: right, hidden }
    saveDashboard(next)
    return { dashboard: next }
  }),

  hideWidget: (id) => set((state) => {
    const d = state.dashboard
    const next = {
      leftColumn: d.leftColumn.filter(w => w !== id),
      rightColumn: d.rightColumn.filter(w => w !== id),
      hidden: [...d.hidden, id],
    }
    saveDashboard(next)
    return { dashboard: next }
  }),

  restoreWidget: (id) => set((state) => {
    const d = state.dashboard
    const col = defaultColumnFor(id)
    const next = {
      ...d,
      [col]: [...d[col], id],
      hidden: d.hidden.filter(w => w !== id),
    }
    saveDashboard(next)
    return { dashboard: next }
  }),

  resetDashboard: () => {
    saveDashboard(DEFAULT_DASHBOARD)
    return set({ dashboard: DEFAULT_DASHBOARD })
  },

  // ── 개인화 설정 ──
  settings: loadSettings(),
  updateSettings: (next) => set((state) => {
    const updated = { ...state.settings, ...next }
    saveSettings(updated)
    return { settings: updated }
  }),

  // ── 일정 새로고침 신호 (Topbar ↔ SchedulesPage 동기화) ──
  scheduleRefreshKey: 0,
  triggerScheduleRefresh: () => set((state) => ({ scheduleRefreshKey: state.scheduleRefreshKey + 1 })),
}))

export default useUIStore
