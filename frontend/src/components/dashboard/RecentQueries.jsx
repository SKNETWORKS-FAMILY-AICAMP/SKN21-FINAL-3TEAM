import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Trophy, HelpCircle } from 'lucide-react';

export default function RecentQueries({ queries = [], tabs = ['월간', '주간', '일간'] }) {
  const [activeTab, setActiveTab] = useState(tabs[0]);

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><Trophy size={16} className="text-neutral-sub" />Top 질의 응답</div>
        <div className="flex gap-1">
          {tabs.map((t) => (
            <button key={t} onClick={() => setActiveTab(t)} className={`px-3 py-1 rounded-md text-[0.75rem] font-medium transition ${activeTab === t ? 'bg-primary-50 text-primary-700 font-semibold' : 'text-neutral-sub hover:bg-surface-hover'}`}>{t}</button>
          ))}
        </div>
      </div>
      <div className="card-body space-y-2">
        {queries.map((q, i) => (
          <Link key={i} to="/chat" className="flex items-center gap-3 p-3 rounded-sm border border-neutral-border transition hover:bg-surface-hover">
            <div className="w-9 h-9 bg-primary-50 rounded-sm flex items-center justify-center flex-shrink-0 text-primary-700"><HelpCircle size={18} /></div>
            <div className="flex-1">
              <div className="text-[0.8125rem] font-semibold text-neutral-main">{q.question}</div>
              <div className="flex gap-2.5 text-[0.6875rem] text-neutral-muted mt-1">
                <span style={{ color: q.type === '판단' ? '#6E87A0' : '#A89580' }}>● {q.type}</span>
                <span>{q.count}회 질의</span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
