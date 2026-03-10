import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Check, X, Clock, Coffee, GitPullRequest, FileText, FileSignature,
    Filter, Search, BellRing, CheckCircle2, XCircle, Trash2,
    Home, DoorOpen, Palette, Award, Receipt, Rocket, Server, ShieldCheck, RefreshCw,
    Sparkles, ArrowRight, Zap, Plus, CheckSquare, Square, ListChecks,
    CalendarPlus, CalendarClock
} from 'lucide-react';
import { listApprovals, createApproval, approveRequest, rejectRequest, deleteApproval, suggestApprovals } from '../../api/approvals';
import { createSchedule } from '../../api/schedules';
import client from '../../api/client';
import useAuthStore from '../../store/authStore';

const typeConfig = {
    leave: { icon: Coffee, color: 'text-orange-500 bg-orange-50', label: '연차/반차 신청' },
    remote: { icon: Home, color: 'text-teal-500 bg-teal-50', label: '재택근무 신청' },
    room: { icon: DoorOpen, color: 'text-indigo-500 bg-indigo-50', label: '회의실 예약' },
    design: { icon: Palette, color: 'text-pink-500 bg-pink-50', label: '디자인 에셋 요청' },
    certificate: { icon: Award, color: 'text-yellow-600 bg-yellow-50', label: '증명서 발급 요청' },
    budget: { icon: Receipt, color: 'text-purple-500 bg-purple-50', label: '결재 요청' },
    review: { icon: GitPullRequest, color: 'text-blue-500 bg-blue-50', label: 'PR 리뷰 요청' },
    deploy: { icon: Rocket, color: 'text-green-500 bg-green-50', label: '배포 승인 요청' },
    infra: { icon: Server, color: 'text-slate-500 bg-slate-50', label: '인프라/권한 신청' },
    security: { icon: ShieldCheck, color: 'text-red-500 bg-red-50', label: '보안 예외 처리' },
};
const defaultTypeConfig = { icon: FileSignature, color: 'text-gray-500 bg-gray-50', label: '요청' };

const statusBadge = {
    pending: { label: '대기중', color: 'bg-sky-50 text-sky-600 border-sky-200', dot: 'bg-sky-400' },
    approved: { label: '승인됨', color: 'bg-emerald-50 text-emerald-600 border-emerald-200', dot: 'bg-emerald-400' },
    rejected: { label: '거절됨', color: 'bg-rose-50 text-rose-600 border-rose-200', dot: 'bg-rose-400' },
};

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

/** suggested_day → 실제 날짜 변환 */
function resolveSuggestedDay(day) {
    const now = new Date();
    if (!day || day === 'today') {
        return now;
    }
    if (day === 'tomorrow') {
        const d = new Date(now);
        d.setDate(d.getDate() + 1);
        return d;
    }
    if (day === 'this_week') {
        const d = new Date(now);
        d.setDate(d.getDate() + 2);
        return d;
    }
    // YYYY-MM-DD
    const parsed = new Date(day);
    return isNaN(parsed.getTime()) ? now : parsed;
}

