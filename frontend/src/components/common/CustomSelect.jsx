import { useState, useRef, useEffect } from 'react';
import { ChevronDown } from 'lucide-react';

export default function CustomSelect({ value, onChange, options = [], className = '', buttonClassName = '' }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => { if (!ref.current?.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={ref} className={`relative inline-flex items-center ${className}`}>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
        className={`flex items-center gap-1.5 px-3 rounded-md border text-xs font-medium whitespace-nowrap transition
          ${buttonClassName || 'py-1.5'}
          ${open
            ? 'border-primary-300 bg-primary-50 text-primary-700'
            : 'border-neutral-border bg-surface-card text-neutral-sub hover:border-primary-300 hover:text-neutral-main'
          }`}
      >
        {value}
        <ChevronDown size={12} className={`transition-transform duration-200 ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute top-full mt-1 left-0 z-50 min-w-full bg-surface-card border border-neutral-border rounded-md shadow-lg overflow-hidden">
          {options.map((opt) => (
            <button
              key={opt}
              type="button"
              onClick={(e) => { e.stopPropagation(); onChange?.(opt); setOpen(false); }}
              className={`w-full text-left px-3 py-2 text-xs whitespace-nowrap transition
                ${opt === value
                  ? 'bg-primary-100 text-primary-700 font-semibold'
                  : 'text-neutral-main hover:bg-primary-50'
                }`}
            >
              {opt}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
