import { useState, useRef } from 'react';
import { TEMPLATE_CATEGORIES } from '../../utils/constants';

export default function TemplateUploadDialog({ isOpen, onClose, onUpload }) {
  const [file, setFile] = useState(null);
  const [name, setName] = useState('');
  const [category, setCategory] = useState('custom');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const fileRef = useRef(null);

  if (!isOpen) return null;

  const handleFileChange = (e) => {
    const f = e.target.files?.[0];
    if (f) {
      setFile(f);
      if (!name) setName(f.name.replace(/\.[^.]+$/, ''));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file || !name.trim()) return;
    setLoading(true);
    try {
      await onUpload?.({ file, name, category, description });
      onClose();
    } catch {
      // 에러는 부모에서 처리
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <div className="bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-lg border border-white/40 dark:border-white/10 w-[480px] shadow-md" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-neutral-divider">
          <h3 className="text-[0.9375rem] font-bold text-neutral-main">템플릿 업로드</h3>
          <button onClick={onClose} className="text-neutral-muted hover:text-neutral-main transition">✕</button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {/* 파일 선택 */}
          <div>
            <label className="block text-[0.8125rem] font-semibold mb-1.5">파일</label>
            <input ref={fileRef} type="file" accept=".docx" onChange={handleFileChange} className="hidden" />
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className="w-full px-3.5 py-6 border-2 border-dashed border-neutral-border rounded-sm text-sm text-neutral-muted hover:border-primary-300 hover:text-primary-700 transition text-center"
            >
              {file ? (
                <span className="text-neutral-main font-medium">{file.name}</span>
              ) : (
                <>클릭하여 파일 선택 (.docx)</>
              )}
            </button>
          </div>

          {/* 템플릿 이름 */}
          <div>
            <label className="block text-[0.8125rem] font-semibold mb-1.5">템플릿 이름</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="예: 주간 보고서 양식"
              className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500"
            />
          </div>

          {/* 카테고리 */}
          <div>
            <label className="block text-[0.8125rem] font-semibold mb-1.5">카테고리</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500 bg-surface-card"
            >
              {TEMPLATE_CATEGORIES.map((c) => (
                <option key={c.value} value={c.value}>{c.label}</option>
              ))}
            </select>
          </div>

          {/* 설명 */}
          <div>
            <label className="block text-[0.8125rem] font-semibold mb-1.5">설명 (선택)</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="템플릿에 대한 설명"
              rows={2}
              className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500 resize-y"
            />
          </div>

          {/* 버튼 */}
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="btn-outline text-xs">취소</button>
            <button
              type="submit"
              disabled={loading || !file || !name.trim()}
              className="btn-primary text-xs disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? '업로드 중...' : '업로드'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
