import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { RefreshCw, Plus, X } from 'lucide-react';
import useGoogleServices from '../../hooks/useGoogleServices';
import { TASK_STATUS_LABELS } from '../../utils/constants';
import { confirm } from '../../store/toastStore';

function TaskCreateModal({ onClose, onSubmit, submitting }) {
  const [formData, setFormData] = useState({ title: '', assignee: '', due_date: '', priority: 'medium' });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.title.trim()) return;
    onSubmit({
      title: formData.title.trim(),
      assignee: formData.assignee.trim() || null,
      due_date: formData.due_date || null,
      priority: formData.priority,
    });
  };

  return createPortal(
    <div className="fixed inset-0 z-[120] flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="absolute inset-0 bg-neutral-900/40 backdrop-blur-sm"
        onClick={onClose}
      />
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        className="relative bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-[2rem] shadow-2xl w-full max-w-[400px] p-8 mx-4 border border-white/40 dark:border-white/10"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-black text-neutral-900 dark:text-white tracking-tighter">New Task</h3>
          <button onClick={onClose} className="w-8 h-8 rounded-lg hover:bg-neutral-100 dark:hover:bg-white/5 text-neutral-400 transition-colors flex items-center justify-center">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-[11px] font-black uppercase tracking-wider text-neutral-400 mb-1.5 ml-1">Title</label>
            <input
              type="text"
              placeholder="What needs to be done?"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              className="w-full px-4 py-3 rounded-xl border border-neutral-200 dark:border-white/10 bg-white/50 dark:bg-black/20 text-sm focus:ring-2 focus:ring-primary-500 outline-none transition-all placeholder:text-neutral-300"
              autoFocus
              required
            />
          </div>
          <div>
            <label className="block text-[11px] font-black uppercase tracking-wider text-neutral-400 mb-1.5 ml-1">Assignee</label>
            <input
              type="text"
              placeholder="Who is responsible?"
              value={formData.assignee}
              onChange={(e) => setFormData({ ...formData, assignee: e.target.value })}
              className="w-full px-4 py-3 rounded-xl border border-neutral-200 dark:border-white/10 bg-white/50 dark:bg-black/20 text-sm focus:ring-2 focus:ring-primary-500 outline-none transition-all"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] font-black uppercase tracking-wider text-neutral-400 mb-1.5 ml-1">Due Date</label>
              <input
                type="date"
                value={formData.due_date}
                onChange={(e) => setFormData({ ...formData, due_date: e.target.value })}
                className="w-full px-4 py-3 rounded-xl border border-neutral-200 dark:border-white/10 bg-white/50 dark:bg-black/20 text-sm focus:ring-2 focus:ring-primary-500 outline-none transition-all"
              />
            </div>
            <div>
              <label className="block text-[11px] font-black uppercase tracking-wider text-neutral-400 mb-1.5 ml-1">Priority</label>
              <select
                value={formData.priority}
                onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
                className="w-full px-4 py-3 rounded-xl border border-neutral-200 dark:border-white/10 bg-white/50 dark:bg-black/20 text-sm focus:ring-2 focus:ring-primary-500 outline-none transition-all"
              >
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-4">
            <button type="button" onClick={onClose} className="px-6 py-2.5 text-xs font-black rounded-xl text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 transition-all">
              Cancel
            </button>
            <button type="submit" disabled={submitting} className="px-8 py-2.5 text-xs font-black rounded-xl bg-neutral-900 dark:bg-white text-white dark:text-neutral-900 shadow-xl hover:scale-105 transition-all">
              {submitting ? 'Creating...' : 'Create'}
            </button>
          </div>
        </form>
      </motion.div>
    </div>,
    document.body
  );
}

