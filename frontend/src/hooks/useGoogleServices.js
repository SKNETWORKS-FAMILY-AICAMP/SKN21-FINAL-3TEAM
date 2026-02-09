/**
 * Google 서비스 커스텀 훅 (팀원 E 담당)
 *
 * 사용법:
 *   const { connected, scopes, connect, disconnect, hasScope, ... } = useGoogleServices()
 *
 * - 마운트 시 fetchStatus() 자동 호출
 * - refreshAll()로 전체 상태 새로고침
 */
import { useEffect } from 'react'
import useGoogleStore from '../store/googleStore'

export default function useGoogleServices() {
  const store = useGoogleStore()

  useEffect(() => {
    store.fetchStatus()
  }, [])

  return {
    ...store,
    refreshAll: async () => {
      // TODO: 팀원 E 구현
      // fetchStatus → connected면 fetchTasks + fetchSheets
    },
  }
}
