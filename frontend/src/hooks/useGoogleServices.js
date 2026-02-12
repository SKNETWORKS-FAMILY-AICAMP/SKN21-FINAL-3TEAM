/**
 * Google 서비스 커스텀 훅
 *
 * 사용법:
 *   const { connected, scopes, connect, disconnect, hasScope, refreshAll, ... } = useGoogleServices()
 *
 * - 마운트 시 fetchStatus() 자동 호출
 * - refreshAll()로 전체 상태 새로고침
 */
import { useEffect, useCallback } from 'react'
import useGoogleStore from '../store/googleStore'

export default function useGoogleServices() {
  const store = useGoogleStore()

  useEffect(() => {
    store.fetchStatus()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // connected 상태 변경 시 Tasks + Sheets 자동 로드
  // Calendar는 페이지에서 시간 범위 지정하여 직접 호출
  useEffect(() => {
    if (store.connected) {
      if (store.hasScope('tasks')) store.fetchTasks()
      if (store.hasScope('sheets')) store.fetchSheets()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [store.connected])

  const refreshAll = useCallback(async () => {
    await store.fetchStatus()
    const state = useGoogleStore.getState()
    if (state.connected) {
      const promises = []
      if (state.hasScope('tasks')) promises.push(state.fetchTasks())
      if (state.hasScope('sheets')) promises.push(state.fetchSheets())
      // Calendar는 페이지에서 시간 범위 지정하여 직접 호출
      await Promise.all(promises)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return {
    ...store,
    refreshAll,
  }
}
