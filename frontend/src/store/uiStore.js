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
  leftColumn: ['TodaySchedule', 'ActivityTimeline'],
  rightColumn: ['AIChatWidget', 'CalendarWidget', 'RecentDocs'],
  hidden: [],
}

function loadDashboard() {
  try {
    const saved = JSON.parse(localStorage.getItem(DASHBOARD_KEY))
    const all = [...saved.leftColumn, ...saved.rightColumn, ...saved.hidden]
    const expected = [...DEFAULT_DASHBOARD.leftColumn, ...DEFAULT_DASHBOARD.rightColumn]
    if (expected.every(w => all.includes(w)) && all.length === expected.length) return saved
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

const useUIStore = create((set) => ({
  sidebarOpen: true,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

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

    if (targetCol === 'leftColumn') {
      const idx = targetId != null ? left.indexOf(targetId) : -1
      left = idx === -1 ? [...left, dragId] : [...left.slice(0, idx), dragId, ...left.slice(idx)]
    } else {
      const idx = targetId != null ? right.indexOf(targetId) : -1
      right = idx === -1 ? [...right, dragId] : [...right.slice(0, idx), dragId, ...right.slice(idx)]
    }

    const next = { ...d, leftColumn: left, rightColumn: right }
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
}))

export default useUIStore
