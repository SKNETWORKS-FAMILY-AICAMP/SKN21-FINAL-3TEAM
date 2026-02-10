/**
 * Google 서비스 커스텀 훅(구글 서비스와 우리 앱을 이어주는 어댑터) (팀원 E 담당)
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
  // 1. 저장소 연결 (useGoogleStore)
  // 구글 연결 상태 (로그인 여부, 허가된 권한 목록 등)를 저장하고 있는 googleStore에서 모든 데이터와 기능을 통째로 가져오는 것.
  const store = useGoogleStore()

  // 2. 자동 상태 확인 (useEffect)
  // 사용자가 이 기능을 키자마자 (마운트 시) 자동으로 서버에 물어봐. 
  // 이 유저 지금 구글이랑 연결되어 있어? 확인 과정 거치는 것. 
  // 덕분에 유저는 매번 연결 버튼 누를 필요 없이, 페이지 들어오자마자 자신의 구글 연동 상태 볼 수 있음.
  useEffect(() => {
    store.fetchStatus()
  }, [])

  // 3. 기능 확장 (refreshAll)
  return {
    ...store,  // 저장소에 있는 모든 정보 (connected, scopes 등)을 그대로 내보냄.
    refreshAll: async () => {
      // TODO: 팀원 E 구현
      // fetchStatus → connected면 fetchTasks + fetchSheets
    },
  }
}
