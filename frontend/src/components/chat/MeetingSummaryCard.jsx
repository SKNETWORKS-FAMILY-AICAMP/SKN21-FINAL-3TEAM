import { User, Calendar } from 'lucide-react';

export default function MeetingSummaryCard({ title, date, attendees = [], decisions = [], actionItems = [] }) {
  return (
    <div className="bg-surface-card rounded-lg border border-neutral-border overflow-hidden">
      <div className="px-4 py-3 border-b border-neutral-divider flex items-center gap-2 font-bold text-sm text-primary-700">
        {title || '회의 요약'}
      </div>
      <div className="p-4 space-y-3.5">
        {/* 회의 정보 */}
        <div className="flex gap-4 text-xs text-neutral-sub">
          {date && <span className="flex items-center gap-1"><Calendar size={12} />{date}</span>}
          {attendees.length > 0 && <span>{attendees.join(', ')}</span>}
        </div>

        {/* 결정사항 */}
        {decisions.length > 0 && (
          <div>
            <div className="text-xs font-semibold text-neutral-sub mb-2">결정사항 ({decisions.length}건)</div>
            <div className="space-y-1.5">
              {decisions.map((d, i) => (
                <div key={i} className="flex items-start gap-2 text-[0.8125rem] text-neutral-main">
                  <span className="text-success flex-shrink-0 mt-0.5">✓</span>
                  <span className="leading-relaxed">{typeof d === 'object' ? (d.decision || d.content || JSON.stringify(d)) : d}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Action Items */}
        {actionItems.length > 0 && (
          <div>
            <div className="text-xs font-semibold text-neutral-sub mb-2">Action Items ({actionItems.length}건)</div>
            <div className="space-y-1.5">
              {actionItems.map((item, i) => (
                <div key={i} className="flex items-start gap-2 px-3 py-2 bg-surface-hover rounded-lg text-[0.8125rem]">
                  <span className="flex-shrink-0 mt-0.5">☐</span>
                  <div className="flex-1">
                    <span className="text-neutral-main">{item.task}</span>
                    {(item.assignee || item.deadline) && (
                      <div className="flex gap-3 mt-1 text-[0.6875rem] text-neutral-muted">
                        {item.assignee && <span className="flex items-center gap-1"><User size={11} />{item.assignee}</span>}
                        {item.deadline && <span className="flex items-center gap-1"><Calendar size={11} />{item.deadline}</span>}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
