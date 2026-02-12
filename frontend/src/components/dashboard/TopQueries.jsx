import { useState } from 'react';
import { Link } from 'react-router-dom';

const PERIOD_TABS = ['월간', '주간', '일간'];

const intentColor = {
  판단: '#6E87A0',
  문서: '#A89580',
  일정: '#5B9A6F',
  일반: '#9CA3AF',
};

export default function TopQueries({ data = {} }) {
  const [period, setPeriod] = useState(PERIOD_TABS[0]);

  const queries = data[period] || [];

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><span>🏆</span>Top 질의 응답</div>
        <div className="flex gap-1">
          {PERIOD_TABS.map((t) => (
            <button
              key={t}
              onClick={() => setPeriod(t)}
              className={`px-3 py-1 rounded-md text-[0.75rem] font-medium transition ${period === t ? 'bg-primary-50 text-primary-700 font-semibold' : 'text-neutral-sub hover:bg-surface-hover'}`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>
      <div className="card-body space-y-2">
        {queries.length === 0 && (
          <p className="text-[0.875rem] text-neutral-muted text-center py-4">데이터가 없습니다</p>
        )}
        {queries.map((q, i) => (
          <Link
            key={i}
            to="/chat"
            className="flex items-center gap-3 p-3 rounded-sm border border-neutral-divider transition hover:border-primary-300 hover:bg-surface-hover"
          >
            <div className="w-7 h-7 rounded-full bg-primary-50 flex items-center justify-center text-[0.75rem] font-bold text-primary-700 flex-shrink-0">
              {i + 1}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[0.8125rem] font-semibold text-neutral-main truncate">{q.question}</div>
              <div className="flex gap-2.5 text-[0.6875rem] text-neutral-muted mt-1">
                <span style={{ color: intentColor[q.type] || '#9CA3AF' }}>● {q.type}</span>
                <span>{q.count}회 질의</span>
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
