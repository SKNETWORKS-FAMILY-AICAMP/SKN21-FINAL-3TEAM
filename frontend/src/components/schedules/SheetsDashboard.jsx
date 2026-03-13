import { useState, useEffect } from 'react';
import { BarChart3, RefreshCw, FolderOpen, Eye, EyeOff } from 'lucide-react';
import useGoogleServices from '../../hooks/useGoogleServices';
import { listProjects, listPipelineTasks } from '../../api/tasks';
import { confirm, toast } from '../../store/toastStore';
import SheetPreview from './SheetPreview';

export default function SheetsDashboard({ externalActions, onReady }) {
  const { sheets, sheetsLoading, sheetsError, hasScope, exportProjectToSheet, syncSheet, deleteSheet } = useGoogleServices();
  const [tasks, setTasks] = useState([]);
  const [dbProjects, setDbProjects] = useState([]);
  const [exporting, setExporting] = useState(null);
  const [syncingId, setSyncingId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [generateWbs, setGenerateWbs] = useState(true);
  const [generateGantt, setGenerateGantt] = useState(false);
  const [generateDashboard, setGenerateDashboard] = useState(false);
  const [generateRisk, setGenerateRisk] = useState(false);
  const [generateReport, setGenerateReport] = useState(false);
  const [previewId, setPreviewId] = useState(null); // 미리보기 중인 spreadsheet_id

  useEffect(() => {
    listProjects().then(res => setDbProjects(Array.isArray(res.data) ? res.data : [])).catch(() => {});
    listPipelineTasks().then(res => setTasks(Array.isArray(res.data) ? res.data : [])).catch(() => {});
  }, []);

  // Pipeline 탭과 동일한 방식으로 프로젝트 목록 생성 (DB + 태스크 그룹핑)
  const projects = (() => {
    const map = {};
    dbProjects.forEach(p => {
      if (!map[p.name]) map[p.name] = { id: p.id, name: p.name, tasks: [] };
    });
    tasks.forEach(t => {
      const key = t.project || '미분류';
      if (!map[key]) map[key] = { id: key, name: key, tasks: [] };
      map[key].tasks.push(t);
    });
    return Object.values(map).filter(p => p.name !== '미분류').sort((a, b) => b.tasks.length - a.tasks.length);
  })();

  const handleExport = async (projectName) => {
    setExporting(projectName);
    try {
      const result = await exportProjectToSheet(projectName, null, {
        generateWbs,
        generateGantt,
        generateDashboard,
        generateRisk,
        generateReport,
      });
      if (result?.spreadsheet_url) {
        window.open(result.spreadsheet_url, '_blank');
      }
      const tabs = [
        result?.wbs_generated && 'WBS',
        result?.gantt_generated && 'Gantt',
        result?.dashboard_generated && 'Dashboard',
        result?.risk_generated && 'Risk',
        result?.report_generated && 'Report',
      ].filter(Boolean);
      const tabsMsg = tabs.length > 0 ? ` (${tabs.join(', ')} 포함)` : '';
      toast.success(`"${projectName}" 프로젝트가 Sheets로 내보내기 되었습니다.${tabsMsg}`);
    } catch {
      toast.error('Sheets 내보내기에 실패했습니다.');
    } finally {
      setExporting(null);
    }
  };

  const handleSync = async (sheet) => {
    if (!sheet.project_name) return;
    setSyncingId(sheet.spreadsheet_id);
    try {
      await syncSheet(sheet.spreadsheet_id, sheet.project_name);
      toast.success('시트가 동기화되었습니다.');
    } catch {
      toast.error('동기화에 실패했습니다.');
    } finally {
      setSyncingId(null);
    }
  };

  const handleDelete = async (spreadsheetId) => {
    if (!await confirm('이 시트를 삭제하시겠습니까?')) return;
    setDeletingId(spreadsheetId);
    try {
      await deleteSheet(spreadsheetId);
      if (previewId === spreadsheetId) setPreviewId(null);
      toast.success('시트가 삭제되었습니다.');
    } catch {
      toast.error('시트 삭제에 실패했습니다.');
    } finally {
      setDeletingId(null);
    }
  };

  const togglePreview = (spreadsheetId) => {
    setPreviewId(prev => prev === spreadsheetId ? null : spreadsheetId);
  };

  const refreshAll = () => {
    listProjects().then(res => setDbProjects(Array.isArray(res.data) ? res.data : [])).catch(() => {});
    listPipelineTasks().then(res => setTasks(Array.isArray(res.data) ? res.data : [])).catch(() => {});
  };

  useEffect(() => {
    if (externalActions && onReady) {
      onReady({ refresh: refreshAll, exporting, sheetsLoading });
    }
  }, [externalActions, onReady, exporting, sheetsLoading]);

  // 이미 내보낸 프로젝트인지 확인
  const isExported = (projectName) => sheets.some(s => s.project_name === projectName);

  const sheetsConnected = hasScope('sheets');

  return (
    <div className="space-y-6">
      {/* Google Sheets 미연결 안내 */}
      {!sheetsConnected && (
        <div className="p-4 bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800 rounded-lg">
          <p className="text-sm font-medium text-amber-800 dark:text-amber-200">Google Sheets가 연결되지 않았습니다</p>
          <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">내보내기를 사용하려면 Google 서비스 연결에서 Sheets를 활성화하세요</p>
        </div>
      )}

      {/* 프로젝트 내보내기 */}
      <div className="card">
        <div className="card-header flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="card-title">프로젝트 → Sheets 내보내기</span>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {[
              { label: 'WBS', state: generateWbs, setter: setGenerateWbs, desc: '작업 분해 구조 (AI가 태스크를 계층별로 정리)' },
              { label: 'Gantt', state: generateGantt, setter: setGenerateGantt, desc: '간트 차트 (태스크+일정을 시간축 막대로 시각화)' },
              { label: 'Dashboard', state: generateDashboard, setter: setGenerateDashboard, desc: '진행 현황 (상태/담당자/결재 통계 집계)' },
              { label: 'AI 리스크', state: generateRisk, setter: setGenerateRisk, desc: 'AI 리스크 분석 (일정충돌, 병목, 과부하 등 식별)' },
              { label: '주간보고', state: generateReport, setter: setGenerateReport, desc: 'AI 주간 보고서 (완료/진행중/예정/블로커 정리)' },
            ].map(({ label, state, setter, desc }) => (
              <label key={label} className="flex items-center gap-1.5 cursor-pointer group relative">
                <input
                  type="checkbox"
                  checked={state}
                  onChange={(e) => setter(e.target.checked)}
                  className="w-3.5 h-3.5 rounded border-neutral-300 text-primary-600 focus:ring-primary-500"
                />
                <span className="text-xs text-neutral-muted font-medium">{label}</span>
                <span className="absolute left-0 top-full mt-1 z-20 hidden group-hover:block w-48 px-2.5 py-1.5 text-[11px] text-white bg-neutral-800 dark:bg-neutral-700 rounded-md shadow-lg whitespace-normal leading-snug pointer-events-none">
                  {desc}
                </span>
              </label>
            ))}
          </div>
        </div>
        <div className="card-body">
          {projects.length === 0 ? (
            <div className="text-center py-6">
              <FolderOpen size={28} className="mx-auto mb-2 text-neutral-300" />
              <p className="text-sm text-neutral-muted">프로젝트가 없습니다</p>
              <p className="text-xs text-neutral-muted mt-1">Pipeline 탭에서 프로젝트를 먼저 생성하세요</p>
            </div>
          ) : (
            <ul className="space-y-2">
              {projects.map((proj) => {
                const exported = isExported(proj.name);
                return (
                  <li
                    key={proj.id || proj.name}
                    className="flex items-center gap-3 px-3 py-3 rounded-md border border-neutral-divider hover:border-primary-300 transition"
                  >
                    <div className="w-8 h-8 rounded-md bg-primary-50 dark:bg-primary-900/20 flex items-center justify-center text-primary-600">
                      <FolderOpen size={16} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-neutral-main truncate">{proj.name}</p>
                      <span className="text-[0.6875rem] text-neutral-muted">{proj.tasks.length}개 태스크</span>
                    </div>
                    <button
                      onClick={() => {
                        if (!sheetsConnected) {
                          toast.error('Google Sheets를 먼저 연결하세요');
                          return;
                        }
                        handleExport(proj.name);
                      }}
                      disabled={exporting === proj.name || proj.tasks.length === 0}
                      className={`text-[0.6875rem] px-3 py-1.5 rounded font-bold transition ${
                        exported
                          ? 'border border-success text-success hover:bg-green-50'
                          : 'border border-primary-300 text-primary-700 bg-primary-50 hover:bg-primary-100'
                      } disabled:opacity-50`}
                    >
                      {exporting === proj.name ? '내보내는 중...' : exported ? '다시 내보내기' : 'Sheets로 내보내기'}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>

      {/* 내보낸 시트 목록 */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">내보낸 시트 목록</span>
        </div>
        <div className="card-body">
          {sheetsError && <p className="text-xs text-error mb-3">{sheetsError}</p>}

          {sheets.length === 0 ? (
            <div className="text-center py-6">
              <p className="text-sm text-neutral-muted">내보낸 시트가 없습니다</p>
              <p className="text-xs text-neutral-muted mt-1">위에서 프로젝트를 Sheets로 내보내세요</p>
            </div>
          ) : (
            <ul className="space-y-2">
              {sheets.map((sheet) => (
                <li key={sheet.spreadsheet_id || sheet.id}>
                  <div className="flex items-center gap-3 px-3 py-3 rounded-md border border-neutral-divider hover:border-primary-300 transition">
                    <div className="w-8 h-8 rounded-md bg-success-bg flex items-center justify-center text-success">
                      <BarChart3 size={16} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-neutral-main truncate">
                        {sheet.sheet_name || '프로젝트 문서'}
                      </p>
                      {sheet.project_name && (
                        <span className="text-[0.6875rem] text-neutral-muted">프로젝트: {sheet.project_name}</span>
                      )}
                    </div>
                    <div className="flex gap-1.5">
                      <button
                        onClick={() => togglePreview(sheet.spreadsheet_id)}
                        className={`text-[0.6875rem] px-2 py-1 rounded border transition flex items-center gap-1 ${
                          previewId === sheet.spreadsheet_id
                            ? 'border-primary-400 text-primary-700 bg-primary-50'
                            : 'border-neutral-divider text-neutral-muted hover:bg-surface-hover'
                        }`}
                      >
                        {previewId === sheet.spreadsheet_id ? <EyeOff size={12} /> : <Eye size={12} />}
                        미리보기
                      </button>
                      <button
                        onClick={() => handleSync(sheet)}
                        disabled={syncingId === sheet.spreadsheet_id}
                        className="text-[0.6875rem] px-2 py-1 rounded border border-neutral-divider text-neutral-muted hover:bg-surface-hover transition flex items-center gap-1"
                      >
                        <RefreshCw size={12} className={syncingId === sheet.spreadsheet_id ? 'animate-spin' : ''} />
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
                      <button
                        onClick={() => handleDelete(sheet.spreadsheet_id)}
                        disabled={deletingId === sheet.spreadsheet_id}
                        className="text-[0.6875rem] px-2 py-1 rounded border border-error text-error hover:bg-red-50 transition disabled:opacity-50"
                      >
                        {deletingId === sheet.spreadsheet_id ? '삭제 중...' : '삭제'}
                      </button>
                    </div>
                  </div>
                  {/* 미리보기 패널 */}
                  {previewId === sheet.spreadsheet_id && (
                    <SheetPreview
                      spreadsheetId={sheet.spreadsheet_id}
                      onClose={() => setPreviewId(null)}
                    />
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
