import { useRef, useCallback, useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { createPipelineFromActionItems, listProjects, createProject } from '../../api/tasks';
import { createTask as createGoogleTask } from '../../api/google';

export default function MeetingPreview({ data, onDownload, loading }) {
  const printRef = useRef(null);
  const [pipelineSent, setPipelineSent] = useState(false);
  const [pipelineLoading, setPipelineLoading] = useState(false);
  const [googleTasksSent, setGoogleTasksSent] = useState(false);
  const [googleTasksLoading, setGoogleTasksLoading] = useState(false);

  // 프로젝트 선택 모달
  const [showProjectModal, setShowProjectModal] = useState(false);
  const [projects, setProjects] = useState([]);
  const [projectsLoading, setProjectsLoading] = useState(false);
  const [selectedProjectName, setSelectedProjectName] = useState('');
  const [newProjectMode, setNewProjectMode] = useState(false);
  const [newProjectInput, setNewProjectInput] = useState('');

  // Google Tasks 액션아이템 선택 모달
  const [showGoogleTasksModal, setShowGoogleTasksModal] = useState(false);
  const [selectedActionItems, setSelectedActionItems] = useState([]);

  // Pipeline 액션아이템 선택
  const [pipelineSelectedItems, setPipelineSelectedItems] = useState([]);

  const fetchProjects = async () => {
    setProjectsLoading(true);
    try {
      const res = await listProjects();
      setProjects(Array.isArray(res.data) ? res.data : []);
    } catch {
      setProjects([]);
    } finally {
      setProjectsLoading(false);
    }
  };

  const handleOpenProjectModal = () => {
    setSelectedProjectName(data?.title || '');
    setNewProjectMode(false);
    setNewProjectInput('');
    setPipelineSelectedItems(data.actionItems.map((_, i) => i)); // 기본 전체 선택
    setShowProjectModal(true);
    fetchProjects();
  };

  const handleConfirmProject = async () => {
    const projectName = newProjectMode ? newProjectInput.trim() : selectedProjectName;
    if (!projectName) return;

    setPipelineLoading(true);
    setShowProjectModal(false);
    try {
      // 새 프로젝트인 경우 먼저 생성
      if (newProjectMode && newProjectInput.trim()) {
        try {
          await createProject({ name: newProjectInput.trim() });
        } catch {
          // 이미 존재하면 무시
        }
      }
      const itemsToAdd = pipelineSelectedItems.map(i => data.actionItems[i]);
      await createPipelineFromActionItems(itemsToAdd, projectName);
      setPipelineSent(true);
    } catch (err) {
      alert(err.response?.data?.detail || 'Pipeline 추가 실패');
    } finally {
      setPipelineLoading(false);
    }
  };

  const handlePrint = useCallback(() => {
    if (!printRef.current) return;
    printRef.current.classList.add('print-area');
    window.print();
    const cleanup = () => {
      printRef.current?.classList.remove('print-area');
      window.removeEventListener('afterprint', cleanup);
    };
    window.addEventListener('afterprint', cleanup);
  }, []);

  if (!data) return null;

  return (
    <div className="card" ref={printRef}>
      <div className="card-header no-print">
        <div className="card-title">생성된 회의록</div>
        <div className="flex gap-2">
          <button onClick={handlePrint} className="btn-outline text-xs">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="inline mr-1">
              <polyline points="6 9 6 2 18 2 18 9" />
              <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" />
              <rect x="6" y="14" width="12" height="8" />
            </svg>
            인쇄
          </button>
          <button onClick={() => onDownload?.('docx')} disabled={loading} className="btn-primary text-xs disabled:opacity-50">
            DOCX 다운로드
          </button>
        </div>
      </div>
      <div ref={printRef} className="card-body">
        {/* 회의 정보 */}
        <div className="flex flex-wrap gap-4 text-xs text-neutral-sub mb-4 pb-4 border-b border-neutral-divider">
          {data.title && <span className="font-semibold text-neutral-main">{data.title}</span>}
          {data.date && <span>{data.date}</span>}
          {data.attendees?.length > 0 && <span>{data.attendees.join(', ')}</span>}
        </div>

        {/* 요약 */}
        {data.summary && (
          <div className="mb-4">
            <h4 className="text-[0.8125rem] font-bold text-neutral-main mb-2">요약</h4>
            <p className="text-sm text-neutral-main leading-relaxed whitespace-pre-wrap bg-surface-hover rounded-sm p-3">
              {data.summary}
            </p>
          </div>
        )}

        {/* 결정사항 */}
        {data.decisions?.length > 0 && (
          <div className="mb-4">
            <h4 className="text-[0.8125rem] font-bold text-neutral-main mb-2">결정사항 ({data.decisions.length}건)</h4>
            <div className="space-y-1.5">
              {data.decisions.map((d, i) => (
                <div key={i} className="flex items-start gap-2 text-sm text-neutral-main">
                  <span className="text-success flex-shrink-0">✓</span>
                  <span className="leading-relaxed">{d}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Action Items */}
        {data.actionItems?.length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-[0.8125rem] font-bold text-neutral-main">Action Items ({data.actionItems.length}건)</h4>
              <div className="flex gap-2 no-print">
                <button
                  onClick={handleOpenProjectModal}
                  disabled={pipelineSent || pipelineLoading}
                  className="px-3 py-1.5 text-xs font-semibold rounded-lg border border-primary-300 text-primary-600 hover:bg-primary-50 transition-colors disabled:opacity-50"
                >
                  {pipelineLoading ? '추가 중...' : pipelineSent ? '✓ Pipeline 추가됨' : 'Pipeline에 추가'}
                </button>
                <button
                  onClick={() => {
                    setSelectedActionItems(data.actionItems.map((_, i) => i)); // 기본 전체 선택
                    setShowGoogleTasksModal(true);
                  }}
                  disabled={googleTasksSent || googleTasksLoading}
                  className="px-3 py-1.5 text-xs font-semibold rounded-lg border border-emerald-300 text-emerald-600 hover:bg-emerald-50 transition-colors disabled:opacity-50"
                >
                  {googleTasksLoading ? '추가 중...' : googleTasksSent ? '✓ Tasks 추가됨' : 'Google Tasks에 추가'}
                </button>
              </div>
            </div>
            <div className="space-y-2">
              {data.actionItems.map((item, i) => (
                <div key={i} className="flex items-start gap-2 px-3 py-2.5 bg-surface-hover rounded-sm text-sm">
                  <span className="flex-shrink-0">☐</span>
                  <div className="flex-1">
                    <span className="text-neutral-main">{item.task}</span>
                    <div className="flex gap-3 mt-1 text-xs text-neutral-muted">
                      {item.assignee && <span>{item.assignee}</span>}
                      {item.due_date && <span>{item.due_date}</span>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 프로젝트 선택 모달 */}
      {showProjectModal && createPortal(
        <div className="fixed inset-0 z-[120] flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-neutral-900/40 backdrop-blur-sm"
            onClick={() => setShowProjectModal(false)}
          />
          <div
            className="relative bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-2xl shadow-2xl w-full max-w-sm p-6 border border-white/40 dark:border-white/10"
            onClick={e => e.stopPropagation()}
          >
            <h3 className="text-base font-bold text-neutral-main mb-1">프로젝트 선택</h3>
            <p className="text-xs text-neutral-muted mb-3">
              추가할 액션아이템을 선택하세요.
            </p>

            {/* 액션아이템 선택 */}
            <div className="space-y-1.5 max-h-[160px] overflow-y-auto mb-4 border border-neutral-200 dark:border-neutral-700 rounded-xl p-2.5">
              {data.actionItems.map((item, i) => (
                <label key={i} className="flex items-start gap-2.5 cursor-pointer p-1.5 rounded-lg hover:bg-surface-hover transition-colors">
                  <input
                    type="checkbox"
                    checked={pipelineSelectedItems.includes(i)}
                    onChange={() => {
                      setPipelineSelectedItems(prev =>
                        prev.includes(i) ? prev.filter(x => x !== i) : [...prev, i]
                      );
                    }}
                    className="mt-0.5 w-4 h-4 rounded accent-primary-700"
                  />
                  <div className="flex-1 min-w-0">
                    <span className="text-sm text-neutral-main block truncate">{item.task}</span>
                    <div className="flex gap-2 text-[10px] text-neutral-muted">
                      {item.assignee && <span>{item.assignee}</span>}
                      {item.due_date && <span>{item.due_date}</span>}
                    </div>
                  </div>
                </label>
              ))}
            </div>

            <p className="text-xs text-neutral-muted mb-4">
              {pipelineSelectedItems.length}건 선택됨 — 어떤 프로젝트에 추가할까요?
            </p>

            {projectsLoading ? (
              <div className="text-center text-sm text-neutral-muted py-6">로딩 중...</div>
            ) : (
              <div className="space-y-2 max-h-[240px] overflow-y-auto mb-4">
                {/* 회의 제목으로 자동 제안 */}
                {data.title && !projects.some(p => p.name === data.title) && (
                  <button
                    onClick={() => { setSelectedProjectName(data.title); setNewProjectMode(false); }}
                    className={`w-full text-left px-3 py-2.5 rounded-xl border text-sm transition-all ${
                      !newProjectMode && selectedProjectName === data.title
                        ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20 text-primary-700 font-semibold'
                        : 'border-neutral-200 dark:border-neutral-700 hover:border-primary-300 text-neutral-main'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-xs bg-primary-100 text-primary-600 dark:bg-primary-900/30 dark:text-primary-400 px-1.5 py-0.5 rounded font-bold">NEW</span>
                      <span className="truncate">{data.title}</span>
                    </div>
                    <span className="text-[10px] text-neutral-muted mt-0.5 block">회의 제목으로 새 프로젝트 생성</span>
                  </button>
                )}

                {/* 기존 프로젝트 목록 */}
                {projects.map(proj => (
                  <button
                    key={proj.id}
                    onClick={() => { setSelectedProjectName(proj.name); setNewProjectMode(false); }}
                    className={`w-full text-left px-3 py-2.5 rounded-xl border text-sm transition-all ${
                      !newProjectMode && selectedProjectName === proj.name
                        ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20 text-primary-700 font-semibold'
                        : 'border-neutral-200 dark:border-neutral-700 hover:border-primary-300 text-neutral-main'
                    }`}
                  >
                    <span className="truncate block">{proj.name}</span>
                  </button>
                ))}

                {projects.length === 0 && !data.title && (
                  <p className="text-xs text-neutral-muted text-center py-3">기존 프로젝트가 없습니다</p>
                )}
              </div>
            )}

            {/* 새 프로젝트 직접 입력 */}
            <div className="border-t border-neutral-100 dark:border-neutral-800 pt-3 mb-4">
              {newProjectMode ? (
                <div className="flex items-center gap-2">
                  <input
                    autoFocus
                    value={newProjectInput}
                    onChange={e => setNewProjectInput(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter' && newProjectInput.trim()) handleConfirmProject(); }}
                    placeholder="새 프로젝트 이름..."
                    className="flex-1 px-3 py-2 text-sm border border-neutral-border rounded-lg outline-none focus:ring-2 focus:ring-primary-400 bg-white dark:bg-neutral-800 text-neutral-main"
                  />
                  <button
                    onClick={() => { setNewProjectMode(false); setNewProjectInput(''); }}
                    className="text-xs text-neutral-400 hover:text-neutral-600 px-2 py-2"
                  >
                    취소
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => { setNewProjectMode(true); setSelectedProjectName(''); }}
                  className="w-full text-left px-3 py-2.5 rounded-xl border-2 border-dashed border-neutral-300 dark:border-neutral-600 text-sm text-neutral-400 hover:text-primary-500 hover:border-primary-300 transition-colors"
                >
                  + 새 프로젝트 이름 직접 입력
                </button>
              )}
            </div>

            {/* 확인 / 취소 */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowProjectModal(false)}
                className="px-5 py-3 text-sm font-extrabold rounded-xl text-neutral-600 dark:text-neutral-300 hover:text-neutral-800 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
              >
                취소
              </button>
              <button
                onClick={handleConfirmProject}
                disabled={pipelineSelectedItems.length === 0 || (newProjectMode ? !newProjectInput.trim() : !selectedProjectName)}
                className="flex-1 px-5 py-3 text-sm font-extrabold rounded-xl bg-primary-900 text-white hover:bg-neutral-main shadow-lg transition-colors disabled:opacity-60"
              >
                {pipelineSelectedItems.length}건 Pipeline에 추가
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
      {/* Google Tasks 액션아이템 선택 모달 */}
      {showGoogleTasksModal && createPortal(
        <div className="fixed inset-0 z-[120] flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-neutral-900/40 backdrop-blur-sm"
            onClick={() => setShowGoogleTasksModal(false)}
          />
          <div
            className="relative bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-2xl shadow-2xl w-full max-w-sm p-6 border border-white/40 dark:border-white/10"
            onClick={e => e.stopPropagation()}
          >
            <h3 className="text-base font-bold text-neutral-main mb-1">Google Tasks에 추가</h3>
            <p className="text-xs text-neutral-muted mb-3">
              추가할 액션아이템을 선택하세요.
            </p>

            <div className="space-y-1.5 max-h-[280px] overflow-y-auto mb-4 border border-neutral-200 dark:border-neutral-700 rounded-xl p-2.5">
              {data.actionItems.map((item, i) => (
                <label key={i} className="flex items-start gap-2.5 cursor-pointer p-1.5 rounded-lg hover:bg-surface-hover transition-colors">
                  <input
                    type="checkbox"
                    checked={selectedActionItems.includes(i)}
                    onChange={() => {
                      setSelectedActionItems(prev =>
                        prev.includes(i) ? prev.filter(x => x !== i) : [...prev, i]
                      );
                    }}
                    className="mt-0.5 w-4 h-4 rounded accent-emerald-600"
                  />
                  <div className="flex-1 min-w-0">
                    <span className="text-sm text-neutral-main block truncate">{item.task}</span>
                    <div className="flex gap-2 text-[10px] text-neutral-muted">
                      {item.assignee && <span>{item.assignee}</span>}
                      {item.due_date && <span>{item.due_date}</span>}
                    </div>
                  </div>
                </label>
              ))}
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowGoogleTasksModal(false)}
                className="px-5 py-3 text-sm font-extrabold rounded-xl text-neutral-600 dark:text-neutral-300 hover:text-neutral-800 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
              >
                취소
              </button>
              <button
                onClick={async () => {
                  setShowGoogleTasksModal(false);
                  setGoogleTasksLoading(true);
                  try {
                    for (const idx of selectedActionItems) {
                      const item = data.actionItems[idx];
                      await createGoogleTask({
                        title: item.task,
                        assignee: item.assignee || null,
                        due_date: item.due_date || null,
                        priority: 'medium',
                      });
                    }
                    setGoogleTasksSent(true);
                  } catch (err) {
                    alert(err.response?.data?.detail || 'Google Tasks 추가 실패');
                  } finally {
                    setGoogleTasksLoading(false);
                  }
                }}
                disabled={selectedActionItems.length === 0}
                className="flex-1 px-5 py-3 text-sm font-extrabold rounded-xl bg-primary-900 text-white hover:bg-neutral-main shadow-lg transition-colors disabled:opacity-60"
              >
                {selectedActionItems.length}건 Tasks에 추가
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
