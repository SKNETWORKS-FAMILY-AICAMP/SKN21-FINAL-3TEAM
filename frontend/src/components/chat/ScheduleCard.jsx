import { useNavigate } from 'react-router-dom';

export default function ScheduleCard({ title, date, time, synced, meetLink, emailSent, emailCount }) {
  const navigate = useNavigate();

  return (
    <div className="bg-surface-card rounded-lg border border-neutral-border overflow-hidden">
      <div className="px-4 py-3 border-b border-neutral-divider flex items-center gap-2 font-bold text-sm text-success">
일정 등록 완료
      </div>
      <div className="p-4">
        <div
          className="bg-accent-50 rounded-md p-3.5 cursor-pointer hover:bg-accent-100 transition-colors"
          onClick={() => navigate('/schedules')}
          title="일정 페이지로 이동"
        >
          <div className="text-sm font-semibold text-neutral-main mb-2">{title}</div>
          <div className="text-[0.8125rem] text-neutral-sub leading-[1.8]">{date}<br />{time}</div>
          {synced && (
            <div className="mt-2 text-[0.6875rem] text-success font-medium flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-success" />Google Calendar 동기화됨
            </div>
          )}
          {meetLink && (
            <a
              href={meetLink}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-flex items-center gap-1.5 text-[0.8125rem] text-primary font-medium hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z" />
              </svg>
              Google Meet 참여
            </a>
          )}
          {emailSent && emailCount > 0 && (
            <div className="mt-2 text-[0.6875rem] text-success font-medium flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-success" />{emailCount}명에게 초대 메일 발송됨
            </div>
          )}
          <div className="mt-3 text-[0.75rem] text-primary font-medium flex items-center gap-1">
            일정 페이지에서 확인 →
          </div>
        </div>
      </div>
    </div>
  );
}
