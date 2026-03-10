import { useState, useEffect, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { FolderOpen, ArrowLeft, Users, Clock, CheckCircle2, Plus, Pencil, Check, X, Trash2 } from 'lucide-react';
import { listPipelineTasks, updatePipelineTask, deletePipelineTask, listProjects, createProject as createProjectApi, updateProject as updateProjectApi, deleteProject as deleteProjectApi } from '../../api/tasks';
import client from '../../api/client';
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
    const isNavigatingRef = useRef(false);

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
            await createProjectApi({ name: newProjectName.trim() });
            await fetchAll();
            selectProject(newProjectName.trim());
            setCreatingProject(false);
            setNewProjectName('');
        } catch (err) {
            alert(err.response?.data?.detail || '프로젝트 생성 실패');
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
            if (!map[p.name]) map[p.name] = { name: p.name, dbId: p.id, tasks: [], assignees: new Set() };
        });
        // 태스크별 그룹
        tasks.forEach(t => {
            const key = t.project || '미분류';
            if (!map[key]) map[key] = { name: key, tasks: [], assignees: new Set() };
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
                        </div>
                    )}
                </div>
                <KanbanBoard
                    key={selectedProject}
                    externalActions={externalActions}
                    onReady={setBoardActions}
                    filterProject={selectedProject}
                />
            </div>
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
                            const assignees = [...proj.assignees];
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
                                    {/* Delete button */}
                                    <button
                                        onClick={(e) => { e.stopPropagation(); setDeleteTarget(proj.name); }}
                                        className="absolute top-3 right-3 p-1.5 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-red-50 dark:hover:bg-red-900/20 text-neutral-300 hover:text-red-500 transition-all"
                                        title="프로젝트 삭제"
                                    >
                                        <Trash2 size={14} />
                                    </button>

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
                            className="bg-white/40 dark:bg-white/5 backdrop-blur-xl p-5 rounded-3xl border-2 border-dashed border-primary-300 dark:border-primary-700 shadow-sm flex flex-col justify-center"
                        >
                            <span className="text-sm font-bold text-neutral-main mb-3">새 프로젝트</span>
                            <input
                                autoFocus
                                value={newProjectName}
                                onChange={e => setNewProjectName(e.target.value)}
                                onKeyDown={e => {
                                    if (e.key === 'Enter') handleCreateProject();
                                    if (e.key === 'Escape') { setCreatingProject(false); setNewProjectName(''); }
                                }}
                                placeholder="프로젝트 이름 입력..."
                                className="w-full px-3 py-2 text-sm border border-neutral-border rounded-xl bg-white/80 dark:bg-neutral-800 text-neutral-main outline-none focus:ring-2 focus:ring-primary-400 mb-3"
                            />
                            <div className="flex items-center gap-2">
                                <button onClick={handleCreateProject} disabled={!newProjectName.trim()}
                                    className="flex-1 px-4 py-3 text-sm font-extrabold rounded-xl bg-primary-900 text-white hover:bg-neutral-main shadow-lg transition-colors disabled:opacity-50">
                                    생성
                                </button>
                                <button onClick={() => { setCreatingProject(false); setNewProjectName(''); }}
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
        </div>
    );
}