export default function TasksPanel({ externalActions, onReady }) {
  const { tasks, tasksLoading, tasksError, updateTask, pullTasks, hasScope, createTask, deleteTask } = useGoogleServices();
  const [filter, setFilter] = useState('all');
  const [showModal, setShowModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // 외부에서 모달/새로고침 트리거용 콜백 전달
  useEffect(() => {
    if (externalActions && onReady) {
      onReady({
        openCreate: () => setShowModal(true),
        refresh: () => pullTasks(),
        tasksLoading,
      });
    }
  }, [externalActions, onReady, tasksLoading]);

  if (!hasScope('tasks')) {
    return (
      <div className="card">
        <div className="card-header"><span className="card-title">Tasks</span></div>
        <div className="card-body text-center py-8">
          <p className="text-sm text-neutral-muted">Tasks가 연결되지 않았습니다</p>
          <p className="text-xs text-neutral-muted mt-1">Google 서비스 연결에서 Tasks를 활성화하세요</p>
        </div>
      </div>
    );
  }

  const filtered = (filter === 'all'
    ? [...tasks].sort((a, b) => a.completed - b.completed)
    : filter === 'pending'
      ? tasks.filter((t) => !t.completed)
      : tasks.filter((t) => t.completed));

  const handleCreate = async (data) => {
    setSubmitting(true);
    try {
      await createTask(data);
      setShowModal(false);
    } catch {
      // error is set in store
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (actionItemId) => {
    const ok = await confirm('이 Task를 삭제하시겠습니까?');
    if (!ok) return;
    try {
      await deleteTask(actionItemId);
    } catch {
      // error is set in store
    }
  };

  return (
    <div className="card">
      {showModal && (
        <TaskCreateModal
          onClose={() => setShowModal(false)}
          onSubmit={handleCreate}
          submitting={submitting}
        />
      )}

      <div className="card-header">
        <div className="flex items-center gap-2">
          <span className="card-title">Tasks</span>
          <span className="text-[0.6875rem] px-2 py-0.5 rounded-full bg-primary-50 text-primary-700 font-medium">
            {tasks.filter((t) => !t.completed).length}개 미완료
          </span>
        </div>
        {!externalActions && (
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowModal(true)}
              className="btn-outline flex items-center gap-1.5"
            >
              <Plus size={14} />
              추가
            </button>
            <button
              onClick={() => pullTasks()}
              disabled={tasksLoading}
              className="btn-outline flex items-center gap-1.5"
              title="새로고침"
            >
              <RefreshCw size={14} className={tasksLoading ? 'animate-spin' : ''} />
              {tasksLoading ? '동기화 중...' : '새로고침'}
            </button>
          </div>
        )}
      </div>

      <div className="px-5 pt-2 flex gap-1">
        {[
          { key: 'all', label: '전체' },
          { key: 'pending', label: '미완료' },
          { key: 'completed', label: '완료' },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`px-3 py-1 rounded-md text-xs font-medium transition ${filter === key ? 'bg-primary-50 text-primary-700 font-semibold' : 'text-neutral-muted hover:bg-surface-hover'
              }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="card-body">
        {tasksError && <p className="text-xs text-error mb-3">{tasksError}</p>}

        {filtered.length === 0 ? (
          <p className="text-sm text-neutral-muted text-center py-6">할 일이 없습니다</p>
        ) : (
          <ul className="space-y-2">
            {filtered.map((task) => (
              <li
                key={task.action_item_id || task.id}
                className="flex items-center gap-3 px-3 py-2.5 rounded-md border border-neutral-divider hover:border-primary-300 transition"
              >
                <input
                  type="checkbox"
                  checked={task.completed || false}
                  onChange={(e) => updateTask(task.action_item_id || task.id, e.target.checked)}
                  className="w-4 h-4 rounded border-neutral-border text-primary-700 focus:ring-primary-500"
                />
                <div className="flex-1 min-w-0">
                  <p className={`text-sm truncate ${task.completed ? 'text-neutral-muted line-through' : 'text-neutral-main'}`}>
                    {task.title}
                  </p>
                  {task.assignee && (
                    <span className="text-[0.6875rem] text-neutral-muted">{task.assignee}</span>
                  )}
                </div>
                {task.deadline && (
                  <span className="text-[0.6875rem] text-neutral-muted whitespace-nowrap">{task.deadline}</span>
                )}
                <span className={`text-[0.625rem] px-2 py-0.5 rounded-full font-medium ${task.completed ? 'bg-success-bg text-success' : 'bg-warning-bg text-warning'
                  }`}>
                  {TASK_STATUS_LABELS[task.status] || (task.completed ? '완료' : '미완료')}
                </span>
                <button
                  onClick={() => handleDelete(task.action_item_id)}
                  className="text-neutral-muted hover:text-error transition p-1 rounded"
                  title="삭제"
                >
                  <X size={14} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
