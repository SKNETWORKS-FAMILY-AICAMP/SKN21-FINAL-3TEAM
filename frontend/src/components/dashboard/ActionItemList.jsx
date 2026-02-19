import { useState } from 'react';
import Badge from '../common/Badge';
import { ListChecks, User } from 'lucide-react';

export default function ActionItemList({ items = [], tabs }) {
  const [activeTab, setActiveTab] = useState(tabs?.[0] || '마감 임박');
  const [data, setData] = useState(items);

  const toggleDone = (i) => {
    const n = [...data];
    n[i] = { ...n[i], done: !n[i].done };
    setData(n);
  };

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><ListChecks size={16} className="text-neutral-sub" />진행 중인 Action Items</div>
        {tabs && (
          <div className="flex gap-1">
            {tabs.map((t) => (
              <button key={t} onClick={() => setActiveTab(t)} className={`px-3 py-1 rounded-md text-xs font-medium transition ${activeTab === t ? 'bg-primary-50 text-primary-700 font-semibold' : 'text-neutral-sub hover:bg-surface-hover'}`}>{t}</button>
            ))}
          </div>
        )}
      </div>
      <div className="card-body space-y-1">
        {data.map((item, i) => (
          <div key={i} className={`flex items-center gap-3 p-3 rounded-sm border-l-[3px] transition hover:bg-surface-hover ${item.priority === 'high' ? 'border-l-error bg-error/[0.03]' : item.priority === 'medium' ? 'border-l-warning bg-warning/[0.03]' : 'border-l-transparent'}`}>
            <button aria-label={`${item.title} 완료 체크`} className={`w-5 h-5 rounded-[5px] border-2 border-primary-300 flex items-center justify-center text-xs font-bold text-white flex-shrink-0 transition ${item.done ? 'bg-success border-success' : ''}`} onClick={() => toggleDone(i)}>
              {item.done && '✓'}
            </button>
            <div className="flex-1">
              <div className="text-[0.8125rem] font-semibold text-neutral-main">{item.title}</div>
              <div className="flex gap-3 mt-1 text-[0.75rem] text-neutral-sub">
                <span className="flex items-center gap-1"><User size={12} />{item.assignee}</span>
                <span className={item.priority === 'high' || item.priority === 'medium' ? 'text-error font-semibold' : ''}>{item.deadline}</span>
              </div>
            </div>
            <Badge variant={`priority-${item.priority}`}>
              {item.priority === 'high' ? '높음' : item.priority === 'medium' ? '중간' : '낮음'}
            </Badge>
          </div>
        ))}
      </div>
    </div>
  );
}
