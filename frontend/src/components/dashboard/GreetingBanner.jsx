import { Smile } from 'lucide-react';
import useAuthStore from '../../store/authStore';

export default function GreetingBanner({ meetingCount = 0, actionCount = 0, riskCount = 0 }) {
  const user = useAuthStore((s) => s.user);
  const name = user?.name || '사용자';

  const parts = [];
  if (meetingCount > 0) parts.push(`회의 ${meetingCount}건`);
  if (actionCount > 0) parts.push(`마감 임박 ${actionCount}건`);
  if (riskCount > 0) parts.push(`리스크 ${riskCount}건`);
  const summary = parts.length > 0 ? `오늘 ${parts.join(', ')}이 있습니다.` : '오늘 예정된 일정이 없습니다.';

  return (
    <div className="rounded-2xl border border-neutral-divider overflow-hidden p-6" style={{ background: 'rgba(255,255,255,0.45)', backdropFilter: 'blur(10px)', WebkitBackdropFilter: 'blur(10px)', boxShadow: '0 1px 2px rgba(0,0,0,0.03), 0 4px 12px rgba(0,0,0,0.04)' }}>
      <div className="flex items-center gap-3">
        <Smile size={24} className="text-primary-700 flex-shrink-0" />
        <div>
          <h2 className="text-xl font-bold text-neutral-main">안녕하세요, {name}님</h2>
          <p className="text-[0.875rem] text-neutral-sub mt-1">{summary}</p>
        </div>
      </div>
    </div>
  );
}
