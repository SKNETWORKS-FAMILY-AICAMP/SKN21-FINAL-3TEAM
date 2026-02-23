/**
 * 챗봇 훅(사용자가 메세지 보냈을 때 어떤 순서로 동작해야 하는지 전체 시나리오 관리) (팀원 E 담당)
 */
import useChatStore from '../store/chatStore'
import useSSE from './useSSE'

export default function useChat() {
  const { messages, isStreaming, currentIntent, currentStatus, addMessage } = useChatStore()
  const { startStream, stopStream } = useSSE()

  const sendMessage = async (text) => {
    if (!text.trim() || useChatStore.getState().isStreaming) return

    const { activeSessionId, selectedDocumentId } = useChatStore.getState()

    // addMessage 내부에서 activeSessionId 없을 때 세션 자동 생성함
    addMessage({ role: 'user', content: text })
    addMessage({ role: 'assistant', content: '' })

    // 전송 후 선택 문서 자동 해제
    useChatStore.getState().clearSelectedDocument()

    try {
      await startStream(text, activeSessionId, selectedDocumentId)
    } catch (err) {
      // 401 → 로그인 페이지로 리다이렉트
      if (err.status === 401) {
        localStorage.removeItem('access_token')
        window.location.href = '/login'
      }
    }
  }

  return { messages, isStreaming, currentIntent, currentStatus, sendMessage, stopStream }
}
