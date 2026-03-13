import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { GitMerge, Clock, CheckCircle2, AlertTriangle, Plus, Trash2, X, Pencil } from 'lucide-react';
import { listPipelineTasks, createPipelineTask, updatePipelineTask, deletePipelineTask } from '../api/tasks';
import client from '../api/client';

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
  { id: 'todo', label: 'To Do', icon: Clock, color: 'text-neutral-muted', headerBg: 'bg-surface-sub dark:bg-surface-sub' },
  { id: 'in_progress', label: 'In Progress', icon: GitMerge, color: 'text-primary-500', headerBg: 'bg-primary-50/60 dark:bg-primary-900/20' },
  { id: 'review', label: 'Review', icon: AlertTriangle, color: 'text-orange-500', headerBg: 'bg-orange-50/60 dark:bg-orange-900/20' },
  { id: 'done', label: 'Done', icon: CheckCircle2, color: 'text-success', headerBg: 'bg-green-50/60 dark:bg-green-900/20' },
];

const EMPTY_FORM = { title: '', description: '', assignee: '', dueDate: '', priority: 'medium', tags: '' };
const INPUT_CLS = 'w-full px-3 py-2 border border-neutral-border rounded-lg bg-surface-card text-neutral-main focus:outline-none focus:ring-2 focus:ring-primary-500';

