/**
 * UI 상태 관리 (팀원 E 담당)
 */
import { create } from 'zustand'

const useUIStore = create((set) => ({
  sidebarOpen: true,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
}))

export default useUIStore
