import { useState, useRef, useEffect, useCallback } from 'react';
import { Scale, FileText, CalendarDays, MessageCircle } from 'lucide-react';

const ALLOWED_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
  'image/png',
  'image/jpeg',
  'image/gif',
  'image/webp',
];
const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.txt', '.png', '.jpg', '.jpeg', '.gif', '.webp'];
const MAX_SIZE = 10 * 1024 * 1024; // 10MB

function validateFile(file) {
  const ext = '.' + file.name.split('.').pop().toLowerCase();
  if (!ALLOWED_TYPES.includes(file.type) && !ALLOWED_EXTENSIONS.includes(ext)) {
    return 'PDF, DOCX, TXT, 이미지 파일만 첨부할 수 있습니다.';
  }
  if (file.size > MAX_SIZE) {
    return '파일 크기는 10MB 이하여야 합니다.';
  }
  return null;
}

function FileChip({ file, onRemove }) {
  const sizeStr = file.size < 1024 * 1024
    ? `${(file.size / 1024).toFixed(0)}KB`
    : `${(file.size / (1024 * 1024)).toFixed(1)}MB`;

  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-primary-50 text-primary-700 text-xs rounded-full border border-primary-100">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
      </svg>
      <span className="max-w-[120px] truncate">{file.name}</span>
      <span className="text-neutral-muted">({sizeStr})</span>
      <button onClick={onRemove} className="hover:text-error transition ml-0.5" title="제거">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    </span>
  );
}

const AGENTS = [
  { key: 'judgment', icon: Scale, label: '규정 판단', intents: ['judgment'] },
  { key: 'document', icon: FileText, label: '문서', intents: ['doc_retrieve', 'doc_generate', 'doc_search', 'doc_summary'] },
  { key: 'schedule', icon: CalendarDays, label: '일정', intents: ['schedule_add', 'schedule_view'] },
  { key: 'general', icon: MessageCircle, label: '일반', intents: ['general'] },
];

