import { useState } from 'react';
import { GOOGLE_SCOPES, GOOGLE_SCOPE_LABELS } from '../../utils/constants';
import useGoogleServices from '../../hooks/useGoogleServices';

import { Calendar, CheckSquare, Mail, BarChart3, CheckCircle, ExternalLink, XCircle, RefreshCw, Trash2 } from 'lucide-react';

const SERVICES = [
  { scope: GOOGLE_SCOPES.CALENDAR, icon: Calendar, desc: '일정을 자동으로 동기화합니다' },
  { scope: GOOGLE_SCOPES.TASKS, icon: CheckSquare, desc: 'Action Item을 할 일로 등록합니다' },
  { scope: GOOGLE_SCOPES.GMAIL_SEND, icon: Mail, desc: '기한 알림 메일을 발송합니다' },
  { scope: GOOGLE_SCOPES.SHEETS, icon: BarChart3, desc: 'Action Item 추적 시트를 생성합니다' },
];

export default function GoogleServicesConnect() {
  const { connected, email, scopes: _scopes, loading, error, connect, disconnect, hasScope } = useGoogleServices();
  const ALL_SCOPES = SERVICES.map((s) => s.scope);
  const [selectedScopes, setSelectedScopes] = useState(ALL_SCOPES);

  const toggleScope = (scope) => {
    setSelectedScopes((prev) =>
      prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]
    );
  };

  const handleConnect = () => {
    if (selectedScopes.length > 0) connect(selectedScopes);
  };

  const missingScopes = ALL_SCOPES.filter((s) => !hasScope(s));

  const handleAddScopes = () => {
    if (missingScopes.length > 0) connect(missingScopes);
  };

  if (connected) {
    return (
      <div className="card mb-3">
        <div className="card-body p-4">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center">
                <CheckCircle className="text-emerald-600" size={16} />
              </div>
              <div>
                <h4 className="text-sm font-bold text-neutral-main">Google 계정 연결됨</h4>
                <p className="text-[10px] text-neutral-muted">{email || '연결 성공'}</p>
              </div>
            </div>
            <button
              onClick={disconnect}
              disabled={loading}
              className="px-3 py-1.5 rounded-lg text-[10px] font-bold text-error border border-error/20 hover:bg-error-bg transition-colors active:scale-95"
            >
              연결 해제
            </button>
          </div>

          <div className="grid grid-cols-2 gap-2">
            {SERVICES.map(({ scope, icon: Icon, desc }) => {
              const active = hasScope(scope);
              return (
                <div
                  key={scope}
                  className={`relative flex flex-col gap-0.5 p-3 rounded-xl border transition-all ${active
                    ? 'border-emerald-200 bg-emerald-50/50'
                    : 'border-neutral-divider bg-neutral-50/50'
                    }`}
                >
                  <div className="flex items-center gap-1.5">
                    <Icon size={13} className={active ? 'text-emerald-600' : 'text-neutral-400'} />
                    <span className={`text-xs font-bold ${active ? 'text-emerald-700' : 'text-neutral-500'}`}>
                      {GOOGLE_SCOPE_LABELS[scope]}
                    </span>
                  </div>
                  <p className="text-[9px] text-neutral-muted leading-tight">{desc}</p>
                  {active && (
                    <div className="absolute top-2 right-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {missingScopes.length > 0 && (
            <button
              onClick={handleAddScopes}
              disabled={loading}
              className="w-full btn-primary mt-6 py-3 rounded-2xl flex items-center justify-center gap-2"
            >
              <ExternalLink size={16} />
              {loading ? '연결 중...' : `추가 기능 연동하기`}
            </button>
          )}
          {error && <p className="text-xs text-error mt-4 font-medium italic">{error}</p>}
        </div>
      </div>
    );
  }

  return (
    <div className="card border-neutral-divider bg-neutral-50/30">
      <div className="card-body p-5 text-center">
        <div className="inline-flex w-10 h-10 rounded-xl bg-primary-100 items-center justify-center mb-4">
          <Calendar className="text-primary-600" size={20} />
        </div>
        <h3 className="text-base font-bold text-neutral-main mb-1">Google 서비스 연결</h3>
        <p className="text-xs text-neutral-muted mb-5 max-w-xs mx-auto">
          캘린더, Tasks 등 다양한 기능을 한 번에 연결하세요.
        </p>

        <div className="grid grid-cols-2 gap-2 mb-5 text-left">
          {SERVICES.map(({ scope, icon: Icon, desc }) => {
            const selected = selectedScopes.includes(scope);
            return (
              <button
                key={scope}
                onClick={() => toggleScope(scope)}
                className={`flex items-start gap-2 p-3 rounded-xl border transition-all ${selected
                  ? 'border-primary-500 bg-white ring-2 ring-primary-100 shadow-soft'
                  : 'border-neutral-divider bg-white/50 hover:bg-white hover:border-primary-300'
                  }`}
              >
                <div className={`mt-0.5 w-6 h-6 rounded-md flex items-center justify-center shrink-0 ${selected ? 'bg-primary-500 text-white' : 'bg-neutral-100 text-neutral-400'}`}>
                  <Icon size={13} />
                </div>
                <div>
                  <div className={`text-xs font-bold ${selected ? 'text-primary-900' : 'text-neutral-700'}`}>{GOOGLE_SCOPE_LABELS[scope]}</div>
                  <div className="text-[9px] text-neutral-muted mt-0.5 leading-snug">{desc}</div>
                </div>
              </button>
            );
          })}
        </div>

        <button
          onClick={handleConnect}
          disabled={loading || selectedScopes.length === 0}
          className="w-full btn-primary py-2.5 rounded-xl font-black text-sm shadow-lg shadow-primary-500/20 active:scale-95 transition-transform"
        >
          {loading ? '연결 중...' : 'Google 계정으로 시작하기'}
        </button>
        {error && <p className="text-xs text-error mt-4 font-medium italic">{error}</p>}
      </div>
    </div>
  );
}
