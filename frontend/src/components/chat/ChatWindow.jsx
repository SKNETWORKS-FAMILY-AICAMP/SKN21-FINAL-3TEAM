import { useState, useRef, useEffect } from 'react';

// FileChip 컴포넌트
function FileChip({ file, onRemove }) {
  return (
    <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-primary-50 border border-primary-200 rounded-md text-xs text-primary-700">
      <span>📎 {file.name}</span>
      <button onClick={onRemove} className="hover:text-primary-900">✕</button>
    </div>
  );
}

export default function ChatWindow({ messages, onSend, children }) {
  const [input, setInput] = useState('');
  const [attachedFiles, setAttachedFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const bottomRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  // 파일 검증 (PDF, DOCX, TXT, 이미지, 10MB 제한)
  const validateFile = (file) => {
    const allowedTypes = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'text/plain',
      'image/png',
      'image/jpeg',
      'image/jpg',
      'image/gif',
    ];
    if (!allowedTypes.includes(file.type)) {
      alert('지원하지 않는 파일 형식입니다. (PDF, DOCX, TXT, 이미지만 가능)');
      return false;
    }
    if (file.size > 10 * 1024 * 1024) {
      alert('파일 크기는 10MB 이하만 가능합니다.');
      return false;
    }
    return true;
  };

  const handleFileSelect = (files) => {
    const validFiles = Array.from(files).filter(validateFile);
    setAttachedFiles((prev) => [...prev, ...validFiles]);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    handleFileSelect(e.dataTransfer.files);
  };

  const handleSend = () => {
    if (!input.trim() && attachedFiles.length === 0) return;
    const message = attachedFiles.length > 0
      ? `${input.trim()} [첨부: ${attachedFiles.map((f) => f.name).join(', ')}]`
      : input.trim();
    onSend?.(message);
    setInput('');
    setAttachedFiles([]);
  };

  return (
    <div
      className="flex flex-col h-full relative"
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* 드래그 오버레이 */}
      {isDragging && (
        <div className="absolute inset-0 bg-primary-500/10 border-4 border-dashed border-primary-500 rounded-md flex items-center justify-center z-50">
          <div className="text-center">
            <div className="text-4xl mb-2">📁</div>
            <div className="text-lg font-bold text-primary-700">파일을 여기에 드롭하세요</div>
            <div className="text-sm text-neutral-sub mt-1">PDF, DOCX, TXT, 이미지 (최대 10MB)</div>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto py-4 px-4">{children}<div ref={bottomRef} /></div>

      <div className="flex flex-col gap-2 pt-4 pb-4 px-4 pr-36 border-t border-neutral-divider flex-shrink-0">
        {/* 첨부 파일 목록 */}
        {attachedFiles.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {attachedFiles.map((file, i) => (
              <FileChip
                key={i}
                file={file}
                onRemove={() => setAttachedFiles((prev) => prev.filter((_, idx) => idx !== i))}
              />
            ))}
          </div>
        )}

        <div className="flex gap-2.5">
          <div className="flex-1 flex items-center bg-surface-card rounded-md border border-neutral-border px-4 py-3 transition focus-within:border-primary-300">
            {/* 파일 첨부 버튼 */}
            <button
              onClick={() => fileInputRef.current?.click()}
              className="mr-3 text-neutral-muted hover:text-primary-700 transition"
              aria-label="파일 첨부"
            >
              📎
            </button>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={(e) => handleFileSelect(e.target.files)}
            />
            <input
              type="text" value={input} onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="질문을 입력하세요..." className="border-none bg-transparent text-sm text-neutral-main w-full outline-none"
            />
          </div>
          <button onClick={handleSend} className="w-11 h-11 rounded-md bg-primary-700 flex items-center justify-center transition hover:bg-primary-900">
            <svg width="18" height="18" viewBox="0 0 18 18"><path d="M2 9L16 2L12 16L9 10L2 9Z" fill="white"/></svg>
          </button>
        </div>
      </div>
    </div>
  );
}
