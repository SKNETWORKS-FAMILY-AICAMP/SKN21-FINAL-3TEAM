import ScopeSelector from './ScopeSelector';
import { Upload } from 'lucide-react';

export default function DocumentUpload({ onUpload, onScopeChange }) {
  return (
    <div className="border-2 border-dashed border-neutral-border rounded-md p-8 text-center transition hover:border-primary-300 hover:bg-primary-50 cursor-pointer mb-5"
      onClick={() => document.getElementById('file-upload')?.click()}>
      <input type="file" id="file-upload" className="hidden" accept=".pdf,.docx,.txt" onChange={(e) => onUpload?.(e.target.files)} />
      <div className="mb-2 flex justify-center"><Upload size={32} className="text-neutral-muted" /></div>
      <div className="text-sm text-neutral-sub">파일을 끌어다 놓거나 클릭하여 업로드</div>
      <div className="text-xs text-neutral-muted mt-1">PDF, DOCX, TXT 지원 (최대 50MB)</div>
      <ScopeSelector onChange={onScopeChange} />
    </div>
  );
}
