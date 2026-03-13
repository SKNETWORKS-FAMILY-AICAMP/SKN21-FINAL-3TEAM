import { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { GitMerge, Clock, CheckCircle2, AlertTriangle, Plus, Trash2, X, Pencil, ExternalLink, CheckSquare, Square, Send, FolderOpen, ChevronDown, RefreshCw, Sparkles, FileCheck, CalendarPlus, Loader2 } from 'lucide-react';
import { listPipelineTasks, createPipelineTask, updatePipelineTask, deletePipelineTask } from '../../api/tasks';
import { createTask as createGoogleTask } from '../../api/google';
import useGoogleServices from '../../hooks/useGoogleServices';
import { suggestForProject } from '../../api/approvals';
import { createSchedule } from '../../api/schedules';
import client from '../../api/client';
import { toast } from '../../store/toastStore';

const priorityColors = {
    high: 'bg-error-bg text-error dark:bg-red-900/40 dark:text-red-400',
    medium: 'bg-warning-bg text-warning dark:bg-orange-900/40 dark:text-orange-400',
    low: 'bg-success-bg text-success dark:bg-green-900/40 dark:text-green-400',
};

const tagColors = {
    Frontend: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
    Backend: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
    'UI/UX': 'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300',
    API: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300',
    Design: 'bg-pink-100 text-pink-700 dark:bg-pink-900/40 dark:text-pink-300',
    Figma: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300',
    Document: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
    PM: 'bg-slate-100 text-slate-700 dark:bg-slate-700/40 dark:text-slate-300',
    QA: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
    Bugfix: 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300',
    DB: 'bg-teal-100 text-teal-700 dark:bg-teal-900/40 dark:text-teal-300',
};

const stageConfig = [
    { id: 'todo', label: 'To Do', icon: Clock, color: 'text-neutral-muted', headerBg: 'bg-surface-sub/70', accent: 'border-neutral-divider' },
    { id: 'in_progress', label: 'In Progress', icon: GitMerge, color: 'text-primary-600', headerBg: 'bg-primary-50/70 dark:bg-primary-900/40', accent: 'border-primary-200' },
    { id: 'review', label: 'Review', icon: AlertTriangle, color: 'text-amber-600', headerBg: 'bg-amber-50/70 dark:bg-amber-900/40', accent: 'border-amber-200' },
    { id: 'done', label: 'Done', icon: CheckCircle2, color: 'text-emerald-600', headerBg: 'bg-emerald-50/70 dark:bg-emerald-900/40', accent: 'border-emerald-200' },
];

const EMPTY_FORM = { title: '', description: '', assignee: '', dueDate: '', priority: 'medium', tags: '', project: '' };
const INPUT_CLS = 'w-full px-3 py-2 border border-neutral-border rounded-lg bg-surface-card text-neutral-main focus:outline-none focus:ring-2 focus:ring-primary-500';

export default function KanbanBoard({ onReady, externalActions, filterProject, projectMembers = [] }) {
    const [tasks, setTasks] = useState([]);
    const [loading, setLoading] = useState(true);
    const [draggingId, setDraggingId] = useState(null);
    const [dragOverStage, setDragOverStage] = useState(null);
    const [showModal, setShowModal] = useState(false);
    const [editingTask, setEditingTask] = useState(null);
    const [form, setForm] = useState(EMPTY_FORM);
    const [members, setMembers] = useState([]);
    const [syncingTaskIds, setSyncingTaskIds] = useState(new Set());

    // Google Tasks 연동
    const { tasks: googleTasks, tasksLoading: googleTasksLoading, updateTask: updateGoogleTask, pullTasks, hasScope } = useGoogleServices();
    const [selectMode, setSelectMode] = useState(false);
    const [selectedIds, setSelectedIds] = useState(new Set());
    const [bulkSending, setBulkSending] = useState(false);
    const [showGoogleTasksPanel, setShowGoogleTasksPanel] = useState(false);
    const [activeProject, setActiveProject] = useState('all'); // 'all' or project name
    const [deleteTarget, setDeleteTarget] = useState(null); // task to delete
    const [deleting, setDeleting] = useState(false);

    // AI 추천 패널
    const [showAiPanel, setShowAiPanel] = useState(false);
    const [aiLoading, setAiLoading] = useState(false);
    const [aiTab, setAiTab] = useState('approvals'); // 'approvals' | 'schedules'
    const [aiApprovals, setAiApprovals] = useState([]);
    const [aiSchedules, setAiSchedules] = useState([]);
    const [aiContext, setAiContext] = useState(null);
    const [aiGlow, setAiGlow] = useState(!!filterProject); // 프로젝트 안에 들어왔을 때 반짝임
    const [addingScheduleIdx, setAddingScheduleIdx] = useState(null); // AI 추천 일정 추가 중인 인덱스

    const fetchTasks = useCallback(async () => {
        try {
            const res = await listPipelineTasks();
            setTasks(Array.isArray(res.data) ? res.data : []);
        } catch (err) {
            console.error('Failed to fetch tasks', err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchTasks(); }, [fetchTasks]);

    useEffect(() => {
        // projectMembers가 있으면 all-members에서 가져옴 (다른 팀 멤버도 포함)
        if (projectMembers.length > 0) {
            Promise.all([
                client.get('/auth/team-members'),
                client.get('/auth/all-members'),
            ]).then(([teamRes, allRes]) => {
                const teamMembers = teamRes.data || [];
                const allMembers = allRes.data || [];
                // 중복 제거하여 합침
                const map = new Map();
                teamMembers.forEach(m => map.set(m.name, m));
                allMembers.forEach(m => { if (!map.has(m.name)) map.set(m.name, m); });
                setMembers([...map.values()]);
            }).catch(() => {
                client.get('/auth/team-members')
                    .then(res => setMembers(res.data || []))
                    .catch(() => setMembers([]));
            });
        } else {
            client.get('/auth/team-members')
                .then(res => setMembers(res.data || []))
                .catch(() => setMembers([]));
        }
    }, [projectMembers.length]);

    useEffect(() => {
        if (onReady && externalActions) {
            onReady({
                refresh: () => fetchTasks(),
                openCreate: () => {
                    setEditingTask(null);
                    setForm({ ...EMPTY_FORM, project: filterProject || '' });
                    setShowModal(true);
                },
                loading,
                startSelectMode: () => setSelectMode(true),
                openGoogleTasksPanel: () => { setShowGoogleTasksPanel(true); if (hasScope('tasks')) pullTasks(); },
                selectMode,
            });
        }
    }, [onReady, externalActions, fetchTasks, loading, selectMode, filterProject]);

    /* ── Modal ── */
    const openCreate = () => {
        setEditingTask(null);
        setForm({ ...EMPTY_FORM, project: filterProject || '' });
        setShowModal(true);
    };

    const openEdit = (task) => {
        setEditingTask(task);
        setForm({
            title: task.title || '',
            description: task.description || '',
            assignee: task.assignee || '',
            dueDate: task.dueDate || '',
            priority: task.priority || 'medium',
            tags: (task.tags || []).join(', '),
            project: task.project || '',
        });
        setShowModal(true);
    };

    const closeModal = () => {
        setShowModal(false);
        setEditingTask(null);
        setForm(EMPTY_FORM);
    };

    /* ── Drag & Drop ── */
    const handleDragStart = (e, id) => {
        setDraggingId(id);
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', id.toString());
    };

    const handleDragOver = (e, stageId) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        setDragOverStage(stageId);
    };

    const handleDragLeave = () => setDragOverStage(null);

    const handleDrop = async (e, stageId) => {
        e.preventDefault();
        setDragOverStage(null);
        if (!draggingId) return;
        const task = tasks.find(t => t.id === draggingId);
        if (!task || task.stage === stageId) { setDraggingId(null); return; }

        // Optimistic update
        setTasks(prev => prev.map(t => t.id === draggingId ? { ...t, stage: stageId } : t));
        setDraggingId(null);

        try {
            await updatePipelineTask(task.id, { stage: stageId });
        } catch {
            fetchTasks();
        }
    };

    /* ── Submit ── */
    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!form.title.trim()) return;
        const tags = form.tags ? form.tags.split(',').map(t => t.trim()).filter(Boolean) : [];
        const data = {
            title: form.title,
            description: form.description || null,
            assignee: form.assignee || null,
            due_date: form.dueDate || null,
            priority: form.priority,
            tags,
            project: filterProject || form.project || null,
        };

        try {
            if (editingTask) {
                await updatePipelineTask(editingTask.id, data);
            } else {
                await createPipelineTask(data);
            }
            closeModal();
            fetchTasks();
        } catch (err) {
            const detail = err.response?.data?.detail || '태스크 저장에 실패했습니다';
            toast.error(detail);
            console.error('Save failed', err);
        }
    };

    /* ── Delete ── */
    const confirmDelete = async () => {
        if (!deleteTarget) return;
        setDeleting(true);
        try {
            await deletePipelineTask(deleteTarget.id);
            setTasks(prev => prev.filter(t => t.id !== deleteTarget.id));
            setDeleteTarget(null);
        } catch (err) {
            console.error('Delete failed', err);
        } finally {
            setDeleting(false);
        }
    };

    /* ── Sync to Google Tasks ── */
    const handleSyncToGoogleTasks = async (e, task) => {
        e.stopPropagation();
        setSyncingTaskIds(prev => new Set([...prev, task.id]));
        try {
            await createGoogleTask({
                title: task.title,
                assignee: task.assignee || null,
                due_date: task.dueDate || null,
                priority: task.priority || 'medium',
            });
            alert('Google Tasks에 추가되었습니다');
        } catch (err) {
            alert(err.response?.data?.detail || 'Google Tasks 추가 실패');
        } finally {
            setSyncingTaskIds(prev => {
                const next = new Set(prev);
                next.delete(task.id);
                return next;
            });
        }
    };

    /* ── Bulk select ── */
    const toggleSelect = (id) => {
        setSelectedIds(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id); else next.add(id);
            return next;
        });
    };

    const handleBulkSendToGoogleTasks = async () => {
        if (selectedIds.size === 0) return;
        setBulkSending(true);
        try {
            const selected = tasks.filter(t => selectedIds.has(t.id));
            for (const task of selected) {
                await createGoogleTask({
                    title: task.title,
                    assignee: task.assignee || null,
                    due_date: task.dueDate || null,
                    priority: task.priority || 'medium',
                });
            }
            alert(`${selected.length}개 태스크가 Google Tasks에 추가되었습니다`);
            setSelectedIds(new Set());
            setSelectMode(false);
            if (hasScope('tasks')) pullTasks();
        } catch (err) {
            alert(err.response?.data?.detail || 'Google Tasks 추가 실패');
        } finally {
            setBulkSending(false);
        }
    };

    /* ── Due badge ── */
    const getDueBadge = (dueDate, stage) => {
        if (!dueDate) return null;
        if (stage === 'todo' || stage === 'done') {
            return { text: dueDate, cls: 'text-neutral-muted' };
        }
        const diff = Math.ceil((new Date(dueDate) - new Date()) / 86400000);
        if (diff < 0) return { text: `${Math.abs(diff)}일 초과`, cls: 'text-red-500 font-bold' };
        if (diff <= 2) return { text: `D-${diff}`, cls: 'text-orange-500 font-bold' };
        return { text: dueDate, cls: 'text-neutral-muted' };
    };

    /* ── AI 추천 ── */
    const handleAiSuggest = async () => {
        const projName = filterProject || activeProject;
        if (!projName || projName === 'all' || projName === 'none') {
            toast.error('프로젝트를 선택해주세요');
            return;
        }
        setAiGlow(false); // 열면 반짝임 끄기
        setShowAiPanel(true);
        setAiLoading(true);
        try {
            const res = await suggestForProject(projName);
            setAiApprovals(res.data.approvals || []);
            setAiSchedules(res.data.schedules || []);
            setAiContext(res.data.context || null);
        } catch (err) {
            toast.error(err.response?.data?.detail || 'AI 추천 실패');
        } finally {
            setAiLoading(false);
        }
    };

    /* ── AI 추천 일정 → 프로젝트 공유 일정으로 등록 ── */
    const handleAddAiSchedule = async (item, idx) => {
        const projName = filterProject || activeProject;
        if (!projName || projName === 'all') return;
        setAddingScheduleIdx(idx);
        try {
            // suggested_day 기반 날짜 계산
            const now = new Date();
            let startDate = new Date(now);
            if (item.suggested_day === 'tomorrow') {
                startDate.setDate(startDate.getDate() + 1);
            } else if (item.suggested_day === 'this_week') {
                // 이번 주 금요일
                const dayOfWeek = startDate.getDay();
                const daysUntilFri = dayOfWeek <= 5 ? 5 - dayOfWeek : 0;
                startDate.setDate(startDate.getDate() + (daysUntilFri || 1));
            }
            const dateStr = `${startDate.getFullYear()}-${String(startDate.getMonth() + 1).padStart(2, '0')}-${String(startDate.getDate()).padStart(2, '0')}`;
            const durationMin = item.duration_minutes || 60;
            const startTime = `${dateStr}T10:00:00`;
            const endHour = 10 + Math.floor(durationMin / 60);
            const endMin = durationMin % 60;
            const endTime = `${dateStr}T${String(endHour).padStart(2, '0')}:${String(endMin).padStart(2, '0')}:00`;

            await createSchedule({
                title: item.title,
                description: item.description || '',
                start_time: startTime,
                end_time: endTime,
                schedule_type: item.schedule_type || 'meeting',
                priority: item.priority || 'medium',
                project_name: projName,
            });
            toast.success(`[${projName}] 프로젝트 일정 등록 완료!`);
            // 등록된 항목 제거
            setAiSchedules((prev) => prev.filter((_, i) => i !== idx));
        } catch (err) {
            toast.error(err.response?.data?.detail || '일정 등록 실패');
        } finally {
            setAddingScheduleIdx(null);
        }
    };

    const approvalTypeIcons = {
        leave: '🏖️', remote: '🏠', room: '🏢', design: '🎨', certificate: '📜',
        budget: '💰', review: '👀', deploy: '🚀', infra: '🔧', security: '🔒',
    };
    const scheduleTypeColors = {
        meeting: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
        task: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
        deadline: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300',
        review: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
        milestone: 'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300',
    };

    return (
        <div className="space-y-6">
            {/* Google Tasks 연동 바 */}
            <div className="flex items-center gap-2 flex-wrap">
                {selectMode ? (
                    <>
                        <span className="text-xs font-bold text-neutral-sub">{selectedIds.size}개 선택됨</span>
                        <button
                            onClick={handleBulkSendToGoogleTasks}
                            disabled={selectedIds.size === 0 || bulkSending}
                            className="px-3 py-1.5 text-xs font-bold rounded-lg bg-emerald-500 text-white hover:bg-emerald-600 transition-colors disabled:opacity-50 flex items-center gap-1.5"
                        >
                            <Send size={12} />
                            {bulkSending ? '전송 중...' : 'Google Tasks로 보내기'}
                        </button>
                        <button
                            onClick={() => { setSelectMode(false); setSelectedIds(new Set()); }}
                            className="px-3 py-1.5 text-xs font-bold rounded-lg text-neutral-400 hover:text-neutral-600 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
                        >
                            취소
                        </button>
                    </>
                ) : (
                    <>
                        <button
                            onClick={() => setSelectMode(true)}
                            className="px-3 py-1.5 text-xs font-bold rounded-lg border border-emerald-300 text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-900/20 transition-colors flex items-center gap-1.5"
                        >
                            <CheckSquare size={13} />
                            Google Tasks 보내기
                        </button>
                        <button
                            onClick={() => { setShowGoogleTasksPanel(true); if (hasScope('tasks')) pullTasks(); }}
                            className="px-3 py-1.5 text-xs font-bold rounded-lg border border-primary-300 text-primary-600 hover:bg-primary-50 dark:hover:bg-primary-900/20 transition-colors flex items-center gap-1.5"
                        >
                            <ExternalLink size={13} />
                            Google Tasks 확인
                        </button>
                        <button
                            onClick={handleAiSuggest}
                            className={`px-3 py-1.5 text-xs font-bold rounded-lg border transition-all flex items-center gap-1.5 ${aiGlow
                                ? 'border-violet-400 text-violet-600 bg-violet-50 dark:bg-violet-900/30 dark:border-violet-500 dark:text-violet-300 shadow-[0_0_12px_rgba(139,92,246,0.4)] animate-pulse'
                                : 'border-violet-300 text-violet-600 hover:bg-violet-50 dark:border-violet-600 dark:text-violet-400 dark:hover:bg-violet-900/20'
                            }`}
                        >
                            <Sparkles size={13} className={aiGlow ? 'animate-spin' : ''} />
                            AI 추천
                        </button>
                    </>
                )}
            </div>

            {/* 프로젝트 필터 (filterProject 외부 지정이 없을 때만 표시) */}
            {!filterProject && (() => {
                const projects = [...new Set(tasks.map(t => t.project).filter(Boolean))];
                if (projects.length === 0) return null;
                return (
                    <div className="flex items-center gap-2 flex-wrap">
                        <FolderOpen size={14} className="text-neutral-muted" />
                        <button
                            onClick={() => setActiveProject('all')}
                            className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all ${activeProject === 'all'
                                ? 'bg-primary-600 text-white shadow-md'
                                : 'bg-surface-card/60 text-neutral-sub border border-neutral-border hover:border-primary-300'
                            }`}
                        >
                            전체 ({tasks.length})
                        </button>
                        {projects.map(proj => {
                            const count = tasks.filter(t => t.project === proj).length;
                            return (
                                <button
                                    key={proj}
                                    onClick={() => setActiveProject(proj)}
                                    className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all ${activeProject === proj
                                        ? 'bg-primary-600 text-white shadow-md'
                                        : 'bg-surface-card/60 text-neutral-sub border border-neutral-border hover:border-primary-300'
                                    }`}
                                >
                                    {proj} ({count})
                                </button>
                            );
                        })}
                        <button
                            onClick={() => setActiveProject('none')}
                            className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all ${activeProject === 'none'
                                ? 'bg-primary-600 text-white shadow-md'
                                : 'bg-surface-card/60 text-neutral-sub border border-neutral-border hover:border-primary-300'
                            }`}
                        >
                            미분류 ({tasks.filter(t => !t.project).length})
                        </button>
                    </div>
                );
            })()}

            {!externalActions && (
                <div className="flex items-center justify-between">
                    <h2 className="text-lg font-bold text-neutral-main">보드 뷰</h2>
                    <button onClick={openCreate} className="btn-primary">
                        <Plus size={16} />
                        태스크 추가
                    </button>
                </div>
            )}

            {loading ? (
                <div className="flex items-center justify-center h-64 text-neutral-sub">데이터 로딩 중...</div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                    {stageConfig.map((stage) => {
                        const filteredTasks = filterProject
                            ? (filterProject === '미분류'
                                ? tasks.filter(t => !t.project || t.project === '미분류')
                                : tasks.filter(t => t.project === filterProject))
                            : activeProject === 'all' ? tasks
                            : activeProject === 'none' ? tasks.filter(t => !t.project)
                            : tasks.filter(t => t.project === activeProject);
                        const stageTasks = filteredTasks.filter(t => t.stage === stage.id);
                        const isOver = dragOverStage === stage.id;
                        return (
                            <div
                                key={stage.id}
                                className="flex flex-col min-h-[420px]"
                                onDragOver={(e) => handleDragOver(e, stage.id)}
                                onDragLeave={handleDragLeave}
                                onDrop={(e) => handleDrop(e, stage.id)}
                            >
                                <div className={`flex items-center gap-2 mb-4 p-3.5 rounded-2xl shadow-md border backdrop-blur-xl ${stage.headerBg} ${stage.accent} border-white/30 dark:border-white/5`}>
                                    <div className={`p-1.5 rounded-lg bg-surface-card/50 shadow-inner`}>
                                        <stage.icon className={stage.color} size={18} />
                                    </div>
                                    <span className="font-bold text-sm text-neutral-main tracking-tight">{stage.label}</span>
                                    <span className="ml-auto text-[0.65rem] font-black text-primary-700 bg-surface-card/60 dark:text-primary-300 px-2.5 py-0.5 rounded-full shadow-sm">
                                        {stageTasks.length}
                                    </span>
                                </div>

                                <div className={`flex-1 space-y-3 p-3 rounded-2xl transition-all duration-300 ${isOver ? 'bg-primary-50/50 dark:bg-primary-900/20 ring-2 ring-inset ring-primary-300/50' : 'bg-white/10 dark:bg-black/10 border-2 border-transparent'}`}>
                                    <AnimatePresence mode="popLayout">
                                        {stageTasks.map((task) => {
                                            const due = getDueBadge(task.dueDate, task.stage);
                                            const memberMatch = members.find(m => m.name === task.assignee);
                                            const avatarSrc = task.assignee
                                                ? (memberMatch?.avatar || `https://api.dicebear.com/7.x/notionists/svg?seed=${encodeURIComponent(task.assignee)}`)
                                                : null;
                                            return (
                                                <motion.div
                                                    key={task.id}
                                                    layout
                                                    initial={{ opacity: 0, y: 10 }}
                                                    animate={{ opacity: 1, y: 0 }}
                                                    exit={{ opacity: 0, scale: 0.9 }}
                                                    transition={{ duration: 0.2 }}
                                                    draggable={!selectMode}
                                                    onDragStart={(e) => !selectMode && handleDragStart(e, task.id)}
                                                    onDragEnd={() => { setDraggingId(null); setDragOverStage(null); }}
                                                    onClick={() => selectMode ? toggleSelect(task.id) : openEdit(task)}
                                                    className={`bg-white/30 dark:bg-gray-800/20 backdrop-blur-md p-4 rounded-2xl border border-white/60 dark:border-white/10 shadow-lg cursor-grab active:cursor-grabbing hover:shadow-[0_20px_40px_-15px_rgba(0,0,0,0.15)] hover:border-primary-400 hover:bg-white/50 dark:hover:bg-gray-700/40 hover:-translate-y-2 hover:scale-[1.02] transition-all duration-300 group ${draggingId === task.id ? 'opacity-40 scale-95' : ''}`}
                                                >
                                                    <div className="flex justify-between items-start mb-2">
                                                        <div className="flex items-center gap-2">
                                                            {selectMode && (
                                                                <span className="flex-shrink-0">
                                                                    {selectedIds.has(task.id)
                                                                        ? <CheckSquare size={16} className="text-emerald-500" />
                                                                        : <Square size={16} className="text-neutral-300" />
                                                                    }
                                                                </span>
                                                            )}
                                                            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${priorityColors[task.priority] || priorityColors.medium}`}>
                                                                {(task.priority || 'medium').toUpperCase()}
                                                            </span>
                                                        </div>
                                                        <div className="flex items-center gap-1">
                                                            <button
                                                                onClick={(e) => handleSyncToGoogleTasks(e, task)}
                                                                disabled={syncingTaskIds.has(task.id)}
                                                                className="opacity-0 group-hover:opacity-100 p-1 rounded-lg hover:bg-emerald-50 dark:hover:bg-emerald-900/30 text-neutral-muted hover:text-emerald-500 transition-all disabled:opacity-50"
                                                                title="Google Tasks에 추가"
                                                            >
                                                                <ExternalLink size={13} />
                                                            </button>
                                                            <button
                                                                onClick={(e) => { e.stopPropagation(); openEdit(task); }}
                                                                className="opacity-0 group-hover:opacity-100 p-1 rounded-lg hover:bg-blue-50 dark:hover:bg-blue-900/30 text-neutral-muted hover:text-blue-500 transition-all"
                                                                title="수정"
                                                            >
                                                                <Pencil size={13} />
                                                            </button>
                                                            <button
                                                                onClick={(e) => { e.stopPropagation(); setDeleteTarget(task); }}
                                                                className="opacity-0 group-hover:opacity-100 p-1 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 text-neutral-muted hover:text-red-500 transition-all"
                                                                title="삭제"
                                                            >
                                                                <Trash2 size={13} />
                                                            </button>
                                                        </div>
                                                    </div>

                                                    <h4 className="text-sm font-semibold text-neutral-main leading-snug mb-1">{task.title}</h4>
                                                    {task.description && (
                                                        <p className="text-[11px] text-neutral-sub mb-2.5 line-clamp-2 leading-relaxed">{task.description}</p>
                                                    )}

                                                    {(task.tags?.length > 0 || task.project) && (
                                                        <div className="flex flex-wrap gap-1 mb-3">
                                                            {task.project && (
                                                                <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-md bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300">
                                                                    {task.project}
                                                                </span>
                                                            )}
                                                            {task.tags?.map(tag => (
                                                                <span key={tag} className={`text-[9px] font-bold px-1.5 py-0.5 rounded-md ${tagColors[tag] || 'bg-surface-sub text-neutral-sub'}`}>
                                                                    {tag}
                                                                </span>
                                                            ))}
                                                        </div>
                                                    )}

                                                    <div className="flex items-center justify-between pt-2.5 border-t border-neutral-divider">
                                                        {task.assignee ? (
                                                            <div className="flex items-center gap-2">
                                                                <img src={avatarSrc} alt={task.assignee} className="w-6 h-6 rounded-full border border-neutral-border bg-surface-card" />
                                                                <span className="text-xs font-medium text-neutral-sub">{task.assignee}</span>
                                                            </div>
                                                        ) : (
                                                            <span className="text-xs text-neutral-muted">미지정</span>
                                                        )}
                                                        {due && <span className={`text-[10px] font-bold ${due.cls}`}>{due.text}</span>}
                                                    </div>
                                                </motion.div>
                                            );
                                        })}
                                    </AnimatePresence>

                                    {stageTasks.length === 0 && (
                                        <div className={`h-28 flex items-center justify-center border-2 border-dashed rounded-2xl transition-all duration-500 overflow-hidden relative group/drop backdrop-blur-sm shadow-inner ${isOver ? 'border-primary-400 bg-primary-100/20' : 'border-neutral-300 dark:border-neutral-700 bg-white/10 dark:bg-black/10'}`}>
                                            <div className="absolute inset-0 bg-gradient-to-br from-white/20 to-transparent opacity-0 group-hover/drop:opacity-100 transition-opacity" />
                                            <span className="text-[10px] font-black uppercase tracking-[0.2em] text-neutral-400 dark:text-neutral-500 opacity-40 z-10 transition-all group-hover/drop:scale-110 group-hover/drop:opacity-80">Drop Zone</span>
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            {/* ── Modal ── */}
            {showModal && createPortal(
                <div className="fixed inset-0 z-[120] flex items-center justify-center p-4">
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="absolute inset-0 bg-neutral-900/40 backdrop-blur-sm"
                        onClick={closeModal}
                    />
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95, y: 20 }}
                        transition={{ duration: 0.2 }}
                        className="relative bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-2xl shadow-2xl w-full max-w-sm mx-4 border border-white/40 dark:border-white/10 max-h-[85vh] flex flex-col"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="flex items-center justify-between px-6 pt-6 pb-2 flex-shrink-0">
                            <h2 className="text-lg font-black text-neutral-main tracking-tighter">
                                {editingTask ? 'Task Details' : 'New Task'}
                            </h2>
                            <button onClick={closeModal} className="w-7 h-7 rounded-lg hover:bg-neutral-100 dark:hover:bg-white/5 text-neutral-400 transition-colors flex items-center justify-center">
                                <X size={18} />
                            </button>
                        </div>
                        <form onSubmit={handleSubmit} className="space-y-3 flex-1 min-h-0 overflow-y-auto px-6 pb-6">
                            <div>
                                <label className="block text-[10px] font-black uppercase tracking-wider text-neutral-400 mb-1 ml-1">Title</label>
                                <input type="text" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} className={INPUT_CLS} placeholder="What needs to be done?" required autoFocus />
                            </div>
                            <div>
                                <label className="block text-[10px] font-black uppercase tracking-wider text-neutral-400 mb-1 ml-1">Description</label>
                                <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} rows={2} className={`${INPUT_CLS} resize-none`} placeholder="Add some context..." />
                            </div>

                            <div>
                                <label className="block text-[10px] font-black uppercase tracking-wider text-neutral-400 mb-1.5 ml-1">Assignee</label>
                                <div className="flex flex-wrap gap-1.5">
                                    {(projectMembers.length > 0
                                        ? members.filter(m => projectMembers.includes(m.name))
                                        : members
                                    ).map((m) => {
                                        const selected = form.assignee === m.name;
                                        const avatarSrc = m.avatar || `https://api.dicebear.com/7.x/notionists/svg?seed=${encodeURIComponent(m.name)}`;
                                        return (
                                            <button
                                                key={m.id}
                                                type="button"
                                                onClick={() => setForm(f => ({ ...f, assignee: selected ? '' : m.name }))}
                                                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-bold border transition-all ${selected
                                                    ? 'border-primary-500 bg-primary-500 text-white shadow-md shadow-primary-500/20'
                                                    : 'border-neutral-border text-neutral-sub bg-surface-card/50 hover:border-primary-300'
                                                    }`}
                                            >
                                                <img src={avatarSrc} alt={m.name} className="w-4 h-4 rounded-full bg-white/50" />
                                                <span>{m.name}</span>
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>

                            {!filterProject && (
                                <div>
                                    <label className="block text-[10px] font-black uppercase tracking-wider text-neutral-400 mb-1 ml-1">Project</label>
                                    <select value={form.project} onChange={e => setForm(f => ({ ...f, project: e.target.value }))} className={`${INPUT_CLS} py-2`}>
                                        <option value="">프로젝트 선택 (선택)</option>
                                        {[...new Set(tasks.map(t => t.project).filter(Boolean))].map(p => (
                                            <option key={p} value={p}>{p}</option>
                                        ))}
                                    </select>
                                </div>
                            )}

                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-[10px] font-black uppercase tracking-wider text-neutral-400 mb-1 ml-1">Priority</label>
                                    <select value={form.priority} onChange={e => setForm(f => ({ ...f, priority: e.target.value }))} className={`${INPUT_CLS} py-2`}>
                                        <option value="high">High</option>
                                        <option value="medium">Medium</option>
                                        <option value="low">Low</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-[10px] font-black uppercase tracking-wider text-neutral-400 mb-1 ml-1">Due Date</label>
                                    <input type="date" value={form.dueDate} onChange={e => setForm(f => ({ ...f, dueDate: e.target.value }))} className={`${INPUT_CLS} py-2`} />
                                </div>
                            </div>

                            <div className="flex justify-end gap-2 pt-2">
                                <button type="button" onClick={closeModal} className="px-5 py-2 text-xs font-black rounded-xl text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 transition-all">
                                    Cancel
                                </button>
                                <button type="submit" className="px-6 py-2 text-xs font-black rounded-xl bg-primary-700 text-white shadow-xl hover:bg-primary-900 hover:scale-105 transition-all">
                                    {editingTask ? 'Save' : 'Create'}
                                </button>
                            </div>
                        </form>
                    </motion.div>
                </div>,
                document.body
            )}
            {/* ── Google Tasks Side Panel ── */}
            <AnimatePresence>
                {showGoogleTasksPanel && (
                    <motion.div
                        initial={{ x: '100%' }}
                        animate={{ x: 0 }}
                        exit={{ x: '100%' }}
                        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
                        className="fixed top-4 right-4 bottom-4 w-[360px] z-[100] bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl shadow-[-8px_0_30px_-10px_rgba(0,0,0,0.15)] border border-white/40 dark:border-white/10 rounded-2xl flex flex-col overflow-hidden"
                    >
                        {/* Header */}
                        <div className="px-5 py-4 border-b border-neutral-100 dark:border-neutral-800">
                            <div className="flex items-center justify-between mb-1">
                                <span className="text-[11px] font-medium text-neutral-muted">할 일 목록</span>
                                <div className="flex items-center gap-1">
                                    <button
                                        onClick={() => pullTasks()}
                                        disabled={googleTasksLoading}
                                        className="p-1.5 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-400 transition-colors"
                                        title="새로고침"
                                    >
                                        <RefreshCw size={15} className={googleTasksLoading ? 'animate-spin' : ''} />
                                    </button>
                                    <button onClick={() => setShowGoogleTasksPanel(false)} className="p-1.5 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-400 transition-colors">
                                        <X size={16} />
                                    </button>
                                </div>
                            </div>
                            <h2 className="text-base font-bold text-neutral-main">WorkFlow Agent</h2>
                        </div>

                        {/* Task List */}
                        <div className="flex-1 overflow-y-auto">
                            {googleTasksLoading && googleTasks.length === 0 ? (
                                <div className="flex items-center justify-center h-32 text-neutral-muted text-sm">로딩 중...</div>
                            ) : googleTasks.length === 0 ? (
                                <div className="flex flex-col items-center justify-center h-40 text-neutral-muted">
                                    <CheckCircle2 size={28} className="mb-2 opacity-30" />
                                    <p className="text-sm">할 일이 없습니다</p>
                                </div>
                            ) : (
                                <ul className="py-2">
                                    {[...googleTasks].sort((a, b) => (a.completed ? 1 : 0) - (b.completed ? 1 : 0)).map((task) => (
                                        <li
                                            key={task.action_item_id || task.id}
                                            className="flex items-start gap-3 px-5 py-3 hover:bg-neutral-50 dark:hover:bg-neutral-800/50 transition-colors"
                                        >
                                            <button
                                                onClick={() => updateGoogleTask(task.action_item_id || task.id, !task.completed)}
                                                className={`w-[18px] h-[18px] mt-0.5 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-all ${task.completed
                                                    ? 'border-blue-500 bg-blue-500 text-white'
                                                    : 'border-neutral-300 dark:border-neutral-600 hover:border-blue-400'
                                                }`}
                                            >
                                                {task.completed && (
                                                    <svg width="10" height="10" viewBox="0 0 12 12" fill="none"><path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                                                )}
                                            </button>
                                            <div className="flex-1 min-w-0">
                                                <p className={`text-sm leading-snug ${task.completed ? 'text-neutral-muted line-through' : 'text-neutral-main'}`}>
                                                    {task.title}
                                                </p>
                                                {(task.assignee || task.priority) && (
                                                    <p className="text-[11px] text-neutral-muted mt-0.5">
                                                        {[
                                                            task.assignee && `담당: ${task.assignee}`,
                                                            task.priority && `우선순위: ${task.priority}`,
                                                        ].filter(Boolean).join(' | ')}
                                                    </p>
                                                )}
                                                {task.deadline && (
                                                    <span className="inline-flex items-center gap-1 mt-1 px-2 py-0.5 rounded-md border border-neutral-200 dark:border-neutral-700 text-[11px] text-neutral-muted">
                                                        <Clock size={10} />
                                                        {task.deadline}
                                                    </span>
                                                )}
                                            </div>
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </div>

                        {/* Footer */}
                        <div className="px-5 py-3 border-t border-neutral-100 dark:border-neutral-800 text-xs text-neutral-muted text-center">
                            {googleTasks.filter(t => !t.completed).length}개 미완료 · {googleTasks.filter(t => t.completed).length}개 완료
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* ── AI 추천 Side Panel ── */}
            <AnimatePresence>
                {showAiPanel && (
                    <motion.div
                        initial={{ x: '100%' }}
                        animate={{ x: 0 }}
                        exit={{ x: '100%' }}
                        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
                        className="fixed top-4 right-4 bottom-4 w-[400px] z-[100] bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl shadow-[-8px_0_30px_-10px_rgba(0,0,0,0.15)] border border-white/40 dark:border-white/10 rounded-[2rem] flex flex-col overflow-hidden"
                    >
                        {/* Header */}
                        <div className="px-5 py-4 border-b border-neutral-100 dark:border-neutral-800">
                            <div className="flex items-center justify-between mb-2">
                                <div className="flex items-center gap-2">
                                    <Sparkles size={16} className="text-violet-500" />
                                    <span className="text-sm font-black text-neutral-main tracking-tight">AI 추천</span>
                                </div>
                                <div className="flex items-center gap-1">
                                    <button
                                        onClick={handleAiSuggest}
                                        disabled={aiLoading}
                                        className="p-1.5 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-400 transition-colors"
                                        title="새로고침"
                                    >
                                        <RefreshCw size={15} className={aiLoading ? 'animate-spin' : ''} />
                                    </button>
                                    <button onClick={() => setShowAiPanel(false)} className="p-1.5 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-400 transition-colors">
                                        <X size={16} />
                                    </button>
                                </div>
                            </div>
                            {aiContext && (
                                <div className="flex items-center gap-2 text-[10px] text-neutral-muted mb-3">
                                    <span className="font-bold text-violet-600 dark:text-violet-400">{aiContext.project_name}</span>
                                    <span>·</span>
                                    <span>태스크 {aiContext.total_tasks}개</span>
                                    <span>·</span>
                                    <span>완료 {aiContext.done_pct}%</span>
                                </div>
                            )}
                            {/* Tabs */}
                            <div className="flex bg-neutral-100 dark:bg-neutral-800 rounded-xl p-1">
                                <button
                                    onClick={() => setAiTab('approvals')}
                                    className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-xs font-bold rounded-lg transition-all ${aiTab === 'approvals'
                                        ? 'bg-white dark:bg-neutral-700 text-violet-600 dark:text-violet-400 shadow-sm'
                                        : 'text-neutral-400 hover:text-neutral-600'
                                    }`}
                                >
                                    <FileCheck size={13} />
                                    결재 추천
                                </button>
                                <button
                                    onClick={() => setAiTab('schedules')}
                                    className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-xs font-bold rounded-lg transition-all ${aiTab === 'schedules'
                                        ? 'bg-white dark:bg-neutral-700 text-violet-600 dark:text-violet-400 shadow-sm'
                                        : 'text-neutral-400 hover:text-neutral-600'
                                    }`}
                                >
                                    <CalendarPlus size={13} />
                                    일정 추천
                                </button>
                            </div>
                        </div>

                        {/* Content */}
                        <div className="flex-1 overflow-y-auto p-4 space-y-3">
                            {aiLoading ? (
                                <div className="flex flex-col items-center justify-center h-40 text-neutral-muted">
                                    <Loader2 size={28} className="animate-spin mb-3 text-violet-400" />
                                    <p className="text-sm font-bold">AI가 분석 중...</p>
                                    <p className="text-xs mt-1">프로젝트 태스크를 분석하고 있습니다</p>
                                </div>
                            ) : aiTab === 'approvals' ? (
                                aiApprovals.length === 0 ? (
                                    <div className="flex flex-col items-center justify-center h-32 text-neutral-muted">
                                        <FileCheck size={28} className="mb-2 opacity-30" />
                                        <p className="text-sm">추천 결재가 없습니다</p>
                                    </div>
                                ) : (
                                    aiApprovals.map((item, idx) => (
                                        <motion.div
                                            key={idx}
                                            initial={{ opacity: 0, y: 10 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            transition={{ delay: idx * 0.1 }}
                                            className="bg-white/60 dark:bg-neutral-800/60 backdrop-blur-md rounded-2xl p-4 border border-white/60 dark:border-white/10 shadow-md hover:shadow-lg hover:border-violet-300 dark:hover:border-violet-600 transition-all"
                                        >
                                            <div className="flex items-start gap-3">
                                                <span className="text-xl">{approvalTypeIcons[item.type] || '📋'}</span>
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2 mb-1">
                                                        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full ${priorityColors[item.priority] || priorityColors.medium}`}>
                                                            {(item.priority || 'medium').toUpperCase()}
                                                        </span>
                                                        <span className="text-[9px] font-bold text-neutral-muted uppercase">{item.type}</span>
                                                    </div>
                                                    <h4 className="text-sm font-bold text-neutral-main leading-snug mb-1">{item.title}</h4>
                                                    <p className="text-[11px] text-neutral-sub leading-relaxed mb-2">{item.detail}</p>
                                                    <p className="text-[10px] text-violet-500 dark:text-violet-400 font-medium">{item.reason}</p>
                                                </div>
                                            </div>
                                        </motion.div>
                                    ))
                                )
                            ) : (
                                aiSchedules.length === 0 ? (
                                    <div className="flex flex-col items-center justify-center h-32 text-neutral-muted">
                                        <CalendarPlus size={28} className="mb-2 opacity-30" />
                                        <p className="text-sm">추천 일정이 없습니다</p>
                                    </div>
                                ) : (
                                    aiSchedules.map((item, idx) => (
                                        <motion.div
                                            key={idx}
                                            initial={{ opacity: 0, y: 10 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            transition={{ delay: idx * 0.1 }}
                                            className="bg-white/60 dark:bg-neutral-800/60 backdrop-blur-md rounded-2xl p-4 border border-white/60 dark:border-white/10 shadow-md hover:shadow-lg hover:border-violet-300 dark:hover:border-violet-600 transition-all"
                                        >
                                            <div className="flex items-center gap-2 mb-2">
                                                <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full ${scheduleTypeColors[item.schedule_type] || 'bg-neutral-100 text-neutral-600'}`}>
                                                    {item.schedule_type}
                                                </span>
                                                <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full ${priorityColors[item.priority] || priorityColors.medium}`}>
                                                    {(item.priority || 'medium').toUpperCase()}
                                                </span>
                                                {item.duration_minutes && (
                                                    <span className="text-[9px] text-neutral-muted font-medium ml-auto">{item.duration_minutes}분</span>
                                                )}
                                            </div>
                                            <h4 className="text-sm font-bold text-neutral-main leading-snug mb-1">{item.title}</h4>
                                            <p className="text-[11px] text-neutral-sub leading-relaxed mb-2">{item.description}</p>
                                            <div className="flex items-center justify-between mb-2">
                                                <p className="text-[10px] text-violet-500 dark:text-violet-400 font-medium">{item.reason}</p>
                                                {item.suggested_day && (
                                                    <span className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-violet-50 text-violet-600 dark:bg-violet-900/30 dark:text-violet-400">
                                                        {item.suggested_day === 'today' ? '오늘' : item.suggested_day === 'tomorrow' ? '내일' : item.suggested_day === 'this_week' ? '이번 주' : item.suggested_day}
                                                    </span>
                                                )}
                                            </div>
                                            <button
                                                onClick={() => handleAddAiSchedule(item, idx)}
                                                disabled={addingScheduleIdx === idx}
                                                className="w-full mt-1 px-3 py-1.5 text-[11px] font-bold rounded-lg bg-violet-500 text-white hover:bg-violet-600 active:scale-95 transition-all disabled:opacity-50 flex items-center justify-center gap-1.5 shadow-sm"
                                            >
                                                {addingScheduleIdx === idx ? (
                                                    <><Loader2 size={12} className="animate-spin" /> 등록 중...</>
                                                ) : (
                                                    <><CalendarPlus size={12} /> [{filterProject || activeProject}] 일정 추가</>
                                                )}
                                            </button>
                                        </motion.div>
                                    ))
                                )
                            )}
                        </div>

                        {/* Footer */}
                        <div className="px-5 py-3 border-t border-neutral-100 dark:border-neutral-800 text-[10px] text-neutral-muted text-center">
                            결재 {aiApprovals.length}개 · 일정 {aiSchedules.length}개 추천
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* ── Task Delete Confirm Modal ── */}
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
                        className="relative bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-2xl shadow-2xl w-full max-w-[380px] p-8 mx-4 border border-white/40 dark:border-white/10"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="flex flex-col items-center text-center">
                            <div className="w-14 h-14 rounded-full bg-red-50 dark:bg-red-900/20 flex items-center justify-center mb-4">
                                <Trash2 size={24} className="text-red-500" />
                            </div>
                            <h3 className="text-lg font-black text-neutral-900 dark:text-white tracking-tight mb-2">태스크 삭제</h3>
                            <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-1">
                                <span className="font-bold text-neutral-700 dark:text-neutral-200">"{deleteTarget.title}"</span>
                            </p>
                            <p className="text-sm text-neutral-500 dark:text-neutral-400 mb-6">
                                이 태스크를 삭제하시겠습니까?<br />이 작업은 되돌릴 수 없습니다.
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
                                    onClick={confirmDelete}
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
