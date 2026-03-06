import { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { GitMerge, Clock, CheckCircle2, AlertTriangle, Plus, Trash2, X, Pencil } from 'lucide-react';
import { listPipelineTasks, createPipelineTask, updatePipelineTask, deletePipelineTask } from '../../api/tasks';
import client from '../../api/client';

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
    { id: 'todo', label: 'To Do', icon: Clock, color: 'text-neutral-500', headerBg: 'bg-neutral-100/50 dark:bg-gray-700/50', accent: 'border-neutral-200' },
    { id: 'in_progress', label: 'In Progress', icon: GitMerge, color: 'text-primary-600', headerBg: 'bg-primary-50/70 dark:bg-primary-900/40', accent: 'border-primary-200' },
    { id: 'review', label: 'Review', icon: AlertTriangle, color: 'text-amber-600', headerBg: 'bg-amber-50/70 dark:bg-amber-900/40', accent: 'border-amber-200' },
    { id: 'done', label: 'Done', icon: CheckCircle2, color: 'text-emerald-600', headerBg: 'bg-emerald-50/70 dark:bg-emerald-900/40', accent: 'border-emerald-200' },
];

const EMPTY_FORM = { title: '', description: '', assignee: '', dueDate: '', priority: 'medium', tags: '' };
const INPUT_CLS = 'w-full px-3 py-2 border border-gray-300 dark:border-gray-500 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-primary-500';

