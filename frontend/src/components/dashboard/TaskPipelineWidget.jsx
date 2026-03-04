import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
    GitMerge, Clock, CheckCircle2, AlertTriangle,
    ArrowRight, Plus, Share
} from 'lucide-react';
import { listPipelineTasks, updatePipelineTask } from '../../api/tasks';

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

    const fetchTasks = async () => {
        try {
            const res = await listPipelineTasks();
            setTasks(Array.isArray(res.data) ? res.data : []);
        } catch (err) {
            console.error('Failed to fetch pipeline tasks', err);
        }
    };

    useEffect(() => { fetchTasks(); }, []);

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
    const teamStats = [...new Map(tasks.filter(t => t.assignee).map(t => [t.assignee, t])).values()].map(t => ({
        name: t.assignee,
        avatar: t.assigneeAvatar || `https://api.dicebear.com/7.x/notionists/svg?seed=${encodeURIComponent(t.assignee)}`,
        count: tasks.filter(task => task.assignee === t.assignee).length
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
                    <div className="absolute left-1/2 -translate-x-1/2 flex items-center bg-white/50 backdrop-blur-md px-5 py-2 rounded-full border border-white/30 shadow-sm gap-2.5">
                        {teamStats.map((member, i) => (
                            <div key={member.name} className="relative group" style={{ zIndex: teamStats.length - i }}>
                                <img
                                    src={member.avatar}
                                    alt={member.name}
                                    className="w-9 h-9 rounded-full border-2 border-white shadow-sm transition-transform group-hover:scale-110 cursor-pointer"
                                    title={member.name}
                                />
                                <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 min-w-[18px] h-[18px] px-1 rounded-full bg-accent-500 flex items-center justify-center text-[9px] font-bold text-white border border-white shadow-sm">
                                    {member.count}
                                </div>
                            </div>
                        ))}
                        <button className="w-9 h-9 rounded-full bg-white/40 hover:bg-white flex items-center justify-center text-neutral-400 transition-colors shadow-sm border border-white/20">
                            <Plus size={16} />
                        </button>
                    </div>
                )}

                {/* Right: Utility Buttons & View All */}
                <div className="flex-1 flex justify-end gap-2 items-center">
                    <div className="flex gap-1.5 mr-3">
                        <button className="w-9 h-9 rounded-full bg-white/40 hover:bg-white flex items-center justify-center text-neutral-500 shadow-sm border border-white/20 transition-all">
                            <Plus size={16} />
                        </button>
                        <button className="w-9 h-9 rounded-full bg-white/40 hover:bg-white flex items-center justify-center text-neutral-500 shadow-sm border border-white/20 transition-all">
                            <Share size={14} />
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
                            <div className="flex items-center gap-2 mb-3 bg-white/60 p-2.5 rounded-2xl shadow-sm border border-white/40 backdrop-blur-sm">
                                <stage.icon className={`${stage.color}`} size={16} />
                                <span className="font-bold text-sm text-neutral-main">{stage.label}</span>
                                <span className="ml-auto text-xs font-bold text-primary-700 bg-primary-50 px-2.5 py-0.5 rounded-full">
                                    {tasks.filter(t => t.stage === stage.id).length}
                                </span>
                            </div>

                            {/* Task Cards Container */}
                            <div className={`flex-1 space-y-3 p-2 rounded-[1.5rem] bg-white/20 border-2 transition-colors min-h-[150px] ${draggingId ? 'border-dashed border-primary-100 bg-primary-50/10' : 'border-transparent'}`}>
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
                                            className={`bg-white p-4 rounded-[1.5rem] border border-transparent hover:border-primary-100 shadow-sm cursor-grab active:cursor-grabbing hover:shadow-md transition-all group ${draggingId === task.id ? 'opacity-50 scale-95' : ''}`}
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

                                            <div className="flex items-center justify-between mt-auto pt-3 border-t border-neutral-50">
                                                <div className="flex items-center gap-2">
                                                    {task.assignee && (
                                                        <img
                                                            src={task.assigneeAvatar || `https://api.dicebear.com/7.x/notionists/svg?seed=${encodeURIComponent(task.assignee)}`}
                                                            alt={task.assignee}
                                                            className="w-7 h-7 rounded-full border-2 border-white shadow-sm"
                                                        />
                                                    )}
                                                    <span className="text-xs text-neutral-sub font-bold">{task.assignee || '미지정'}</span>
                                                </div>
                                                <button className="text-neutral-muted hover:text-primary-500 transition-colors">
                                                    <ArrowRight size={16} />
                                                </button>
                                            </div>
                                        </motion.div>
                                    ))}
                                </AnimatePresence>

                                {tasks.filter(t => t.stage === stage.id).length === 0 && (
                                    <div className="h-20 flex items-center justify-center border-2 border-dashed border-neutral-100 rounded-[1.5rem]">
                                        <span className="text-[11px] font-bold text-neutral-300 uppercase tracking-widest">Empty</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            <div className="mt-5 flex items-center gap-3 bg-neutral-50/50 p-3 rounded-2xl border border-neutral-100">
                <div className="flex-1 h-1.5 bg-neutral-200/50 rounded-full overflow-hidden">
                    {(() => {
                        const doneCount = tasks.filter(t => t.stage === 'done').length;
                        const donePct = tasks.length > 0 ? (doneCount / tasks.length) * 100 : 0;
                        return (
                            <div
                                className="h-full bg-primary-500 transition-all duration-700 ease-out"
                                style={{ width: `${donePct}%` }}
                            />
                        );
                    })()}
                </div>
                <span className="text-[11px] font-extrabold text-neutral-400 whitespace-nowrap">
                    {tasks.length > 0 ? Math.round((tasks.filter(t => t.stage === 'done').length / tasks.length) * 100) : 0}% COMPLETE
                </span>
            </div>
        </div>
    );
}
