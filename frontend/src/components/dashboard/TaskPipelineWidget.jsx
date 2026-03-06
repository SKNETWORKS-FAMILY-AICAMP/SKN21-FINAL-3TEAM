import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { createPortal } from 'react-dom';
import {
    GitMerge, Clock, CheckCircle2, AlertTriangle,
    ArrowRight, Plus, Share, X, Mail, Phone, Briefcase
} from 'lucide-react';
import { listPipelineTasks, updatePipelineTask, createPipelineTask } from '../../api/tasks';
import client from '../../api/client';

const priorityColors = {
    high: 'bg-error-bg text-error dark:bg-red-900/40 dark:text-red-400',
    medium: 'bg-warning-bg text-warning dark:bg-orange-900/40 dark:text-orange-400',
    low: 'bg-success-bg text-success dark:bg-green-900/40 dark:text-green-400',
};

const stageConfig = [
    { id: 'todo', label: 'To Do', icon: Clock, color: 'text-neutral-500' },
    { id: 'in_progress', label: 'In Progress', icon: GitMerge, color: 'text-primary-500' },
    { id: 'review', label: 'Review', icon: AlertTriangle, color: 'text-orange-500' },
    { id: 'done', label: 'Done', icon: CheckCircle2, color: 'text-success' },
];

