import { useState } from 'react';
import Badge from '../common/Badge';

export default function ActionItemPanel({ items = [] }) {
  const [data, setData] = useState(items);

  const toggleDone = (i) => {
    const n = [...data];
    n[i] = { ...n[i], done: !n[i].done };
    setData(n);
  };

  return (
    <div className="space-y-1">
      {data.map((item, i) => (
        <div key={i} className={`flex items-center gap-3 p-3 rounded-sm border-l-[3px] transition hover:bg-surface-hover ${item.priority === 'high' ? 'border-l-error bg-error/[0.03]' : item.priority === 'medium' ? 'border-l-warning bg-warning/[0.03]' : 'border-l-transparent'}`}>
          <button aria-label={`${item.title} 완료 체크`} className={`w-5 h-5 rounded-[5px] border-2 border-primary-300 flex items-center justify-center text-xs font-bold text-white flex-shrink-0 transition ${item.done ? 'bg-success border-success' : ''}`} onClick={() => toggleDone(i)}>
            {item.done && '✓'}
          </button>
          <div className="flex-1">
            <div className="text-[0.8125rem] font-semibold text-neutral-main">{item.title}</div>
            <div className="flex gap-3 mt-1 text-xs text-neutral-sub">
              <span>👤 {item.assignee}</span>
              <span className={item.priority === 'high' ? 'text-error font-semibold' : ''}>{item.deadline}</span>
            </div>
          </div>
          <Badge variant={`priority-${item.priority}`}>{item.priority === 'high' ? '높음' : item.priority === 'medium' ? '중간' : '낮음'}</Badge>
        </div>
      ))}
    </div>
  );
}
