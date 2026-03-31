import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown } from 'lucide-react';

// 00:00 ~ 23:45 (15분 간격) 타임 옵션 생성
const timeOptions = [];
for (let h = 0; h < 24; h++) {
  for (let m = 0; m < 60; m += 15) {
    const val = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
    timeOptions.push(val);
  }
}

function addOneHour(timeStr) {
  const [h, m] = timeStr.split(':').map(Number);
  const totalMin = h * 60 + m + 60;
  if (totalMin >= 24 * 60) return '23:50';
  return `${String(Math.floor(totalMin / 60)).padStart(2, '0')}:${String(totalMin % 60).padStart(2, '0')}`;
}

export default function TimeSelect({ value, onChange }) {
  const [isOpen, setIsOpen] = useState(false);
  const [dropStyle, setDropStyle] = useState({});
  const triggerRef = useRef(null);
  const listRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (
        triggerRef.current && !triggerRef.current.contains(e.target) &&
        listRef.current && !listRef.current.contains(e.target)
      ) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (isOpen && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      const dropdownHeight = 192; // max-h-48 = 12rem = 192px
      const spaceBelow = window.innerHeight - rect.bottom;
      const openUpward = spaceBelow < dropdownHeight && rect.top > spaceBelow;

      setDropStyle({
        position: 'fixed',
        left: rect.left,
        width: rect.width,
        zIndex: 9999,
        ...(openUpward
          ? { bottom: window.innerHeight - rect.top + 2 }
          : { top: rect.bottom + 2 }),
      });
    }
  }, [isOpen]);

  // 드롭다운 열릴 때 선택된 항목으로 스크롤
  useEffect(() => {
    if (isOpen && listRef.current) {
      const selected = listRef.current.querySelector('[data-selected="true"]');
      if (selected) selected.scrollIntoView({ block: 'center' });
    }
  }, [isOpen]);

  return (
    <div className="relative" ref={triggerRef}>
      <button
        type="button"
        onClick={() => setIsOpen((o) => !o)}
        className="w-full flex items-center justify-between px-3 py-2.5 border border-neutral-border rounded-sm text-sm bg-surface-card hover:border-primary-400 outline-none transition"
      >
        <span>{value}</span>
        <ChevronDown size={14} className="text-neutral-muted" />
      </button>

      {isOpen && createPortal(
        <div
          ref={listRef}
          style={dropStyle}
          className="bg-surface-card border border-neutral-border rounded-md shadow-lg overflow-y-auto max-h-48"
        >
          {timeOptions.map((t) => (
            <button
              key={t}
              type="button"
              data-selected={t === value}
              onClick={() => { onChange(t); setIsOpen(false); }}
              className={`w-full text-left px-3 py-1.5 text-sm transition ${t === value
                ? 'bg-primary-50 text-primary-700 font-semibold'
                : 'text-neutral-main hover:bg-surface-hover'
                }`}
            >
              {t}
            </button>
          ))}
        </div>,
        document.body
      )}
    </div>
  );
}

export { timeOptions, addOneHour };