export default function ApprovalPanel({ onReady, externalActions }) {
    const user = useAuthStore((s) => s.user);
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [formData, setFormData] = useState({ type: 'leave', title: '', detail: '' });
    const [submitting, setSubmitting] = useState(false);
    const [suggestions, setSuggestions] = useState([]);
    const [suggestLoading, setSuggestLoading] = useState(false);
    const [suggestContext, setSuggestContext] = useState(null);
    const [suggestError, setSuggestError] = useState(null);
    const [deleteConfirm, setDeleteConfirm] = useState(null);

    // Schedule checklist state
    const [checklist, setChecklist] = useState([]);
    const [checklistLoading, setChecklistLoading] = useState(false);
    const [checklistError, setChecklistError] = useState(null);

    // Schedule suggestions state
    const [scheduleSuggestions, setScheduleSuggestions] = useState([]);
    const [schedSuggestLoading, setSchedSuggestLoading] = useState(false);
    const [schedSuggestError, setSchedSuggestError] = useState(null);
    const [addingScheduleId, setAddingScheduleId] = useState(null);

    // New Tasks tab: 'approvals' | 'schedules'
    const [newTasksTab, setNewTasksTab] = useState('approvals');

    const loadAll = async () => {
        setLoading(true);
        try {
            const [pendingRes, approvedRes, rejectedRes] = await Promise.all([
                client.get('/approvals/', { params: { status: 'pending' } }).catch(() => ({ data: [] })),
                client.get('/approvals/history', { params: { status: 'approved' } }).catch(() => ({ data: [] })),
                client.get('/approvals/history', { params: { status: 'rejected' } }).catch(() => ({ data: [] })),
            ]);
            const all = [
                ...(Array.isArray(pendingRes.data) ? pendingRes.data : []),
                ...(Array.isArray(approvedRes.data) ? approvedRes.data : []),
                ...(Array.isArray(rejectedRes.data) ? rejectedRes.data : []),
            ];
            setItems(all);
        } catch {
            setItems([]);
        } finally {
            setLoading(false);
        }
    };

    const loadChecklist = async () => {
        setChecklistLoading(true);
        setChecklistError(null);
        try {
            const res = await client.post('/approvals/checklist');
            const items = res.data?.checklist || [];

            const saved = JSON.parse(localStorage.getItem('schedule_checklist') || '{}');
            const withState = items.map((item, idx) => ({
                id: `chk-${idx}-${item.title?.slice(0, 10)}`,
                title: item.title,
                category: item.category || 'task',
                priority: item.priority || 'medium',
                due: item.due || '',
                related: item.related || '',
                done: saved[`chk-${idx}-${item.title?.slice(0, 10)}`] || false,
            }));

            setChecklist(withState);
        } catch (err) {
            const status = err.response?.status;
            const detail = err.response?.data?.detail || err.message || '알 수 없는 오류';
            console.error('Checklist load failed:', status, detail, err);
            setChecklistError(`${status || 'ERR'}: ${detail}`);
            setChecklist([]);
        } finally {
            setChecklistLoading(false);
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
            console.error('일정 추천 실패:', status, detail);
            setSchedSuggestError(`${status || 'ERR'}: ${detail}`);
        } finally {
            setSchedSuggestLoading(false);
        }
    };

    useEffect(() => { loadAll(); loadChecklist(); }, []);

    useEffect(() => {
        if (onReady && externalActions) {
            onReady({
                refresh: () => { loadAll(); loadChecklist(); if (newTasksTab === 'schedules') loadScheduleSuggestions(); else handleSuggest(); },
                openCreate: () => {
                    setFormData({ type: 'leave', title: '', detail: '' });
                    setShowModal(true);
                },
                loading
            });
        }
    }, [onReady, externalActions, loading]);

    const myItems = items.filter(i => i.requester_id === user?.id);

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
        setSubmitting(true);
        try {
            await createApproval({ type: formData.type, title: formData.title.trim(), detail: formData.detail.trim() || null });
            setShowModal(false);
            setFormData({ type: 'leave', title: '', detail: '' });
            await loadAll();
        } catch {
            alert('요청 생성에 실패했습니다.');
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
            setSuggestions([]);
        } finally {
            setSuggestLoading(false);
        }
    };

    const applySuggestion = (s) => {
        setFormData({ type: s.type, title: s.title, detail: s.detail || '' });
        setShowModal(true);
    };

    /** 추천 일정을 캘린더에 추가 */
    const addScheduleToCalendar = async (s, idx) => {
        setAddingScheduleId(idx);
        try {
            const startDate = resolveSuggestedDay(s.suggested_day);
            startDate.setHours(10, 0, 0, 0); // 기본 시작 10시

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

            // 추가 성공 → 해당 항목 제거
            setScheduleSuggestions(prev => prev.filter((_, i) => i !== idx));
        } catch (err) {
            const msg = err.response?.data?.detail || '캘린더 추가에 실패했습니다.';
            alert(msg);
        } finally {
            setAddingScheduleId(null);
        }
    };

    const toggleCheckItem = (itemId) => {
        setChecklist(prev => {
            const updated = prev.map(c => c.id === itemId ? { ...c, done: !c.done } : c);
            const saved = {};
            updated.forEach(c => { saved[c.id] = c.done; });
            localStorage.setItem('schedule_checklist', JSON.stringify(saved));
            return updated;
        });
    };

    // Load initial suggestions based on active tab
    useEffect(() => { handleSuggest(); }, []);

    /* ── Process 카드 ── */
    const renderProcessCard = (item) => {
        const cfg = typeConfig[item.type] || defaultTypeConfig;
        const IconComp = cfg.icon;
        const badge = statusBadge[item.status] || statusBadge.pending;
        return (
            <motion.div
                key={item.id}
                layout
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.2 }}
                className="bg-white dark:bg-neutral-800 p-4 rounded-xl shadow-[0_1px_4px_rgba(0,0,0,0.06)] hover:shadow-[0_4px_12px_rgba(0,0,0,0.1)] transition-all group"
            >
                <div className="flex items-center justify-between mb-2.5">
                    <div className="flex items-center gap-2">
                        <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${cfg.color}`}>
                            <IconComp size={14} />
                        </div>
                        <span className="text-[11px] font-semibold text-slate-400">{cfg.label}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${badge.color} flex items-center gap-1`}>
                            <span className={`w-1.5 h-1.5 rounded-full ${badge.dot}`} />
                            {badge.label}
                        </span>
                        <button
                            onClick={() => handleDeleteClick(item)}
                            className="opacity-0 group-hover:opacity-100 p-1 rounded-md hover:bg-red-50 text-slate-300 hover:text-red-400 transition-all"
                            title="삭제"
                        >
                            <Trash2 size={12} />
                        </button>
                    </div>
                </div>
                <h4 className="text-[13px] font-bold text-slate-700 dark:text-slate-200 leading-snug mb-1 line-clamp-2">{item.title}</h4>
                {item.detail && (
                    <p className="text-[11px] text-slate-400 line-clamp-2 mb-3">{item.detail}</p>
                )}
                {item.created_at && (
                    <div className="flex items-center pt-2.5 border-t border-slate-100 dark:border-slate-700">
                        <span className="text-[10px] text-slate-300">
                            {new Date(item.created_at).toLocaleDateString('ko-KR', { month: 'numeric', day: 'numeric', hour: 'numeric', minute: 'numeric' })}
                        </span>
                    </div>
                )}
            </motion.div>
        );
    };

    /* ── New Tasks 탭 전환 시 데이터 로드 ── */
    const switchNewTasksTab = (tab) => {
        setNewTasksTab(tab);
        if (tab === 'schedules' && scheduleSuggestions.length === 0 && !schedSuggestLoading) {
            loadScheduleSuggestions();
        }
    };

    return (
        <div className="space-y-4">
            {loading ? (
                <div className="flex items-center justify-center h-64 text-slate-400">
                    <RefreshCw className="animate-spin mr-2" size={18} /> 로딩 중...
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
                    {/* ── Column 1: Process (내 요청) ── */}
                    <div className="flex flex-col min-h-[420px]">
                        <div className="flex items-center justify-center gap-2 mb-3">
                            <div className="w-2 h-2 rounded-full bg-sky-400" />
                            <span className="text-sm font-bold text-slate-600 dark:text-slate-300 tracking-tight">Process</span>
                            <span className="text-[11px] font-semibold text-slate-400 bg-slate-100 dark:bg-slate-700 px-2 py-0.5 rounded-full">
                                {myItems.length}
                            </span>
                        </div>
                        <div className="flex-1 bg-slate-50/80 dark:bg-slate-800/40 rounded-2xl p-4 border border-slate-200/50 dark:border-slate-700/50 overflow-y-auto max-h-[600px]">
                            <div className="space-y-3">
                                <AnimatePresence mode="popLayout">
                                    {myItems.map(renderProcessCard)}
                                </AnimatePresence>
                                {myItems.length === 0 && (
                                    <div className="h-28 flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 dark:border-slate-600">
                                        <FileSignature size={16} className="text-slate-300 mb-1" />
                                        <span className="text-[11px] text-slate-300 dark:text-slate-500">보낸 요청이 없습니다</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* ── Column 2: Schedule (체크리스트) ── */}
                    <div className="flex flex-col min-h-[420px]">
                        <div className="flex items-center justify-center gap-2 mb-3">
                            <div className="w-2 h-2 rounded-full bg-emerald-400" />
                            <span className="text-sm font-bold text-slate-600 dark:text-slate-300 tracking-tight">Schedule</span>
                            <span className="text-[11px] font-semibold text-slate-400 bg-slate-100 dark:bg-slate-700 px-2 py-0.5 rounded-full">
                                {checklist.length}
                            </span>
                            <button
                                onClick={loadChecklist}
                                disabled={checklistLoading}
                                className="p-1 rounded-lg hover:bg-slate-200/60 dark:hover:bg-slate-600/40 text-slate-400 hover:text-slate-600 transition-colors"
                                title="새로고침"
                            >
                                <RefreshCw size={12} className={checklistLoading ? 'animate-spin' : ''} />
                            </button>
                        </div>
                        <div className="flex-1 bg-slate-50/80 dark:bg-slate-800/40 rounded-2xl p-4 border border-slate-200/50 dark:border-slate-700/50 overflow-y-auto max-h-[600px]">
                            {checklistLoading ? (
                                <div className="flex flex-col items-center justify-center py-12">
                                    <div className="relative w-10 h-10 mb-3">
                                        <div className="absolute inset-0 rounded-full border-2 border-emerald-100" />
                                        <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-emerald-400 animate-spin" />
                                        <ListChecks size={14} className="absolute inset-0 m-auto text-emerald-400" />
                                    </div>
                                    <p className="text-xs text-slate-400">AI 분석 중...</p>
                                </div>
                            ) : checklistError ? (
                                <div className="h-28 flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-rose-200 dark:border-rose-800 bg-rose-50/50 dark:bg-rose-900/10">
                                    <XCircle size={14} className="text-rose-300 mb-1" />
                                    <span className="text-[10px] text-rose-400">{checklistError}</span>
                                    <button onClick={loadChecklist} className="mt-1.5 text-[10px] text-sky-500 hover:underline">다시 시도</button>
                                </div>
                            ) : checklist.length === 0 ? (
                                <div className="h-28 flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 dark:border-slate-600">
                                    <ListChecks size={16} className="text-slate-300 mb-1" />
                                    <span className="text-[11px] text-slate-300 dark:text-slate-500">할 일이 없습니다</span>
                                </div>
                            ) : (
                                <div className="space-y-2">
                                    {checklist.length > 0 && (
                                        <div className="mb-3">
                                            <div className="flex items-center justify-between mb-1.5">
                                                <span className="text-[10px] font-semibold text-slate-400">진행률</span>
                                                <span className="text-[10px] font-bold text-emerald-500">
                                                    {checklist.filter(c => c.done).length}/{checklist.length}
                                                </span>
                                            </div>
                                            <div className="w-full h-1.5 bg-slate-200 dark:bg-slate-600 rounded-full overflow-hidden">
                                                <div
                                                    className="h-full bg-emerald-400 rounded-full transition-all duration-500"
                                                    style={{ width: `${(checklist.filter(c => c.done).length / checklist.length) * 100}%` }}
                                                />
                                            </div>
                                        </div>
                                    )}
                                    <AnimatePresence mode="popLayout">
                                        {checklist.map((item) => {
                                            const catColors = {
                                                meeting: 'bg-indigo-50 text-indigo-500',
                                                task: 'bg-sky-50 text-sky-500',
                                                review: 'bg-amber-50 text-amber-500',
                                                prepare: 'bg-violet-50 text-violet-500',
                                                report: 'bg-teal-50 text-teal-500',
                                            };
                                            const priColors = {
                                                high: 'text-red-400',
                                                medium: 'text-amber-400',
                                                low: 'text-slate-300',
                                            };
                                            return (
                                                <motion.div
                                                    key={item.id}
                                                    layout
                                                    initial={{ opacity: 0, y: 4 }}
                                                    animate={{ opacity: 1, y: 0 }}
                                                    exit={{ opacity: 0, x: -20 }}
                                                    className={`flex items-start gap-3 p-3 rounded-xl bg-white dark:bg-neutral-800 shadow-[0_1px_4px_rgba(0,0,0,0.06)] hover:shadow-[0_4px_12px_rgba(0,0,0,0.1)] cursor-pointer transition-all ${item.done ? 'opacity-60' : ''}`}
                                                    onClick={() => toggleCheckItem(item.id)}
                                                >
                                                    <div className="mt-0.5 shrink-0">
                                                        {item.done ? (
                                                            <CheckSquare size={16} className="text-emerald-500" />
                                                        ) : (
                                                            <Square size={16} className={priColors[item.priority] || 'text-slate-300'} />
                                                        )}
                                                    </div>
                                                    <div className="flex-1 min-w-0">
                                                        <h4 className={`text-[12px] font-bold leading-snug line-clamp-2 ${item.done ? 'text-slate-400 line-through' : 'text-slate-700 dark:text-slate-200'}`}>
                                                            {item.title}
                                                        </h4>
                                                        <div className="flex items-center gap-1.5 mt-1">
                                                            <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded-md ${catColors[item.category] || catColors.task}`}>
                                                                {item.category}
                                                            </span>
                                                            {item.due && (
                                                                <span className="text-[9px] text-slate-300">{item.due}</span>
                                                            )}
                                                        </div>
                                                        {item.related && (
                                                            <span className="text-[9px] text-slate-300 mt-0.5 block truncate">→ {item.related}</span>
                                                        )}
                                                    </div>
                                                </motion.div>
                                            );
                                        })}
                                    </AnimatePresence>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* ── Column 3: New Tasks (AI 추천 - 결재 + 일정) ── */}
                    <div className="flex flex-col min-h-[420px]">
                        <div className="flex items-center justify-center gap-2 mb-3">
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
                                className={`flex-1 py-1.5 text-[11px] font-bold rounded-lg transition-all ${newTasksTab === 'approvals' ? 'bg-violet-100 text-violet-600' : 'text-slate-400 hover:bg-slate-100'}`}
                            >
                                결재 추천
                            </button>
                            <button
                                onClick={() => switchNewTasksTab('schedules')}
                                className={`flex-1 py-1.5 text-[11px] font-bold rounded-lg transition-all flex items-center justify-center gap-1 ${newTasksTab === 'schedules' ? 'bg-violet-100 text-violet-600' : 'text-slate-400 hover:bg-slate-100'}`}
                            >
                                <CalendarClock size={11} /> 일정 추천
                            </button>
                        </div>

                        <div className="flex-1 bg-slate-50/80 dark:bg-slate-800/40 rounded-2xl p-4 border border-slate-200/50 dark:border-slate-700/50 overflow-y-auto max-h-[560px]">
                            {/* ── 결재 추천 탭 ── */}
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
                                    ) : suggestions.length === 0 ? (
                                        <div className="h-28 flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 dark:border-slate-600">
                                            <Zap size={14} className="text-slate-300 mb-1" />
                                            <span className="text-[11px] text-slate-300">추천 없음</span>
                                        </div>
                                    ) : (
                                        <div className="grid grid-cols-2 gap-2.5">
                                            <AnimatePresence mode="popLayout">
                                                {suggestions.map((s, idx) => {
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

                            {/* ── 일정 추천 탭 ── */}
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
                                                                {isAdding ? (
                                                                    <RefreshCw size={12} className="animate-spin" />
                                                                ) : (
                                                                    <CalendarPlus size={12} />
                                                                )}
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
            {showModal && createPortal(
                <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/40 p-4">
                    <AnimatePresence>
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="absolute inset-0"
                            onClick={() => setShowModal(false)}
                        />
                    </AnimatePresence>
                    <motion.div
                        initial={{ scale: 0.95, opacity: 0, y: 20 }}
                        animate={{ scale: 1, opacity: 1, y: 0 }}
                        className="relative bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-[2.5rem] shadow-2xl p-8 w-full max-w-md mx-4 overflow-hidden border border-white/40 dark:border-white/10"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="flex items-center justify-between mb-6">
                            <h3 className="text-lg font-bold text-slate-800 dark:text-white">새 요청 올리기</h3>
                            <button onClick={() => setShowModal(false)} className="w-8 h-8 rounded-lg hover:bg-slate-100 dark:hover:bg-white/5 text-slate-400 transition-colors flex items-center justify-center">
                                <X size={18} />
                            </button>
                        </div>
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div>
                                <label className="block text-[11px] font-semibold text-slate-400 mb-1.5 ml-0.5">유형</label>
                                <select
                                    value={formData.type}
                                    onChange={(e) => setFormData(prev => ({ ...prev, type: e.target.value }))}
                                    className="w-full px-3.5 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm outline-none focus:ring-2 focus:ring-sky-400 focus:border-transparent transition-all"
                                >
                                    {Object.entries(typeConfig).map(([key, cfg]) => (
                                        <option key={key} value={key}>{cfg.label}</option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label className="block text-[11px] font-semibold text-slate-400 mb-1.5 ml-0.5">제목</label>
                                <input
                                    type="text"
                                    value={formData.title}
                                    onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
                                    placeholder="요청 제목을 입력하세요"
                                    className="w-full px-3.5 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm outline-none focus:ring-2 focus:ring-sky-400 focus:border-transparent transition-all placeholder:text-slate-300"
                                    required
                                />
                            </div>
                            <div>
                                <label className="block text-[11px] font-semibold text-slate-400 mb-1.5 ml-0.5">상세 내용</label>
                                <textarea
                                    value={formData.detail}
                                    onChange={(e) => setFormData(prev => ({ ...prev, detail: e.target.value }))}
                                    placeholder="상세 내용을 입력하세요 (선택)"
                                    rows={4}
                                    className="w-full px-3.5 py-2.5 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm outline-none focus:ring-2 focus:ring-sky-400 focus:border-transparent resize-none transition-all placeholder:text-slate-300"
                                />
                            </div>
                            <div className="flex gap-3 pt-3">
                                <button
                                    type="button"
                                    onClick={() => setShowModal(false)}
                                    className="flex-1 py-2.5 text-xs font-black rounded-xl text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 transition-all"
                                >
                                    취소
                                </button>
                                <button
                                    type="submit"
                                    disabled={submitting}
                                    className="flex-1 py-2.5 bg-primary-700 text-white text-xs font-black rounded-xl shadow-xl shadow-primary-700/20 hover:bg-primary-800 hover:scale-105 transition-all disabled:opacity-50"
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
