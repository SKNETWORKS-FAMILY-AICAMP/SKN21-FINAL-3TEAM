import { useState } from 'react';
import useGoogleServices from '../../hooks/useGoogleServices';

export default function SheetsDashboard() {
  const { sheets, sheetsLoading, sheetsError, hasScope, createSheet, syncSheet } = useGoogleServices();
  const [creating, setCreating] = useState(false);

  if (!hasScope('sheets')) {
    return (
      <div className="card">
        <div className="card-header"><span className="card-title">Google Sheets 추적</span></div>
        <div className="card-body text-center py-8">
          <p className="text-sm text-neutral-muted">Google Sheets가 연결되지 않았습니다</p>
          <p className="text-xs text-neutral-muted mt-1">Google 서비스 연결에서 Sheets를 활성화하세요</p>
        </div>
      </div>
    );
  }

  const handleCreate = async () => {
    setCreating(true);
    try {
      const result = await createSheet('Action Items 추적');
      if (result?.spreadsheet_url) {
        window.open(result.spreadsheet_url, '_blank');
      }
    } catch {
      // error handled in store
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">Google Sheets 추적</span>
        <button
          onClick={handleCreate}
          disabled={creating || sheetsLoading}
          className="text-xs px-2.5 py-1.5 rounded-md border border-neutral-border text-neutral-sub hover:bg-primary-50 hover:text-primary-700 transition"
        >
          {creating ? '생성 중...' : '+ 새 시트'}
        </button>
      </div>
      <div className="card-body">
        {sheetsError && <p className="text-xs text-error mb-3">{sheetsError}</p>}

        {sheets.length === 0 ? (
          <div className="text-center py-6">
            <p className="text-sm text-neutral-muted">생성된 추적 시트가 없습니다</p>
            <p className="text-xs text-neutral-muted mt-1">"새 시트" 버튼으로 Action Item 추적 시트를 만드세요</p>
          </div>
        ) : (
          <ul className="space-y-2">
            {sheets.map((sheet) => (
              <li
                key={sheet.spreadsheet_id || sheet.id}
                className="flex items-center gap-3 px-3 py-3 rounded-md border border-neutral-divider hover:border-primary-300 transition"
              >
                <div className="w-8 h-8 rounded-md bg-success-bg flex items-center justify-center text-success text-sm">
                  📊
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-neutral-main truncate">
                    {sheet.sheet_name || sheet.title || 'Action Items 추적'}
                  </p>
                  {sheet.meeting_title && (
                    <span className="text-[0.6875rem] text-neutral-muted">{sheet.meeting_title}</span>
                  )}
                </div>
                <div className="flex gap-1.5">
                  <button
                    onClick={() => syncSheet(sheet.spreadsheet_id)}
                    className="text-[0.6875rem] px-2 py-1 rounded border border-neutral-divider text-neutral-muted hover:bg-surface-hover transition"
                  >
                    동기화
                  </button>
                  {sheet.spreadsheet_url && (
                    <a
                      href={sheet.spreadsheet_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[0.6875rem] px-2 py-1 rounded border border-primary-300 text-primary-700 bg-primary-50 hover:bg-primary-100 transition"
                    >
                      열기
                    </a>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
