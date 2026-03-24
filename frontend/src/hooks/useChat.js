/**
 * 챗봇 훅(사용자가 메세지 보냈을 때 어떤 순서로 동작해야 하는지 전체 시나리오 관리) (팀원 E 담당)
 */
import useChatStore from '../store/chatStore'
import useSSE from './useSSE'

export default function useChat() {
  const { messages, isStreaming, currentIntent, currentStatus, addMessage } = useChatStore()
  const { startStream, stopStream } = useSSE()

  const sendMessage = async (text, options = {}) => {
    if (!text.trim()) return
    // 후속 액션(doc_pick, 버튼 클릭)은 isStreaming 중에도 허용
    if (useChatStore.getState().isStreaming && !options.forceIntent) return

    // 후속 액션 옵션: { forceIntent, documentId, documentName, silent }
    const { forceIntent, documentId, documentName, silent } = options

    // 후속 액션에서 document 컨텍스트 설정
    if (documentId) {
      useChatStore.getState().setSelectedDocument(documentId, documentName || '')
    }

    // 활성 세션이 없으면 먼저 생성
    if (!useChatStore.getState().activeSessionId) {
      await useChatStore.getState().createSession()
    }

    const { activeSessionId, selectedDocumentId, selectedDocumentName, selectedTemplateId, selectedTemplateType } = useChatStore.getState()

    // silent 모드: 사용자 메시지 버블 없이 전송 (template_pick 선택 등)
    if (!silent) {
      const displayText = selectedDocumentName
        ? text.replace(/이\s*문서/g, `"${selectedDocumentName}"`).replace(/^요약해줘$/, `"${selectedDocumentName}" 요약해줘`)
        : text
      addMessage({ role: 'user', content: displayText })
    }
    addMessage({ role: 'assistant', content: '' })

    // 전송 후 선택 상태 자동 해제 (template은 useSSE에서 result 수신 시 해제 — clarify면 유지)
    useChatStore.getState().clearSelectedDocument()

    // template 선택 상태가 있으면 → 문서 생성 흐름 유지 (오케스트레이터 재분류 방지)
    const effectiveForceIntent = forceIntent || (selectedTemplateId ? 'doc_generate' : undefined)

    try {
      await startStream(text, activeSessionId, selectedDocumentId, selectedTemplateId, selectedTemplateType, effectiveForceIntent)
    } catch (err) {
      // 에러는 상위에서 처리
    }
  }

  return { messages, isStreaming, currentIntent, currentStatus, sendMessage, stopStream }
}
