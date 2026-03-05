import { useState, useEffect, useMemo, useRef } from 'react';
import { useOutletContext, useSearchParams } from 'react-router-dom';
import { MessageSquarePlus, Menu, CheckCircle, XCircle, AlertTriangle, HelpCircle, ShieldCheck, FileText } from 'lucide-react';
import ChatWindow from '../components/chat/ChatWindow';
import MessageBubble from '../components/chat/MessageBubble';
import StreamingMessage from '../components/chat/StreamingMessage';

import ErrorMessage from '../components/chat/ErrorMessage';
import SuggestedQuestions from '../components/chat/SuggestedQuestions';
import RegulationPanel from '../components/chat/RegulationPanel';
import DocumentViewPanel from '../components/chat/DocumentViewPanel';
import ChatSessionSidebar from '../components/chat/ChatSessionSidebar';
import JudgmentCard from '../components/chat/JudgmentCard';
import ScheduleCard from '../components/chat/ScheduleCard';
import GenerateCard from '../components/chat/GenerateCard';
import MarkdownText from '../components/chat/MarkdownText';
import SourceItem from '../components/chat/SourceItem';
import useChat from '../hooks/useChat';
import useChatStore from '../store/chatStore';
import { listRegulations } from '../api/regulations';
import { listDocuments, downloadDocument, uploadDocument } from '../api/documents';
import { toast } from '../store/toastStore';