export default function KanbanBoard({ onReady, externalActions }) {
    const [tasks, setTasks] = useState([]);
    const [loading, setLoading] = useState(true);
    const [draggingId, setDraggingId] = useState(null);
    const [dragOverStage, setDragOverStage] = useState(null);
    const [showModal, setShowModal] = useState(false);
    const [editingTask, setEditingTask] = useState(null);
    const [form, setForm] = useState(EMPTY_FORM);
    const [members, setMembers] = useState([]);

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
        client.get('/auth/team-members')
            .then(res => setMembers(res.data || []))
            .catch(() => setMembers([]));
    }, []);

    useEffect(() => {
        if (onReady && externalActions) {
            onReady({
                refresh: () => fetchTasks(),
                openCreate: () => {
                    setEditingTask(null);
                    setForm(EMPTY_FORM);
                    setShowModal(true);
                },
                loading
            });
        }
    }, [onReady, externalActions, fetchTasks, loading]);

    /* ── Modal ── */
    const openCreate = () => {
        setEditingTask(null);
        setForm(EMPTY_FORM);
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
            console.error('Save failed', err);
        }
    };

    /* ── Delete ── */
    const handleDelete = async (e, id) => {
        e.stopPropagation();
        if (!confirm('태스크를 삭제하시겠습니까?')) return;
        try {
            await deletePipelineTask(id);
            setTasks(prev => prev.filter(t => t.id !== id));
        } catch (err) {
            console.error('Delete failed', err);
        }
    };

    /* ── Due badge ── */
    const getDueBadge = (dueDate, stage) => {
        if (!dueDate) return null;
        if (stage === 'todo' || stage === 'done') {
            return { text: dueDate, cls: 'text-gray-500 dark:text-gray-400' };
        }
        const diff = Math.ceil((new Date(dueDate) - new Date()) / 86400000);
        if (diff < 0) return { text: `${Math.abs(diff)}일 초과`, cls: 'text-red-500 font-bold' };
        if (diff <= 2) return { text: `D-${diff}`, cls: 'text-orange-500 font-bold' };
        return { text: dueDate, cls: 'text-gray-500 dark:text-gray-400' };
    };

    return (
        <div className="space-y-6">
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
                <div className="flex items-center justify-center h-64 text-gray-500 dark:text-gray-400">데이터 로딩 중...</div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                    {stageConfig.map((stage) => {
                        const stageTasks = tasks.filter(t => t.stage === stage.id);
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
                                    <div className={`p-1.5 rounded-lg bg-white/50 dark:bg-gray-800/50 shadow-inner`}>
                                        <stage.icon className={stage.color} size={18} />
                                    </div>
                                    <span className="font-bold text-sm text-gray-900 dark:text-white tracking-tight">{stage.label}</span>
                                    <span className="ml-auto text-[0.65rem] font-black text-primary-700 bg-white/60 dark:bg-black/20 dark:text-primary-300 px-2.5 py-0.5 rounded-full shadow-sm">
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
                                                    draggable="true"
                                                    onDragStart={(e) => handleDragStart(e, task.id)}
                                                    onDragEnd={() => { setDraggingId(null); setDragOverStage(null); }}
                                                    onClick={() => openEdit(task)}
                                                    className={`bg-white/30 dark:bg-gray-800/20 backdrop-blur-md p-4 rounded-2xl border border-white/60 dark:border-white/10 shadow-lg cursor-grab active:cursor-grabbing hover:shadow-[0_20px_40px_-15px_rgba(0,0,0,0.15)] hover:border-primary-400 hover:bg-white/50 dark:hover:bg-gray-700/40 hover:-translate-y-2 hover:scale-[1.02] transition-all duration-300 group ${draggingId === task.id ? 'opacity-40 scale-95' : ''}`}
                                                >
                                                    <div className="flex justify-between items-start mb-2">
                                                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${priorityColors[task.priority] || priorityColors.medium}`}>
                                                            {(task.priority || 'medium').toUpperCase()}
                                                        </span>
                                                        <div className="flex items-center gap-1">
                                                            <button
                                                                onClick={(e) => { e.stopPropagation(); openEdit(task); }}
                                                                className="opacity-0 group-hover:opacity-100 p-1 rounded-lg hover:bg-blue-50 dark:hover:bg-blue-900/30 text-gray-500 dark:text-gray-400 hover:text-blue-500 transition-all"
                                                                title="수정"
                                                            >
                                                                <Pencil size={13} />
                                                            </button>
                                                            <button
                                                                onClick={(e) => handleDelete(e, task.id)}
                                                                className="opacity-0 group-hover:opacity-100 p-1 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/30 text-gray-500 dark:text-gray-400 hover:text-red-500 transition-all"
                                                                title="삭제"
                                                            >
                                                                <Trash2 size={13} />
                                                            </button>
                                                        </div>
                                                    </div>

                                                    <h4 className="text-sm font-semibold text-gray-900 dark:text-white leading-snug mb-1">{task.title}</h4>
                                                    {task.description && (
                                                        <p className="text-[11px] text-gray-500 dark:text-gray-400 mb-2.5 line-clamp-2 leading-relaxed">{task.description}</p>
                                                    )}

                                                    {task.tags?.length > 0 && (
                                                        <div className="flex flex-wrap gap-1 mb-3">
                                                            {task.tags.map(tag => (
                                                                <span key={tag} className={`text-[9px] font-bold px-1.5 py-0.5 rounded-md ${tagColors[tag] || 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'}`}>
                                                                    {tag}
                                                                </span>
                                                            ))}
                                                        </div>
                                                    )}

                                                    <div className="flex items-center justify-between pt-2.5 border-t border-gray-200 dark:border-gray-600">
                                                        {task.assignee ? (
                                                            <div className="flex items-center gap-2">
                                                                <img src={avatarSrc} alt={task.assignee} className="w-6 h-6 rounded-full border border-gray-300 dark:border-gray-500 bg-white" />
                                                                <span className="text-xs font-medium text-gray-600 dark:text-gray-300">{task.assignee}</span>
                                                            </div>
                                                        ) : (
                                                            <span className="text-xs text-gray-500 dark:text-gray-400">미지정</span>
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
                        className="relative bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-[2rem] shadow-2xl w-full max-w-sm p-8 mx-4 border border-white/40 dark:border-white/10"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-xl font-black text-neutral-900 dark:text-white tracking-tighter">
                                {editingTask ? 'Task Details' : 'New Task'}
                            </h2>
                            <button onClick={closeModal} className="w-8 h-8 rounded-lg hover:bg-neutral-100 dark:hover:bg-white/5 text-neutral-400 transition-colors flex items-center justify-center">
                                <X size={20} />
                            </button>
                        </div>
                        <form onSubmit={handleSubmit} className="space-y-5">
                            <div>
                                <label className="block text-[11px] font-black uppercase tracking-wider text-neutral-400 mb-1.5 ml-1">Title</label>
                                <input type="text" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} className={INPUT_CLS} placeholder="What needs to be done?" required autoFocus />
                            </div>
                            <div>
                                <label className="block text-[11px] font-black uppercase tracking-wider text-neutral-400 mb-1.5 ml-1">Description</label>
                                <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} rows={3} className={`${INPUT_CLS} resize-none`} placeholder="Add some context..." />
                            </div>

                            <div>
                                <label className="block text-[11px] font-black uppercase tracking-wider text-neutral-400 mb-2 ml-1">Assignee</label>
                                <div className="flex flex-wrap gap-2">
                                    {members.map((m) => {
                                        const selected = form.assignee === m.name;
                                        const avatarSrc = m.avatar || `https://api.dicebear.com/7.x/notionists/svg?seed=${encodeURIComponent(m.name)}`;
                                        return (
                                            <button
                                                key={m.id}
                                                type="button"
                                                onClick={() => setForm(f => ({ ...f, assignee: selected ? '' : m.name }))}
                                                className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-bold border transition-all ${selected
                                                    ? 'border-primary-500 bg-primary-500 text-white shadow-lg shadow-primary-500/20 scale-105'
                                                    : 'border-neutral-200 dark:border-white/10 text-neutral-500 bg-white/50 dark:bg-black/20 hover:border-primary-300'
                                                    }`}
                                            >
                                                <img src={avatarSrc} alt={m.name} className="w-4 h-4 rounded-full bg-white/50" />
                                                <span>{m.name}</span>
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-[11px] font-black uppercase tracking-wider text-neutral-400 mb-1.5 ml-1">Priority</label>
                                    <select value={form.priority} onChange={e => setForm(f => ({ ...f, priority: e.target.value }))} className={`${INPUT_CLS} py-2`}>
                                        <option value="high">High</option>
                                        <option value="medium">Medium</option>
                                        <option value="low">Low</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-[11px] font-black uppercase tracking-wider text-neutral-400 mb-1.5 ml-1">Due Date</label>
                                    <input type="date" value={form.dueDate} onChange={e => setForm(f => ({ ...f, dueDate: e.target.value }))} className={`${INPUT_CLS} py-2`} />
                                </div>
                            </div>

                            <div className="flex justify-end gap-2 pt-4">
                                <button type="button" onClick={closeModal} className="px-6 py-2.5 text-xs font-black rounded-xl text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 transition-all">
                                    Cancel
                                </button>
                                <button type="submit" className="px-8 py-2.5 text-xs font-black rounded-xl bg-neutral-900 dark:bg-white text-white dark:text-neutral-900 shadow-xl hover:scale-105 transition-all">
                                    {editingTask ? 'Save' : 'Create'}
                                </button>
                            </div>
                        </form>
                    </motion.div>
                </div>,
                document.body
            )}
        </div>
    );
}
