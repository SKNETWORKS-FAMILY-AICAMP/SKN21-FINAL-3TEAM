import { useState, useRef, useEffect, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown, X } from 'lucide-react';

const fallbackAvatar = (name) =>
  `https://api.dicebear.com/7.x/notionists/svg?seed=${encodeURIComponent(name || 'unknown')}`;

export default function MemberMultiSelect({ members = [], selectedIds = [], onChange, placeholder = '참석자 선택' }) {
  const [open, setOpen] = useState(false);
  const [filterTeam, setFilterTeam] = useState('전체');
  const [dropStyle, setDropStyle] = useState({});
  const ref = useRef(null);
  const dropRef = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (
        ref.current && !ref.current.contains(e.target) &&
        dropRef.current && !dropRef.current.contains(e.target)
      ) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // 포탈 위치 계산 — 트리거 오른쪽에 배치
  useEffect(() => {
    if (open && ref.current) {
      const rect = ref.current.getBoundingClientRect();
      const dropWidth = 260;
      const dropHeight = Math.min(360, window.innerHeight - 40);
      // 수직 중앙 정렬 (트리거 기준), 뷰포트 범위 내 클램핑
      const idealTop = rect.top + rect.height / 2 - dropHeight / 2;
      const clampedTop = Math.max(8, Math.min(idealTop, window.innerHeight - dropHeight - 8));

      setDropStyle({
        position: 'fixed',
        top: clampedTop,
        left: rect.right + 8,
        width: dropWidth,
        maxHeight: dropHeight,
        zIndex: 9999,
      });
    }
  }, [open]);

  // 팀 목록 추출
  const teams = useMemo(() => {
    const set = new Set();
    members.forEach((m) => { if (m.team) set.add(m.team); });
    return ['전체', ...Array.from(set).sort()];
  }, [members]);

  // 필터된 멤버
  const filtered = filterTeam === '전체' ? members : members.filter((m) => m.team === filterTeam);

  const toggle = (id) => {
    const strId = String(id);
    if (selectedIds.includes(strId)) {
      onChange(selectedIds.filter((s) => s !== strId));
    } else {
      onChange([...selectedIds, strId]);
    }
  };

  const remove = (id) => {
    onChange(selectedIds.filter((s) => s !== String(id)));
  };

  const selectedMembers = members.filter((m) => selectedIds.includes(String(m.id)));

  return (
    <div ref={ref} className="relative">
      {/* Trigger */}
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-sm outline-none focus:ring-2 focus:ring-sky-400 transition-all cursor-pointer text-left min-h-[42px]"
      >
        {selectedMembers.length > 0 ? (
          <div className="flex flex-wrap gap-1 flex-1">
            {selectedMembers.map((m) => (
              <span
                key={m.id}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary-50 text-primary-700 text-xs font-medium"
              >
                <img
                  src={m.avatar || fallbackAvatar(m.name)}
                  alt={m.name}
                  className="w-4 h-4 rounded-full object-cover"
                />
                {m.name}
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); remove(m.id); }}
                  className="hover:text-red-500 transition-colors"
                >
                  <X size={12} />
                </button>
              </span>
            ))}
          </div>
        ) : (
          <span className="truncate flex-1 text-neutral-400">{placeholder}</span>
        )}
        <ChevronDown size={16} className={`text-neutral-400 transition-transform flex-shrink-0 ${open ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown — Portal로 렌더링하여 overflow 문제 해결 */}
      {open && createPortal(
        <div
          ref={dropRef}
          style={dropStyle}
          className="rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 shadow-lg flex flex-col"
        >
          {/* 팀 필터 탭 — 스크롤 밖 고정 */}
          {teams.length > 2 && (
            <div className="flex gap-1 px-2 py-2 border-b border-neutral-100 dark:border-neutral-700 overflow-x-auto flex-shrink-0">
              {teams.map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setFilterTeam(t)}
                  className={`px-2.5 py-1 text-[11px] font-semibold rounded-full whitespace-nowrap transition-colors ${
                    filterTeam === t
                      ? 'bg-primary-100 text-primary-700'
                      : 'text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-700'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          )}

          {/* 멤버 리스트 */}
          <div className="flex-1 overflow-y-auto">
            {filtered.length === 0 && (
              <div className="px-3 py-2 text-xs text-neutral-400 text-center">멤버 없음</div>
            )}
            {filtered.map((m) => {
              const isSelected = selectedIds.includes(String(m.id));
              return (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => toggle(m.id)}
                  className={`w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-neutral-50 dark:hover:bg-neutral-700 transition-colors ${
                    isSelected ? 'bg-sky-50 dark:bg-sky-900/20' : ''
                  }`}
                >
                  <img
                    src={m.avatar || fallbackAvatar(m.name)}
                    alt={m.name}
                    className="w-6 h-6 rounded-full object-cover flex-shrink-0 border border-neutral-200 dark:border-neutral-600"
                  />
                  <span className="truncate text-neutral-800 dark:text-neutral-100">
                    {m.name}
                  </span>
                  {m.team && (
                    <span className="ml-auto text-[10px] text-neutral-400 flex-shrink-0">
                      {m.team}
                    </span>
                  )}
                  {isSelected && (
                    <span className="ml-1 text-primary-500 flex-shrink-0">✓</span>
                  )}
                </button>
              );
            })}
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
