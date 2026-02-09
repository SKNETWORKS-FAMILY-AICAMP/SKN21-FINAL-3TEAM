/**
 * Google 서비스 Zustand 상태 관리 (팀원 E 담당)
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
 *   - fetchSheets(): Sheets 목록 조회
 */
import { create } from 'zustand'

const useGoogleStore = create((set, get) => ({
  // TODO: 팀원 E 구현
  connected: false,
  scopes: [],
  loading: false,
  error: null,
  tasks: [],
  tasksLoading: false,
  sheets: [],
  sheetsLoading: false,

  fetchStatus: async () => { /* TODO: 팀원 E 구현 */ },
  connect: async (scopes) => { /* TODO: 팀원 E 구현 */ },
  disconnect: async () => { /* TODO: 팀원 E 구현 */ },
  hasScope: (scope) => get().scopes.includes(scope),
  fetchTasks: async () => { /* TODO: 팀원 E 구현 */ },
  fetchSheets: async () => { /* TODO: 팀원 E 구현 */ },
}))

export default useGoogleStore