export default function TasksPage() {
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
      return { text: dueDate, cls: 'text-neutral-muted' };
    }
    const diff = Math.ceil((new Date(dueDate) - new Date()) / 86400000);
    if (diff < 0) return { text: `${Math.abs(diff)}일 초과`, cls: 'text-red-500' };
    if (diff <= 2) return { text: `D-${diff}`, cls: 'text-orange-500 font-bold' };
    return { text: dueDate, cls: 'text-neutral-muted' };
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-neutral-main">Task Pipeline</h1>
          <p className="text-sm text-neutral-sub mt-1">팀 프로젝트 진행 현황을 한눈에 관리하세요</p>
        </div>
        <button onClick={openCreate} className="btn-primary">
          <Plus size={16} />
          태스크 추가
        </button>
      </div>

      {/* Kanban Board */}
      {loading ? (
        <div className="flex items-center justify-center h-64 text-neutral-sub">로딩 중...</div>
      ) : (
        <div className="grid grid-cols-4 gap-4">
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
                <div className={`flex items-center gap-2 mb-3 bg-white/20 dark:bg-white/5 p-2.5 rounded-2xl shadow-sm border border-white/20 dark:border-white/10 backdrop-blur-md`}>
                  <stage.icon className={stage.color} size={18} />
                  <span className="font-bold text-sm text-neutral-main">{stage.label}</span>
                  <span className="ml-auto text-xs font-bold text-primary-700 dark:text-primary-300 bg-primary-50 dark:bg-primary-900/50 px-2.5 py-0.5 rounded-full">
                    {stageTasks.length}
                  </span>
                </div>

                <div className={`flex-1 space-y-3 p-3 rounded-xl transition-all duration-200 ${isOver ? 'bg-primary-50/40 dark:bg-primary-900/10 border-2 border-dashed border-primary-300' : 'bg-surface-sub/30 border-2 border-transparent'}`}>
                  <AnimatePresence>
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
                          className={`bg-white/40 dark:bg-white/[0.05] backdrop-blur-md p-4 rounded-xl border border-white/20 dark:border-white/10 shadow-sm cursor-grab active:cursor-grabbing hover:shadow-md transition-all group ${draggingId === task.id ? 'opacity-40 scale-95' : ''}`}
                        >
                          <div className="flex justify-between items-start mb-2">
                            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${priorityColors[task.priority] || priorityColors.medium}`}>
                              {(task.priority || 'medium').toUpperCase()}
                            </span>
                            <div className="flex items-center gap-1">
                              <button
                                onClick={(e) => { e.stopPropagation(); openEdit(task); }}
                                className="opacity-0 group-hover:opacity-100 p-1 rounded-lg hover:bg-blue-50 dark:hover:bg-blue-900/30 text-neutral-muted hover:text-blue-500 transition-all"
                                title="수정"
                              >
                                <Pencil size={13} />
                              </button>
                              <button
                                onClick={(e) => handleDelete(e, task.id)}
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

                          {task.tags?.length > 0 && (
                            <div className="flex flex-wrap gap-1 mb-3">
                              {task.tags.map(tag => (
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
                            {due && <span className={`text-[10px] font-medium ${due.cls}`}>{due.text}</span>}
                          </div>
                        </motion.div>
                      );
                    })}
                  </AnimatePresence>

                  {stageTasks.length === 0 && (
                    <div className={`h-24 flex items-center justify-center border-2 border-dashed rounded-xl transition-colors ${isOver ? 'border-primary-400 bg-primary-50/30' : 'border-neutral-border'}`}>
                      <span className="text-xs font-medium text-neutral-muted">드래그하여 이동</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Modal ── */}
      <AnimatePresence>
        {showModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
            onClick={closeModal}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              transition={{ duration: 0.2 }}
              className="relative bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-3xl shadow-2xl w-full max-w-md p-8 border border-white/40 dark:border-white/10"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-8">
                <h2 className="text-2xl font-black text-neutral-900 dark:text-white tracking-tighter">
                  {editingTask ? '태스크 수정' : '태스크 추가'}
                </h2>
                <button onClick={closeModal} className="p-2 rounded-full hover:bg-neutral-100 dark:hover:bg-white/10 transition-colors">
                  <X size={20} className="text-neutral-400" />
                </button>
              </div>
              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="space-y-2">
                  <label className="block text-[11px] font-black uppercase tracking-widest text-neutral-400 ml-1">제목 *</label>
                  <input
                    type="text"
                    value={form.title}
                    onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                    className="w-full px-5 py-3 rounded-xl border border-neutral-200 dark:border-white/10 bg-white/50 dark:bg-black/20 text-sm outline-none focus:ring-2 focus:ring-primary-500 transition-all placeholder:text-neutral-300 dark:text-white"
                    placeholder="태스크 제목을 입력하세요"
                    required
                    autoFocus
                  />
                </div>
                <div className="space-y-2">
                  <label className="block text-[11px] font-black uppercase tracking-widest text-neutral-400 ml-1">설명</label>
                  <textarea
                    value={form.description}
                    onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                    rows={3}
                    className="w-full px-5 py-3 rounded-xl border border-neutral-200 dark:border-white/10 bg-white/50 dark:bg-black/20 text-sm outline-none focus:ring-2 focus:ring-primary-500 transition-all placeholder:text-neutral-300 dark:text-white resize-none"
                    placeholder="태스크에 대한 설명"
                  />
                </div>

                {/* 담당자 선택 */}
                <div className="space-y-2">
                  <label className="block text-[11px] font-black uppercase tracking-widest text-neutral-400 ml-1">담당자</label>
                  <div className="flex flex-wrap gap-2">
                    {members.length === 0 && (
                      <span className="text-xs text-neutral-muted">팀원이 없습니다</span>
                    )}
                    {members.map((m) => {
                      const selected = form.assignee === m.name;
                      const avatarSrc = m.avatar || `https://api.dicebear.com/7.x/notionists/svg?seed=${encodeURIComponent(m.name)}`;
                      return (
                        <button
                          key={m.id}
                          type="button"
                          onClick={() => setForm(f => ({ ...f, assignee: selected ? '' : m.name }))}
                          className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${selected
                            ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/30 text-primary-700 dark:text-primary-300 ring-1 ring-primary-300'
                            : 'border-neutral-border text-neutral-sub hover:border-neutral-muted dark:bg-white/5'
                            }`}
                        >
                          <img src={avatarSrc} alt={m.name} className="w-5 h-5 rounded-full bg-surface-card" />
                          <span>{m.name}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="block text-[11px] font-black uppercase tracking-widest text-neutral-400 ml-1">우선순위</label>
                    <select
                      value={form.priority}
                      onChange={e => setForm(f => ({ ...f, priority: e.target.value }))}
                      className="w-full px-4 py-3 rounded-xl border border-neutral-200 dark:border-white/10 bg-white/50 dark:bg-black/20 text-sm outline-none focus:ring-2 focus:ring-primary-500 transition-all dark:text-white appearance-none cursor-pointer"
                    >
                      <option value="high">높음</option>
                      <option value="medium">보통</option>
                      <option value="low">낮음</option>
                    </select>
                  </div>
                  <div className="space-y-2">
                    <label className="block text-[11px] font-black uppercase tracking-widest text-neutral-400 ml-1">마감일</label>
                    <input
                      type="date"
                      value={form.dueDate}
                      onChange={e => setForm(f => ({ ...f, dueDate: e.target.value }))}
                      className="w-full px-4 py-3 rounded-xl border border-neutral-200 dark:border-white/10 bg-white/50 dark:bg-black/20 text-sm outline-none focus:ring-2 focus:ring-primary-500 transition-all dark:text-white"
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="block text-[11px] font-black uppercase tracking-widest text-neutral-400 ml-1">태그</label>
                  <input
                    type="text"
                    value={form.tags}
                    onChange={e => setForm(f => ({ ...f, tags: e.target.value }))}
                    className="w-full px-5 py-3 rounded-xl border border-neutral-200 dark:border-white/10 bg-white/50 dark:bg-black/20 text-sm outline-none focus:ring-2 focus:ring-primary-500 transition-all placeholder:text-neutral-300 dark:text-white"
                    placeholder="Frontend, API (쉼표로 구분)"
                  />
                </div>
                <div className="flex gap-3 pt-6">
                  <button
                    type="button"
                    onClick={closeModal}
                    className="flex-1 py-4 text-xs font-black rounded-xl text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 transition-all"
                  >
                    취소
                  </button>
                  <button
                    type="submit"
                    className="flex-1 py-4 bg-primary-700 text-white text-xs font-black rounded-xl shadow-xl hover:bg-primary-900 hover:scale-105 active:scale-95 transition-all"
                  >
                    {editingTask ? '저장' : '추가'}
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
