import { useState } from 'react';
import { GOOGLE_SCOPES, GOOGLE_SCOPE_LABELS } from '../../utils/constants';
import useGoogleServices from '../../hooks/useGoogleServices';

const SERVICES = [
  { scope: GOOGLE_SCOPES.CALENDAR, icon: '📅', desc: '일정을 자동으로 동기화합니다' },
  { scope: GOOGLE_SCOPES.TASKS, icon: '✅', desc: 'Action Item을 할 일로 등록합니다' },
  { scope: GOOGLE_SCOPES.GMAIL_SEND, icon: '📧', desc: '기한 알림 메일을 발송합니다' },
  { scope: GOOGLE_SCOPES.SHEETS, icon: '📊', desc: 'Action Item 추적 시트를 생성합니다' },
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
      <div className="card mb-5">
        <div className="card-header">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-success" />
            <span className="text-sm font-semibold text-success">Google 서비스 연결됨</span>
            {email && <span className="text-xs text-neutral-muted ml-1">{email}</span>}
          </div>
          <button onClick={disconnect} disabled={loading} className="text-xs text-neutral-muted hover:text-error transition">
            연결 해제
          </button>
        </div>
        <div className="card-body">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {SERVICES.map(({ scope, icon }) => {
              const active = hasScope(scope);
              return (
                <div
                  key={scope}
                  className={`flex items-center gap-2 px-3 py-2 rounded-md border text-sm ${
                    active
                      ? 'border-primary-300 bg-primary-50 text-primary-700'
                      : 'border-neutral-divider bg-surface-hover text-neutral-muted'
                  }`}
                >
                  <span>{icon}</span>
                  <span className="font-medium">{GOOGLE_SCOPE_LABELS[scope]}</span>
                  {active && <span className="ml-auto text-[0.625rem] text-success font-semibold">ON</span>}
                </div>
              );
            })}
          </div>
          {missingScopes.length > 0 && (
            <button
              onClick={handleAddScopes}
              disabled={loading}
              className="btn-primary mt-3 text-sm"
            >
              {loading ? '연결 중...' : `나머지 서비스 추가 연결 (${missingScopes.map((s) => GOOGLE_SCOPE_LABELS[s]).join(', ')})`}
            </button>
          )}
          {error && <p className="text-xs text-error mt-3">{error}</p>}
        </div>
      </div>
    );
  }

  return (
    <div className="card mb-5">
      <div className="card-header">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-neutral-muted" />
          <span className="text-sm font-semibold text-neutral-sub">Google 서비스 미연결</span>
        </div>
      </div>
      <div className="card-body">
        <p className="text-xs text-neutral-muted mb-3">연결할 서비스를 선택하세요</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
          {SERVICES.map(({ scope, icon, desc }) => {
            const selected = selectedScopes.includes(scope);
            return (
              <button
                key={scope}
                onClick={() => toggleScope(scope)}
                className={`flex flex-col items-start gap-1 px-3 py-3 rounded-md border text-left transition ${
                  selected
                    ? 'border-primary-500 bg-primary-50 text-primary-700'
                    : 'border-neutral-divider bg-surface-card text-neutral-sub hover:border-primary-300'
                }`}
              >
                <div className="flex items-center gap-2 text-sm font-medium">
                  <span>{icon}</span>
                  {GOOGLE_SCOPE_LABELS[scope]}
                </div>
                <span className="text-[0.6875rem] text-neutral-muted">{desc}</span>
              </button>
            );
          })}
        </div>
        <button
          onClick={handleConnect}
          disabled={loading || selectedScopes.length === 0}
          className="btn-primary"
        >
          {loading ? '연결 중...' : 'Google 계정 연결하기'}
        </button>
        {error && <p className="text-xs text-error mt-3">{error}</p>}
      </div>
    </div>
  );
}
