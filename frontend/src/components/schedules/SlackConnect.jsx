import { useEffect } from 'react';
import { Hash, CheckCircle } from 'lucide-react';
import useSlackStore from '../../store/slackStore';
import { toast } from '../../store/toastStore';

export default function SlackConnect() {
  const { connected, loading, fetchStatus, connect, disconnect } = useSlackStore();

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const handleToggle = async () => {
    if (connected) {
      const ok = await disconnect();
      if (ok) toast.info('Slack 알림이 비활성화되었습니다.');
      else toast.error('처리에 실패했습니다. 다시 시도해주세요.');
    } else {
      const ok = await connect();
      if (ok) toast.success('Slack 알림이 활성화되었습니다.');
      else toast.error('활성화에 실패했습니다. 관리자에게 문의하세요.');
    }
  };

  return (
    <div className="card p-5 mb-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-[#4A154B] flex items-center justify-center">
            <Hash size={16} className="text-white" />
          </div>
          <div>
            <div className="text-sm font-bold text-neutral-main flex items-center gap-2">
              Slack 알림
              {connected && <CheckCircle size={13} className="text-success" />}
            </div>
            <div className="text-xs text-neutral-muted">
              {connected ? '일정 등록 시 채널로 알림이 전송됩니다' : '활성화하면 일정 등록 시 Slack 채널로 알림을 보냅니다'}
            </div>
          </div>
        </div>
        <button
          onClick={handleToggle}
          disabled={loading}
          className={`relative w-11 h-6 rounded-full transition-colors duration-200 outline-none disabled:opacity-50 ${connected ? 'bg-primary-700' : 'bg-[#b0b0b0] dark:bg-neutral-500'}`}
        >
          <div className={`absolute top-1 left-1 w-4 h-4 rounded-full shadow-sm transition-transform duration-200 ${connected ? 'bg-white translate-x-5' : 'bg-white translate-x-0'}`} />
        </button>
      </div>
    </div>
  );
}
