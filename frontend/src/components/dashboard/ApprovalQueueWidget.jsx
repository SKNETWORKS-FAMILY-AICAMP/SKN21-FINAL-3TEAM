import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { createPortal } from 'react-dom';
import {
  Check, X, Clock, AlertTriangle, UserX, CalendarClock, ClipboardList,
  ChevronUp, ChevronDown, ArrowRight, Plus, Paperclip, ExternalLink,
  Coffee, FileSignature, HelpCircle, FileText, GitPullRequest,
  Home, DoorOpen, Palette, Award, Receipt, Rocket, Server, ShieldCheck
} from 'lucide-react';
import { listPipelineTasks } from '../../api/tasks';
import { listApprovals, createApproval, approveRequest, rejectRequest, seedApprovals } from '../../api/approvals';
import { getAllMembers } from '../../api/auth';
import client from '../../api/client';
import useAuthStore from '../../store/authStore';
import MemberDropdown from '../common/MemberDropdown';

const TEAMS = ['개발', 'QA기획', 'UI/UX', '영업', '마케팅', 'CS'];

/**
 * Needs Attention 위젯
 * - category: 'approval' → 결재/승인 요청 (Approve/Reject 버튼, 백엔드 연동)
 * - category: 'task'     → 파이프라인 태스크 알림 (태스크 보기/확인 완료 버튼)
 */

const typeConfig = {
  leave: { icon: Coffee, color: 'text-orange-500 bg-orange-100 dark:bg-orange-900/30', label: '연차/반차 신청' },
  remote: { icon: Home, color: 'text-teal-500 bg-teal-100 dark:bg-teal-900/30', label: '재택근무 신청' },
  room: { icon: DoorOpen, color: 'text-indigo-500 bg-indigo-100 dark:bg-indigo-900/30', label: '회의실 예약' },
  design: { icon: Palette, color: 'text-pink-500 bg-pink-100 dark:bg-pink-900/30', label: '디자인 에셋 요청' },
  certificate: { icon: Award, color: 'text-yellow-500 bg-yellow-100 dark:bg-yellow-900/30', label: '증명서 발급 요청' },
  budget: { icon: Receipt, color: 'text-purple-500 bg-purple-100 dark:bg-purple-900/30', label: '결재 요청' },
  review: { icon: GitPullRequest, color: 'text-blue-500 bg-blue-100 dark:bg-blue-900/30', label: 'PR 리뷰 요청' },
  deploy: { icon: Rocket, color: 'text-green-500 bg-green-100 dark:bg-green-900/30', label: '배포 승인 요청' },
  infra: { icon: Server, color: 'text-slate-500 bg-slate-100 dark:bg-slate-900/30', label: '인프라/권한 신청' },
  security: { icon: ShieldCheck, color: 'text-red-500 bg-red-100 dark:bg-red-900/30', label: '보안 예외 처리' },
};

const defaultTypeConfig = { icon: FileSignature, color: 'text-neutral-sub bg-surface-sub', label: '요청' };

