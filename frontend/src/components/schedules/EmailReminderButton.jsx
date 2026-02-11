import { useState } from 'react';
import { sendReminder, sendBulkReminders } from '../../api/google';
import useGoogleServices from '../../hooks/useGoogleServices';

export default function EmailReminderButton({ actionItemId, recipientEmail, bulk = false, daysBefore = 3 }) {
  const { hasScope } = useGoogleServices();
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState(null);

  if (!hasScope('gmail_send')) return null;

  const handleSend = async () => {
    setSending(true);
    setError(null);
    try {
      if (bulk) {
        await sendBulkReminders(daysBefore);
      } else {
        await sendReminder(actionItemId, recipientEmail);
      }
      setSent(true);
      setTimeout(() => setSent(false), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || '발송 실패');
    } finally {
      setSending(false);
    }
  };

  if (sent) {
    return (
      <span className="inline-flex items-center gap-1 text-[0.6875rem] text-success font-medium">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M20 6L9 17l-5-5"/></svg>
        발송 완료
      </span>
    );
  }

  return (
    <div className="inline-flex flex-col">
      <button
        onClick={handleSend}
        disabled={sending}
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-neutral-border text-[0.6875rem] text-neutral-sub hover:bg-accent-50 hover:text-accent-700 hover:border-accent-300 transition disabled:opacity-50"
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
          <polyline points="22,6 12,13 2,6" />
        </svg>
        {sending ? '발송 중...' : bulk ? '일괄 알림' : '알림 발송'}
      </button>
      {error && <span className="text-[0.625rem] text-error mt-0.5">{error}</span>}
    </div>
  );
}
