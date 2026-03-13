import { useState, useEffect } from 'react';
import { HelpCircle, FileText, CalendarClock } from 'lucide-react';
import { getTopQueries } from '../../api/admin';

const PERIODS = [
  { label: '일간', value: 'daily' },
  { label: '주간', value: 'weekly' },
  { label: '월간', value: 'monthly' },
];

const INTENT_COLORS = {
  judgment: '#6E87A0',
  doc_retrieve: '#A89580',
  doc_search: '#A89580',
  doc_generate: '#A89580',
  doc_summary: '#A89580',
  schedule_add: '#5B9A6F',
  schedule_view: '#5B9A6F',
  general: '#9B8EC4',
};

const INTENT_LABELS = {
  judgment: '판단 질의',
  doc_retrieve: '문서 검색/조회',
  doc_search: '문서 검색/조회',
  doc_generate: '문서 생성',
  doc_summary: '문서 요약',
  schedule_add: '일정 추가',
  schedule_view: '일정 조회',
  general: '일반 질문',
};

function timeAgo(timestamp) {
  if (!timestamp) return '';
  const diff = Date.now() - new Date(timestamp).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return '방금';
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}시간 전`;
  return `${Math.floor(hours / 24)}일 전`;
}

export default function SystemStats({ queryLogs = [], team = null }) {
  const [period, setPeriod] = useState('daily');
  const [topQueries, setTopQueries] = useState([]);
  const [selectedQuery, setSelectedQuery] = useState(null);

  useEffect(() => {
    getTopQueries(period, 5, team)
      .then((res) => setTopQueries(res.data || []))
      .catch(() => setTopQueries([]));
  }, [period, team]);

  // Top queries → 비율 계산
  const total = topQueries.reduce((sum, q) => sum + q.count, 0) || 1;
  const stats = topQueries.map((q) => ({
    label: q.question?.slice(0, 20) + (q.question?.length > 20 ? '...' : ''),
    fullQuestion: q.question || '',
    intent: q.intent,
    percent: Math.round((q.count / total) * 100),
    color: INTENT_COLORS[q.intent] || '#999',
    count: q.count,
  }));

  return (
    <div className="space-y-5 overflow-hidden">
      <div className="card overflow-hidden">
        <div className="card-header">
          <div className="card-title">인기 질의</div>
          <div className="flex gap-1">
            {PERIODS.map((t) => (
              <button
                key={t.value}
                onClick={() => setPeriod(t.value)}
                className={`px-3 py-1 rounded-md text-xs font-medium transition ${period === t.value ? 'bg-primary-50 text-primary-700 font-semibold' : 'text-neutral-sub hover:bg-surface-hover'}`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
        <div className="card-body space-y-3">
          {stats.length === 0 ? (
            <p className="text-sm text-neutral-sub text-center py-4">데이터가 없습니다</p>
          ) : stats.map((s, i) => (
            <div key={i} className="flex justify-between items-center cursor-pointer rounded-md px-1 py-1 hover:bg-surface-hover transition" onClick={() => setSelectedQuery(s)}>
              <span className="text-[0.8125rem] text-neutral-sub w-40 truncate">{s.label}</span>
              <div className="flex-1 mx-3 h-2 bg-neutral-divider rounded-full">
                <div className="h-full rounded-full transition-all duration-300" style={{ width: s.percent + '%', background: s.color }} />
              </div>
              <span className="text-[0.8125rem] font-semibold w-12 text-right" style={{ color: s.color }}>{s.count}건</span>
            </div>
          ))}
        </div>
      </div>

      {selectedQuery && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setSelectedQuery(null)}>
          <div className="bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-xl shadow-xl max-w-md w-full mx-4 overflow-hidden border border-white/40 dark:border-white/10" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-neutral-divider">
              <span className="text-sm font-bold text-neutral-main">질의 상세</span>
              <button onClick={() => setSelectedQuery(null)} className="text-neutral-muted hover:text-neutral-main text-lg leading-none">&times;</button>
            </div>
            <div className="px-5 py-4 space-y-3">
              <div>
                <div className="text-xs text-neutral-muted mb-1">질문 내용</div>
                <div className="text-sm text-neutral-main leading-relaxed break-words">{selectedQuery.fullQuestion}</div>
              </div>
              <div className="flex gap-4">
                <div>
                  <div className="text-xs text-neutral-muted mb-1">분류</div>
                  <span className="inline-block px-2 py-0.5 rounded text-xs font-medium text-white" style={{ background: selectedQuery.color }}>
                    {INTENT_LABELS[selectedQuery.intent] || selectedQuery.intent}
                  </span>
                </div>
                <div>
                  <div className="text-xs text-neutral-muted mb-1">조회 수</div>
                  <div className="text-sm font-semibold" style={{ color: selectedQuery.color }}>{selectedQuery.count}건</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="card overflow-hidden">
        <div className="card-header"><div className="card-title">최근 질의 로그</div></div>
        <div className="card-body">
          {queryLogs.length === 0 ? (
            <p className="text-sm text-neutral-sub text-center py-4">질의 로그가 없습니다</p>
          ) : queryLogs.slice(0, 10).map((q, i) => {
            const type = q.intent?.startsWith('doc') ? 'doc'
              : q.intent?.startsWith('schedule') ? 'schedule' : 'query';
            return (
              <div key={q.id || i} className={`flex items-center gap-3 px-2 py-3 rounded-sm transition hover:bg-surface-hover cursor-pointer ${i < queryLogs.length - 1 ? 'border-b border-neutral-divider' : ''}`} onClick={() => setSelectedQuery({ fullQuestion: q.question, intent: q.intent, count: 1, color: INTENT_COLORS[q.intent] || '#999' })}>
                <div className={`w-9 h-9 rounded-sm flex items-center justify-center flex-shrink-0 ${type === 'query' ? 'bg-accent-50 text-accent-700' : type === 'doc' ? 'bg-primary-50 text-primary-700' : 'bg-success-bg text-success'}`}>
                  {type === 'query' ? <HelpCircle size={18} /> : type === 'doc' ? <FileText size={18} /> : <CalendarClock size={18} />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[0.8125rem] font-semibold truncate">{q.question}</div>
                  <div className="text-xs text-neutral-sub mt-0.5">
                    {INTENT_LABELS[q.intent] || q.agent || q.intent || '-'}
                    {q.response_time_ms ? ` · ${(q.response_time_ms / 1000).toFixed(1)}초` : ''}
                  </div>
                </div>
                <span className="text-[0.6875rem] text-neutral-muted whitespace-nowrap">{timeAgo(q.timestamp)}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