export default function ApprovalQueueWidget() {
  const navigate = useNavigate();
  const currentUser = useAuthStore((s) => s.user);
  const [items, setItems] = useState([]);
  const [dismissed, setDismissed] = useState([]);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [members, setMembers] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [formData, setFormData] = useState({ type: 'leave', title: '', detail: '', target_team: '', target_user_id: '' });
  const [formFile, setFormFile] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [allMembers, setAllMembers] = useState([]);

  useEffect(() => {
    client.get('/auth/team-members')
      .then(res => setMembers(res.data || []))
      .catch(() => { });
    getAllMembers()
      .then(res => setAllMembers(res.data || []))
      .catch(() => { });
  }, []);

  const loadApprovals = async (trySeed = false) => {
    try {
      if (trySeed) {
        try { await seedApprovals(); } catch { }
      }
      const res = await client.get('/approvals/', { params: { status: 'pending' } });
      const approvals = (Array.isArray(res.data) ? res.data : []).map(a => {
        const cfg = typeConfig[a.type] || defaultTypeConfig;
        return {
          id: `approval-${a.id}`,
          backendId: a.id,
          category: 'approval',
          type: a.type,
          icon: cfg.icon,
          color: cfg.color,
          title: a.title,
          requester: a.requester_name || '알 수 없음',
          detail: a.detail || '',
          avatar: a.requester_avatar || `https://api.dicebear.com/7.x/notionists/svg?seed=${encodeURIComponent(a.requester_name || 'unknown')}`,
          priority: 2,
          created_at: a.created_at,
        };
      });
      return approvals;
    } catch {
      return [];
    }
  };

  const loadTaskAlerts = async () => {
    try {
      const res = await listPipelineTasks();
      const tasks = Array.isArray(res.data) ? res.data : [];
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      const alerts = [];
      const myName = currentUser?.name;
      const addedTaskIds = new Set();

      tasks.forEach(task => {
        if (task.stage === 'done') return;

        // 나에게 할당된 태스크 → 무조건 표시
        if (myName && task.assignee === myName && !addedTaskIds.has(task.id)) {
          addedTaskIds.add(task.id);
          const stageLabels = { todo: 'To Do', in_progress: '진행 중', review: '리뷰 중' };
          let detail = stageLabels[task.stage] || task.stage;
          if (task.dueDate) {
            const due = new Date(task.dueDate);
            due.setHours(0, 0, 0, 0);
            const diff = Math.ceil((due - today) / 86400000);
            if (diff < 0) detail += ` · ${Math.abs(diff)}일 초과`;
            else if (diff === 0) detail += ' · 오늘 마감!';
            else if (diff <= 2) detail += ` · D-${diff}`;
          }
          alerts.push({
            id: `my-task-${task.id}`, category: 'task', taskId: task.id,
            type: 'my_task', icon: ClipboardList,
            color: 'text-sky-500 bg-sky-100 dark:bg-sky-900/30',
            title: task.title,
            detail,
            assignee: task.assignee, priority: task.dueDate ? 3 : 2,
          });
        }

        if (task.dueDate && !addedTaskIds.has(task.id)) {
          const due = new Date(task.dueDate);
          due.setHours(0, 0, 0, 0);
          const diff = Math.ceil((due - today) / 86400000);

          if (diff < 0) {
            addedTaskIds.add(task.id);
            alerts.push({
              id: `overdue-${task.id}`, category: 'task', taskId: task.id,
              type: 'overdue', icon: AlertTriangle,
              color: 'text-red-500 bg-red-100 dark:bg-red-900/30',
              title: task.title,
              detail: `${Math.abs(diff)}일 초과 (마감: ${task.dueDate})`,
              assignee: task.assignee, priority: 4,
            });
          } else if (diff <= 2) {
            addedTaskIds.add(task.id);
            alerts.push({
              id: `due-soon-${task.id}`, category: 'task', taskId: task.id,
              type: 'due_soon', icon: CalendarClock,
              color: 'text-orange-500 bg-orange-100 dark:bg-orange-900/30',
              title: task.title,
              detail: diff === 0 ? '오늘 마감!' : `D-${diff} (마감: ${task.dueDate})`,
              assignee: task.assignee, priority: 3,
            });
          }
        }

        if (!task.assignee && !addedTaskIds.has(task.id)) {
          addedTaskIds.add(task.id);
          alerts.push({
            id: `unassigned-${task.id}`, category: 'task', taskId: task.id,
            type: 'unassigned', icon: UserX,
            color: 'text-purple-500 bg-purple-100 dark:bg-purple-900/30',
            title: task.title,
            detail: '담당자가 지정되지 않았습니다',
            assignee: null, priority: 1,
          });
        }

        if (task.stage === 'review' && task.created_at && !addedTaskIds.has(task.id)) {
          const created = new Date(task.created_at);
          const daysSince = Math.floor((today - created) / 86400000);
          if (daysSince >= 3) {
            addedTaskIds.add(task.id);
            alerts.push({
              id: `stale-review-${task.id}`, category: 'task', taskId: task.id,
              type: 'stale_review', icon: Clock,
              color: 'text-blue-500 bg-blue-100 dark:bg-blue-900/30',
              title: task.title,
              detail: `Review 단계 ${daysSince}일째 정체 중`,
              assignee: task.assignee, priority: 1,
            });
          }
        }
      });

      return alerts;
    } catch {
      return [];
    }
  };

  const loadAll = async (trySeed = false) => {
    try {
      const [approvals, taskAlerts] = await Promise.all([loadApprovals(trySeed), loadTaskAlerts()]);
      setItems([...taskAlerts, ...approvals].sort((a, b) => b.priority - a.priority));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAll(true); }, []);

  const getAvatar = (name) => {
    if (!name) return null;
    const member = members.find(m => m.name === name);
    return member?.avatar || `https://api.dicebear.com/7.x/notionists/svg?seed=${encodeURIComponent(name)}`;
  };

  const handleDismiss = (id) => {
    setDismissed(prev => [...prev, id]);
  };

  const handleApproval = async (item, approved) => {
    try {
      if (approved) {
        await approveRequest(item.backendId);
      } else {
        await rejectRequest(item.backendId);
      }
      setDismissed(prev => [...prev, item.id]);
    } catch (err) {
      console.error('Approval action failed', err);
    }
  };

  const handleSubmitRequest = async (e) => {
    e.preventDefault();
    if (!formData.title.trim()) return;
    setSubmitting(true);
    try {
      await createApproval({
        type: formData.type,
        title: formData.title.trim(),
        detail: formData.detail.trim() || null,
        target_team: formData.target_team || null,
        target_user_id: formData.target_user_id || null,
      }, formFile);
      setShowModal(false);
      setFormData({ type: 'leave', title: '', detail: '', target_team: '', target_user_id: '' });
      setFormFile(null);
      await loadAll();
    } catch (err) {
      console.error('Failed to create approval request', err);
      alert('요청 생성에 실패했습니다. 서버 연결을 확인해주세요.');
    } finally {
      setSubmitting(false);
    }
  };

  const typeLabels = {
    my_task: '내 태스크',
    overdue: '마감 초과',
    due_soon: '마감 임박',
    unassigned: '미지정',
    stale_review: '리뷰 정체',
    leave: '연차/반차 신청',
    remote: '재택근무 신청',
    room: '회의실 예약',
    design: '디자인 에셋 요청',
    certificate: '증명서 발급 요청',
    budget: '결재 요청',
    review: 'PR 리뷰 요청',
    deploy: '배포 승인 요청',
    infra: '인프라/권한 신청',
    security: '보안 예외 처리',
  };

  const badgeStyle = (item) => {
    if (item.type === 'overdue') return 'text-red-700 bg-red-50 dark:bg-red-900/20 border-red-300 dark:border-red-800';
    if (item.type === 'my_task') return 'text-sky-700 bg-sky-50 dark:bg-sky-900/20 border-sky-300 dark:border-sky-800';
    return 'text-accent-700 bg-accent-50 dark:bg-orange-900/20 border-accent-300 dark:border-orange-800';
  };

  const badgeText = (item) => {
    if (item.type === 'overdue') return 'Urgent';
    if (item.type === 'my_task') return 'Assigned';
    return 'Pending';
  };

  const visibleItems = items.filter(i => !dismissed.includes(i.id));
  const displayItems = isCollapsed ? visibleItems.slice(0, 1) : visibleItems;

  return (
    <div className="card flex flex-col p-6 shadow-soft transition-all duration-300">
      <div
        className="flex items-center justify-between mb-4 cursor-pointer"
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <h3 className="text-xl font-bold text-neutral-main flex items-center gap-2">
          Needs Attention
          {visibleItems.length > 0 && (
            <span className="bg-accent-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full ml-1">
              {visibleItems.length}
            </span>
          )}
        </h3>
        <div className="flex items-center gap-2">
          <button
            className="w-9 h-9 rounded-full bg-surface-hover hover:bg-primary-50 hover:text-primary-600 flex items-center justify-center text-neutral-sub shadow-sm border border-neutral-divider transition-all"
            onClick={(e) => { e.stopPropagation(); setShowModal(true); }}
            title="새 요청 올리기"
          >
            <Plus size={16} />
          </button>
          <button
            className="w-9 h-9 rounded-full bg-surface-hover hover:bg-primary-50 hover:text-primary-600 flex items-center justify-center text-neutral-sub shadow-sm border border-neutral-divider transition-all"
            onClick={(e) => { e.stopPropagation(); navigate('/schedules?tab=approvals'); }}
            title="전체 보기"
          >
            <ExternalLink size={14} />
          </button>
          <button
            className="w-9 h-9 rounded-full bg-surface-hover hover:bg-primary-50 hover:text-primary-600 flex items-center justify-center text-neutral-sub shadow-sm border border-neutral-divider transition-all"
            onClick={() => setIsCollapsed(!isCollapsed)}
          >
            {isCollapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
          </button>
        </div>
      </div>

      <div className="overflow-y-auto pr-2 custom-scrollbar space-y-3 max-h-[480px]">
        <AnimatePresence>
          {displayItems.map((item, idx) => (
            <motion.div
              key={item.id}
              layout
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, x: -20, scale: 0.9 }}
              transition={{ duration: 0.2, delay: idx * 0.05 }}
              className="bg-white/40 dark:bg-white/[0.05] backdrop-blur-md p-4 rounded-xl border border-white/20 dark:border-white/10 shadow-sm hover:shadow-md transition-shadow group"
            >
              <div className="flex justify-between items-start mb-3">
                <div className="flex items-center gap-2">
                  <div className={`p-1.5 rounded-xl ${item.color}`}>
                    <item.icon size={16} />
                  </div>
                  <span className="text-[10px] font-bold text-neutral-sub px-2.5 py-1 bg-surface-sub/60 rounded-full">
                    {typeLabels[item.type] || item.type.toUpperCase()}
                  </span>
                </div>
                <span className={`text-[10px] font-bold px-2.5 py-1 rounded-full border ${badgeStyle(item)}`}>
                  {badgeText(item)}
                </span>
              </div>

              <h4 className="text-sm font-semibold text-neutral-main mb-1">{item.title}</h4>

              <div className="flex items-center gap-2 mb-4 bg-surface-sub/60 p-2 rounded-lg">
                {item.category === 'approval' ? (
                  <>
                    <img src={item.avatar} alt={item.requester} className="w-8 h-8 rounded-full" />
                    <div>
                      <p className="text-xs font-medium text-neutral-main">{item.requester}</p>
                      <p className="text-[10px] text-neutral-muted">{item.detail}</p>
                    </div>
                  </>
                ) : item.assignee ? (
                  <>
                    <img src={getAvatar(item.assignee)} alt={item.assignee} className="w-8 h-8 rounded-full border border-neutral-border bg-surface-card" />
                    <div>
                      <p className="text-xs font-medium text-neutral-main">{item.assignee}</p>
                      <p className="text-[10px] text-neutral-muted">{item.detail}</p>
                    </div>
                  </>
                ) : (
                  <div>
                    <p className="text-xs font-medium text-neutral-main">#{item.taskId}</p>
                    <p className="text-[10px] text-neutral-muted">{item.detail}</p>
                  </div>
                )}
              </div>

              {item.category === 'approval' ? (
                <div className="flex gap-2">
                  <button
                    onClick={() => handleApproval(item, true)}
                    className="flex-1 flex items-center justify-center gap-1 py-2 bg-success/10 hover:bg-success text-success hover:text-white text-xs font-semibold rounded-lg transition-all duration-200"
                  >
                    <Check size={14} /> Approve
                  </button>
                  <button
                    onClick={() => handleApproval(item, false)}
                    className="flex-1 flex items-center justify-center gap-1 py-2 bg-error/10 hover:bg-error text-error hover:text-white text-xs font-semibold rounded-lg transition-all duration-200"
                  >
                    <X size={14} /> Reject
                  </button>
                </div>
              ) : (
                <div className="flex gap-2">
                  <button
                    onClick={() => navigate('/tasks')}
                    className="flex-1 flex items-center justify-center gap-1 py-2 bg-primary-50 hover:bg-primary-500 text-primary-600 hover:text-white text-xs font-semibold rounded-lg transition-all duration-200"
                  >
                    <ArrowRight size={14} /> 태스크 보기
                  </button>
                  <button
                    onClick={() => handleDismiss(item.id)}
                    className="flex-1 flex items-center justify-center gap-1 py-2 bg-neutral-100 hover:bg-neutral-200 text-neutral-500 hover:text-neutral-700 text-xs font-semibold rounded-lg transition-all duration-200 dark:bg-neutral-700 dark:hover:bg-neutral-600 dark:text-neutral-400"
                  >
                    <Check size={14} /> 확인 완료
                  </button>
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>

        {visibleItems.length === 0 && !isCollapsed && !loading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-col items-center justify-center h-40 text-neutral-muted"
          >
            <Check className="mb-2 text-success opacity-50" size={32} />
            <p className="text-sm">모든 항목을 처리했습니다!</p>
          </motion.div>
        )}
      </div>

      {/* 요청 올리기 모달 */}
      {showModal && createPortal(
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
          <AnimatePresence>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-neutral-900/40 backdrop-blur-sm"
              onClick={() => setShowModal(false)}
            />
          </AnimatePresence>
          <motion.div
            initial={{ scale: 0.95, opacity: 0, y: 20 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.95, opacity: 0, y: 20 }}
            className="relative bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-[2.5rem] shadow-2xl p-8 w-full max-w-md mx-4 overflow-hidden border border-white/40 dark:border-white/10"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-8">
              <div>
                <h3 className="text-2xl font-black text-neutral-900 dark:text-white tracking-tighter">새 요청 올리기</h3>
                <p className="text-xs text-neutral-400 font-bold mt-1">도움이나 승인이 필요한 내용을 적어주세요.</p>
              </div>
              <button onClick={() => setShowModal(false)} className="p-2 rounded-full hover:bg-neutral-100 dark:hover:bg-white/10 transition-colors">
                <X size={20} className="text-neutral-400" />
              </button>
            </div>

            <form onSubmit={handleSubmitRequest} className="space-y-6">
              <div className="space-y-2">
                <label className="block text-[11px] font-black uppercase tracking-widest text-neutral-400 ml-1">요청 유형</label>
                <select
                  value={formData.type}
                  onChange={(e) => setFormData(prev => ({ ...prev, type: e.target.value }))}
                  className="w-full px-4 py-3 rounded-xl border border-neutral-200 dark:border-white/10 bg-white/50 dark:bg-black/20 text-sm outline-none focus:ring-2 focus:ring-primary-500 transition-all appearance-none cursor-pointer"
                >
                  <option value="leave">연차/반차 신청</option>
                  <option value="remote">재택근무 신청</option>
                  <option value="room">회의실 예약</option>
                  <option value="design">디자인 에셋 요청</option>
                  <option value="certificate">증명서 발급 요청</option>
                  <option value="budget">결재 요청</option>
                  <option value="review">PR 리뷰 요청</option>
                  <option value="deploy">배포 승인 요청</option>
                  <option value="infra">인프라/권한 신청</option>
                  <option value="security">보안 예외 처리</option>
                </select>
              </div>
              {/* 대상 팀 / 팀원 선택 */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <label className="block text-[11px] font-black uppercase tracking-widest text-neutral-400 ml-1">보낼 팀</label>
                  <select
                    value={formData.target_team}
                    onChange={(e) => setFormData(prev => ({ ...prev, target_team: e.target.value, target_user_id: '' }))}
                    className="w-full px-4 py-3 rounded-xl border border-neutral-200 dark:border-white/10 bg-white/50 dark:bg-black/20 text-sm outline-none focus:ring-2 focus:ring-primary-500 transition-all appearance-none cursor-pointer"
                  >
                    <option value="">전체</option>
                    {TEAMS.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="block text-[11px] font-black uppercase tracking-widest text-neutral-400 ml-1">보낼 팀원</label>
                  <MemberDropdown
                    members={allMembers.filter(m => !formData.target_team || m.team === formData.target_team)}
                    value={formData.target_user_id}
                    onChange={(id) => setFormData(prev => ({ ...prev, target_user_id: id }))}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <label className="block text-[11px] font-black uppercase tracking-widest text-neutral-400 ml-1">제목</label>
                <input
                  type="text"
                  value={formData.title}
                  onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
                  placeholder="요청 제목을 입력하세요"
                  className="w-full px-5 py-3 rounded-xl border border-neutral-200 dark:border-white/10 bg-white/50 dark:bg-black/20 text-sm outline-none focus:ring-2 focus:ring-primary-500 transition-all placeholder:text-neutral-300"
                  required
                />
              </div>
              <div className="space-y-2">
                <label className="block text-[11px] font-black uppercase tracking-widest text-neutral-400 ml-1">상세 내용</label>
                <textarea
                  value={formData.detail}
                  onChange={(e) => setFormData(prev => ({ ...prev, detail: e.target.value }))}
                  placeholder="상세 내용을 입력하세요 (선택)"
                  rows={4}
                  className="w-full px-5 py-3 rounded-xl border border-neutral-200 dark:border-white/10 bg-white/50 dark:bg-black/20 text-sm outline-none focus:ring-2 focus:ring-primary-500 transition-all placeholder:text-neutral-300 resize-none"
                />
              </div>
              <div className="space-y-2">
                <label className="block text-[11px] font-black uppercase tracking-widest text-neutral-400 ml-1">첨부파일 (선택)</label>
                <input
                  type="file"
                  accept=".pdf,.docx,.doc,.txt,.png,.jpg,.jpeg,.gif,.webp"
                  onChange={(e) => setFormFile(e.target.files[0] || null)}
                  className="w-full text-sm text-neutral-400 file:mr-3 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-black file:bg-neutral-100 file:text-neutral-500 hover:file:bg-neutral-200 dark:file:bg-white/10 dark:file:text-neutral-300"
                />
                {formFile && (
                  <div className="flex items-center gap-1 mt-1 text-xs text-neutral-400">
                    <Paperclip size={12} />
                    <span className="truncate">{formFile.name}</span>
                    <button type="button" onClick={() => setFormFile(null)} className="ml-1 p-0.5 rounded-full hover:bg-red-100 text-red-400 hover:text-red-600 transition-colors">
                      <X size={14} />
                    </button>
                  </div>
                )}
              </div>
              <div className="flex gap-3 pt-6">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="flex-1 py-4 text-xs font-black rounded-xl text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 transition-all"
                >
                  취소
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex-1 py-4 bg-primary-700 text-white text-xs font-black rounded-xl shadow-xl hover:bg-primary-900 hover:scale-105 active:scale-95 transition-all disabled:opacity-50"
                >
                  {submitting ? '제출 중...' : '요청 제출'}
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
