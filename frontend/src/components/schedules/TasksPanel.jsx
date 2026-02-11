import { useState } from 'react';
import useGoogleServices from '../../hooks/useGoogleServices';
import { TASK_STATUS_LABELS } from '../../utils/constants';

export default function TasksPanel() {
  const { tasks, tasksLoading, tasksError, updateTask, syncTasks, pullTasks, hasScope } = useGoogleServices();
  const [filter, setFilter] = useState('all');

  if (!hasScope('tasks')) {
    return (
      <div className="card">
        <div className="card-header"><span className="card-title">Google Tasks</span></div>
        <div className="card-body text-center py-8">
          <p className="text-sm text-neutral-muted">Google Tasks가 연결되지 않았습니다</p>
          <p className="text-xs text-neutral-muted mt-1">Google 서비스 연결에서 Tasks를 활성화하세요</p>
        </div>
      </div>
    );
  }

  const filtered = filter === 'all'
    ? tasks
    : filter === 'pending'
      ? tasks.filter((t) => !t.completed)
      : tasks.filter((t) => t.completed);

  return (
    <div className="card">
      <div className="card-header">
        <div className="flex items-center gap-2">
          <span className="card-title">Google Tasks</span>
          <span className="text-[0.6875rem] px-2 py-0.5 rounded-full bg-primary-50 text-primary-700 font-medium">
            {tasks.filter((t) => !t.completed).length}개 미완료
          </span>
        </div>
        <div className="flex gap-1.5">
          <button
            onClick={() => syncTasks()}
            disabled={tasksLoading}
            className="text-xs px-2.5 py-1.5 rounded-md border border-neutral-border text-neutral-sub hover:bg-primary-50 hover:text-primary-700 transition"
          >
            {tasksLoading ? '동기화 중...' : 'Push'}
          </button>
          <button
            onClick={() => pullTasks()}
            disabled={tasksLoading}
            className="text-xs px-2.5 py-1.5 rounded-md border border-neutral-border text-neutral-sub hover:bg-primary-50 hover:text-primary-700 transition"
          >
            Pull
          </button>
        </div>
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
            className={`px-3 py-1 rounded-md text-xs font-medium transition ${
              filter === key ? 'bg-primary-50 text-primary-700 font-semibold' : 'text-neutral-muted hover:bg-surface-hover'
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
                <span className={`text-[0.625rem] px-2 py-0.5 rounded-full font-medium ${
                  task.completed ? 'bg-success-bg text-success' : 'bg-warning-bg text-warning'
                }`}>
                  {TASK_STATUS_LABELS[task.status] || (task.completed ? '완료' : '미완료')}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
