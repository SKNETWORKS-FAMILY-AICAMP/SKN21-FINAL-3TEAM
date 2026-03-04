import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { GitMerge, Clock, CheckCircle2, AlertTriangle, ChevronUp, ChevronDown } from 'lucide-react';
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
    const [tasks, setTasks] = useState([]);
    const [draggingId, setDraggingId] = useState(null);
    const [isCollapsed, setIsCollapsed] = useState(false);
    const navigate = useNavigate();

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

    return (
        <div className="card flex flex-col overflow-hidden p-6 shadow-soft transition-all duration-300">
            <div
                className="flex items-center justify-between mb-4 cursor-pointer"
                onClick={() => setIsCollapsed(!isCollapsed)}
            >
                <h3 className="text-xl font-bold text-neutral-main">Task Pipeline</h3>
                <div className="flex items-center gap-3">
                    <button
                        className="text-xs text-primary-600 hover:text-primary-700 font-bold"
                        onClick={(e) => { e.stopPropagation(); navigate('/tasks'); }}
                    >
                        View All Tasks &rarr;
                    </button>
                    <button className="text-neutral-muted hover:text-primary-500 transition-colors p-1 rounded-full hover:bg-surface-hover">
                        {isCollapsed ? <ChevronDown size={20} /> : <ChevronUp size={20} />}
                    </button>
                </div>
            </div>

            <div className="overflow-x-auto custom-scrollbar pb-2">
                <div className="flex items-start gap-4 min-w-[800px]">
                    {stageConfig.map((stage) => (
                        <div
                            key={stage.id}
                            className="flex-1 flex flex-col min-w-[220px]"
                            onDragOver={handleDragOver}
                            onDrop={(e) => handleDrop(e, stage.id)}
                        >
                            <div className="flex items-center gap-2 mb-2 bg-white p-2.5 rounded-2xl shadow-sm border border-neutral-100">
                                <stage.icon className={stage.color} size={16} />
                                <span className="font-bold text-sm text-neutral-main">{stage.label}</span>
                                <span className="ml-auto text-xs font-bold text-primary-700 bg-primary-50 px-2.5 py-0.5 rounded-full">
                                    {tasks.filter(t => t.stage === stage.id).length}
                                </span>
                            </div>

                            <div className={`flex-1 space-y-2.5 p-2 rounded-[1.5rem] bg-white/40 border-2 transition-colors ${draggingId ? 'border-dashed border-primary-100 bg-primary-50/20' : 'border-transparent'}`}>
                                <AnimatePresence>
                                    {tasks.filter(t => t.stage === stage.id).slice(0, isCollapsed ? 1 : 999).map((task) => (
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
                                            className={`bg-white p-3.5 rounded-3xl border border-transparent hover:border-primary-200 shadow-sm cursor-grab active:cursor-grabbing hover:shadow-soft transition-all group ${draggingId === task.id ? 'opacity-50 scale-95' : ''}`}
                                        >
                                            <div className="flex justify-between items-start mb-2">
                                                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${priorityColors[task.priority] || priorityColors.medium}`}>
                                                    {(task.priority || 'medium').toUpperCase()}
                                                </span>
                                            </div>

                                            <h4 className="text-[13px] font-bold text-neutral-main leading-snug mb-3 group-hover:text-primary-600 transition-colors">
                                                {task.title}
                                            </h4>

                                            <div className="flex items-center justify-between mt-auto pt-2 border-t border-neutral-100">
                                                <div className="flex items-center gap-2">
                                                    {task.assignee && (
                                                        <img
                                                            src={`https://api.dicebear.com/7.x/notionists/svg?seed=${encodeURIComponent(task.assignee)}`}
                                                            alt={task.assignee}
                                                            className="w-6 h-6 rounded-full border border-neutral-200 bg-white"
                                                        />
                                                    )}
                                                    <span className="text-xs text-neutral-sub font-bold">{task.assignee || '미지정'}</span>
                                                </div>
                                                {task.dueDate && (
                                                    <span className="text-[10px] text-neutral-muted">{task.dueDate}</span>
                                                )}
                                            </div>
                                        </motion.div>
                                    ))}
                                </AnimatePresence>

                                {tasks.filter(t => t.stage === stage.id).length === 0 && !isCollapsed && (
                                    <div className="h-20 flex items-center justify-center border-2 border-dashed border-neutral-200 rounded-2xl">
                                        <span className="text-[11px] font-bold text-neutral-muted">드래그하여 항목 추가</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
