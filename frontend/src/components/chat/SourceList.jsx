import { useState } from 'react';
import { ChevronRight } from 'lucide-react';
import SourceItem from './SourceItem';

const MAX_COUNT = 5;

export default function SourceList({ sources, onSelect }) {
  const [expanded, setExpanded] = useState(true);
  const visible = sources.slice(0, MAX_COUNT);

  return (
    <div>
      <button
        onClick={() => setExpanded(v => !v)}
        className="flex items-center gap-1 text-xs font-semibold text-neutral-sub mb-2 hover:text-primary-600 transition"
      >
        <ChevronRight size={14} className={`transition-transform ${expanded ? 'rotate-90' : ''}`} />
        <span>관련 문서 ({visible.length}건)</span>
      </button>
      {expanded && visible.map((s, idx) => (
        <SourceItem key={idx} source={s} index={idx} onSelect={onSelect} />
      ))}
    </div>
  );
}