function AgentBar({ activeIntent, isStreaming }) {
  const activeKey = AGENTS.find((a) => a.intents.includes(activeIntent))?.key;

  return (
    <div className="flex items-center justify-center gap-2 px-4 py-2">
      {AGENTS.map((agent) => {
        const isActive = agent.key === activeKey;
        const Icon = agent.icon;
        return (
          <div
            key={agent.key}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-full text-xs font-semibold transition-all duration-300 select-none ${isActive
              ? 'bg-primary-700 text-white shadow-md scale-105'
              : 'bg-surface-hover text-neutral-sub'
              }`}
          >
            <Icon size={14} className={isActive && isStreaming ? 'animate-pulse' : ''} />
            {agent.label}
          </div>
        );
      })}
    </div>
  );
}

export default function ChatWindow({ messages, onSend, selectedDocumentName, onClearDocument, activeIntent, isStreaming, panelOpen, onScrollChange, topbarScrolled, children }) {
  const [input, setInput] = useState('');
  const [files, setFiles] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const [fileError, setFileError] = useState(null);
  const bottomRef = useRef(null);
  const scrollContainerRef = useRef(null);
  const fileInputRef = useRef(null);
  const dragCounterRef = useRef(0);
  const mountedRef = useRef(false);
  const lastScrollTopRef = useRef(0);
  const programmaticScrollRef = useRef(false);
  const programmaticTimerRef = useRef(null);

  const markProgrammaticScroll = () => {
    programmaticScrollRef.current = true;
    clearTimeout(programmaticTimerRef.current);
    programmaticTimerRef.current = setTimeout(() => {
      programmaticScrollRef.current = false;
    }, 500);
  };

  const handleScroll = (e) => {
    if (programmaticScrollRef.current) return;

    const scrollTop = e.target.scrollTop;
    lastScrollTopRef.current = scrollTop;

    // 메시지가 없으면 헤더 상태 변경하지 않음
    if (onScrollChange && messages && messages.length > 0) {
      onScrollChange(scrollTop > 100);
    }
  };

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    if (!mountedRef.current) {
      mountedRef.current = true;
      if (messages && messages.length > 0) {
        markProgrammaticScroll();
        container.scrollTo({ top: container.scrollHeight, behavior: 'instant' });
      }
    } else {
      // 사용자가 위로 스크롤한 상태면 자동 스크롤하지 않음
      const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 150;
      if (isNearBottom) {
        markProgrammaticScroll();
        // 스트리밍 중: instant (토큰마다 smooth하면 끊김), 완료 후: smooth
        container.scrollTo({ top: container.scrollHeight, behavior: isStreaming ? 'instant' : 'smooth' });
      }
    }
  }, [messages, isStreaming]);

  // 카드 렌더링 등으로 컨텐츠 높이가 변할 때 자동 스크롤
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const observer = new ResizeObserver(() => {
      // 사용자가 위로 스크롤한 상태가 아닐 때만 자동 스크롤
      const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 150;
      if (isNearBottom) {
        markProgrammaticScroll();
        container.scrollTo({ top: container.scrollHeight, behavior: 'instant' });
      }
    });
    // 스크롤 컨테이너의 직접 자식들 높이 변화 감지
    Array.from(container.children).forEach(child => observer.observe(child));
    return () => observer.disconnect();
  }, [messages]);

  const addFiles = useCallback((fileList) => {
    setFileError(null);
    const newFiles = [];
    for (const file of fileList) {
      const err = validateFile(file);
      if (err) {
        setFileError(err);
        return;
      }
      // 중복 방지
      if (!files.some(f => f.name === file.name && f.size === file.size)) {
        newFiles.push(file);
      }
    }
    setFiles(prev => [...prev, ...newFiles]);
  }, [files]);

  const removeFile = useCallback((index) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
    setFileError(null);
  }, []);

  const handleDragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current++;
    if (e.dataTransfer.types.includes('Files')) {
      setDragOver(true);
    }
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current--;
    if (dragCounterRef.current === 0) {
      setDragOver(false);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
    dragCounterRef.current = 0;
    if (e.dataTransfer.files?.length > 0) {
      addFiles(e.dataTransfer.files);
    }
  };

  const handleSend = () => {
    const text = input.trim();
    if (!text && files.length === 0) return;

    let finalText = text;
    if (files.length > 0) {
      const fileNames = files.map(f => f.name).join(', ');
      const attachText = `[첨부: ${fileNames}]`;
      finalText = finalText ? `${finalText}\n${attachText}` : attachText;
    }

    onSend?.(finalText, files);
    setInput('');
    setFiles([]);
    setFileError(null);
  };

  return (
    <div
      className="flex flex-col h-full relative"
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {/* 드래그 오버레이 */}
      {dragOver && (
        <div className="absolute inset-0 z-40 bg-primary-50/80 border-2 border-dashed border-primary-300 rounded-lg flex items-center justify-center pointer-events-none">
          <div className="text-center">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="mx-auto mb-2 text-primary-500">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            <p className="text-sm font-semibold text-primary-700">파일을 여기에 놓으세요</p>
            <p className="text-xs text-neutral-sub mt-1">PDF, DOCX, TXT, 이미지 (최대 10MB)</p>
          </div>
        </div>
      )}


      {/* 헤더는 ChatPage에서 별도로 렌더링됨 */}

      <div ref={scrollContainerRef} className="flex-1 min-h-0 overflow-y-auto py-4 custom-scrollbar" data-main-scroll="" onScroll={handleScroll}>
        <div className="max-w-4xl mx-auto w-full px-6 min-h-[calc(100%+1px)]">
          {children}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* 선택 문서 칩 & 파일 칩 & 에러 */}
      {(selectedDocumentName || files.length > 0 || fileError) && (
        <div className="max-w-4xl mx-auto w-full px-6 pb-2 flex flex-wrap gap-1.5">
          {selectedDocumentName && (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-accent-50 text-accent-700 text-xs rounded-full border border-accent-300/40">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
              <span className="max-w-[160px] truncate">{selectedDocumentName}</span>
              <button onClick={onClearDocument} className="hover:text-error transition ml-0.5" title="문서 선택 해제">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </span>
          )}
          {fileError && (
            <p className="w-full text-xs text-error">{fileError}</p>
          )}
          {files.map((file, i) => (
            <FileChip key={`${file.name}-${i}`} file={file} onRemove={() => removeFile(i)} />
          ))}
        </div>
      )}

      {/* 입력 영역 */}
      <div className={`border-t border-neutral-divider flex-shrink-0 ${panelOpen ? 'pr-[3px]' : ''}`}>
      <div className={`max-w-4xl mx-auto w-full flex gap-2.5 pt-4 pb-4 px-6`}>
        <div className="flex-1 flex items-center bg-surface-card rounded-md border border-neutral-border px-4 py-3 transition focus-within:border-primary-300">
          {/* 파일 첨부 버튼 */}
          <button
            onClick={() => fileInputRef.current?.click()}
            className="mr-2 text-neutral-muted hover:text-primary-700 transition flex-shrink-0"
            title="파일 첨부"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
            </svg>
          </button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.txt,.png,.jpg,.jpeg,.gif,.webp"
            className="hidden"
            onChange={(e) => {
              if (e.target.files?.length > 0) {
                addFiles(e.target.files);
              }
              e.target.value = '';
            }}
          />
          <textarea
            data-testid="chat-input"
            value={input} onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="질문을 입력하세요..." rows={1}
            className="border-none bg-transparent text-sm text-neutral-main w-full outline-none resize-none overflow-hidden leading-5"
            style={{ maxHeight: '120px', overflowY: input.split('\n').length > 6 ? 'auto' : 'hidden' }}
            ref={(el) => {
              if (el) {
                el.style.height = 'auto';
                el.style.height = Math.min(el.scrollHeight, 120) + 'px';
              }
            }}
          />
        </div>
        <button onClick={handleSend} className="w-11 h-11 rounded-md bg-primary-700 flex-shrink-0 flex items-center justify-center transition hover:bg-primary-900">
          <svg width="18" height="18" viewBox="0 0 18 18"><path d="M2 9L16 2L12 16L9 10L2 9Z" fill="white" /></svg>
        </button>
      </div>
      </div>
    </div>
  );
}
