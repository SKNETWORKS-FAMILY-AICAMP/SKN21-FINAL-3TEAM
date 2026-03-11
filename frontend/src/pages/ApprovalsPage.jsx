import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Check, X, Clock, Coffee, GitPullRequest, FileText, FileSignature,
  Search, BellRing, CheckCircle2, XCircle, Trash2, Download, Paperclip, Eye,
  Home, DoorOpen, Palette, Award, Receipt, Rocket, Server, ShieldCheck, RefreshCw,
  Sparkles, Plus, Zap, CalendarPlus, CalendarClock
} from 'lucide-react';
import {
  listApprovals, createApproval, approveRequest, rejectRequest,
  deleteApproval, downloadApprovalFile, getApprovalFileBlobUrl, suggestApprovals
} from '../api/approvals';
import { createSchedule } from '../api/schedules';
import { getAllMembers } from '../api/auth';
import client from '../api/client';
import useAuthStore from '../store/authStore';
import MemberDropdown from '../components/common/MemberDropdown';

const TEAMS = ['개발', 'QA기획', 'UI/UX', '영업', '마케팅', 'CS'];

const typeConfig = {
  leave: { icon: Coffee, color: 'text-orange-500 bg-orange-50 dark:bg-orange-900/30', label: '연차/반차 신청' },
  remote: { icon: Home, color: 'text-teal-500 bg-teal-50 dark:bg-teal-900/30', label: '재택근무 신청' },
  room: { icon: DoorOpen, color: 'text-indigo-500 bg-indigo-50 dark:bg-indigo-900/30', label: '회의실 예약' },
  design: { icon: Palette, color: 'text-pink-500 bg-pink-50 dark:bg-pink-900/30', label: '디자인 에셋 요청' },
  certificate: { icon: Award, color: 'text-yellow-500 bg-yellow-50 dark:bg-yellow-900/30', label: '증명서 발급 요청' },
  budget: { icon: Receipt, color: 'text-purple-500 bg-purple-50 dark:bg-purple-900/30', label: '결재 요청' },
  review: { icon: GitPullRequest, color: 'text-blue-500 bg-blue-50 dark:bg-blue-900/30', label: 'PR 리뷰 요청' },
  deploy: { icon: Rocket, color: 'text-green-500 bg-green-50 dark:bg-green-900/30', label: '배포 승인 요청' },
  infra: { icon: Server, color: 'text-slate-500 bg-slate-50 dark:bg-slate-900/30', label: '인프라/권한 신청' },
  security: { icon: ShieldCheck, color: 'text-red-500 bg-red-50 dark:bg-red-900/30', label: '보안 예외 처리' },
  other: { icon: FileSignature, color: 'text-gray-500 bg-gray-50 dark:bg-gray-900/30', label: '기타' },
};
const defaultTypeConfig = { icon: FileSignature, color: 'text-neutral-sub bg-surface-sub', label: '요청' };

const priorityBadge = {
  high: 'bg-red-50 text-red-500',
  medium: 'bg-amber-50 text-amber-500',
  low: 'bg-green-50 text-green-500',
};

const scheduleTypeConfig = {
  meeting: { color: 'bg-indigo-50 text-indigo-500', label: '회의' },
  task: { color: 'bg-sky-50 text-sky-500', label: '작업' },
  deadline: { color: 'bg-rose-50 text-rose-500', label: '마감' },
  review: { color: 'bg-amber-50 text-amber-500', label: '리뷰' },
  milestone: { color: 'bg-emerald-50 text-emerald-500', label: '마일스톤' },
};

function resolveSuggestedDay(day) {
  const now = new Date();
  if (!day || day === 'today') return now;
  if (day === 'tomorrow') { const d = new Date(now); d.setDate(d.getDate() + 1); return d; }
  if (day === 'this_week') { const d = new Date(now); d.setDate(d.getDate() + 2); return d; }
  const parsed = new Date(day);
  return isNaN(parsed.getTime()) ? now : parsed;
}

