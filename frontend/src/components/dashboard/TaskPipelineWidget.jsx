import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { GitMerge, Clock, CheckCircle2, AlertTriangle, ArrowRight, ChevronUp, ChevronDown } from 'lucide-react';

const mockTasks = [
    { id: 101, title: '디자인 시스템 리뉴얼', stage: 'todo', assigneeName: 'Brooklyn', assigneeAvatar: 'https://i.pravatar.cc/150?u=1', priority: 'high', dependency: null },
    { id: 102, title: '메인보드 UI 컴포넌트 개발', stage: 'inProgress', assigneeName: 'Cody', assigneeAvatar: 'https://i.pravatar.cc/150?u=2', priority: 'medium', dependency: '#101 디자인 리뉴얼' },
    { id: 103, title: '사용자 프로필 페이지 수정', stage: 'review', assigneeName: 'Ralph', assigneeAvatar: 'https://i.pravatar.cc/150?u=3', priority: 'low', dependency: null },
    { id: 104, title: '결제 모듈 연동 테스트', stage: 'done', assigneeName: 'Eleanor', assigneeAvatar: 'https://i.pravatar.cc/150?u=4', priority: 'high', dependency: null },
];

const priorityColors = {
    high: 'bg-error-bg text-error dark:bg-red-900/40 dark:text-red-400',
    medium: 'bg-warning-bg text-warning dark:bg-orange-900/40 dark:text-orange-400',
    low: 'bg-success-bg text-success dark:bg-green-900/40 dark:text-green-400',
};

const stageConfig = [
    { id: 'todo', label: 'To Do', icon: Clock, color: 'text-neutral-500' },
    { id: 'inProgress', label: 'In Progress', icon: GitMerge, color: 'text-primary-500' },
    { id: 'review', label: 'Review', icon: AlertTriangle, color: 'text-orange-500' },
    { id: 'done', label: 'Done', icon: CheckCircle2, color: 'text-success' },
];

export default function TaskPipelineWidget() {
    const navigate = useNavigate();
    const [tasks, setTasks] = useState(mockTasks);
    const [draggingId, setDraggingId] = useState(null);
    const [isCollapsed, setIsCollapsed] = useState(false);

    const handleDragStart = (e, id) => {
        setDraggingId(id);
        e.dataTransfer.effectAllowed = 'move';
        // Required for Firefox
        e.dataTransfer.setData('text/plain', id.toString());
    };

    const handleDragOver = (e) => {
        e.preventDefault(); // allow drop
        e.dataTransfer.dropEffect = 'move';
    };

    const handleDrop = (e, stageId) => {
        e.preventDefault();
        if (draggingId) {
            setTasks(prev => prev.map(t => t.id === draggingId ? { ...t, stage: stageId } : t));
            setDraggingId(null);
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
                        onClick={(e) => { e.stopPropagation(); navigate('/schedules?tab=tasks'); }}
                    >
                        View All Tasks &rarr;
                    </button>
                    <button className="text-neutral-muted hover:text-primary-500 transition-colors p-1 rounded-full hover:bg-surface-hover">
                        {isCollapsed ? <ChevronDown size={20} /> : <ChevronUp size={20} />}
                    </button>
                </div>
            </div>

            {/* Horizontal Scroll Area */}
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
                            <div className="flex items-center gap-2 mb-2 bg-white p-2.5 rounded-2xl shadow-sm border border-neutral-100">
                                <stage.icon className={`${stage.color}`} size={16} />
                                <span className="font-bold text-sm text-neutral-main">{stage.label}</span>
                                <span className="ml-auto text-xs font-bold text-primary-700 bg-primary-50 px-2.5 py-0.5 rounded-full">
                                    {tasks.filter(t => t.stage === stage.id).length}
                                </span>
                            </div>

                            {/* Task Cards Container */}
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
                                                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${priorityColors[task.priority]}`}>
                                                    {task.priority.toUpperCase()}
                                                </span>
                                                <span className="text-xs text-neutral-muted font-mono font-bold">{`#${task.id}`}</span>
                                            </div>

                                            <h4 className="text-[13px] font-bold text-neutral-main leading-snug mb-3 group-hover:text-primary-600 transition-colors">
                                                {task.title}
                                            </h4>

                                            {/* Dependency Badge */}
                                            {task.dependency && (
                                                <div className="flex items-center gap-1 mb-3 bg-error-bg text-error px-2 py-1 rounded-xl border border-error-bg shadow-sm">
                                                    <AlertTriangle size={12} />
                                                    <span className="text-[10px] font-bold truncate w-full" title={`대기중: ${task.dependency}`}>
                                                        Wait: {task.dependency}
                                                    </span>
                                                </div>
                                            )}

                                            <div className="flex items-center justify-between mt-auto pt-2 border-t border-neutral-100">
                                                <div className="flex items-center gap-2">
                                                    <img src={task.assigneeAvatar} alt={task.assigneeName} className="w-7 h-7 rounded-full border-2 border-white shadow-sm" />
                                                    <span className="text-xs text-neutral-sub font-bold">{task.assigneeName}</span>
                                                </div>
                                                <button className="text-neutral-muted hover:text-primary-500 transition-colors">
                                                    <ArrowRight size={16} />
                                                </button>
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