function exportChat(messages) {
  if (messages.length === 0) return;

  const now = new Date();
  const dateStr = now.toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' }).replace(/\. /g, '-').replace('.', '');
  const timeStr = now.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false });

  const lines = [`AI 챗봇 대화 기록`, `내보낸 시각: ${dateStr} ${timeStr}`, `총 ${messages.length}개 메시지`, '─'.repeat(40), ''];

  messages.forEach((msg) => {
    const role = msg.role === 'user' ? '[나]' : '[AI]';
    lines.push(`${role}:`);
    lines.push(msg.content);
    lines.push('');
  });

  const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `chat-export-${dateStr}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

const RESULT_MAP = { yes: '가능', no: '불가', conditional: '조건부 가능', no_regulation: '규정 없음' };

// LLM 응답 텍스트에서 raw enum 값을 한국어로 치환
function cleanResultText(text) {
  if (!text) return text;
  return text
    .replace(/[""\u201C\u201D]no_regulation[""\u201C\u201D]/g, '"규정 없음"')
    .replace(/\bno_regulation\b/g, '규정 없음');
}

const RESULT_BADGE = {
  yes: { icon: CheckCircle, bg: 'bg-green-50', border: 'border-green-200', text: 'text-green-700', iconColor: 'text-green-500' },
  no: { icon: XCircle, bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-700', iconColor: 'text-red-500' },
  conditional: { icon: AlertTriangle, bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-700', iconColor: 'text-amber-500' },
  no_regulation: { icon: HelpCircle, bg: 'bg-gray-50', border: 'border-gray-200', text: 'text-gray-600', iconColor: 'text-gray-400' },
};

function renderCardMessage(msg, onSelectClarify, onSelectDoc, messages = [], index = -1) {
  const { resultIntent, agentResponse, content } = msg;
  const data = agentResponse || {};

  switch (resultIntent) {
    case 'judgment': {
      // 사용자의 질문 내용 확인 (이전 메시지)
      const userMsg = index > 0 ? messages[index - 1]?.content || '' : '';
      // '규정', '알려줘', '설명'만 있는 경우는 정보 조회로 간주 (의문형/판단형 키워드가 없을 때)
      const isJudgmentRequest = /가능|요건|조건|되나요|있나요|수 있|있습니|허용|금지|위반|처벌|준수/.test(userMsg);

      // 'none'이나 판단 결과가 명확하지 않거나, 단순 정보 조회인 경우 배지 숨김
      const isInformational = !data.result || data.result === 'none' || data.result === 'info' || (data.result === 'yes' && !isJudgmentRequest);

      const resultLabel = isInformational ? null : (RESULT_MAP[data.result] || data.result || '판단 완료');
      const badge = isInformational ? null : (RESULT_BADGE[data.result] || null);

      const regType = data.result === 'no' ? 'deny' : data.result === 'conditional' ? 'conditional' : 'ref';
      const regulations = (data.regulations || []).map((r) => ({
        name: `${r.name || ''} ${r.article || ''}`.trim(),
        type: regType,
        verdict: r.content || '',
      }));
      return (
        <>
          {/* 판단 배지 (불가/가능 등) — 맨 위 */}
          {resultLabel && badge && (() => {
            const Icon = badge.icon;
            return (
              <div className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-sm font-semibold mb-2 ${badge.bg} ${badge.border} ${badge.text}`}>
                <Icon size={16} className={badge.iconColor} />
                {resultLabel}
              </div>
            );
          })()}
          {/* 줄글 (스트리밍 텍스트) */}
          <div className="bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm p-4 text-sm text-neutral-main leading-relaxed shadow-sm">
            <MarkdownText>{cleanResultText(content || data.reasoning)}</MarkdownText>
          </div>
          {/* 규정 + 신뢰도 카드 */}
          <JudgmentCard summary={null} regulations={regulations} confidenceBreakdown={data.confidence_breakdown} warnings={data.warnings} confidence={data.confidence} />
        </>
      );
    }

    case 'doc_search': {
      const sources = data.sources || data.references || [];
      return (
        <div className="bg-surface-card rounded-[14px] border border-neutral-border overflow-hidden">
          <div className="px-4 py-3 border-b border-neutral-divider flex items-center gap-2 font-bold text-sm text-primary-700">
            문서 검색 결과
          </div>
          <div className="p-4">
            {content && <div className="text-[0.8125rem] text-neutral-main leading-[1.7] mb-3.5"><MarkdownText>{content}</MarkdownText></div>}
            {sources.length > 0 && (
              <div>
                <div className="text-xs font-semibold text-neutral-sub mb-2">출처 ({sources.length}건)</div>
                {sources.map((s, idx) => (
                  <SourceItem key={idx} source={s} index={idx} onSelect={onSelectDoc} />
                ))}
              </div>
            )}
          </div>
        </div>
      );
    }

    case 'doc_generate': {
      const docData = data.data || {};
      const TEMPLATE_NAMES = { meeting_minutes: '회의록', report: '업무보고서', proposal: '제안서' };
      const templateName = data.template_name || TEMPLATE_NAMES[data.template_type] || '문서';

      const fieldsMap = {
        meeting_minutes: [
          { label: '날짜', value: String(docData.date || '') },
          { label: '참석자', value: Array.isArray(docData.attendees) ? docData.attendees.join(', ') : String(docData.attendees || '') },
          { label: '요약', value: String(data.summary || docData.summary || '') },
        ],
        report: [
          { label: '보고 개요', value: typeof docData.overview === 'string' ? docData.overview : '' },
          { label: '향후 계획', value: typeof docData.next_plan === 'string' ? docData.next_plan : '' },
        ],
        proposal: [
          { label: '제안 배경', value: typeof docData.background === 'string' ? docData.background : '' },
          { label: '기대 효과', value: typeof docData.expected_effect === 'string' ? docData.expected_effect : '' },
        ],
      };
      const fields = (fieldsMap[data.template_type] || []).filter((f) => f.value);

      const handleDocDownload = async () => {
        if (!data.document_id) { toast.warning('문서 ID가 없습니다.'); return; }
        try {
          const resp = await downloadDocument(data.document_id, 'docx');
          const url = URL.createObjectURL(resp.data);
          const a = document.createElement('a');
          a.href = url;
          a.download = `${templateName}.docx`;
          a.click();
          URL.revokeObjectURL(url);
        } catch (err) {
          toast.error('다운로드 실패: ' + (err.response?.data?.detail || err.message));
        }
      };

      return (
        <GenerateCard
          title={String(docData.title || templateName)}
          templateType={data.template_type}
          fields={fields}
          onDownload={handleDocDownload}
        />
      );
    }

    case 'schedule_add': {
      const gs = data.google_services || {};
      const sched = data.schedule || {};
      return (
        <div>
          <ScheduleCard
            title={sched.title || data.title || data.summary || '일정 등록'}
            date={sched.start_time?.split('T')[0] || data.date || ''}
            time={sched.start_time?.split('T')[1]?.slice(0, 5) || data.time || ''}
            synced={gs.calendar_synced || data.synced || data.google_synced || false}
            meetLink={gs.meet_link || null}
            emailSent={gs.email_sent || false}
            emailCount={gs.email_count || 0}
          />
          {content && (
            <div className="mt-2 bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm p-4 text-sm text-neutral-main leading-relaxed whitespace-pre-wrap">
              {content}
            </div>
          )}
        </div>
      );
    }

    case 'doc_qa': {
      const sources = data.sources || [];
      const citations = data.citations || [];
      const qaConfidence = typeof data.confidence === 'number' ? data.confidence : null;
      const confColor = qaConfidence >= 0.7 ? { bar: 'bg-green-500', text: 'text-green-600' } : qaConfidence >= 0.4 ? { bar: 'bg-yellow-500', text: 'text-yellow-600' } : { bar: 'bg-red-500', text: 'text-red-600' };
      return (
        <div className="bg-surface-card rounded-[14px] border border-neutral-border overflow-hidden">
          <div className="px-4 py-3 border-b border-neutral-divider flex items-center justify-between">
            <div className="flex items-center gap-2 font-bold text-sm text-primary-700">문서 Q&A</div>
            {qaConfidence !== null && (
              <div className="flex items-center gap-1.5">
                <ShieldCheck size={14} className={confColor.text} />
                <div className="w-16 h-2 bg-neutral-100 rounded-full overflow-hidden">
                  <div className={`h-full rounded-full ${confColor.bar}`} style={{ width: `${Math.round(qaConfidence * 100)}%` }} />
                </div>
                <span className={`text-xs font-bold ${confColor.text}`}>{Math.round(qaConfidence * 100)}%</span>
              </div>
            )}
          </div>
          <div className="p-4">
            {content && <div className="text-[0.8125rem] text-neutral-main leading-[1.7] mb-3.5"><MarkdownText>{content}</MarkdownText></div>}
            {citations.length > 0 && (
              <div className="mb-3">
                <div className="text-xs font-semibold text-neutral-sub mb-2">인용 ({citations.length}건)</div>
                {citations.map((c, idx) => {
                  const rel = c.relevance || '';
                  const relColor = rel === '높음' ? 'bg-green-100 text-green-700' : rel === '중간' ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700';
                  return (
                    <div key={idx} className="px-3 py-2 bg-surface-hover rounded-lg mb-1.5 border-l-[3px] border-l-primary-300">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-semibold text-neutral-main truncate">{c.source || `인용 ${idx + 1}`}</span>
                        {rel && <span className={`text-[0.625rem] font-semibold px-1.5 py-0.5 rounded-full ${relColor}`}>{rel}</span>}
                      </div>
                      {c.content && <div className="text-[0.6875rem] text-neutral-sub mt-0.5">{c.content}</div>}
                    </div>
                  );
                })}
              </div>
            )}
            {sources.length > 0 && (
              <div>
                <div className="text-xs font-semibold text-neutral-sub mb-2">검색 출처 ({sources.length}건)</div>
                {sources.map((s, idx) => (
                  <SourceItem key={idx} source={s} index={idx} onSelect={onSelectDoc} />
                ))}
              </div>
            )}
          </div>
        </div>
      );
    }

    case 'doc_summary': {
      return (
        <div className="bg-surface-card rounded-[14px] border border-neutral-border overflow-hidden">
          <div className="px-4 py-3 border-b border-neutral-divider flex items-center gap-2 font-bold text-sm text-primary-700">
            <FileText size={16} />
            문서 요약
          </div>
          <div className="p-4 text-[0.8125rem] text-neutral-main leading-[1.7]">
            <MarkdownText>{content || data.answer || data.message}</MarkdownText>
          </div>
        </div>
      );
    }

    case 'doc_pick': {
      const documents = data.documents || [];
      // 이 assistant 메시지 바로 앞의 user 메시지가 원본 쿼리
      const originalQuery = index > 0 ? (messages[index - 1]?.content || '요약해줘') : '요약해줘';
      return (
        <div>
          <div className="bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm p-4 text-sm text-neutral-main leading-relaxed">
            {data.message || '요약할 문서를 선택해주세요:'}
          </div>
          {documents.length > 0 && (
            <div className="mt-2 flex flex-col gap-2 max-h-64 overflow-y-auto pr-1">
              {documents.map((doc, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    useChatStore.getState().setSelectedDocument(doc.document_id, doc.title);
                    onSelectClarify?.(originalQuery);
                  }}
                  className="flex items-center gap-2 px-4 py-2.5 text-sm bg-surface-card border border-neutral-border rounded-xl hover:bg-primary-50 hover:border-primary-300 text-neutral-main hover:text-primary-700 transition text-left"
                >
                  <FileText size={14} className="flex-shrink-0 text-neutral-muted" />
                  <span className="truncate">{doc.title}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      );
    }

    case 'clarify': {
      const candidates = data.candidates || [];
      return (
        <div>
          <div className="bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm p-4 text-sm text-neutral-main leading-relaxed whitespace-pre-wrap">
            {content || data.message || '질문을 명확히 해주세요.'}
          </div>
          {candidates.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {candidates.map((c, idx) => (
                <button
                  key={idx}
                  onClick={() => onSelectClarify?.(typeof c === 'string' ? c : c.query || c.label)}
                  className="px-3 py-1.5 text-xs bg-primary-50 text-primary-700 rounded-full border border-primary-200 hover:bg-primary-100 transition"
                >
                  {typeof c === 'string' ? c : c.label || c.query}
                </button>
              ))}
            </div>
          )}
        </div>
      );
    }

    default:
      return (
        <div className="bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm p-4 text-sm text-neutral-main leading-relaxed">
          <MarkdownText>{content}</MarkdownText>
        </div>
      );
  }
}

