import { useState, useRef, useEffect } from 'react';
import { ChevronDown, X } from 'lucide-react';

/**
 * Custom dropdown for selecting a team member, showing avatar + name.
 * Props:
 *  - members: array of { id, name, team, avatar }
 *  - value: selected member id (string or number, '' for none)
 *  - onChange: (id: string) => void
 *  - placeholder: string (default '전체')
 *  - className: additional wrapper class
 */
export default function MemberDropdown({ members = [], value, onChange, placeholder = '전체', className = '' }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const selected = members.find(m => String(m.id) === String(value));
  const fallbackAvatar = (name) =>
    `https://api.dicebear.com/7.x/notionists/svg?seed=${encodeURIComponent(name || 'unknown')}`;

  return (
    <div ref={ref} className={`relative ${className}`}>
      {/* Trigger button */}
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-sm outline-none focus:ring-2 focus:ring-sky-400 transition-all cursor-pointer text-left"
      >
        {selected ? (
          <>
            <img
              src={selected.avatar || fallbackAvatar(selected.name)}
              alt={selected.name}
              className="w-6 h-6 rounded-full object-cover flex-shrink-0 border border-neutral-200 dark:border-neutral-600"
            />
            <span className="truncate flex-1 text-neutral-800 dark:text-neutral-100">
              {selected.name}{selected.team ? ` (${selected.team})` : ''}
            </span>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onChange(''); setOpen(false); }}
              className="p-0.5 rounded-full hover:bg-neutral-100 dark:hover:bg-neutral-700 text-neutral-400 hover:text-neutral-600 transition-colors flex-shrink-0"
            >
              <X size={14} />
            </button>
          </>
        ) : (
          <>
            <span className="truncate flex-1 text-neutral-400">{placeholder}</span>
            <ChevronDown size={16} className={`text-neutral-400 transition-transform ${open ? 'rotate-180' : ''}`} />
          </>
        )}
      </button>

      {/* Dropdown list */}
      {open && (
        <div className="absolute z-50 mt-1 w-full max-h-48 overflow-y-auto rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 shadow-lg">
          <button
            type="button"
            onClick={() => { onChange(''); setOpen(false); }}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-700 transition-colors"
          >
            {placeholder}
          </button>
          {members.map(m => (
            <button
              key={m.id}
              type="button"
              onClick={() => { onChange(String(m.id)); setOpen(false); }}
              className={`w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-neutral-50 dark:hover:bg-neutral-700 transition-colors ${
                String(m.id) === String(value) ? 'bg-sky-50 dark:bg-sky-900/20' : ''
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
            </button>
          ))}
          {members.length === 0 && (
            <div className="px-3 py-2 text-xs text-neutral-400 text-center">멤버 없음</div>
          )}
        </div>
      )}
    </div>
  );
}
