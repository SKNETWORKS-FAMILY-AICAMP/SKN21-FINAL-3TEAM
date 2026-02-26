import { useState } from 'react';
import { Link } from 'react-router-dom';
import Badge from '../common/Badge';
import { Calendar, MapPin, Users, ListChecks, User } from 'lucide-react';

export default function TodaySchedule({ meetings = [], actions = [] }) {
  const [actionData, setActionData] = useState(actions);

  const toggleDone = (i) => {
    const next = [...actionData];
    next[i] = { ...next[i], done: !next[i].done };
    setActionData(next);
  };

  return (
    <div className="card">
      {/* 섹션 1: 오늘 일정 */}
      <div className="card-header">
        <div className="card-title"><Calendar size={16} className="text-neutral-sub" />오늘 일정</div>
      </div>
      <div className="card-body space-y-2.5">
        {meetings.length === 0 && (
          <p className="text-sm text-neutral-muted py-2">오늘 예정된 회의가 없습니다.</p>
        )}
        {meetings.map((m, i) => (
          <Link key={i} to="/meetings" className="flex items-center gap-3.5 p-3.5 rounded-sm border border-neutral-border transition hover:bg-surface-hover">
            <div className="text-center flex-shrink-0">
              <div className="font-display text-lg font-bold text-primary-700">{m.time}</div>
              <div className="text-[0.6875rem] text-neutral-muted font-medium">{m.period}</div>
            </div>
            <div className="flex-1">
              <div className="text-sm font-semibold text-neutral-main">{m.title}</div>
              <div className="flex gap-3 mt-1 text-xs text-neutral-sub">
                <span className="flex items-center gap-1"><MapPin size={12} />{m.location}</span>
                <span className="flex items-center gap-1"><Users size={12} />{m.attendees}명</span>
              </div>
            </div>
            <Badge variant="status-scheduled">예정</Badge>
          </Link>
        ))}
      </div>

      {/* 구분선 */}
      <div className="border-t border-neutral-border mx-4" />

      {/* 섹션 2: 마감 임박 */}
      <div className="card-header mt-1">
        <div className="card-title"><ListChecks size={16} className="text-neutral-sub" />마감 임박</div>
      </div>
      <div className="card-body space-y-1">
        {actionData.length === 0 && (
          <p className="text-sm text-neutral-muted py-2">마감 임박한 항목이 없습니다.</p>
        )}
        {actionData.map((item, i) => (
          <div
            key={i}
            className={`flex items-center gap-3 p-3 rounded-sm border-l-[3px] transition hover:bg-surface-hover ${
              item.priority === 'high' ? 'border-l-error bg-error/[0.03]' :
              item.priority === 'medium' ? 'border-l-warning bg-warning/[0.03]' :
              'border-l-transparent'
            }`}
          >
            <button
              aria-label={`${item.title} 완료 체크`}
              className={`w-5 h-5 rounded-[5px] border-2 border-primary-300 flex items-center justify-center text-xs font-bold text-white flex-shrink-0 transition ${
                item.done ? 'bg-success border-success' : ''
              }`}
              onClick={() => toggleDone(i)}
            >
              {item.done && '✓'}
            </button>
            <div className="flex-1">
              <div className={`text-[0.8125rem] font-semibold text-neutral-main ${item.done ? 'line-through opacity-50' : ''}`}>
                {item.title}
              </div>
              <div className="flex gap-3 mt-1 text-[0.75rem] text-neutral-sub">
                <span className="flex items-center gap-1"><User size={12} />{item.assignee}</span>
                <span className={item.priority === 'high' || item.priority === 'medium' ? 'text-error font-semibold' : ''}>
                  {item.deadline}
                </span>
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
