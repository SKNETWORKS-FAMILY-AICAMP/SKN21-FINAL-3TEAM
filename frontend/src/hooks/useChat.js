/**
 * 챗봇 훅 (팀원 E 담당)
 */
import useChatStore from '../store/chatStore'
import useSSE from './useSSE'

export default function useChat() {
  const { messages, isStreaming, currentIntent, addMessage } = useChatStore()
  const { startStream, stopStream } = useSSE()

  const sendMessage = (text) => {
    addMessage({ role: 'user', content: text })
    addMessage({ role: 'assistant', content: '' })
    startStream(text)
  }

  return { messages, isStreaming, currentIntent, sendMessage, stopStream }
}