export default function ChatPage() {
  const { isScrolled } = useOutletContext();
  const [searchParams] = useSearchParams();
  const { messages, isStreaming, currentIntent, currentStatus, sendMessage } = useChat();
  const clearMessages = useChatStore((s) => s.clearMessages);
  const initSession = useChatStore((s) => s.initSession);
  const switchSession = useChatStore((s) => s.switchSession);
  const startNewSession = useChatStore((s) => s.startNewSession);
  const pendingQuestion = useChatStore((s) => s.pendingQuestion);
  const clearPendingQuestion = useChatStore((s) => s.clearPendingQuestion);
  const selectedDocumentId = useChatStore((s) => s.selectedDocumentId);
  const selectedDocumentName = useChatStore((s) => s.selectedDocumentName);
  const setSelectedDocument = useChatStore((s) => s.setSelectedDocument);
  const clearSelectedDocument = useChatStore((s) => s.clearSelectedDocument);
  const [panelOpen, setPanelOpen] = useState(false);
  const [docViewDoc, setDocViewDoc] = useState(null);
  const [sessionSidebarOpen, setSessionSidebarOpen] = useState(false);
  const [lastError, setLastError] = useState(null);
  const [lastInput, setLastInput] = useState('');
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [dbRegulations, setDbRegulations] = useState([]);
  const [docPickerOpen, setDocPickerOpen] = useState(false);
  const [docList, setDocList] = useState([]);
  const [docSearch, setDocSearch] = useState('');
  const [hasNewRegulations, setHasNewRegulations] = useState(false);

  const mountedRef = useRef(false);
  const lastSeenJudgmentIdxRef = useRef(-1);

  useEffect(() => {
    if (mountedRef.current) return;
    mountedRef.current = true;

    const sessionParam = searchParams.get('session');
    const q = useChatStore.getState().pendingQuestion;
    if (sessionParam) {
      // URL에서 세션 ID로 직접 전환 (마이페이지 등에서 클릭)
      switchSession(sessionParam);
    } else if (q) {
      // 대시보드에서 질문 클릭 → 새 세션 시작 후 자동 전송 (세션은 sendMessage에서 생성)
      clearPendingQuestion();
      setLastInput(q);
      sendMessage(q);
    } else {
      initSession();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    listRegulations()
      .then((res) => setDbRegulations(res.data || []))
      .catch((err) => console.warn('[ChatPage] 규정 로드 실패:', err));
  }, []);

  useEffect(() => {
    if (!docPickerOpen) return;
    listDocuments()
      .then((res) => setDocList(res.data?.documents || res.data || []))
      .catch((err) => console.warn('[ChatPage] 문서 로드 실패:', err));
  }, [docPickerOpen]);

  const handleSend = async (text, files = []) => {
    const storeState = useChatStore.getState();
    if (storeState.isStreaming) return; // 전송/업로드 중복 방지

    setLastError(null);
    setLastInput(text);

    if (files && files.length > 0) {
      const storeState = useChatStore.getState();
      storeState.setStreaming(true);
      storeState.setCurrentStatus('문서 업로드 및 문서 구조 분석 중...');
      try {
        const file = files[0];
        const res = await uploadDocument(file, 'personal');
        storeState.setSelectedDocument(res.data.id, res.data.title);
      } catch (err) {
        console.error('[ChatPage] 파일 업로드 실패:', err);
        setLastError('파일 업로드에 실패했습니다. 다시 시도해주세요.');
        storeState.setStreaming(false);
        storeState.setCurrentStatus(null);
        return;
      }
      storeState.setCurrentStatus(null);
      storeState.setStreaming(false);
    }

    sendMessage(text);
  };

  const handleRetry = () => {
    if (lastInput) {
      setLastError(null);
      sendMessage(lastInput);
    }
  };

  const handleClear = () => {
    if (messages.length === 0) return;
    setShowClearConfirm(true);
  };

  const confirmClear = () => {
    clearMessages();
    setLastError(null);
    setLastInput('');
    setShowClearConfirm(false);
  };

  // 메시지에서 마지막 judgment 응답의 regulations 추출 (DB 원문 우선 병합)
  const regulationsFromMessages = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.resultIntent === 'judgment' && msg.agentResponse?.regulations) {
        const confidence = msg.agentResponse.confidence;
        return msg.agentResponse.regulations.map((r) => {
          const articleKey = (r.article || r.name || '').match(/제\d+조/)?.[0];
          const dbReg = articleKey
            ? dbRegulations.find((db) => db.article_number === articleKey)
            : null;
          const rawRelevance = r.relevance ?? r.score ?? null;
          const relevance = typeof rawRelevance === 'number' && !isNaN(rawRelevance)
            ? rawRelevance
            : (typeof confidence === 'number' && !isNaN(confidence) ? confidence : null);
          return {
            name: r.name || dbReg?.title || '',
            article: r.article || dbReg?.article_number || '',
            content: dbReg?.content || r.content || '',
            relevance,
          };
        });
      }
    }
    return [];
  }, [messages, dbRegulations]);

  // 판단 agent 응답으로 새 규정이 들어오면 알림 활성화
  useEffect(() => {
    let latestIdx = -1;
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].resultIntent === 'judgment' && messages[i].agentResponse?.regulations?.length > 0) {
        latestIdx = i;
        break;
      }
    }
    if (latestIdx > -1 && latestIdx !== lastSeenJudgmentIdxRef.current && !panelOpen) {
      setHasNewRegulations(true);
    }
  }, [messages, panelOpen]);

  return (
    <div className="flex flex-col h-full">
      <header className={`flex justify-between items-center pl-8 pr-8 bg-surface-main z-10 flex-shrink-0 transition-all duration-300 ${isScrolled ? 'py-2.5' : 'py-6'}`}>
        <div>
          <h1 className={`font-bold transition-all duration-300 ${isScrolled ? 'text-lg' : 'text-2xl'}`}>나에게 물어봐</h1>
          <p className={`text-neutral-sub transition-all duration-300 overflow-hidden ${isScrolled ? 'text-xs mt-0 max-h-0 opacity-0' : 'text-sm mt-0.5 max-h-6 opacity-100'}`}>규정 판단, 문서 분석, 일정 관리를 도와드립니다</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => exportChat(messages)}
            disabled={messages.length === 0}
            className="btn-outline text-xs disabled:opacity-40 disabled:cursor-not-allowed"
            title="대화 내보내기"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="inline mr-1">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            내보내기
          </button>
          <button
            onClick={handleClear}
            disabled={messages.length === 0}
            className="btn-outline text-xs disabled:opacity-40 disabled:cursor-not-allowed text-red-500 border-red-200 hover:bg-red-50"
            title="대화 초기화"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="inline mr-1">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            </svg>
            초기화
          </button>
          <button
            onClick={() => setDocPickerOpen(true)}
            className={`btn-outline text-xs ${selectedDocumentId ? 'bg-accent-50 border-accent-300 text-accent-700' : ''}`}
            title="요약할 문서 선택"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="inline mr-1">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            {selectedDocumentId ? '문서 선택됨' : '문서 선택'}
          </button>
          <button
            onClick={() => {
              const opening = !panelOpen;
              setPanelOpen(opening);
              if (opening) {
                setHasNewRegulations(false);
                for (let i = messages.length - 1; i >= 0; i--) {
                  if (messages[i].resultIntent === 'judgment' && messages[i].agentResponse?.regulations?.length > 0) {
                    lastSeenJudgmentIdxRef.current = i;
                    break;
                  }
                }
              }
            }}
            className={`btn-outline text-xs relative ${panelOpen ? 'bg-primary-50 border-primary-300' : ''} ${hasNewRegulations && !panelOpen ? 'border-primary-400 bg-primary-50 text-primary-700 shadow-[0_0_8px_rgba(59,130,246,0.5)]' : ''}`}
            style={hasNewRegulations && !panelOpen ? { animation: 'reg-glow 1.5s ease-in-out infinite' } : undefined}
          >
            규정 패널
            {hasNewRegulations && !panelOpen && (
              <span className="absolute -top-1.5 -right-1.5 flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-primary-500"></span>
              </span>
            )}
          </button>
        </div>
      </header>

      {/* 문서 선택 피커 */}
      {docPickerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => { setDocPickerOpen(false); setDocSearch(''); }}>
          <div className="bg-surface-card rounded-xl shadow-xl w-[28rem] max-w-[90vw] overflow-hidden" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b border-neutral-divider">
              <h3 className="text-sm font-semibold text-neutral-main">요약할 문서 선택</h3>
              <button onClick={() => { setDocPickerOpen(false); setDocSearch(''); }} className="text-neutral-muted hover:text-neutral-main transition">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
            <div className="px-4 py-3 border-b border-neutral-divider">
              <input
                autoFocus
                value={docSearch}
                onChange={(e) => setDocSearch(e.target.value)}
                placeholder="문서 검색..."
                className="w-full px-3 py-2 text-sm border border-neutral-border rounded-md bg-surface-main outline-none focus:border-primary-300 text-neutral-main placeholder:text-neutral-muted"
              />
            </div>
            <div className="max-h-64 overflow-y-auto py-1">
              {docList.filter(d => !docSearch || d.title?.includes(docSearch) || d.original_filename?.includes(docSearch)).length === 0 ? (
                <div className="py-8 text-center text-sm text-neutral-muted">
                  {docList.length === 0 ? '등록된 문서가 없습니다' : '검색 결과 없음'}
                </div>
              ) : (
                docList
                  .filter(d => !docSearch || d.title?.includes(docSearch) || d.original_filename?.includes(docSearch))
                  .map((doc) => (
                    <button
                      key={doc.id}
                      onClick={() => { setSelectedDocument(doc.id, doc.title || doc.original_filename); setDocPickerOpen(false); setDocSearch(''); }}
                      className={`w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-surface-hover transition text-sm ${selectedDocumentId === doc.id ? 'bg-accent-50 text-accent-700' : 'text-neutral-main'}`}
                    >
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="flex-shrink-0 text-neutral-muted">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <polyline points="14 2 14 8 20 8" />
                      </svg>
                      <span className="truncate">{doc.title || doc.original_filename}</span>
                    </button>
                  ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* 초기화 확인 다이얼로그 */}
      {showClearConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-surface-card rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
            <h3 className="text-base font-semibold mb-2">대화 기록을 초기화할까요?</h3>
            <p className="text-sm text-neutral-sub mb-5">모든 대화 내용이 삭제됩니다. 이 작업은 되돌릴 수 없습니다.</p>
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowClearConfirm(false)} className="btn-outline text-sm px-4 py-2">취소</button>
              <button onClick={confirmClear} className="bg-red-500 hover:bg-red-600 text-white text-sm px-4 py-2 rounded-md transition">삭제</button>
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-1 min-h-0">
        {/* 왼쪽 아이콘 레일 + 세션 사이드바 */}
        <div className="flex flex-shrink-0 h-full">
          <div className="w-11 bg-surface-card border-r border-neutral-divider flex flex-col items-center py-2 gap-2">
            <button
              onClick={() => setSessionSidebarOpen(!sessionSidebarOpen)}
              title={sessionSidebarOpen ? '대화 목록 닫기' : '대화 목록'}
              className={`w-8 h-8 flex items-center justify-center rounded-md transition ${sessionSidebarOpen
                ? 'text-primary-700 bg-primary-50'
                : 'text-neutral-sub hover:text-primary-700 hover:bg-primary-50'
                }`}
            >
              <Menu size={18} />
            </button>
            <button
              onClick={() => { startNewSession(); setSessionSidebarOpen(true); }}
              title="새 대화"
              className="w-8 h-8 flex items-center justify-center rounded-md text-neutral-sub hover:text-primary-700 hover:bg-primary-50 transition"
            >
              <MessageSquarePlus size={18} />
            </button>
          </div>
          <ChatSessionSidebar isOpen={sessionSidebarOpen} />
        </div>

        {/* 챗 영역 */}
        <div className="flex-1 min-w-0">
          <ChatWindow onSend={handleSend} messages={messages} selectedDocumentName={selectedDocumentName} onClearDocument={clearSelectedDocument} activeIntent={currentIntent || messages.filter(m => m.role === 'assistant').at(-1)?.resultIntent || messages.filter(m => m.role === 'assistant').at(-1)?.intent} isStreaming={isStreaming} panelOpen={panelOpen || !!docViewDoc}>
            {/* 메시지가 없을 때 — 추천 질문 */}
            {messages.length === 0 && (
              <SuggestedQuestions onSelect={handleSend} />
            )}

            {/* 메시지 렌더링 */}
            {messages.map((msg, i) => {
              const isLastAssistant = msg.role === 'assistant' && i === messages.length - 1 && isStreaming;
              // 빈 어시스턴트 메시지: isStreaming 설정 전에도 타이핑 인디케이터 표시
              const isWaitingForResponse = !isLastAssistant && msg.role === 'assistant' && i === messages.length - 1 && !msg.content && !msg.error && !msg.agentResponse;

              // 사용자 메시지
              if (msg.role === 'user') {
                return <MessageBubble key={i} type="user">{msg.content}</MessageBubble>;
              }

              // 에러 메시지
              if (msg.error) {
                return <ErrorMessage key={i} message={msg.error} onRetry={handleRetry} />;
              }

              // 스트리밍 중인 AI 응답 (데이터가 미리 왔더라도 텍스트 출력을 우선으로 보여줌)
              if (isLastAssistant || isWaitingForResponse) {
                const intent = currentIntent || msg.resultIntent || msg.intent || 'general';
                return (
                  <MessageBubble key={i} type="bot" intent={intent}>
                    <StreamingMessage
                      text={intent === 'judgment' ? cleanResultText(msg.content) : msg.content}
                      status={currentStatus}
                      intent={intent}
                      isInsideBubble
                    />
                  </MessageBubble>
                );
              }

              // AI 완료 — agentResponse 카드 렌더링
              if (msg.agentResponse && msg.resultIntent) {
                return (
                  <MessageBubble key={i} type="bot" intent={msg.resultIntent || msg.intent}>
                    {renderCardMessage(msg, handleSend, setDocViewDoc, messages, i)}
                  </MessageBubble>
                );
              }

              // AI 완료 — 기본 텍스트 버블
              return (
                <MessageBubble key={i} type="bot" intent={msg.intent}>
                  <div className="bg-surface-card border border-neutral-border rounded-2xl rounded-bl-sm p-4 text-sm text-neutral-main leading-relaxed">
                    <MarkdownText>{msg.content}</MarkdownText>
                  </div>
                </MessageBubble>
              );
            })}

            {/* 에러 표시 */}
            {lastError && <ErrorMessage message={lastError} onRetry={handleRetry} />}
          </ChatWindow>
        </div>

        {/* 우측 패널: 문서 보기 or 규정 패널 */}
        {docViewDoc ? (
          <DocumentViewPanel doc={docViewDoc} onClose={() => setDocViewDoc(null)} />
        ) : (
          <RegulationPanel
            regulations={regulationsFromMessages}
            isOpen={panelOpen}
            onClose={() => setPanelOpen(false)}
          />
        )}
      </div>
    </div>
  );
}
