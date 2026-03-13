import { useState, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { FolderOpen, ArrowLeft, Users, Clock, CheckCircle2, Plus, Pencil, Check, X, Trash2, FileSpreadsheet, Search } from 'lucide-react';
import { listPipelineTasks, updatePipelineTask, deletePipelineTask, listProjects, createProject as createProjectApi, updateProject as updateProjectApi, deleteProject as deleteProjectApi } from '../../api/tasks';
import client from '../../api/client';
import { getAllMembers } from '../../api/auth';
import useGoogleServices from '../../hooks/useGoogleServices';
import { toast } from '../../store/toastStore';
import KanbanBoard from './KanbanBoard';

export default function ProjectFolderView({ externalActions, onReady }) {
    const [tasks, setTasks] = useState([]);
    const [dbProjects, setDbProjects] = useState([]);
    const [members, setMembers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedProject, setSelectedProject] = useState(null); // null = folder view
    const [boardActions, setBoardActions] = useState(null);
    const [editingName, setEditingName] = useState(false);
    const [newName, setNewName] = useState('');
    const [renaming, setRenaming] = useState(false);
    const [creatingProject, setCreatingProject] = useState(false);
    const [newProjectName, setNewProjectName] = useState('');
    const [statusFilter, setStatusFilter] = useState('all'); // 'all' | 'in_progress' | 'done'
    const [deleteTarget, setDeleteTarget] = useState(null); // project name to delete
    const [deleting, setDeleting] = useState(false);
    const [exportingProject, setExportingProject] = useState(null);
    const [allMembers, setAllMembers] = useState([]);
    const [selectedMembers, setSelectedMembers] = useState([]);
    const [memberSearch, setMemberSearch] = useState('');
    const [editMembersTarget, setEditMembersTarget] = useState(null); // { name, dbId, members }
    const [editMembers, setEditMembers] = useState([]);
    const [editMemberSearch, setEditMemberSearch] = useState('');
    const [savingMembers, setSavingMembers] = useState(false);
    // Sheets 내보내기 모달
    const [exportTarget, setExportTarget] = useState(null); // project name
    const [exportOpts, setExportOpts] = useState({
        generateWbs: true, generateGantt: false, generateDashboard: false, generateRisk: false, generateReport: false,
    });
    const [exportResult, setExportResult] = useState(null); // { projName, url, tabs }
    const isNavigatingRef = useRef(false);
    const { hasScope, exportProjectToSheet } = useGoogleServices();

    // 프로젝트 선택 시 history에 state push → 브라우저 뒤로가기로 목록 복귀
    const selectProject = useCallback((name) => {
        isNavigatingRef.current = true;
        window.history.pushState({ pipelineProject: name }, '');
        setSelectedProject(name);
    }, []);

    useEffect(() => {
        const handlePopState = (e) => {
            if (selectedProject !== null) {
                // 프로젝트 내부에서 뒤로가기 → 목록으로
                setSelectedProject(null);
            }
        };
        window.addEventListener('popstate', handlePopState);
        return () => window.removeEventListener('popstate', handlePopState);
    }, [selectedProject]);

    const fetchAll = useCallback(async () => {
        setLoading(true);
        // 각각 독립적으로 fetch (하나 실패해도 다른 건 유지)
        try {
            const tasksRes = await listPipelineTasks();
            setTasks(Array.isArray(tasksRes.data) ? tasksRes.data : []);
        } catch {
            setTasks([]);
        }
        try {
            const projRes = await listProjects();
            setDbProjects(Array.isArray(projRes.data) ? projRes.data : []);
        } catch {
            setDbProjects([]);
        }
        setLoading(false);
    }, []);

    useEffect(() => { fetchAll(); }, [fetchAll]);

    const handleRenameProject = async () => {
        const trimmed = newName.trim();
        if (!trimmed || trimmed === selectedProject) {
            setEditingName(false);
            return;
        }
        setRenaming(true);
        try {
            // 최신 태스크를 API에서 다시 가져와서 사용 (stale state 방지)
            const freshRes = await listPipelineTasks();
            const freshTasks = Array.isArray(freshRes.data) ? freshRes.data : [];

            // 현재 프로젝트의 태스크 필터 (미분류: project가 null인 것도 포함)
            const projectTasks = selectedProject === '미분류'
                ? freshTasks.filter(t => !t.project || t.project === '미분류')
                : freshTasks.filter(t => t.project === selectedProject);

            // 태스크의 project 필드 일괄 업데이트
            await Promise.all(projectTasks.map(t =>
                updatePipelineTask(t.id, { project: trimmed })
            ));
            // DB 프로젝트 레코드 이름도 변경
            const dbProj = dbProjects.find(p => p.name === selectedProject);
            if (dbProj) {
                await updateProjectApi(dbProj.id, { name: trimmed });
            }
            await fetchAll();
            selectProject(trimmed);
            setEditingName(false);
        } catch (err) {
            alert('프로젝트 이름 변경 실패');
        } finally {
            setRenaming(false);
        }
    };

    const handleCreateProject = async () => {
        if (!newProjectName.trim()) return;
        try {
            await createProjectApi({
                name: newProjectName.trim(),
                members: selectedMembers.length > 0 ? selectedMembers : undefined,
            });
            await fetchAll();
            selectProject(newProjectName.trim());
            setCreatingProject(false);
            setNewProjectName('');
            setSelectedMembers([]);
            setMemberSearch('');
        } catch (err) {
            alert(err.response?.data?.detail || '프로젝트 생성 실패');
        }
    };

    const toggleMember = (name) => {
        setSelectedMembers(prev =>
            prev.includes(name) ? prev.filter(n => n !== name) : [...prev, name]
        );
    };

    // 현재 로그인 사용자 포함한 전체 선택 가능 멤버
    const availableMembers = (() => {
        // allMembers는 자신을 제외하므로, 자신은 members(team-members)에서 가져옴
        const me = members.find(m => !allMembers.some(a => a.id === m.id));
        const all = me ? [me, ...allMembers] : [...allMembers];
        if (!memberSearch.trim()) return all;
        const q = memberSearch.trim().toLowerCase();
        return all.filter(m => m.name?.toLowerCase().includes(q) || m.email?.toLowerCase().includes(q) || m.team?.toLowerCase().includes(q));
    })();

    const handleExportWithOpts = async () => {
        const projName = exportTarget;
        if (!projName) return;
        setExportTarget(null);
        setExportingProject(projName);
        try {
            const result = await exportProjectToSheet(projName, null, exportOpts);
            const tabs = [
                result?.wbs_generated && 'WBS',
                result?.gantt_generated && 'Gantt',
                result?.dashboard_generated && 'Dashboard',
                result?.risk_generated && 'Risk',
                result?.report_generated && 'Report',
            ].filter(Boolean);
            setExportResult({ projName, url: result?.spreadsheet_url, tabs });
        } catch (err) {
            const detail = err?.response?.data?.detail || err?.message || 'Sheets 내보내기 실패';
            toast.error(detail);
            console.error('Sheets export error:', err?.response?.data || err);
        } finally {
            setExportingProject(null);
        }
    };

    // 멤버 수정 모달용 전체 멤버 (검색 포함)
    const editAvailableMembers = (() => {
        const me = members.find(m => !allMembers.some(a => a.id === m.id));
        const all = me ? [me, ...allMembers] : [...allMembers];
        if (!editMemberSearch.trim()) return all;
        const q = editMemberSearch.trim().toLowerCase();
        return all.filter(m => m.name?.toLowerCase().includes(q) || m.email?.toLowerCase().includes(q) || m.team?.toLowerCase().includes(q));
    })();

    const openEditMembers = (proj) => {
        setEditMembersTarget({ name: proj.name, dbId: proj.dbId, members: proj.members || [] });
        setEditMembers(proj.members?.length > 0 ? [...proj.members] : [...proj.assignees]);
        setEditMemberSearch('');
    };

    const toggleEditMember = (name) => {
        setEditMembers(prev =>
            prev.includes(name) ? prev.filter(n => n !== name) : [...prev, name]
        );
    };

    const handleSaveMembers = async () => {
        if (!editMembersTarget?.dbId) return;
        setSavingMembers(true);
        try {
            await updateProjectApi(editMembersTarget.dbId, { members: editMembers });
            await fetchAll();
            setEditMembersTarget(null);
            toast.success('멤버가 업데이트되었습니다');
        } catch (err) {
            toast.error(err.response?.data?.detail || '멤버 수정 실패');
        } finally {
            setSavingMembers(false);
        }
    };

    const handleDeleteProject = async (projName) => {
        setDeleting(true);
        try {
            // DB 프로젝트 레코드 삭제
            const dbProj = dbProjects.find(p => p.name === projName);
            if (dbProj) {
                await deleteProjectApi(dbProj.id);
            }
            // 해당 프로젝트의 태스크도 삭제
            const projectTasks = tasks.filter(t => t.project === projName);
            await Promise.all(projectTasks.map(t => deletePipelineTask(t.id)));
            setDeleteTarget(null);
            fetchAll();
        } catch (err) {
            alert('프로젝트 삭제 실패');
        } finally {
            setDeleting(false);
        }
    };

    useEffect(() => {
        client.get('/auth/team-members')
            .then(res => setMembers(res.data || []))
            .catch(() => setMembers([]));
        getAllMembers()
            .then(res => setAllMembers(res.data || []))
            .catch(() => setAllMembers([]));
    }, []);

    // Expose actions to parent (SchedulesPage)
    useEffect(() => {
        if (onReady && externalActions) {
            if (selectedProject !== null) {
                // Inside kanban - delegate to kanban actions
                onReady({
                    refresh: () => { fetchAll(); boardActions?.refresh?.(); },
                    openCreate: () => boardActions?.openCreate?.(),
                    loading,
                    goBack: () => window.history.back(),
                    inProject: true,
                });
            } else {
                onReady({
                    refresh: fetchAll,
                    openCreate: null,
                    loading,
                    inProject: false,
                });
            }
        }
    }, [onReady, externalActions, selectedProject, boardActions, loading, fetchAll]);

    // Group tasks by project, including empty DB projects
    const projects = (() => {
        const map = {};
        // DB 프로젝트 먼저 등록 (빈 프로젝트도 표시)
        dbProjects.forEach(p => {
            if (!map[p.name]) map[p.name] = { name: p.name, dbId: p.id, tasks: [], assignees: new Set(), members: p.members || [] };
        });
        // 태스크별 그룹
        tasks.forEach(t => {
            const key = t.project || '미분류';
            if (!map[key]) map[key] = { name: key, tasks: [], assignees: new Set(), members: [] };
            map[key].tasks.push(t);
            if (t.assignee) map[key].assignees.add(t.assignee);
        });
        return Object.values(map).sort((a, b) => {
            if (a.name === '미분류') return 1;
            if (b.name === '미분류') return -1;
            return b.tasks.length - a.tasks.length;
        });
    })();

    const getProgress = (projectTasks) => {
        if (projectTasks.length === 0) return 0;
        const done = projectTasks.filter(t => t.stage === 'done').length;
        return Math.round((done / projectTasks.length) * 100);
    };

    const getLatestDue = (projectTasks) => {
        const dues = projectTasks.map(t => t.dueDate).filter(Boolean).sort();
        return dues.length > 0 ? dues[dues.length - 1] : null;
    };

    const getAvatarSrc = (name) => {
        const m = members.find(m => m.name === name);
        return m?.avatar || `https://api.dicebear.com/7.x/notionists/svg?seed=${encodeURIComponent(name)}`;
    };

    const getDday = (dateStr) => {
        if (!dateStr) return null;
        const diff = Math.ceil((new Date(dateStr) - new Date()) / 86400000);
        if (diff < 0) return { text: `${Math.abs(diff)}일 초과`, cls: 'text-red-500' };
        if (diff === 0) return { text: 'D-Day', cls: 'text-orange-500' };
        if (diff <= 3) return { text: `D-${diff}`, cls: 'text-orange-500' };
        return { text: `D-${diff}`, cls: 'text-neutral-muted' };
    };

    const progressColors = ['bg-emerald-400', 'bg-blue-400', 'bg-amber-400', 'bg-rose-400', 'bg-cyan-400', 'bg-violet-400'];

    // Filter projects by status
    const filteredProjects = projects.filter(proj => {
        const progress = getProgress(proj.tasks);
        if (statusFilter === 'done') return progress === 100 && proj.tasks.length > 0;
        if (statusFilter === 'in_progress') return progress < 100 || proj.tasks.length === 0;
        return true;
    });

    const statusCounts = {
        all: projects.length,
        in_progress: projects.filter(p => getProgress(p.tasks) < 100 || p.tasks.length === 0).length,
        done: projects.filter(p => getProgress(p.tasks) === 100 && p.tasks.length > 0).length,
    };

    if (loading) {
        return <div className="flex items-center justify-center h-64 text-neutral-sub">프로젝트 로딩 중...</div>;
    }

    // Inside a project → show KanbanBoard
    if (selectedProject !== null) {
        return (
            <>
            <div className="space-y-4">
                <button
                    onClick={() => window.history.back()}
                    className="flex items-center gap-2 text-sm font-bold text-neutral-sub hover:text-primary-600 transition-colors"
                >
                    <ArrowLeft size={16} />
                    프로젝트 목록으로
                </button>
                <div className="flex items-center gap-3 mb-2">
                    <FolderOpen size={22} className="text-primary-500" />
                    {editingName ? (
                        <div className="flex items-center gap-2">
                            <input
                                autoFocus
                                value={newName}
                                onChange={e => setNewName(e.target.value)}
                                onKeyDown={e => { if (e.key === 'Enter') handleRenameProject(); if (e.key === 'Escape') setEditingName(false); }}
                                className="text-xl font-black text-neutral-main tracking-tight bg-transparent border-b-2 border-primary-400 outline-none px-1 py-0.5 w-64"
                                disabled={renaming}
                            />
                            <button
                                onClick={handleRenameProject}
                                disabled={renaming}
                                className="p-1.5 rounded-lg bg-primary-50 hover:bg-primary-100 text-primary-600 transition-colors disabled:opacity-50"
                                title="확인"
                            >
                                <Check size={16} />
                            </button>
                            <button
                                onClick={() => setEditingName(false)}
                                className="p-1.5 rounded-lg hover:bg-neutral-100 text-neutral-400 transition-colors"
                                title="취소"
                            >
                                <X size={16} />
                            </button>
                        </div>
                    ) : (
                        <div className="flex items-center gap-2 group/name">
                            <h2 className="text-xl font-black text-neutral-main tracking-tight">{selectedProject}</h2>
                            <button
                                onClick={() => { setNewName(selectedProject === '미분류' ? '' : selectedProject); setEditingName(true); }}
                                className="opacity-0 group-hover/name:opacity-100 p-1.5 rounded-lg hover:bg-neutral-100 dark:hover:bg-white/10 text-neutral-400 hover:text-primary-500 transition-all"
                                title="프로젝트 이름 수정"
                            >
                                <Pencil size={14} />
                            </button>
                            {hasScope('sheets') && (
                                <button
                                    onClick={() => setExportTarget(selectedProject)}
                                    disabled={!!exportingProject}
                                    className="opacity-0 group-hover/name:opacity-100 p-1.5 rounded-lg hover:bg-green-50 dark:hover:bg-green-900/20 text-neutral-400 hover:text-green-600 transition-all disabled:opacity-50"
                                    title="Sheets로 내보내기"
                                >
                                    <FileSpreadsheet size={14} className={exportingProject ? 'animate-pulse' : ''} />
                                </button>
                            )}
                        </div>
                    )}
                </div>
                <KanbanBoard
                    key={selectedProject}
                    externalActions={externalActions}
                    onReady={setBoardActions}
                    filterProject={selectedProject}
                    projectMembers={(() => {
                        const proj = projects.find(p => p.name === selectedProject);
                        if (!proj) return [];
                        // DB members가 있으면 그것, 없으면 태스크 assignee 목록으로 fallback
                        return proj.members.length > 0 ? proj.members : [...proj.assignees];
                    })()}
                />
            </div>

            {/* Exporting 로딩 오버레이 */}
            {exportingProject && createPortal(
                <div className="fixed inset-0 z-[115] flex items-center justify-center">
                    <div className="absolute inset-0 bg-neutral-900/30 backdrop-blur-sm" />
                    <motion.div
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="relative bg-white/90 dark:bg-neutral-900/90 backdrop-blur-xl rounded-[2rem] shadow-2xl p-8 border border-white/40 dark:border-white/10 flex flex-col items-center"
                    >
                        <div className="w-12 h-12 border-4 border-green-200 border-t-green-500 rounded-full animate-spin mb-4" />
                        <p className="text-sm font-bold text-neutral-main">Sheets로 내보내는 중...</p>
                        <p className="text-xs text-neutral-muted mt-1">"{exportingProject}"</p>
                    </motion.div>
                </div>,
                document.body
            )}

            {/* Export success modal */}
            {exportResult && createPortal(
                <div className="fixed inset-0 z-[120] flex items-center justify-center p-4">
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="absolute inset-0 bg-neutral-900/40 backdrop-blur-sm"
                        onClick={() => setExportResult(null)}
                    />
                    <motion.div
                        initial={{ opacity: 0, scale: 0.9, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        className="relative bg-white/90 dark:bg-neutral-900/90 backdrop-blur-xl rounded-[2rem] shadow-2xl w-full max-w-[380px] p-8 mx-4 border border-white/40 dark:border-white/10"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="flex flex-col items-center text-center">
                            <div className="w-16 h-16 rounded-full bg-green-50 dark:bg-green-900/20 flex items-center justify-center mb-4">
                                <CheckCircle2 size={32} className="text-green-500" />
                            </div>
                            <h3 className="text-lg font-black text-neutral-900 dark:text-white tracking-tight mb-1">내보내기 완료!</h3>
                            <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-2">
                                <span className="font-bold text-neutral-700 dark:text-neutral-200">"{exportResult.projName}"</span>
                            </p>
                            {exportResult.tabs.length > 0 && (
                                <div className="flex flex-wrap justify-center gap-1.5 mb-4">
                                    {exportResult.tabs.map(tab => (
                                        <span key={tab} className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300">
                                            {tab}
                                        </span>
                                    ))}
                                </div>
                            )}
                            <p className="text-xs text-neutral-muted mb-5">Sheets 탭에서 미리보기할 수 있습니다</p>
                            <div className="flex gap-3 w-full">
                                <button
                                    onClick={() => setExportResult(null)}
                                    className="flex-1 px-4 py-3 text-sm font-extrabold rounded-xl bg-neutral-200 dark:bg-neutral-700 text-neutral-800 dark:text-neutral-100 hover:bg-neutral-300 dark:hover:bg-neutral-600 transition-colors"
                                >
                                    닫기
                                </button>
                                {exportResult.url && (
                                    <a
                                        href={exportResult.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        onClick={() => setExportResult(null)}
                                        className="flex-1 px-4 py-3 text-sm font-extrabold rounded-xl bg-green-600 text-white hover:bg-green-700 shadow-lg transition-colors text-center"
                                    >
                                        Sheets에서 열기
                                    </a>
                                )}
                            </div>
                        </div>
                    </motion.div>
                </div>,
                document.body
            )}

            {/* Export options modal */}
            {exportTarget && createPortal(
                <div className="fixed inset-0 z-[120] flex items-center justify-center p-4">
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="absolute inset-0 bg-neutral-900/40 backdrop-blur-sm" onClick={() => setExportTarget(null)} />
                    <motion.div initial={{ opacity: 0, scale: 0.95, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }} className="relative bg-white/90 dark:bg-neutral-900/90 backdrop-blur-xl rounded-[2rem] shadow-2xl w-full max-w-[380px] p-8 mx-4 border border-white/40 dark:border-white/10" onClick={(e) => e.stopPropagation()}>
                        <div className="flex flex-col items-center text-center">
                            <div className="w-14 h-14 rounded-full bg-green-50 dark:bg-green-900/20 flex items-center justify-center mb-4">
                                <FileSpreadsheet size={24} className="text-green-600" />
                            </div>
                            <h3 className="text-lg font-black text-neutral-900 dark:text-white tracking-tight mb-1">Sheets 내보내기</h3>
                            <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-4">
                                <span className="font-bold text-neutral-700 dark:text-neutral-200">"{exportTarget}"</span>
                            </p>
                            <div className="w-full space-y-2 mb-5 text-left">
                                {[
                                    { key: 'generateWbs', label: 'WBS (작업 분해 구조)', desc: 'AI가 태스크를 계층별로 자동 정리' },
                                    { key: 'generateGantt', label: 'Gantt 차트', desc: '태스크+일정을 시간축 막대로 시각화' },
                                    { key: 'generateDashboard', label: '통합 대시보드', desc: '진행률/우선순위/담당자 현황 종합' },
                                    { key: 'generateRisk', label: 'AI 리스크 분석', desc: 'AI가 프로젝트 리스크를 자동 분석' },
                                    { key: 'generateReport', label: 'AI 주간 보고서', desc: 'AI가 주간 진행 상황 보고서 생성' },
                                ].map(({ key, label, desc }) => (
                                    <label key={key} className="flex items-start gap-3 p-2.5 rounded-xl hover:bg-neutral-50 dark:hover:bg-white/5 cursor-pointer transition-colors">
                                        <input type="checkbox" checked={exportOpts[key]} onChange={() => setExportOpts(prev => ({ ...prev, [key]: !prev[key] }))} className="mt-0.5 w-4 h-4 rounded accent-green-600" />
                                        <div><div className="text-sm font-bold text-neutral-main">{label}</div><div className="text-[11px] text-neutral-muted">{desc}</div></div>
                                    </label>
                                ))}
                            </div>
                            <div className="flex gap-3 w-full">
                                <button onClick={() => setExportTarget(null)} className="flex-1 px-4 py-3 text-sm font-extrabold rounded-xl bg-neutral-200 dark:bg-neutral-700 text-neutral-800 dark:text-neutral-100 hover:bg-neutral-300 dark:hover:bg-neutral-600 transition-colors">취소</button>
                                <button onClick={handleExportWithOpts} className="flex-1 px-4 py-3 text-sm font-extrabold rounded-xl bg-green-600 text-white hover:bg-green-700 shadow-lg transition-colors">내보내기</button>
                            </div>
                        </div>
                    </motion.div>
                </div>,
                document.body
            )}
            </>
        );
    }

    // Folder view
    return (
        <div className="space-y-6">
            {/* Section header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <h2 className="text-lg font-black text-neutral-main tracking-tight">Projects</h2>
                    <span className="text-xs font-bold text-neutral-muted bg-neutral-100 dark:bg-neutral-800 px-2.5 py-1 rounded-full">
                        {projects.length} Projects
                    </span>
                </div>
                {/* Status filter */}
                <div className="flex gap-1">
                    {[
                        { key: 'all', label: '전체' },
                        { key: 'in_progress', label: '진행중' },
                        { key: 'done', label: '완료' },
                    ].map(({ key, label }) => (
                        <button
                            key={key}
                            onClick={() => setStatusFilter(key)}
                            className={`px-3 py-1.5 rounded-full text-xs font-bold transition-all ${
                                statusFilter === key
                                    ? 'bg-primary-700 text-white shadow-sm'
                                    : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-muted hover:bg-neutral-200 dark:hover:bg-neutral-700'
                            }`}
                        >
                            {label} <span className="ml-0.5 opacity-70">{statusCounts[key]}</span>
                        </button>
                    ))}
                </div>
            </div>

            {filteredProjects.length === 0 && !creatingProject && !selectedProject ? (
                <div className="flex flex-col items-center justify-center h-52 text-neutral-muted">
                    <FolderOpen size={36} className="mb-3 opacity-30" />
                    <p className="text-sm font-medium">아직 프로젝트가 없습니다</p>
                    <p className="text-xs mt-1 mb-4">회의록에서 액션아이템을 Pipeline에 추가하거나 직접 프로젝트를 생성하세요</p>
                    <button
                        onClick={() => setCreatingProject(true)}
                        className="px-4 py-2 text-sm font-bold rounded-xl bg-primary-600 text-white hover:bg-primary-700 transition-colors flex items-center gap-2"
                    >
                        <Plus size={16} /> 새 프로젝트
                    </button>
                </div>
            ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                    <AnimatePresence mode="popLayout">
                        {filteredProjects.map((proj, idx) => {
                            const progress = getProgress(proj.tasks);
                            const latestDue = getLatestDue(proj.tasks);
                            const dday = getDday(latestDue);
                            const assignees = proj.members.length > 0 ? proj.members : [...proj.assignees];
                            const pColor = progressColors[idx % progressColors.length];

                            return (
                                <motion.div
                                    key={proj.name}
                                    layout
                                    initial={{ opacity: 0, y: 16 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0, scale: 0.95 }}
                                    transition={{ duration: 0.25, delay: idx * 0.04 }}
                                    onClick={() => selectProject(proj.name)}
                                    className="relative bg-white/40 dark:bg-white/5 backdrop-blur-xl pt-8 pb-5 px-5 rounded-3xl border border-neutral-200/60 dark:border-white/10 shadow-sm cursor-pointer hover:shadow-lg hover:-translate-y-1 transition-all duration-300 group flex flex-col items-center text-center"
                                >
                                    {/* Action buttons */}
                                    <div className="absolute top-3 right-3 flex gap-1 opacity-0 group-hover:opacity-100 transition-all">
                                        {proj.tasks.length > 0 && (
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    if (!hasScope('sheets')) {
                                                        toast.error('Google Sheets를 먼저 연결하세요');
                                                        return;
                                                    }
                                                    setExportTarget(proj.name);
                                                }}
                                                disabled={exportingProject === proj.name}
                                                className="p-1.5 rounded-lg hover:bg-green-50 dark:hover:bg-green-900/20 text-neutral-300 hover:text-green-600 transition-all"
                                                title="Sheets로 내보내기"
                                            >
                                                <FileSpreadsheet size={14} className={exportingProject === proj.name ? 'animate-pulse' : ''} />
                                            </button>
                                        )}
                                        <button
                                            onClick={(e) => { e.stopPropagation(); openEditMembers(proj); }}
                                            className="p-1.5 rounded-lg hover:bg-blue-50 dark:hover:bg-blue-900/20 text-neutral-300 hover:text-blue-500 transition-all"
                                            title="멤버 수정"
                                        >
                                            <Users size={14} />
                                        </button>
                                        <button
                                            onClick={(e) => { e.stopPropagation(); setDeleteTarget(proj.name); }}
                                            className="p-1.5 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 text-neutral-300 hover:text-red-500 transition-all"
                                            title="프로젝트 삭제"
                                        >
                                            <Trash2 size={14} />
                                        </button>
                                    </div>

                                    {/* Centered avatars at top */}
                                    <div className="flex items-center justify-center mb-3">
                                        {assignees.length > 0 ? (
                                            <div className="flex items-center -space-x-2">
                                                {assignees.map((name, ai) => (
                                                    <img
                                                        key={ai}
                                                        src={getAvatarSrc(name)}
                                                        alt={name}
                                                        title={name}
                                                        className="w-10 h-10 rounded-full border-2 border-white dark:border-neutral-800 shadow-md object-cover bg-surface-card"
                                                        style={{ zIndex: assignees.length - ai }}
                                                    />
                                                ))}
                                            </div>
                                        ) : (
                                            <div className="w-10 h-10 rounded-full border-2 border-white dark:border-neutral-700 shadow-md bg-neutral-100 dark:bg-neutral-700 flex items-center justify-center">
                                                <FolderOpen size={16} className="text-neutral-400" />
                                            </div>
                                        )}
                                    </div>

                                    {/* Project name */}
                                    <h3 className="font-bold text-[15px] text-neutral-main leading-snug mb-0.5 line-clamp-1 w-full">{proj.name}</h3>
                                    <p className="text-[11px] text-neutral-muted mb-4 line-clamp-1">
                                        {assignees.length > 0
                                            ? assignees.join(', ')
                                            : '참여자 없음'}
                                    </p>

                                    {/* Progress bar */}
                                    <div className="w-full mb-3">
                                        <div className="flex items-center justify-between text-[10px] font-bold mb-1.5">
                                            <span className="text-neutral-sub">진행률</span>
                                            <span className="text-neutral-main">{progress}%</span>
                                        </div>
                                        <div className="w-full h-2 bg-neutral-200 dark:bg-white/15 rounded-full overflow-hidden">
                                            <div className={`h-full ${pColor} rounded-full transition-all duration-700`} style={{ width: `${progress}%` }} />
                                        </div>
                                    </div>

                                    {/* Bottom: tasks count + D-day */}
                                    <div className="flex items-center justify-between w-full">
                                        <span className="text-[10px] font-bold text-neutral-muted">
                                            {proj.tasks.length} tasks
                                        </span>
                                        {dday && (
                                            <span className={`text-[10px] font-bold ${dday.cls}`}>
                                                {dday.text}
                                            </span>
                                        )}
                                    </div>

                                    {/* Colored dot indicators */}
                                    <div className="flex items-center gap-1 mt-2.5">
                                        {proj.tasks.filter(t => t.stage === 'done').length > 0 && <span className="w-2 h-2 rounded-full bg-emerald-400" title="Done" />}
                                        {proj.tasks.filter(t => t.stage === 'in_progress').length > 0 && <span className="w-2 h-2 rounded-full bg-primary-400" title="In Progress" />}
                                        {proj.tasks.filter(t => t.stage === 'review').length > 0 && <span className="w-2 h-2 rounded-full bg-amber-400" title="Review" />}
                                        {proj.tasks.filter(t => t.stage === 'todo').length > 0 && <span className="w-2 h-2 rounded-full bg-neutral-300" title="To Do" />}
                                    </div>
                                </motion.div>
                            );
                        })}
                    </AnimatePresence>

                    {/* 새 프로젝트 카드 */}
                    {creatingProject ? (
                        <motion.div
                            initial={{ opacity: 0, y: 16 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="bg-white/40 dark:bg-white/5 backdrop-blur-xl p-5 rounded-3xl border-2 border-dashed border-primary-300 dark:border-primary-700 shadow-sm flex flex-col justify-center col-span-1 sm:col-span-2"
                        >
                            <span className="text-sm font-bold text-neutral-main mb-3">새 프로젝트</span>
                            <input
                                autoFocus
                                value={newProjectName}
                                onChange={e => setNewProjectName(e.target.value)}
                                onKeyDown={e => {
                                    if (e.key === 'Enter' && newProjectName.trim()) handleCreateProject();
                                    if (e.key === 'Escape') { setCreatingProject(false); setNewProjectName(''); setSelectedMembers([]); }
                                }}
                                placeholder="프로젝트 이름 입력..."
                                className="w-full px-3 py-2 text-sm border border-neutral-border rounded-xl bg-white/80 dark:bg-neutral-800 text-neutral-main outline-none focus:ring-2 focus:ring-primary-400 mb-3"
                            />

                            {/* 멤버 선택 */}
                            <div className="mb-3">
                                <label className="block text-[10px] font-black uppercase tracking-wider text-neutral-400 mb-1.5 ml-1">
                                    멤버 선택 {selectedMembers.length > 0 && <span className="text-primary-500">({selectedMembers.length}명)</span>}
                                </label>
                                {/* 선택된 멤버 칩 */}
                                {selectedMembers.length > 0 && (
                                    <div className="flex flex-wrap gap-1 mb-2">
                                        {selectedMembers.map(name => (
                                            <span
                                                key={name}
                                                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300"
                                            >
                                                {name}
                                                <button type="button" onClick={() => toggleMember(name)} className="hover:text-red-500">
                                                    <X size={10} />
                                                </button>
                                            </span>
                                        ))}
                                    </div>
                                )}
                                {/* 검색 */}
                                <div className="relative mb-2">
                                    <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-400" />
                                    <input
                                        value={memberSearch}
                                        onChange={e => setMemberSearch(e.target.value)}
                                        placeholder="이름 또는 팀으로 검색..."
                                        className="w-full pl-8 pr-3 py-1.5 text-xs border border-neutral-border rounded-lg bg-white/80 dark:bg-neutral-800 text-neutral-main outline-none focus:ring-1 focus:ring-primary-400"
                                    />
                                </div>
                                {/* 멤버 목록 */}
                                <div className="max-h-36 overflow-y-auto space-y-0.5 rounded-lg border border-neutral-border bg-white/50 dark:bg-neutral-800/50 p-1">
                                    {availableMembers.map(m => {
                                        const selected = selectedMembers.includes(m.name);
                                        const avatarSrc = m.avatar || `https://api.dicebear.com/7.x/notionists/svg?seed=${encodeURIComponent(m.name)}`;
                                        return (
                                            <button
                                                key={m.id}
                                                type="button"
                                                onClick={() => toggleMember(m.name)}
                                                className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs transition-all ${
                                                    selected
                                                        ? 'bg-primary-50 dark:bg-primary-900/20 border border-primary-300'
                                                        : 'hover:bg-neutral-100 dark:hover:bg-neutral-700 border border-transparent'
                                                }`}
                                            >
                                                <img src={avatarSrc} alt={m.name} className="w-5 h-5 rounded-full bg-white/50" />
                                                <span className={`font-bold ${selected ? 'text-primary-700 dark:text-primary-300' : 'text-neutral-main'}`}>{m.name}</span>
                                                {m.team && <span className="text-[10px] text-neutral-muted ml-auto">{m.team}</span>}
                                                {selected && <Check size={12} className="text-primary-500 ml-1" />}
                                            </button>
                                        );
                                    })}
                                    {availableMembers.length === 0 && (
                                        <p className="text-[11px] text-neutral-muted text-center py-2">검색 결과 없음</p>
                                    )}
                                </div>
                            </div>

                            <div className="flex items-center gap-2">
                                <button onClick={handleCreateProject} disabled={!newProjectName.trim()}
                                    className="flex-1 px-4 py-3 text-sm font-extrabold rounded-xl bg-primary-900 text-white hover:bg-neutral-main shadow-lg transition-colors disabled:opacity-50">
                                    생성
                                </button>
                                <button onClick={() => { setCreatingProject(false); setNewProjectName(''); setSelectedMembers([]); setMemberSearch(''); }}
                                    className="flex-1 px-4 py-3 text-sm font-extrabold rounded-xl bg-neutral-200 dark:bg-neutral-700 text-neutral-800 dark:text-neutral-100 hover:bg-neutral-300 dark:hover:bg-neutral-600 transition-colors">
                                    취소
                                </button>
                            </div>
                        </motion.div>
                    ) : (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            onClick={() => setCreatingProject(true)}
                            className="bg-white/20 dark:bg-white/5 backdrop-blur-xl p-5 rounded-3xl border-2 border-dashed border-neutral-300/60 dark:border-neutral-700 cursor-pointer hover:border-primary-400 hover:bg-white/40 dark:hover:bg-white/10 hover:-translate-y-1 transition-all duration-300 flex flex-col items-center justify-center min-h-[200px] group"
                        >
                            <div className="w-12 h-12 rounded-full bg-neutral-100/80 dark:bg-white/10 group-hover:bg-primary-50 dark:group-hover:bg-primary-900/20 flex items-center justify-center transition-colors mb-2.5">
                                <Plus size={20} className="text-neutral-400 group-hover:text-primary-500 transition-colors" />
                            </div>
                            <span className="text-xs font-bold text-neutral-400 group-hover:text-primary-600 transition-colors">새 프로젝트</span>
                        </motion.div>
                    )}
                </div>
            )}

            {/* Delete confirmation modal */}
            {deleteTarget && createPortal(
                <div className="fixed inset-0 z-[120] flex items-center justify-center p-4">
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="absolute inset-0 bg-neutral-900/40 backdrop-blur-sm"
                        onClick={() => !deleting && setDeleteTarget(null)}
                    />
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95, y: 20 }}
                        className="relative bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-[2rem] shadow-2xl w-full max-w-[380px] p-8 mx-4 border border-white/40 dark:border-white/10"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="flex flex-col items-center text-center">
                            <div className="w-14 h-14 rounded-full bg-red-50 dark:bg-red-900/20 flex items-center justify-center mb-4">
                                <Trash2 size={24} className="text-red-500" />
                            </div>
                            <h3 className="text-lg font-black text-neutral-900 dark:text-white tracking-tight mb-2">프로젝트 삭제</h3>
                            <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-1">
                                <span className="font-bold text-neutral-700 dark:text-neutral-200">"{deleteTarget}"</span>
                            </p>
                            <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-6">
                                프로젝트와 모든 태스크가 삭제됩니다.<br />이 작업은 되돌릴 수 없습니다.
                            </p>
                            <div className="flex gap-3 w-full">
                                <button
                                    onClick={() => setDeleteTarget(null)}
                                    disabled={deleting}
                                    className="flex-1 px-4 py-3 text-sm font-extrabold rounded-xl bg-neutral-200 dark:bg-neutral-700 text-neutral-800 dark:text-neutral-100 hover:bg-neutral-300 dark:hover:bg-neutral-600 transition-colors"
                                >
                                    취소
                                </button>
                                <button
                                    onClick={() => handleDeleteProject(deleteTarget)}
                                    disabled={deleting}
                                    className="flex-1 px-4 py-3 text-sm font-extrabold rounded-xl bg-red-500 text-white hover:bg-red-600 shadow-lg transition-colors disabled:opacity-50"
                                >
                                    {deleting ? '삭제 중...' : '삭제'}
                                </button>
                            </div>
                        </div>
                    </motion.div>
                </div>,
                document.body
            )}

            {/* Edit members modal */}
            {editMembersTarget && createPortal(
                <div className="fixed inset-0 z-[120] flex items-center justify-center p-4">
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="absolute inset-0 bg-neutral-900/40 backdrop-blur-sm"
                        onClick={() => !savingMembers && setEditMembersTarget(null)}
                    />
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95, y: 20 }}
                        className="relative bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-[2rem] shadow-2xl w-full max-w-[420px] mx-4 border border-white/40 dark:border-white/10 max-h-[85vh] flex flex-col"
                        onClick={(e) => e.stopPropagation()}
                    >
                        {/* Header */}
                        <div className="flex items-center justify-between px-6 pt-6 pb-3 flex-shrink-0">
                            <div>
                                <h3 className="text-lg font-black text-neutral-900 dark:text-white tracking-tight">멤버 수정</h3>
                                <p className="text-xs text-neutral-muted mt-0.5">{editMembersTarget.name}</p>
                            </div>
                            <button
                                onClick={() => setEditMembersTarget(null)}
                                className="w-7 h-7 rounded-lg hover:bg-neutral-100 dark:hover:bg-white/5 text-neutral-400 transition-colors flex items-center justify-center"
                            >
                                <X size={18} />
                            </button>
                        </div>

                        {/* Content */}
                        <div className="flex-1 min-h-0 overflow-y-auto px-6 pb-6">
                            {/* Selected members chips */}
                            {editMembers.length > 0 && (
                                <div className="flex flex-wrap gap-1.5 mb-3">
                                    {editMembers.map(name => (
                                        <span
                                            key={name}
                                            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300"
                                        >
                                            <img src={getAvatarSrc(name)} alt={name} className="w-4 h-4 rounded-full" />
                                            {name}
                                            <button type="button" onClick={() => toggleEditMember(name)} className="hover:text-red-500 transition-colors">
                                                <X size={10} />
                                            </button>
                                        </span>
                                    ))}
                                </div>
                            )}

                            {/* Search */}
                            <div className="relative mb-2">
                                <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-400" />
                                <input
                                    value={editMemberSearch}
                                    onChange={e => setEditMemberSearch(e.target.value)}
                                    placeholder="이름 또는 팀으로 검색..."
                                    className="w-full pl-8 pr-3 py-2 text-xs border border-neutral-border rounded-xl bg-white/80 dark:bg-neutral-800 text-neutral-main outline-none focus:ring-2 focus:ring-primary-400"
                                    autoFocus
                                />
                            </div>

                            {/* Member list */}
                            <div className="max-h-56 overflow-y-auto space-y-0.5 rounded-xl border border-neutral-border bg-white/50 dark:bg-neutral-800/50 p-1.5">
                                {editAvailableMembers.map(m => {
                                    const selected = editMembers.includes(m.name);
                                    const avatarSrc = m.avatar || `https://api.dicebear.com/7.x/notionists/svg?seed=${encodeURIComponent(m.name)}`;
                                    return (
                                        <button
                                            key={m.id}
                                            type="button"
                                            onClick={() => toggleEditMember(m.name)}
                                            className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs transition-all ${
                                                selected
                                                    ? 'bg-primary-50 dark:bg-primary-900/20 border border-primary-300'
                                                    : 'hover:bg-neutral-100 dark:hover:bg-neutral-700 border border-transparent'
                                            }`}
                                        >
                                            <img src={avatarSrc} alt={m.name} className="w-6 h-6 rounded-full bg-white/50" />
                                            <span className={`font-bold ${selected ? 'text-primary-700 dark:text-primary-300' : 'text-neutral-main'}`}>{m.name}</span>
                                            {m.team && <span className="text-[10px] text-neutral-muted ml-auto">{m.team}</span>}
                                            {selected && <Check size={14} className="text-primary-500 ml-1" />}
                                        </button>
                                    );
                                })}
                                {editAvailableMembers.length === 0 && (
                                    <p className="text-[11px] text-neutral-muted text-center py-3">검색 결과 없음</p>
                                )}
                            </div>

                            {/* Action buttons */}
                            <div className="flex gap-3 mt-4">
                                <button
                                    onClick={() => setEditMembersTarget(null)}
                                    disabled={savingMembers}
                                    className="flex-1 px-4 py-3 text-sm font-extrabold rounded-xl bg-neutral-200 dark:bg-neutral-700 text-neutral-800 dark:text-neutral-100 hover:bg-neutral-300 dark:hover:bg-neutral-600 transition-colors"
                                >
                                    취소
                                </button>
                                <button
                                    onClick={handleSaveMembers}
                                    disabled={savingMembers}
                                    className="flex-1 px-4 py-3 text-sm font-extrabold rounded-xl bg-primary-700 text-white hover:bg-primary-900 shadow-lg transition-colors disabled:opacity-50"
                                >
                                    {savingMembers ? '저장 중...' : `저장 (${editMembers.length}명)`}
                                </button>
                            </div>
                        </div>
                    </motion.div>
                </div>,
                document.body
            )}

            {/* Sheets export options modal */}
            {exportTarget && createPortal(
                <div className="fixed inset-0 z-[120] flex items-center justify-center p-4">
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="absolute inset-0 bg-neutral-900/40 backdrop-blur-sm"
                        onClick={() => setExportTarget(null)}
                    />
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95, y: 20 }}
                        className="relative bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-[2rem] shadow-2xl w-full max-w-[400px] p-8 mx-4 border border-white/40 dark:border-white/10"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="flex flex-col items-center text-center">
                            <div className="w-14 h-14 rounded-full bg-green-50 dark:bg-green-900/20 flex items-center justify-center mb-4">
                                <FileSpreadsheet size={24} className="text-green-600" />
                            </div>
                            <h3 className="text-lg font-black text-neutral-900 dark:text-white tracking-tight mb-1">Sheets 내보내기</h3>
                            <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-5">
                                <span className="font-bold text-neutral-700 dark:text-neutral-200">"{exportTarget}"</span>
                            </p>

                            {/* Checkbox options */}
                            <div className="w-full space-y-2 mb-6">
                                {[
                                    { key: 'generateWbs', label: 'WBS', desc: '작업 분해 구조 (AI가 태스크를 계층별로 정리)' },
                                    { key: 'generateGantt', label: 'Gantt', desc: '간트 차트 (태스크+일정을 시간축 막대로 시각화)' },
                                    { key: 'generateDashboard', label: 'Dashboard', desc: '진행 현황 (상태/담당자/결재 통계 집계)' },
                                    { key: 'generateRisk', label: 'AI 리스크', desc: 'AI 리스크 분석 (일정충돌, 병목, 과부하 등 식별)' },
                                    { key: 'generateReport', label: '주간보고', desc: 'AI 주간 보고서 (완료/진행중/예정/블로커 정리)' },
                                ].map(({ key, label, desc }) => (
                                    <label
                                        key={key}
                                        className={`flex items-start gap-3 px-4 py-3 rounded-xl border cursor-pointer transition-all ${
                                            exportOpts[key]
                                                ? 'border-primary-300 bg-primary-50/50 dark:bg-primary-900/10'
                                                : 'border-neutral-200 dark:border-neutral-700 hover:border-neutral-300 dark:hover:border-neutral-600'
                                        }`}
                                    >
                                        <input
                                            type="checkbox"
                                            checked={exportOpts[key]}
                                            onChange={(e) => setExportOpts(prev => ({ ...prev, [key]: e.target.checked }))}
                                            className="w-4 h-4 mt-0.5 rounded border-neutral-300 text-primary-600 focus:ring-primary-500"
                                        />
                                        <div className="text-left">
                                            <span className="text-sm font-bold text-neutral-main">{label}</span>
                                            <p className="text-[11px] text-neutral-muted leading-snug mt-0.5">{desc}</p>
                                        </div>
                                    </label>
                                ))}
                            </div>

                            <div className="flex gap-3 w-full">
                                <button
                                    onClick={() => setExportTarget(null)}
                                    className="flex-1 px-4 py-3 text-sm font-extrabold rounded-xl bg-neutral-200 dark:bg-neutral-700 text-neutral-800 dark:text-neutral-100 hover:bg-neutral-300 dark:hover:bg-neutral-600 transition-colors"
                                >
                                    취소
                                </button>
                                <button
                                    onClick={handleExportWithOpts}
                                    className="flex-1 px-4 py-3 text-sm font-extrabold rounded-xl bg-green-600 text-white hover:bg-green-700 shadow-lg transition-colors flex items-center justify-center gap-2"
                                >
                                    <FileSpreadsheet size={16} />
                                    내보내기
                                </button>
                            </div>
                        </div>
                    </motion.div>
                </div>,
                document.body
            )}

            {/* Export success modal */}
            {exportResult && createPortal(
                <div className="fixed inset-0 z-[120] flex items-center justify-center p-4">
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="absolute inset-0 bg-neutral-900/40 backdrop-blur-sm"
                        onClick={() => setExportResult(null)}
                    />
                    <motion.div
                        initial={{ opacity: 0, scale: 0.9, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        className="relative bg-white/90 dark:bg-neutral-900/90 backdrop-blur-xl rounded-[2rem] shadow-2xl w-full max-w-[380px] p-8 mx-4 border border-white/40 dark:border-white/10"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="flex flex-col items-center text-center">
                            <div className="w-16 h-16 rounded-full bg-green-50 dark:bg-green-900/20 flex items-center justify-center mb-4">
                                <CheckCircle2 size={32} className="text-green-500" />
                            </div>
                            <h3 className="text-lg font-black text-neutral-900 dark:text-white tracking-tight mb-1">내보내기 완료!</h3>
                            <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-2">
                                <span className="font-bold text-neutral-700 dark:text-neutral-200">"{exportResult.projName}"</span>
                            </p>
                            {exportResult.tabs.length > 0 && (
                                <div className="flex flex-wrap justify-center gap-1.5 mb-4">
                                    {exportResult.tabs.map(tab => (
                                        <span key={tab} className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300">
                                            {tab}
                                        </span>
                                    ))}
                                </div>
                            )}
                            <p className="text-xs text-neutral-muted mb-5">Sheets 탭에서 미리보기할 수 있습니다</p>
                            <div className="flex gap-3 w-full">
                                <button
                                    onClick={() => setExportResult(null)}
                                    className="flex-1 px-4 py-3 text-sm font-extrabold rounded-xl bg-neutral-200 dark:bg-neutral-700 text-neutral-800 dark:text-neutral-100 hover:bg-neutral-300 dark:hover:bg-neutral-600 transition-colors"
                                >
                                    닫기
                                </button>
                                {exportResult.url && (
                                    <a
                                        href={exportResult.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        onClick={() => setExportResult(null)}
                                        className="flex-1 px-4 py-3 text-sm font-extrabold rounded-xl bg-green-600 text-white hover:bg-green-700 shadow-lg transition-colors text-center"
                                    >
                                        Sheets에서 열기
                                    </a>
                                )}
                            </div>
                        </div>
                    </motion.div>
                </div>,
                document.body
            )}
        </div>
    );
}