export default function TaskPipelineWidget() {
    const navigate = useNavigate();
    const [tasks, setTasks] = useState([]);
    const [draggingId, setDraggingId] = useState(null);
    const [members, setMembers] = useState([]);
    const [profilePopup, setProfilePopup] = useState(null); // member object or null
    const [showAddModal, setShowAddModal] = useState(false);
    const [addForm, setAddForm] = useState({ title: '', assignee: '', priority: 'medium' });
    const [addSubmitting, setAddSubmitting] = useState(false);
    const [shareToast, setShareToast] = useState(false);

    const fetchTasks = async () => {
        try {
            const res = await listPipelineTasks();
            setTasks(Array.isArray(res.data) ? res.data : []);
        } catch (err) {
            console.error('Failed to fetch pipeline tasks', err);
        }
    };

    useEffect(() => { fetchTasks(); }, []);

    useEffect(() => {
        client.get('/auth/team-members')
            .then(res => setMembers(res.data || []))
            .catch(() => setMembers([]));
    }, []);

    const handleDragStart = (e, id) => {
        setDraggingId(id);
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', id.toString());
    };

    const handleDragOver = (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
    };

    const handleDrop = async (e, stageId) => {
        e.preventDefault();
        if (!draggingId) return;
        const task = tasks.find(t => t.id === draggingId);
        if (!task || task.stage === stageId) { setDraggingId(null); return; }

        setTasks(prev => prev.map(t => t.id === draggingId ? { ...t, stage: stageId } : t));
        setDraggingId(null);

        try {
            await updatePipelineTask(task.id, { stage: stageId });
        } catch {
            fetchTasks();
        }
    };

    // 팀원 아바타 목록 (각 팀원이 가진 태스크 개수 계산)
    const getAvatar = (name) => {
        const member = members.find(m => m.name === name);
        return member?.avatar || `https://api.dicebear.com/7.x/notionists/svg?seed=${encodeURIComponent(name)}`;
    };
    const openProfile = (name) => {
        const member = members.find(m => m.name === name);
        if (member) setProfilePopup(member);
    };

    const handleAddTask = async (e) => {
        e.preventDefault();
        if (!addForm.title.trim()) return;
        setAddSubmitting(true);
        try {
            await createPipelineTask({
                title: addForm.title.trim(),
                assignee: addForm.assignee || null,
                priority: addForm.priority,
                stage: 'todo',
            });
            setShowAddModal(false);
            setAddForm({ title: '', assignee: '', priority: 'medium' });
            fetchTasks();
        } catch {
            alert('태스크 추가에 실패했습니다.');
        } finally {
            setAddSubmitting(false);
        }
    };

    const handleShare = () => {
        const summary = stageConfig.map(s => {
            const count = tasks.filter(t => t.stage === s.id).length;
            return `${s.label}: ${count}건`;
        }).join(' | ');
        const doneCount = tasks.filter(t => t.stage === 'done').length;
        const pct = tasks.length > 0 ? Math.round((doneCount / tasks.length) * 100) : 0;
        const text = `📋 Task Pipeline\n${summary}\n✅ 진행률: ${pct}%`;
        navigator.clipboard.writeText(text).then(() => {
            setShareToast(true);
            setTimeout(() => setShareToast(false), 2000);
        });
    };

    const teamStats = [...new Set(tasks.filter(t => t.assignee).map(t => t.assignee))].map(name => ({
        name,
        avatar: getAvatar(name),
        count: tasks.filter(task => task.assignee === name).length
    }));

    return (
        <div className="card flex flex-col overflow-hidden p-6 shadow-soft transition-all duration-300">
            {/* Top Bar: Team & Utilities */}
            <div className="flex items-center justify-between mb-8 w-full relative">
                <div className="flex-1">
                    <h3 className="text-xl font-extrabold text-neutral-main tracking-tight">Task Pipeline</h3>
                </div>

                {/* Center: Team Avatars Pill */}
                {teamStats.length > 0 && (
                    <div className="absolute left-1/2 -translate-x-1/2 flex items-center bg-surface-card/80 backdrop-blur-md px-5 py-2 rounded-full border border-neutral-divider shadow-sm gap-2.5">
                        {teamStats.map((member, i) => (
                            <div key={member.name} className="relative group" style={{ zIndex: teamStats.length - i }}>
                                <img
                                    src={member.avatar}
                                    alt={member.name}
                                    className="w-9 h-9 rounded-full border-2 border-surface-card shadow-sm transition-transform group-hover:scale-110 cursor-pointer"
                                    title={member.name}
                                    onClick={() => openProfile(member.name)}
                                />
                                <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 min-w-[18px] h-[18px] px-1 rounded-full bg-accent-500 flex items-center justify-center text-[9px] font-bold text-white border border-surface-card shadow-sm">
                                    {member.count}
                                </div>
                            </div>
                        ))}
                    </div>
                )}

                {/* Right: Utility Buttons & View All */}
                <div className="flex-1 flex justify-end gap-2 items-center">
                    <div className="flex gap-1.5 mr-3">
                        <button
                            onClick={() => setShowAddModal(true)}
                            title="태스크 추가"
                            className="w-9 h-9 rounded-full bg-surface-hover hover:bg-primary-50 hover:text-primary-600 flex items-center justify-center text-neutral-sub shadow-sm border border-neutral-divider transition-all"
                        >
                            <Plus size={16} />
                        </button>
                        <button
                            onClick={handleShare}
                            title="현황 복사"
                            className="w-9 h-9 rounded-full bg-surface-hover hover:bg-primary-50 hover:text-primary-600 flex items-center justify-center text-neutral-sub shadow-sm border border-neutral-divider transition-all relative"
                        >
                            <Share size={14} />
                            {shareToast && (
                                <span className="absolute -top-8 left-1/2 -translate-x-1/2 px-2 py-1 bg-gray-800 text-white text-[10px] rounded-lg whitespace-nowrap shadow">
                                    복사됨!
                                </span>
                            )}
                        </button>
                    </div>
                    <button
                        className="text-xs text-primary-600 hover:text-primary-700 font-bold whitespace-nowrap"
                        onClick={() => navigate('/tasks')}
                    >
                        View All &rarr;
                    </button>
                </div>
            </div>

            {/* Pipeline 칼럼 */}
            <div className="overflow-x-auto custom-scrollbar pb-2">
                <div className="flex items-start gap-4 min-w-[800px]">
                    {stageConfig.map((stage) => (
                        <div
                            key={stage.id}
                            className="flex-1 flex flex-col min-w-[220px]"
                            onDragOver={handleDragOver}
                            onDrop={(e) => handleDrop(e, stage.id)}
                        >
                            {/* Stage Header */}
                            <div className="flex items-center gap-2 mb-3 bg-surface-hover p-2.5 rounded-2xl shadow-sm border border-neutral-divider backdrop-blur-sm">
                                <stage.icon className={`${stage.color}`} size={16} />
                                <span className="font-bold text-sm text-neutral-main">{stage.label}</span>
                                <span className="ml-auto text-xs font-bold text-primary-700 dark:text-primary-300 bg-primary-50 dark:bg-primary-900/50 px-2.5 py-0.5 rounded-full">
                                    {tasks.filter(t => t.stage === stage.id).length}
                                </span>
                            </div>

                            {/* Task Cards Container */}
                            <div className={`flex-1 space-y-3 p-2 rounded-[1.5rem] bg-surface-main/40 border-2 transition-colors min-h-[150px] ${draggingId ? 'border-dashed border-primary-300 bg-primary-50/10' : 'border-transparent'}`}>
                                <AnimatePresence mode="popLayout">
                                    {tasks.filter(t => t.stage === stage.id).map((task) => (
                                        <motion.div
                                            key={task.id}
                                            layout
                                            initial={{ opacity: 0, scale: 0.95 }}
                                            animate={{ opacity: 1, scale: 1 }}
                                            exit={{ opacity: 0, scale: 0.9 }}
                                            transition={{ duration: 0.2 }}
                                            whileHover={{ scale: 1.02 }}
                                            draggable="true"
                                            onDragStart={(e) => handleDragStart(e, task.id)}
                                            onDragEnd={() => setDraggingId(null)}
                                            className={`bg-surface-card p-4 rounded-[1.5rem] border border-neutral-divider hover:border-primary-300 shadow-sm cursor-grab active:cursor-grabbing hover:shadow-md transition-all group ${draggingId === task.id ? 'opacity-50 scale-95' : ''}`}
                                        >
                                            <div className="flex justify-between items-start mb-2.5">
                                                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${priorityColors[task.priority] || priorityColors.medium}`}>
                                                    {(task.priority || 'medium').toUpperCase()}
                                                </span>
                                                <span className="text-xs text-neutral-muted font-mono font-bold tracking-tight">{`#${task.id}`}</span>
                                            </div>

                                            <h4 className="text-[13px] font-bold text-neutral-main leading-snug mb-4 group-hover:text-primary-600 transition-colors">
                                                {task.title}
                                            </h4>

                                            {/* Dependency Badge */}
                                            {task.dependency && (
                                                <div className="flex items-center gap-1.5 mb-4 bg-error-bg text-error px-2.5 py-1 rounded-xl border border-error-bg/50 shadow-sm">
                                                    <AlertTriangle size={12} />
                                                    <span className="text-[10px] font-bold truncate w-full" title={`대기중: ${task.dependency}`}>
                                                        Wait: {task.dependency}
                                                    </span>
                                                </div>
                                            )}

                                            <div
                                                className={`flex items-center justify-between mt-auto pt-3 border-t border-neutral-100 dark:border-white/10 rounded-xl px-1 -mx-1 ${task.assignee ? 'cursor-pointer hover:bg-primary-50/50 dark:hover:bg-white/[0.04] transition-colors' : ''}`}
                                                onClick={(e) => { if (task.assignee) { e.stopPropagation(); openProfile(task.assignee); } }}
                                            >
                                                <div className="flex items-center gap-2">
                                                    {task.assignee && (
                                                        <img
                                                            src={getAvatar(task.assignee)}
                                                            alt={task.assignee}
                                                            className="w-7 h-7 rounded-full border-2 border-surface-card shadow-sm"
                                                        />
                                                    )}
                                                    <span className="text-xs text-neutral-sub font-bold">{task.assignee || '미지정'}</span>
                                                </div>
                                                <ArrowRight size={16} className="text-neutral-muted" />
                                            </div>
                                        </motion.div>
                                    ))}
                                </AnimatePresence>

                                {tasks.filter(t => t.stage === stage.id).length === 0 && (
                                    <div className="h-20 flex items-center justify-center border-2 border-dashed border-neutral-divider rounded-[1.5rem]">
                                        <span className="text-[11px] font-bold text-neutral-muted uppercase tracking-widest">Empty</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Profile Popup */}
            <AnimatePresence>
                {profilePopup && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm"
                        onClick={() => setProfilePopup(null)}
                    >
                        <motion.div
                            initial={{ opacity: 0, scale: 0.9, y: 20 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.9, y: 20 }}
                            transition={{ type: 'spring', duration: 0.35 }}
                            className="bg-white dark:bg-gray-800 rounded-3xl shadow-2xl w-[340px] overflow-hidden"
                            onClick={(e) => e.stopPropagation()}
                        >
                            {/* Header banner */}
                            <div className="h-20 bg-gradient-to-br from-primary-400 to-accent-500 relative">
                                <button
                                    onClick={() => setProfilePopup(null)}
                                    className="absolute top-3 right-3 w-7 h-7 rounded-full bg-black/15 hover:bg-black/30 flex items-center justify-center text-neutral-700 dark:text-gray-200 transition-colors"
                                >
                                    <X size={14} />
                                </button>
                            </div>

                            {/* Avatar */}
                            <div className="flex justify-center -mt-10">
                                <img
                                    src={profilePopup.avatar || `https://api.dicebear.com/7.x/notionists/svg?seed=${encodeURIComponent(profilePopup.name)}`}
                                    alt={profilePopup.name}
                                    className="w-20 h-20 rounded-full border-4 border-white dark:border-gray-800 shadow-lg object-cover bg-white"
                                />
                            </div>

                            {/* Info */}
                            <div className="px-6 pt-3 pb-6 text-center">
                                <h3 className="text-lg font-bold text-neutral-main dark:text-white">{profilePopup.name}</h3>
                                {profilePopup.role && (
                                    <span className="inline-block mt-1 text-xs font-semibold text-primary-600 bg-primary-50 dark:bg-primary-900/30 dark:text-primary-300 px-3 py-0.5 rounded-full">
                                        {profilePopup.role}
                                    </span>
                                )}
                                {profilePopup.team && (
                                    <p className="text-xs text-neutral-muted mt-2">Team: {profilePopup.team}</p>
                                )}

                                <div className="mt-5 space-y-2.5 text-left">
                                    {profilePopup.email && (
                                        <div className="flex items-center gap-3 px-4 py-2.5 bg-neutral-50 dark:bg-gray-700/50 rounded-xl">
                                            <Mail size={14} className="text-neutral-400 shrink-0" />
                                            <span className="text-xs text-neutral-sub dark:text-gray-300 truncate">{profilePopup.email}</span>
                                        </div>
                                    )}
                                    {profilePopup.phone && (
                                        <div className="flex items-center gap-3 px-4 py-2.5 bg-neutral-50 dark:bg-gray-700/50 rounded-xl">
                                            <Phone size={14} className="text-neutral-400 shrink-0" />
                                            <span className="text-xs text-neutral-sub dark:text-gray-300">{profilePopup.phone}</span>
                                        </div>
                                    )}
                                </div>

                                {/* Task stats for this member */}
                                {(() => {
                                    const memberTasks = tasks.filter(t => t.assignee === profilePopup.name);
                                    if (memberTasks.length === 0) return null;
                                    const byStage = stageConfig.map(s => ({
                                        ...s,
                                        count: memberTasks.filter(t => t.stage === s.id).length
                                    }));
                                    return (
                                        <div className="mt-5 pt-4 border-t border-neutral-100 dark:border-gray-600">
                                            <p className="text-[11px] font-bold text-neutral-400 uppercase tracking-wider mb-3">담당 태스크</p>
                                            <div className="grid grid-cols-4 gap-2">
                                                {byStage.map(s => (
                                                    <div key={s.id} className="text-center">
                                                        <div className="text-lg font-extrabold text-neutral-main dark:text-white">{s.count}</div>
                                                        <div className="text-[10px] text-neutral-muted">{s.label}</div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    );
                                })()}
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Add Task Modal */}
            {showAddModal && createPortal(
                <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
                    <AnimatePresence>
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="absolute inset-0 bg-neutral-900/40 backdrop-blur-sm"
                            onClick={() => setShowAddModal(false)}
                        />
                    </AnimatePresence>
                    <motion.div
                        initial={{ scale: 0.95, opacity: 0, y: 20 }}
                        animate={{ scale: 1, opacity: 1, y: 0 }}
                        exit={{ scale: 0.95, opacity: 0, y: 20 }}
                        className="relative bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-[2.5rem] shadow-2xl p-8 w-full max-w-[420px] mx-4 border border-white/40 dark:border-white/10"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="flex items-center justify-between mb-8">
                            <div>
                                <h3 className="text-2xl font-black text-neutral-900 dark:text-white tracking-tighter">태스크 추가</h3>
                                <p className="text-xs text-neutral-400 font-bold mt-1">새로운 태스크를 생성합니다.</p>
                            </div>
                            <button onClick={() => setShowAddModal(false)} className="p-2 rounded-full hover:bg-neutral-100 dark:hover:bg-white/10 transition-colors">
                                <X size={20} className="text-neutral-400" />
                            </button>
                        </div>

                        <form onSubmit={handleAddTask} className="space-y-6">
                            <div className="space-y-2">
                                <label className="block text-[11px] font-black uppercase tracking-widest text-neutral-400 ml-1">태스크 제목</label>
                                <input
                                    type="text"
                                    value={addForm.title}
                                    onChange={(e) => setAddForm(p => ({ ...p, title: e.target.value }))}
                                    placeholder="무엇을 해야 하나요?"
                                    className="w-full px-5 py-3 rounded-xl border border-neutral-200 dark:border-white/10 bg-white/50 dark:bg-black/20 text-sm outline-none focus:ring-2 focus:ring-primary-500 transition-all placeholder:text-neutral-300"
                                    required
                                    autoFocus
                                />
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <label className="block text-[11px] font-black uppercase tracking-widest text-neutral-400 ml-1">담당자</label>
                                    <select
                                        value={addForm.assignee}
                                        onChange={(e) => setAddForm(p => ({ ...p, assignee: e.target.value }))}
                                        className="w-full px-4 py-3 rounded-xl border border-neutral-200 dark:border-white/10 bg-white/50 dark:bg-black/20 text-sm outline-none focus:ring-2 focus:ring-primary-500 transition-all appearance-none cursor-pointer"
                                    >
                                        <option value="">미지정</option>
                                        {members.map(m => (
                                            <option key={m.id} value={m.name}>{m.name}</option>
                                        ))}
                                    </select>
                                </div>
                                <div className="space-y-2">
                                    <label className="block text-[11px] font-black uppercase tracking-widest text-neutral-400 ml-1">우선순위</label>
                                    <select
                                        value={addForm.priority}
                                        onChange={(e) => setAddForm(p => ({ ...p, priority: e.target.value }))}
                                        className="w-full px-4 py-3 rounded-xl border border-neutral-200 dark:border-white/10 bg-white/50 dark:bg-black/20 text-sm outline-none focus:ring-2 focus:ring-primary-500 transition-all appearance-none cursor-pointer"
                                    >
                                        <option value="low">Low</option>
                                        <option value="medium">Medium</option>
                                        <option value="high">High</option>
                                    </select>
                                </div>
                            </div>
                            <div className="flex gap-3 pt-6">
                                <button
                                    type="button"
                                    onClick={() => setShowAddModal(false)}
                                    className="flex-1 py-4 text-xs font-black rounded-xl text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 transition-all"
                                >
                                    취소
                                </button>
                                <button
                                    type="submit"
                                    disabled={addSubmitting}
                                    className="flex-1 py-4 bg-neutral-900 dark:bg-white text-white dark:text-neutral-900 text-xs font-black rounded-xl shadow-xl hover:scale-105 active:scale-95 transition-all disabled:opacity-50"
                                >
                                    {addSubmitting ? '추가 중...' : '태스크 생성'}
                                </button>
                            </div>
                        </form>
                    </motion.div>
                </div>,
                document.body
            )}

            <div className="mt-5 flex items-center gap-3 bg-neutral-50/50 dark:bg-white/[0.05] p-3 rounded-2xl border border-neutral-100 dark:border-white/10">
                <div className="flex-1 h-1.5 bg-neutral-200/50 dark:bg-white/10 rounded-full overflow-hidden">
                    {(() => {
                        const doneCount = tasks.filter(t => t.stage === 'done').length;
                        const donePct = tasks.length > 0 ? (doneCount / tasks.length) * 100 : 0;
                        return (
                            <div
                                className="h-full bg-primary-500 dark:bg-primary-400 transition-all duration-700 ease-out"
                                style={{ width: `${donePct}%` }}
                            />
                        );
                    })()}
                </div>
                <span className="text-[11px] font-extrabold text-neutral-sub dark:text-neutral-300 whitespace-nowrap">
                    {tasks.length > 0 ? Math.round((tasks.filter(t => t.stage === 'done').length / tasks.length) * 100) : 0}% COMPLETE
                </span>
            </div>
        </div>
    );
}