export default function ApprovalsPage({ embedded = false, onReady, externalActions }) {
  const user = useAuthStore((s) => s.user);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [formData, setFormData] = useState({ type: 'leave', title: '', detail: '', target_team: '', target_user_id: '', customType: '' });
  const [formFile, setFormFile] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [allMembers, setAllMembers] = useState([]);
  const [detailItem, setDetailItem] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  // New Tasks state
  const [suggestions, setSuggestions] = useState([]);
  const [suggestLoading, setSuggestLoading] = useState(false);
  const [suggestContext, setSuggestContext] = useState(null);
  const [suggestError, setSuggestError] = useState(null);
  const [newTasksTab, setNewTasksTab] = useState('approvals');

  // Schedule suggestions state
  const [scheduleSuggestions, setScheduleSuggestions] = useState([]);
  const [schedSuggestLoading, setSchedSuggestLoading] = useState(false);
  const [schedSuggestError, setSchedSuggestError] = useState(null);
  const [addingScheduleId, setAddingScheduleId] = useState(null);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [pendingRes, approvedRes, rejectedRes, pendingSentRes] = await Promise.all([
        client.get('/approvals/', { params: { status: 'pending' } }).catch(() => ({ data: [] })),
        client.get('/approvals/history', { params: { status: 'approved' } }).catch(() => ({ data: [] })),
        client.get('/approvals/history', { params: { status: 'rejected' } }).catch(() => ({ data: [] })),
        client.get('/approvals/history', { params: { status: 'pending' } }).catch(() => ({ data: [] })),
      ]);
      // 받은 pending 요청에 _received 마킹
      const received = (Array.isArray(pendingRes.data) ? pendingRes.data : []).map(i => ({ ...i, _received: true }));
      // 내가 보낸 요청들에 _sent 마킹
      const sentApproved = (Array.isArray(approvedRes.data) ? approvedRes.data : []).map(i => ({ ...i, _sent: true }));
      const sentRejected = (Array.isArray(rejectedRes.data) ? rejectedRes.data : []).map(i => ({ ...i, _sent: true }));
      const sentPending = (Array.isArray(pendingSentRes.data) ? pendingSentRes.data : []).map(i => ({ ...i, _sent: true }));
      const all = [...received, ...sentApproved, ...sentRejected, ...sentPending];
      setItems(all);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
    handleSuggest();
    getAllMembers().then(res => setAllMembers(res.data || [])).catch(() => {});
  }, []);

  const handleApproval = async (id, approve) => {
    try {
      if (approve) await approveRequest(id);
      else await rejectRequest(id);
      await loadAll();
    } catch (err) {
      console.error('Action failed', err);
    }
  };

  const handleDeleteClick = (item) => {
    setDeleteConfirm({ id: item.id, title: item.title });
  };

  const handleDeleteConfirm = async () => {
    if (!deleteConfirm) return;
    try {
      await deleteApproval(deleteConfirm.id);
      setDeleteConfirm(null);
      await loadAll();
    } catch (err) {
      const msg = err.response?.data?.detail || '삭제에 실패했습니다.';
      alert(msg);
      setDeleteConfirm(null);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.title.trim()) return;
    if (!formData.target_user_id) {
      alert('보낼 팀원을 선택해주세요.');
      return;
    }
    setSubmitting(true);
    try {
      await createApproval(
        {
          type: formData.type === 'other' ? (formData.customType.trim() || 'other') : formData.type,
          title: formData.title.trim(),
          detail: formData.detail.trim() || null,
          target_team: formData.target_team || null,
          target_user_id: formData.target_user_id || null,
        },
        formFile
      );
      setShowModal(false);
      setFormData({ type: 'leave', title: '', detail: '', target_team: '', target_user_id: '', customType: '' });
      setFormFile(null);
      await loadAll();
      // 추천 목록에서 방금 보낸 요청 제거
      setSuggestions(prev => prev.filter(s => !(s.type === formData.type && s.title === formData.title.trim())));
      handleSuggest();
    } catch (err) {
      console.error('Approval create error:', err.response?.status, err.response?.data, err);
      alert('요청 생성에 실패했습니다. (' + (err.response?.data?.detail || err.message) + ')');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSuggest = async () => {
    setSuggestLoading(true);
    setSuggestions([]);
    setSuggestError(null);
    try {
      const res = await suggestApprovals();
      setSuggestions(res.data?.suggestions || []);
      setSuggestContext(res.data?.context || null);
    } catch (err) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail || err.message || '알 수 없는 오류';
      console.error('AI 추천 실패:', status, detail);
      setSuggestError(`${status || 'ERR'}: ${detail}`);
    } finally {
      setSuggestLoading(false);
    }
  };

  const loadScheduleSuggestions = async () => {
    setSchedSuggestLoading(true);
    setScheduleSuggestions([]);
    setSchedSuggestError(null);
    try {
      const res = await client.post('/approvals/suggest-schedules');
      setScheduleSuggestions(res.data?.suggestions || []);
    } catch (err) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail || err.message || '알 수 없는 오류';
      setSchedSuggestError(`${status || 'ERR'}: ${detail}`);
    } finally {
      setSchedSuggestLoading(false);
    }
  };

  const applySuggestion = (s) => {
    setFormData({ type: s.type, title: s.title, detail: s.detail || '', target_team: '', target_user_id: '', customType: '' });
    setShowModal(true);
  };

  const addScheduleToCalendar = async (s, idx) => {
    setAddingScheduleId(idx);
    try {
      const startDate = resolveSuggestedDay(s.suggested_day);
      startDate.setHours(10, 0, 0, 0);
      const endDate = new Date(startDate);
      endDate.setMinutes(endDate.getMinutes() + (s.duration_minutes || 60));
      await createSchedule({
        title: s.title,
        description: s.description || s.reason || '',
        start_time: startDate.toISOString(),
        end_time: endDate.toISOString(),
        schedule_type: s.schedule_type || 'task',
        priority: s.priority || 'medium',
      });
      setScheduleSuggestions(prev => prev.filter((_, i) => i !== idx));
    } catch (err) {
      alert(err.response?.data?.detail || '캘린더 추가에 실패했습니다.');
    } finally {
      setAddingScheduleId(null);
    }
  };

  const switchNewTasksTab = (tab) => {
    setNewTasksTab(tab);
    if (tab === 'schedules' && scheduleSuggestions.length === 0 && !schedSuggestLoading) {
      loadScheduleSuggestions();
    }
  };

  const pendingItems = items.filter(i => i._received);
  const sentItems = items.filter(i => i._sent);

  // 이미 보낸 요청과 같은 type의 추천은 제외
  const filteredSuggestions = suggestions.filter(s =>
    !sentItems.some(sent => sent.type === s.type && sent.title === s.title)
  );

  /* ── 칸반 카드 렌더 (Pending - 받은 요청) ── */
  const renderPendingCard = (item) => {
    const cfg = typeConfig[item.type] || defaultTypeConfig;
    const IconComp = cfg.icon;
    return (
      <motion.div
        key={item.id}
        layout
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95 }}
        transition={{ duration: 0.2 }}
        className="bg-white dark:bg-neutral-800 p-4 rounded-xl shadow-[0_1px_4px_rgba(0,0,0,0.06)] hover:shadow-[0_4px_12px_rgba(0,0,0,0.1)] transition-all group cursor-pointer"
        onClick={() => setDetailItem(item)}
      >
        <div className="flex items-center justify-between mb-2.5">
          <div className="flex items-center gap-2">
            <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${cfg.color}`}>
              <IconComp size={14} />
            </div>
            <span className="text-[11px] font-semibold text-slate-400">{cfg.label}</span>
          </div>
          <button
            onClick={(e) => { e.stopPropagation(); handleDeleteClick(item); }}
            className="opacity-0 group-hover:opacity-100 p-1 rounded-md hover:bg-red-50 text-slate-300 hover:text-red-400 transition-all"
            title="삭제"
          >
            <Trash2 size={12} />
          </button>
        </div>
        <h4 className="text-[13px] font-bold text-slate-700 dark:text-slate-200 leading-snug mb-1 line-clamp-2">{item.title}</h4>
        {item.detail && (
          <p className="text-[11px] text-slate-400 line-clamp-2 mb-3">{item.detail}</p>
        )}
        {/* 보낸 사람 프로필 */}
        <div className="flex items-center gap-2 pt-2.5 border-t border-slate-100 dark:border-slate-700">
          {item.requester_avatar ? (
            <img src={item.requester_avatar} alt="" className="w-7 h-7 rounded-full object-cover ring-2 ring-white dark:ring-neutral-800" />
          ) : (
            <div className="w-7 h-7 rounded-full bg-sky-100 dark:bg-sky-900/30 flex items-center justify-center text-[11px] font-bold text-sky-500">
              {(item.requester_name || '?')[0]}
            </div>
          )}
          <span className="text-[11px] font-medium text-slate-500 truncate">{item.requester_name || '알 수 없음'}</span>
          {item.created_at && (
            <span className="text-[10px] text-slate-300 ml-auto shrink-0">
              {new Date(item.created_at).toLocaleDateString('ko-KR', { month: 'numeric', day: 'numeric' })}
            </span>
          )}
        </div>
        {/* Approve / Reject 버튼 */}
        <div className="flex gap-2 mt-3" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => handleApproval(item.id, true)}
            className="flex-1 flex items-center justify-center gap-1 py-1.5 bg-sky-50 hover:bg-sky-500 text-sky-500 hover:text-white text-[11px] font-semibold rounded-lg transition-all"
          >
            <Check size={12} /> Approve
          </button>
          <button
            onClick={() => handleApproval(item.id, false)}
            className="flex-1 flex items-center justify-center gap-1 py-1.5 bg-rose-50 hover:bg-rose-500 text-rose-500 hover:text-white text-[11px] font-semibold rounded-lg transition-all"
          >
            <X size={12} /> Reject
          </button>
        </div>
      </motion.div>
    );
  };

  /* ── 보낸 결재 카드 (Sent - pending/approved/rejected) ── */
  const renderSentCard = (item) => {
    const cfg = typeConfig[item.type] || defaultTypeConfig;
    const IconComp = cfg.icon;
    const isApproved = item.status === 'approved';
    const isPending = item.status === 'pending';
    return (
      <motion.div
        key={item.id}
        layout
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95 }}
        transition={{ duration: 0.2 }}
        className="bg-white dark:bg-neutral-800 p-4 rounded-xl shadow-[0_1px_4px_rgba(0,0,0,0.06)] hover:shadow-[0_4px_12px_rgba(0,0,0,0.1)] transition-all group cursor-pointer"
        onClick={() => setDetailItem(item)}
      >
        <div className="flex items-center justify-between mb-2.5">
          <div className="flex items-center gap-2">
            <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${cfg.color}`}>
              <IconComp size={14} />
            </div>
            <span className="text-[11px] font-semibold text-slate-400">{cfg.label}</span>
          </div>
          {/* 상태 배지 */}
          <span className={`inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full ${
            isPending
              ? 'bg-amber-50 text-amber-500 dark:bg-amber-900/30'
              : isApproved
                ? 'bg-emerald-50 text-emerald-500 dark:bg-emerald-900/30'
                : 'bg-rose-50 text-rose-500 dark:bg-rose-900/30'
          }`}>
            {isPending ? <Clock size={10} /> : isApproved ? <CheckCircle2 size={10} /> : <XCircle size={10} />}
            {isPending ? '대기중' : isApproved ? 'Approved' : 'Rejected'}
          </span>
        </div>
        <h4 className="text-[13px] font-bold text-slate-700 dark:text-slate-200 leading-snug mb-1 line-clamp-2">{item.title}</h4>
        {item.detail && (
          <p className="text-[11px] text-slate-400 line-clamp-2 mb-3">{item.detail}</p>
        )}
        {/* 받는 사람 프로필 */}
        <div className="flex items-center gap-2 pt-2.5 border-t border-slate-100 dark:border-slate-700">
          <span className="text-[9px] text-slate-300 shrink-0">To</span>
          {item.target_user_avatar ? (
            <img src={item.target_user_avatar} alt="" className="w-7 h-7 rounded-full object-cover ring-2 ring-white dark:ring-neutral-800" />
          ) : (
            <div className={`w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold ${isPending ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-500' : isApproved ? 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-500' : 'bg-rose-100 dark:bg-rose-900/30 text-rose-500'}`}>
              {(item.target_user_name || item.target_team || '?')[0]}
            </div>
          )}
          <span className="text-[11px] font-medium text-slate-500 truncate">
            {item.target_user_name || item.target_team || '알 수 없음'}
            {(item.target_user_team || item.target_team) && <span className="text-[9px] text-slate-300 ml-1">({item.target_user_team || item.target_team})</span>}
          </span>
          {item.file_name && (
            <Paperclip size={11} className="text-slate-300 shrink-0" />
          )}
          {item.created_at && (
            <span className="text-[10px] text-slate-300 ml-auto shrink-0">
              {new Date(item.created_at).toLocaleDateString('ko-KR', { month: 'numeric', day: 'numeric' })}
            </span>
          )}
        </div>
      </motion.div>
    );
  };

  const columnConfig = [
    { id: 'pending', label: 'Pending', dotColor: 'bg-sky-400', items: pendingItems, renderFn: renderPendingCard },
    { id: 'sent', label: 'Sent', dotColor: 'bg-amber-400', items: sentItems, renderFn: renderSentCard },
  ];

  return (
    <div className="p-6 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-2xl font-bold text-neutral-main flex items-center gap-3">
            <BellRing className="text-accent-500" size={28} />
            Approval Requests
          </h1>
          <p className="text-sm text-neutral-muted mt-1">모든 결재/승인 요청을 확인하고 관리합니다</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { loadAll(); handleSuggest(); }}
            className="p-2.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-600 transition-colors"
            title="새로고침"
          >
            <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
          </button>
          <button
            onClick={() => setShowModal(true)}
            className="px-4 py-2.5 bg-primary-500 hover:bg-primary-600 text-white text-sm font-semibold rounded-xl transition-colors shadow-sm"
          >
            + 새 요청
          </button>
        </div>
      </div>

      {/* Kanban Board */}
      {loading ? (
        <div className="flex items-center justify-center flex-1 text-slate-400">
          <RefreshCw className="animate-spin mr-2" size={18} /> 로딩 중...
        </div>
      ) : (
        <div className="flex-1 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5 min-h-0">
          {/* Pending / Approved / Rejected columns */}
          {columnConfig.map((col) => (
            <div key={col.id} className="flex flex-col min-h-0">
              <div className="flex items-center gap-2 mb-3 px-1">
                <div className={`w-2 h-2 rounded-full ${col.dotColor}`} />
                <span className="text-sm font-bold text-slate-600 dark:text-slate-300 tracking-tight">{col.label}</span>
                <span className="text-[11px] font-semibold text-slate-400 bg-slate-100 dark:bg-slate-700 px-2 py-0.5 rounded-full">
                  {col.items.length}
                </span>
              </div>
              <div className="flex-1 bg-slate-50/80 dark:bg-slate-800/40 rounded-2xl p-3 border border-slate-200/50 dark:border-slate-700/50 overflow-y-auto">
                <div className="space-y-3">
                  <AnimatePresence mode="popLayout">
                    {col.items.map(col.renderFn)}
                  </AnimatePresence>
                  {col.items.length === 0 && (
                    <div className="h-28 flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 dark:border-slate-600">
                      <span className="text-[11px] text-slate-300 dark:text-slate-500">비어 있음</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}

          {/* Column 4: New Tasks (AI 추천) */}
          <div className="flex flex-col min-h-0">
            <div className="flex items-center gap-2 mb-3 px-1">
              <div className="w-2 h-2 rounded-full bg-violet-400" />
              <span className="text-sm font-bold text-slate-600 dark:text-slate-300 tracking-tight">New Tasks</span>
              <button
                onClick={() => newTasksTab === 'approvals' ? handleSuggest() : loadScheduleSuggestions()}
                disabled={suggestLoading || schedSuggestLoading}
                className="p-1 rounded-lg hover:bg-slate-200/60 dark:hover:bg-slate-600/40 text-slate-400 hover:text-slate-600 transition-colors"
                title="새로고침"
              >
                <RefreshCw size={12} className={(suggestLoading || schedSuggestLoading) ? 'animate-spin' : ''} />
              </button>
            </div>

            {/* Sub-tabs */}
            <div className="flex gap-1 mb-2">
              <button
                onClick={() => switchNewTasksTab('approvals')}
                className={`flex-1 py-1.5 text-[11px] font-bold rounded-lg transition-all ${newTasksTab === 'approvals' ? 'bg-violet-100 text-violet-600 dark:bg-violet-900/30' : 'text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'}`}
              >
                결재 추천
              </button>
              <button
                onClick={() => switchNewTasksTab('schedules')}
                className={`flex-1 py-1.5 text-[11px] font-bold rounded-lg transition-all flex items-center justify-center gap-1 ${newTasksTab === 'schedules' ? 'bg-violet-100 text-violet-600 dark:bg-violet-900/30' : 'text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'}`}
              >
                <CalendarClock size={11} /> 일정 추천
              </button>
            </div>

            <div className="flex-1 bg-slate-50/80 dark:bg-slate-800/40 rounded-2xl p-3 border border-slate-200/50 dark:border-slate-700/50 overflow-y-auto">
              {/* 결재 추천 탭 */}
              {newTasksTab === 'approvals' && (
                <>
                  {suggestContext && !suggestLoading && (
                    <div className="flex flex-wrap gap-1.5 mb-3">
                      <span className="text-[9px] font-semibold px-2 py-0.5 rounded-full bg-sky-50 text-sky-500">태스크 {suggestContext.total_tasks}</span>
                      <span className="text-[9px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-500">완료 {suggestContext.done_pct}%</span>
                      <span className="text-[9px] font-semibold px-2 py-0.5 rounded-full bg-violet-50 text-violet-500">일정 {suggestContext.upcoming_events}</span>
                    </div>
                  )}
                  {suggestLoading ? (
                    <div className="flex flex-col items-center justify-center py-12">
                      <div className="relative w-10 h-10 mb-3">
                        <div className="absolute inset-0 rounded-full border-2 border-violet-100" />
                        <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-violet-400 animate-spin" />
                        <Sparkles size={14} className="absolute inset-0 m-auto text-violet-400" />
                      </div>
                      <p className="text-xs text-slate-400">분석 중...</p>
                    </div>
                  ) : suggestError ? (
                    <div className="h-28 flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-rose-200 dark:border-rose-800 bg-rose-50/50 dark:bg-rose-900/10">
                      <XCircle size={14} className="text-rose-300 mb-1" />
                      <span className="text-[10px] text-rose-400 text-center px-2 leading-relaxed">{suggestError}</span>
                      <button onClick={handleSuggest} className="mt-1.5 text-[10px] text-sky-500 hover:underline">다시 시도</button>
                    </div>
                  ) : filteredSuggestions.length === 0 ? (
                    <div className="h-28 flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 dark:border-slate-600">
                      <Zap size={14} className="text-slate-300 mb-1" />
                      <span className="text-[11px] text-slate-300">추천 없음</span>
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 gap-2.5">
                      <AnimatePresence mode="popLayout">
                        {filteredSuggestions.map((s, idx) => {
                          const cfg = typeConfig[s.type] || defaultTypeConfig;
                          return (
                            <motion.div
                              key={idx}
                              layout
                              initial={{ opacity: 0, y: 6 }}
                              animate={{ opacity: 1, y: 0 }}
                              transition={{ delay: idx * 0.05 }}
                              onClick={() => applySuggestion(s)}
                              className="bg-white dark:bg-neutral-800 p-3 rounded-xl shadow-[0_1px_4px_rgba(0,0,0,0.06)] hover:shadow-[0_4px_12px_rgba(0,0,0,0.1)] cursor-pointer transition-all group"
                            >
                              <div className="flex flex-col items-center text-center gap-1.5">
                                {s.priority && (
                                  <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded-md self-end ${priorityBadge[s.priority] || priorityBadge.medium}`}>
                                    {s.priority.toUpperCase()}
                                  </span>
                                )}
                                <h4 className="text-[11px] font-bold text-slate-600 dark:text-slate-200 group-hover:text-violet-500 transition-colors line-clamp-2 leading-snug">
                                  {s.title}
                                </h4>
                                {s.reason && (
                                  <p className="text-[9px] text-slate-400 line-clamp-2 leading-relaxed">{s.reason}</p>
                                )}
                                <Plus size={12} className="text-slate-300 group-hover:text-violet-400 transition-colors mt-0.5" />
                              </div>
                            </motion.div>
                          );
                        })}
                      </AnimatePresence>
                    </div>
                  )}
                </>
              )}

              {/* 일정 추천 탭 */}
              {newTasksTab === 'schedules' && (
                <>
                  {schedSuggestLoading ? (
                    <div className="flex flex-col items-center justify-center py-12">
                      <div className="relative w-10 h-10 mb-3">
                        <div className="absolute inset-0 rounded-full border-2 border-violet-100" />
                        <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-violet-400 animate-spin" />
                        <CalendarClock size={14} className="absolute inset-0 m-auto text-violet-400" />
                      </div>
                      <p className="text-xs text-slate-400">일정 분석 중...</p>
                    </div>
                  ) : schedSuggestError ? (
                    <div className="h-28 flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-rose-200 dark:border-rose-800 bg-rose-50/50 dark:bg-rose-900/10">
                      <XCircle size={14} className="text-rose-300 mb-1" />
                      <span className="text-[10px] text-rose-400 text-center px-2 leading-relaxed">{schedSuggestError}</span>
                      <button onClick={loadScheduleSuggestions} className="mt-1.5 text-[10px] text-sky-500 hover:underline">다시 시도</button>
                    </div>
                  ) : scheduleSuggestions.length === 0 ? (
                    <div className="h-28 flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 dark:border-slate-600">
                      <CalendarClock size={14} className="text-slate-300 mb-1" />
                      <span className="text-[11px] text-slate-300">추천 일정 없음</span>
                    </div>
                  ) : (
                    <div className="space-y-2.5">
                      <AnimatePresence mode="popLayout">
                        {scheduleSuggestions.map((s, idx) => {
                          const stCfg = scheduleTypeConfig[s.schedule_type] || scheduleTypeConfig.task;
                          const isAdding = addingScheduleId === idx;
                          return (
                            <motion.div
                              key={idx}
                              layout
                              initial={{ opacity: 0, y: 6 }}
                              animate={{ opacity: 1, y: 0 }}
                              exit={{ opacity: 0, x: 20, scale: 0.95 }}
                              transition={{ delay: idx * 0.05 }}
                              className="bg-white dark:bg-neutral-800 p-3.5 rounded-xl shadow-[0_1px_4px_rgba(0,0,0,0.06)] hover:shadow-[0_4px_12px_rgba(0,0,0,0.1)] transition-all"
                            >
                              <div className="flex items-start justify-between gap-2 mb-2">
                                <div className="flex items-center gap-1.5">
                                  <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded-md ${stCfg.color}`}>
                                    {stCfg.label}
                                  </span>
                                  {s.priority && (
                                    <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded-md ${priorityBadge[s.priority] || priorityBadge.medium}`}>
                                      {s.priority.toUpperCase()}
                                    </span>
                                  )}
                                </div>
                                {s.duration_minutes && (
                                  <span className="text-[9px] text-slate-300 shrink-0">{s.duration_minutes}분</span>
                                )}
                              </div>
                              <h4 className="text-[12px] font-bold text-slate-700 dark:text-slate-200 leading-snug mb-1 line-clamp-2">
                                {s.title}
                              </h4>
                              {s.reason && (
                                <p className="text-[9px] text-slate-400 line-clamp-2 leading-relaxed mb-2">{s.reason}</p>
                              )}
                              {s.suggested_day && (
                                <span className="text-[9px] text-slate-300 block mb-2">
                                  {s.suggested_day === 'today' ? '오늘' : s.suggested_day === 'tomorrow' ? '내일' : s.suggested_day === 'this_week' ? '이번 주' : s.suggested_day}
                                </span>
                              )}
                              <button
                                onClick={() => addScheduleToCalendar(s, idx)}
                                disabled={isAdding}
                                className="w-full flex items-center justify-center gap-1.5 py-2 bg-violet-50 hover:bg-violet-500 text-violet-500 hover:text-white text-[11px] font-bold rounded-lg transition-all disabled:opacity-50"
                              >
                                {isAdding ? <RefreshCw size={12} className="animate-spin" /> : <CalendarPlus size={12} />}
                                {isAdding ? '추가 중...' : '캘린더에 추가'}
                              </button>
                            </motion.div>
                          );
                        })}
                      </AnimatePresence>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 상세 보기 모달 */}
      <AnimatePresence>
        {detailItem && (() => {
          const cfg = typeConfig[detailItem.type] || defaultTypeConfig;
          const IconComp = cfg.icon;
          const isImage = detailItem.file_name && /\.(png|jpg|jpeg|gif|webp)$/i.test(detailItem.file_name);
          const isPdf = detailItem.file_name && /\.pdf$/i.test(detailItem.file_name);
          const stLabel = detailItem.status === 'approved' ? 'Approved' : detailItem.status === 'rejected' ? 'Rejected' : '대기중';
          const stColor = detailItem.status === 'approved'
            ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30'
            : detailItem.status === 'rejected'
              ? 'bg-rose-50 text-rose-600 dark:bg-rose-900/30'
              : 'bg-amber-50 text-amber-600 dark:bg-amber-900/30';
          const isSentItem = !!detailItem._sent;
          return (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
              onClick={() => setDetailItem(null)}
            >
              <motion.div
                initial={{ scale: 0.95, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.95, opacity: 0 }}
                className="bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-[2.5rem] shadow-2xl p-8 w-full max-w-lg mx-4 max-h-[85vh] overflow-y-auto border border-white/40 dark:border-white/10"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="flex items-center justify-between mb-5">
                  <div className="flex items-center gap-3">
                    <div className={`p-2.5 rounded-xl ${cfg.color}`}>
                      <IconComp size={22} />
                    </div>
                    <div>
                      <span className="text-xs font-bold text-neutral-sub">{cfg.label}</span>
                      <h3 className="text-lg font-bold text-neutral-main">{detailItem.title}</h3>
                    </div>
                  </div>
                  <button onClick={() => setDetailItem(null)} className="p-1.5 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-400 hover:text-neutral-600 transition-colors">
                    <X size={20} />
                  </button>
                </div>

                <div className="mb-4">
                  <span className={`inline-flex items-center gap-1 text-xs font-bold px-3 py-1 rounded-full ${stColor}`}>
                    {detailItem.status === 'approved' && <CheckCircle2 size={14} />}
                    {detailItem.status === 'rejected' && <XCircle size={14} />}
                    {detailItem.status === 'pending' && <Clock size={14} />}
                    {stLabel}
                  </span>
                </div>

                <div className="mb-4 p-3 bg-surface-sub rounded-xl">
                  <p className="text-[10px] font-bold text-neutral-muted mb-2">{isSentItem ? '받는 사람' : '보낸 사람'}</p>
                  <div className="flex items-center gap-3">
                    {(() => {
                      const avatar = isSentItem ? (detailItem.target_user_avatar || null) : (detailItem.requester_avatar || null);
                      const name = isSentItem ? (detailItem.target_user_name || detailItem.target_team || '알 수 없음') : (detailItem.requester_name || '알 수 없음');
                      const team = isSentItem ? (detailItem.target_user_team || detailItem.target_team) : detailItem.target_team;
                      return (
                        <>
                          {avatar ? (
                            <img src={avatar} alt="" className="w-9 h-9 rounded-full" />
                          ) : (
                            <div className="w-9 h-9 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center text-sm font-bold text-primary-600">
                              {(name || '?')[0]}
                            </div>
                          )}
                          <div>
                            <p className="text-sm font-semibold text-neutral-main">
                              {name}
                              {team && <span className="text-xs text-neutral-muted font-normal ml-1">({team})</span>}
                            </p>
                            <div className="flex items-center gap-2 text-xs text-neutral-muted">
                              {detailItem.created_at && <span>요청일: {new Date(detailItem.created_at).toLocaleString('ko-KR')}</span>}
                            </div>
                          </div>
                        </>
                      );
                    })()}
                  </div>
                </div>

                <div className="mb-4">
                  <label className="block text-xs font-semibold text-neutral-sub mb-1">상세 내용</label>
                  <div className="p-3 bg-surface-sub rounded-xl text-sm text-neutral-main whitespace-pre-wrap min-h-[60px]">
                    {detailItem.detail || '(내용 없음)'}
                  </div>
                </div>

                {detailItem.file_name && (
                  <div className="mb-5">
                    <label className="block text-xs font-semibold text-neutral-sub mb-2">첨부파일</label>
                    <div className="flex items-center gap-2 p-3 bg-surface-sub rounded-xl">
                      <Paperclip size={16} className="text-neutral-muted shrink-0" />
                      <span className="text-sm text-neutral-main truncate flex-1">{detailItem.file_name}</span>
                      {(isImage || isPdf) && (
                        <button
                          onClick={async () => {
                            setPreviewLoading(true);
                            try {
                              const url = await getApprovalFileBlobUrl(detailItem.id, detailItem.file_name);
                              setPreviewUrl(url);
                              setShowPreview(true);
                            } catch { alert('미리보기를 불러올 수 없습니다.'); }
                            setPreviewLoading(false);
                          }}
                          disabled={previewLoading}
                          className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-semibold text-primary-500 hover:text-primary-600 bg-primary-50 hover:bg-primary-100 dark:bg-primary-900/20 rounded-lg transition-colors disabled:opacity-50"
                        >
                          <Eye size={14} /> {previewLoading ? '로딩...' : '미리보기'}
                        </button>
                      )}
                      <button
                        onClick={() => downloadApprovalFile(detailItem.id, detailItem.file_name)}
                        className="flex items-center gap-1 px-2.5 py-1.5 text-xs font-semibold text-green-600 hover:text-green-700 bg-green-50 hover:bg-green-100 dark:bg-green-900/20 rounded-lg transition-colors"
                      >
                        <Download size={14} /> 다운로드
                      </button>
                    </div>
                  </div>
                )}

                {detailItem.status === 'pending' && (
                  <div className="flex gap-2">
                    <button
                      onClick={async () => { await handleApproval(detailItem.id, true); setDetailItem(null); }}
                      className="flex-1 flex items-center justify-center gap-1.5 py-2.5 bg-green-500 hover:bg-green-600 text-white text-sm font-semibold rounded-xl transition-colors"
                    >
                      <Check size={16} /> Approve
                    </button>
                    <button
                      onClick={async () => { await handleApproval(detailItem.id, false); setDetailItem(null); }}
                      className="flex-1 flex items-center justify-center gap-1.5 py-2.5 bg-red-500 hover:bg-red-600 text-white text-sm font-semibold rounded-xl transition-colors"
                    >
                      <X size={16} /> Reject
                    </button>
                  </div>
                )}
              </motion.div>
            </motion.div>
          );
        })()}
      </AnimatePresence>

      {/* 파일 미리보기 모달 */}
      <AnimatePresence>
        {showPreview && previewUrl && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60"
            onClick={() => { window.URL.revokeObjectURL(previewUrl); setPreviewUrl(null); setShowPreview(false); }}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="relative bg-white dark:bg-neutral-900 rounded-2xl shadow-2xl w-full max-w-4xl mx-4 max-h-[90vh] overflow-hidden flex flex-col"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between p-4 border-b border-neutral-divider">
                <span className="text-sm font-semibold text-neutral-main">파일 미리보기</span>
                <div className="flex items-center gap-2">
                  {detailItem && (
                    <button
                      onClick={() => downloadApprovalFile(detailItem.id, detailItem.file_name)}
                      className="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-green-600 bg-green-50 hover:bg-green-100 rounded-lg transition-colors"
                    >
                      <Download size={14} /> 다운로드
                    </button>
                  )}
                  <button onClick={() => { if (previewUrl) window.URL.revokeObjectURL(previewUrl); setPreviewUrl(null); setShowPreview(false); }} className="p-1.5 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-800 text-neutral-400 hover:text-neutral-600 transition-colors">
                    <X size={20} />
                  </button>
                </div>
              </div>
              <div className="flex-1 overflow-auto p-4 flex items-center justify-center bg-surface-sub min-h-[400px]">
                {detailItem?.file_name && /\.(png|jpg|jpeg|gif|webp)$/i.test(detailItem.file_name) ? (
                  <img src={previewUrl} alt="미리보기" className="max-w-full max-h-[80vh] object-contain" />
                ) : detailItem?.file_name && /\.pdf$/i.test(detailItem.file_name) ? (
                  <iframe src={previewUrl + '#toolbar=0'} className="w-full h-[80vh] border-0" title="PDF 미리보기" />
                ) : (
                  <div className="text-center text-neutral-muted space-y-3 p-8">
                    <FileText size={48} className="mx-auto opacity-40" />
                    <p className="text-sm">이 파일 형식은 미리보기를 지원하지 않습니다.</p>
                  </div>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 삭제 확인 모달 */}
      {deleteConfirm && createPortal(
        <div className="fixed inset-0 z-[130] flex items-center justify-center bg-black/40 p-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="absolute inset-0"
            onClick={() => setDeleteConfirm(null)}
          />
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="relative bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-[2.5rem] shadow-2xl p-6 w-full max-w-sm border border-white/40 dark:border-white/10"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex flex-col items-center text-center">
              <div className="w-12 h-12 rounded-full bg-red-50 flex items-center justify-center mb-3">
                <Trash2 size={20} className="text-red-400" />
              </div>
              <h3 className="text-base font-bold text-slate-800 dark:text-white mb-1">요청을 삭제하시겠습니까?</h3>
              <p className="text-sm text-slate-400 mb-5 line-clamp-2">"{deleteConfirm.title}"</p>
              <div className="flex gap-3 w-full">
                <button
                  onClick={() => setDeleteConfirm(null)}
                  className="flex-1 py-2.5 text-xs font-black rounded-xl text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 transition-all"
                >
                  취소
                </button>
                <button
                  onClick={handleDeleteConfirm}
                  className="flex-1 py-2.5 bg-red-500 text-white text-xs font-black rounded-xl shadow-xl shadow-red-500/20 hover:bg-red-600 hover:scale-105 transition-all"
                >
                  삭제
                </button>
              </div>
            </div>
          </motion.div>
        </div>,
        document.body
      )}

      {/* 새 요청 모달 */}
      <AnimatePresence>
        {showModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
            onClick={() => setShowModal(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-[2.5rem] shadow-2xl p-8 w-full max-w-md mx-4 border border-white/40 dark:border-white/10"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-bold text-neutral-main">새 요청 올리기</h3>
                <button onClick={() => setShowModal(false)} className="w-8 h-8 rounded-lg hover:bg-slate-100 dark:hover:bg-white/5 text-slate-400 transition-colors flex items-center justify-center">
                  <X size={18} />
                </button>
              </div>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-neutral-main mb-1">유형</label>
                  <select
                    value={formData.type}
                    onChange={(e) => setFormData(prev => ({ ...prev, type: e.target.value }))}
                    className="w-full px-3 py-2 rounded-lg border border-neutral-border bg-surface-card text-neutral-main text-sm"
                  >
                    {Object.entries(typeConfig).map(([key, cfg]) => (
                      <option key={key} value={key}>{cfg.label}</option>
                    ))}
                  </select>
                </div>
                {formData.type === 'other' && (
                  <div>
                    <label className="block text-sm font-medium text-neutral-main mb-1">유형 직접 입력</label>
                    <input
                      type="text"
                      value={formData.customType}
                      onChange={(e) => setFormData(prev => ({ ...prev, customType: e.target.value }))}
                      placeholder="예: 출장 신청, 장비 요청 등"
                      className="w-full px-3 py-2 rounded-lg border border-neutral-border bg-surface-card text-neutral-main text-sm"
                    />
                  </div>
                )}
                {/* 대상 팀 / 팀원 선택 */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-neutral-main mb-1">보낼 팀</label>
                    <select
                      value={formData.target_team}
                      onChange={(e) => setFormData(prev => ({ ...prev, target_team: e.target.value, target_user_id: '' }))}
                      className="w-full px-3 py-2 rounded-lg border border-neutral-border bg-surface-card text-neutral-main text-sm"
                    >
                      <option value="">전체</option>
                      {TEAMS.map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-neutral-main mb-1">보낼 팀원</label>
                    <MemberDropdown
                      members={allMembers.filter(m => !formData.target_team || m.team === formData.target_team)}
                      value={formData.target_user_id}
                      onChange={(id) => setFormData(prev => ({ ...prev, target_user_id: id }))}
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-neutral-main mb-1">제목</label>
                  <input
                    type="text"
                    value={formData.title}
                    onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
                    placeholder="요청 제목을 입력하세요"
                    className="w-full px-3 py-2 rounded-lg border border-neutral-border bg-surface-card text-neutral-main text-sm"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-neutral-main mb-1">상세 내용</label>
                  <textarea
                    value={formData.detail}
                    onChange={(e) => setFormData(prev => ({ ...prev, detail: e.target.value }))}
                    placeholder="상세 내용을 입력하세요 (선택)"
                    rows={3}
                    className="w-full px-3 py-2 rounded-lg border border-neutral-border bg-surface-card text-neutral-main text-sm resize-none"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-neutral-main mb-1">첨부파일 (선택)</label>
                  <input
                    type="file"
                    accept=".pdf,.docx,.doc,.txt,.png,.jpg,.jpeg,.gif,.webp"
                    onChange={(e) => setFormFile(e.target.files[0] || null)}
                    className="w-full text-sm text-neutral-sub file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-primary-50 file:text-primary-600 hover:file:bg-primary-100 dark:file:bg-primary-900/30 dark:file:text-primary-400"
                  />
                  {formFile && (
                    <div className="flex items-center gap-1 mt-1 text-xs text-neutral-muted">
                      <Paperclip size={12} />
                      <span className="truncate">{formFile.name}</span>
                      <button type="button" onClick={() => setFormFile(null)} className="ml-1 p-0.5 rounded hover:bg-red-100 text-red-400 hover:text-red-600 transition-colors">
                        <X size={14} />
                      </button>
                    </div>
                  )}
                </div>
                <div className="flex gap-3 pt-6">
                  <button
                    type="submit"
                    disabled={submitting || !formData.target_user_id}
                    className="flex-1 py-4 bg-primary-700 text-white text-xs font-black rounded-xl shadow-xl hover:bg-primary-900 hover:scale-105 active:scale-95 transition-all disabled:opacity-50"
                  >
                    {submitting ? '제출 중...' : !formData.target_user_id ? '팀원 선택 필요' : '요청 제출'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowModal(false)}
                    className="flex-1 py-4 text-xs font-black rounded-xl text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 transition-all"
                  >
                    취소
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
