/**
 * 챗봇 훅(사용자가 메세지 보냈을 때 어떤 순서로 동작해야 하는지 전체 시나리오 관리) (팀원 E 담당)
 */
import useChatStore from '../store/chatStore'
import useSSE from './useSSE'

export default function useChat() {
  const { messages, isStreaming, currentIntent, currentStatus, addMessage, createSession, activeSessionId } = useChatStore()
  const { startStream, stopStream } = useSSE()

  const sendMessage = async (text) => {
    if (!text.trim() || isStreaming) return

    const isFirstMessage = messages.length === 0 && !activeSessionId;

    addMessage({ role: 'user', content: text })
    addMessage({ role: 'assistant', content: '' })

    // 첫 메시지면 세션 자동 생성
    if (isFirstMessage) {
      createSession();
    }

    try {
      await startStream(text)
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
