import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search } from 'lucide-react';

const SUGGESTED_TAGS = ['정보보안', '인사규정', '재택근무', '출장비', '개인정보', '코드리뷰'];

export default function QuickSearch() {
  const [query, setQuery] = useState('');
  const navigate = useNavigate();

  const handleSearch = (text) => {
    const q = text || query;
    if (!q.trim()) return;
    navigate(`/chat?q=${encodeURIComponent(q.trim())}`);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleSearch();
  };

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><Search size={16} className="text-neutral-sub" />빠른 규정 검색</div>
      </div>
      <div className="card-body">
        <div className="flex items-center gap-2 mb-3">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="규정을 검색하세요 (예: 재택근무 규정)"
            className="flex-1 px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500 focus:shadow-[0_0_0_3px_rgba(110,135,160,0.1)] placeholder:text-neutral-muted"
          />
          <button
            onClick={() => handleSearch()}
            className="btn-primary px-5"
          >
            검색
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {SUGGESTED_TAGS.map((tag) => (
            <button
              key={tag}
              onClick={() => handleSearch(tag)}
              className="px-3 py-1.5 rounded-full text-xs font-medium bg-primary-50 text-primary-700 border border-primary-100 transition hover:bg-primary-100"
            >
              {tag}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
