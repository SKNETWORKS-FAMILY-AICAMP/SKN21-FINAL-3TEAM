/**
 * Google 서비스 Zustand 상태 관리
 *
 * 상태:
 *   - connected: bool (Google 연결 여부)
 *   - scopes: string[] (연결된 scope 목록)
 *   - loading / error
 *   - tasks: Google Tasks 목록
 *   - sheets: 추적 스프레드시트 목록
 *
 * 액션:
 *   - fetchStatus(): 연결 상태 조회
 *   - connect(scopes): OAuth URL로 리다이렉트
 *   - disconnect(): 연결 해제
 *   - hasScope(scope): scope 보유 여부
 *   - fetchTasks(): Tasks 목록 조회
 *   - updateTask(id, completed): Task 상태 변경
 *   - syncTasks(): Tasks 동기화
 *   - fetchSheets(): Sheets 목록 조회
 */
import { create } from 'zustand'
import * as googleApi from '../api/google'

const useGoogleStore = create((set, get) => ({
  connected: false,
  email: null,
  scopes: [],
  loading: false,
  error: null,

  tasks: [],
  tasksLoading: false,
  tasksError: null,

  sheets: [],
  sheetsLoading: false,
  sheetsError: null,

  calendarEvents: [],
  calendarLoading: false,
  calendarError: null,

  // ── OAuth 상태 조회 ──
  fetchStatus: async () => {
    set({ loading: true, error: null })
    try {
      const { data } = await googleApi.getGoogleStatus()
      set({
        connected: data.connected,
        email: data.email || null,
        scopes: data.scopes || [],
        loading: false,
      })
    } catch (err) {
      set({ loading: false, error: err.response?.data?.detail || '상태 조회 실패' })
    }
  },

  // ── OAuth 연결 (리다이렉트) ──
  connect: async (scopes) => {
    set({ loading: true, error: null })
    try {
      const { data } = await googleApi.connectGoogle(scopes)
      if (data.auth_url) {
        window.location.href = data.auth_url
      }
    } catch (err) {
      set({ loading: false, error: err.response?.data?.detail || '연결 실패' })
    }
  },

  // ── 연결 해제 ──
  disconnect: async () => {
    set({ loading: true, error: null })
    try {
      await googleApi.disconnectGoogle()
      set({
        connected: false,
        email: null,
        scopes: [],
        tasks: [],
        sheets: [],
        loading: false,
      })
    } catch (err) {
      set({ loading: false, error: err.response?.data?.detail || '연결 해제 실패' })
    }
  },

  // ── Scope 보유 여부 ──
  hasScope: (scope) => get().scopes.includes(scope),

  // ── Google Tasks ──
  fetchTasks: async () => {
    set({ tasksLoading: true, tasksError: null })
    try {
      const { data } = await googleApi.listTasks()
      set({ tasks: data.tasks || data || [], tasksLoading: false })
    } catch (err) {
      set({ tasksLoading: false, tasksError: err.response?.data?.detail || 'Tasks 조회 실패' })
    }
  },

  updateTask: async (actionItemId, completed) => {
    try {
      await googleApi.updateTaskStatus(actionItemId, completed)
      set((state) => ({
        tasks: state.tasks.map((t) =>
          t.action_item_id === actionItemId
            ? { ...t, completed, status: completed ? 'completed' : 'needsAction' }
            : t
        ),
      }))
    } catch (err) {
      set({ tasksError: err.response?.data?.detail || 'Task 상태 변경 실패' })
    }
  },

  syncTasks: async (meetingId = null) => {
    set({ tasksLoading: true, tasksError: null })
    try {
      await googleApi.syncAllTasks(meetingId)
      await get().fetchTasks()
    } catch (err) {
      set({ tasksLoading: false, tasksError: err.response?.data?.detail || 'Tasks 동기화 실패' })
    }
  },

  pullTasks: async () => {
    set({ tasksLoading: true, tasksError: null })
    try {
      await googleApi.pullTaskStatus()
      await get().fetchTasks()
    } catch (err) {
      set({ tasksLoading: false, tasksError: err.response?.data?.detail || 'Tasks Pull 실패' })
    }
  },

  // ── Google Sheets ──
  fetchSheets: async () => {
    set({ sheetsLoading: true, sheetsError: null })
    try {
      const { data } = await googleApi.listSheets()
      set({ sheets: data.sheets || data || [], sheetsLoading: false })
    } catch (err) {
      set({ sheetsLoading: false, sheetsError: err.response?.data?.detail || 'Sheets 조회 실패' })
    }
  },

  createSheet: async (title, meetingId = null) => {
    set({ sheetsLoading: true, sheetsError: null })
    try {
      const { data } = await googleApi.createSheet(title, meetingId)
      await get().fetchSheets()
      return data
    } catch (err) {
      set({ sheetsLoading: false, sheetsError: err.response?.data?.detail || 'Sheets 생성 실패' })
      throw err
    }
  },

  syncSheet: async (spreadsheetId, meetingId = null) => {
    try {
      await googleApi.syncSheet(spreadsheetId, meetingId)
    } catch (err) {
      set({ sheetsError: err.response?.data?.detail || 'Sheets 동기화 실패' })
    }
  },

  // ── Google Calendar ──
  fetchCalendarEvents: async (timeMin = null, timeMax = null) => {
    set({ calendarLoading: true, calendarError: null })
    try {
      const response = await googleApi.listCalendarEvents(timeMin, timeMax)
      const events = response.data.events || response.data || []
      set({ calendarEvents: events, calendarLoading: false })
    } catch (err) {
      set({ calendarLoading: false, calendarError: err.response?.data?.detail || 'Calendar 조회 실패' })
    }
  },

  createEventWithMeet: async (eventData) => {
    set({ calendarLoading: true, calendarError: null })
    try {
      const { data } = await googleApi.createEventWithMeet(eventData)
      await get().fetchCalendarEvents()
      return data
    } catch (err) {
      set({ calendarLoading: false, calendarError: err.response?.data?.detail || '이벤트 생성 실패' })
      throw err
    }
  },

  syncEventToGoogle: async (eventData) => {
    try {
      await googleApi.syncEventToGoogle(eventData)
      await get().fetchCalendarEvents()
    } catch (err) {
      set({ calendarError: err.response?.data?.detail || '이벤트 동기화 실패' })
    }
  },

  deleteCalendarEvent: async (eventId, calendarId = 'primary') => {
    try {
      await googleApi.deleteCalendarEvent(eventId, calendarId)
      set((state) => ({
        calendarEvents: state.calendarEvents.filter((e) => e.event_id !== eventId),
      }))
    } catch (err) {
      set({ calendarError: err.response?.data?.detail || '이벤트 삭제 실패' })
      throw err
    }
  },
}))

export default useGoogleStore
