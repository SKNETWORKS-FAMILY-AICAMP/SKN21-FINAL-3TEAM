import { useState } from 'react';

const PERIODS = ['일간', '주간', '월간'];

const STATS_BY_PERIOD = {
  '일간': [
    { label: '판단 질의', percent: 72, color: '#6E87A0' },
    { label: '문서 분석', percent: 18, color: '#A89580' },
    { label: '일정 관리', percent: 10, color: '#5B9A6F' },
  ],
  '주간': [
    { label: '판단 질의', percent: 58, color: '#6E87A0' },
    { label: '문서 분석', percent: 27, color: '#A89580' },
    { label: '일정 관리', percent: 15, color: '#5B9A6F' },
  ],
  '월간': [
    { label: '판단 질의', percent: 63, color: '#6E87A0' },
    { label: '문서 분석', percent: 22, color: '#A89580' },
    { label: '일정 관리', percent: 15, color: '#5B9A6F' },
  ],
};

export default function SystemStats({ stats = [], queryLogs = [] }) {
  const [period, setPeriod] = useState('일간');
  const currentStats = STATS_BY_PERIOD[period] || stats;

  return (
    <div className="space-y-5">
      <div className="card">
        <div className="card-header">
          <div className="card-title"><span>📊</span>시스템 통계</div>
          <div className="flex gap-1">
            {PERIODS.map((t) => (
              <button
                key={t}
                onClick={() => setPeriod(t)}
                className={`px-3 py-1 rounded-md text-xs font-medium transition ${period === t ? 'bg-primary-50 text-primary-700 font-semibold' : 'text-neutral-sub hover:bg-surface-hover'}`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
        <div className="card-body space-y-3">
          {currentStats.map((s, i) => (
            <div key={i} className="flex justify-between items-center">
              <span className="text-[0.8125rem] text-neutral-sub w-16">{s.label}</span>
              <div className="flex-1 mx-3 h-2 bg-neutral-divider rounded-full"><div className="h-full rounded-full transition-all duration-300" style={{ width: s.percent + '%', background: s.color }} /></div>
              <span className="text-[0.8125rem] font-semibold w-10 text-right" style={{ color: s.color }}>{s.percent}%</span>
            </div>
          ))}
        </div>
      </div>
      <div className="card">
        <div className="card-header"><div className="card-title"><span>📝</span>최근 질의 로그</div></div>
        <div className="card-body">
          {queryLogs.map((q, i) => (
            <div key={i} className={`flex items-center gap-3 px-2 py-3 rounded-sm transition hover:bg-surface-hover ${i < queryLogs.length - 1 ? 'border-b border-neutral-divider' : ''}`}>
              <div className={`w-9 h-9 rounded-sm flex items-center justify-center text-base flex-shrink-0 ${q.type === 'query' ? 'bg-accent-50' : q.type === 'doc' ? 'bg-primary-50' : 'bg-success-bg'}`}>{q.icon}</div>
              <div className="flex-1">
                <div className="text-[0.8125rem] font-semibold">{q.title}</div>
                <div className="text-xs text-neutral-sub mt-0.5">{q.description}</div>
              </div>
              <span className="text-[0.6875rem] text-neutral-muted whitespace-nowrap">{q.time}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
