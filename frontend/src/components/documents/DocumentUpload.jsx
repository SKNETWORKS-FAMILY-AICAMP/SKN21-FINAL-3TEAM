import { useState, useCallback } from 'react';
import ScopeSelector from './ScopeSelector';
import { Upload } from 'lucide-react';

export default function DocumentUpload({ onUpload, onScopeChange }) {
  const [dragging, setDragging] = useState(false);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(false);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(false);
    const files = e.dataTransfer?.files;
    if (files?.length > 0) onUpload?.(files);
  }, [onUpload]);

  return (
    <div
      className={`border-2 border-dashed rounded-md min-h-[280px] flex flex-col items-center justify-center text-center transition cursor-pointer mb-5 ${
        dragging
          ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20'
          : 'border-neutral-border hover:border-primary-300 hover:bg-primary-50'
      }`}
      onClick={() => document.getElementById('file-upload')?.click()}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <input type="file" id="file-upload" className="hidden" accept=".pdf,.docx,.txt" onChange={(e) => { onUpload?.(e.target.files); e.target.value = ''; }} />
      <div className="mb-2"><Upload size={32} className={dragging ? 'text-primary-500' : 'text-neutral-muted'} /></div>
      <div className="text-sm text-neutral-sub">{dragging ? '여기에 놓으세요!' : '파일을 끌어다 놓거나 클릭하여 업로드'}</div>
      <div className="text-xs text-neutral-muted mt-1">PDF, DOCX, TXT 지원 (최대 50MB)</div>
      <ScopeSelector onChange={onScopeChange} />
    </div>
  );
}
