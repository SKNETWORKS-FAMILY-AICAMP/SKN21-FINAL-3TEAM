import { useState } from 'react';

export default function ScopeSelector({ value, onChange }) {
  const [selected, setSelected] = useState(value || 'company');
  const handleClick = (v) => { setSelected(v); onChange?.(v); };

  return (
    <div className="flex gap-2 mt-3">
      {[{ v: 'company', l: '회사 문서' }, { v: 'personal', l: '개인 문서' }].map(({ v, l }) => (
        <button key={v} onClick={() => handleClick(v)}
          className={`px-4 py-1.5 rounded-full border text-xs font-medium transition ${selected === v ? 'bg-primary-700 text-white border-primary-700' : 'bg-surface-card text-neutral-sub border-neutral-border'}`}>{l}</button>
      ))}
    </div>
  );
}
