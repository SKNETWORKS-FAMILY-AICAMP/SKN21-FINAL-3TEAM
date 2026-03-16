import { useState, useRef, useEffect } from 'react';
import { ChevronDown, X } from 'lucide-react';

const fallbackAvatar = (name) =>
  `https://api.dicebear.com/7.x/notionists/svg?seed=${encodeURIComponent(name || 'unknown')}`;

export default function MemberMultiSelect({ members = [], selectedIds = [], onChange, placeholder = '참석자 선택' }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

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

      {/* Dropdown */}
      {open && (
        <div className="absolute z-50 mt-1 w-full max-h-48 overflow-y-auto rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 shadow-lg">
          {members.length === 0 && (
            <div className="px-3 py-2 text-xs text-neutral-400 text-center">멤버 없음</div>
          )}
          {members.map((m) => {
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
      )}
    </div>
  );
}
