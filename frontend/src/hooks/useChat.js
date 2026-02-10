/**
 * 챗봇 훅(사용자가 메세지 보냈을 때 어떤 순서로 동작해야 하는지 전체 시나리오 관리) (팀원 E 담당)
 */
import useChatStore from '../store/chatStore'  // 채팅 기록과 상태를 저장하는 저장소
import useSSE from './useSSE'  // 한 글자 씩 출력하는 기능을 담당하는 훅

export default function useChat() {
  // 저장소에서 다섯 가지 정보를 실시간으로 받아와 
  // (지금까지 나눈 대화 목록, 지금 AI가 말하고 있는 중인지 여부(중복 전송 방지용), AI가 파악한 사용자의 의도(ex: 일정 조회, 문서 검색), 현재 진행 상태(ex: 답변을 생성 중입니다), 새 메시지를 추가하는 함수)
  const { messages, isStreaming, currentIntent, currentStatus, addMessage } = useChatStore()
  const { startStream, stopStream } = useSSE()

  // 메세지 전송 로직 
  const sendMessage = (text) => {
    // 1. 방어코드: 빈 메시지거나 이미 AI가 말하는 중이면 무시해
    if (!text.trim() || isStreaming) return
    // 2. 사용자가 보낸 말을 채팅창에 즉시 추가해 
    addMessage({ role: 'user', content: text })
    // 3. AI가 대답할 빈 칸 (말풍선)을 미리 하나 만들어둬
    addMessage({ role: 'assistant', content: '' })
    // 4. 실제로 AI 응답을 받아오는 스트리밍 엔진을 가동해!
    startStream(text)
  }

  return { messages, isStreaming, currentIntent, currentStatus, sendMessage, stopStream }
}
