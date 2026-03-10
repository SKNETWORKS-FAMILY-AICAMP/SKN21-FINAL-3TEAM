import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Check, X, Clock, Coffee, GitPullRequest, FileText, FileSignature,
    Filter, Search, BellRing, CheckCircle2, XCircle, Trash2,
    Home, DoorOpen, Palette, Award, Receipt, Rocket, Server, ShieldCheck, RefreshCw,
    Sparkles, ArrowRight, Zap, Plus
} from 'lucide-react';
import { listApprovals, createApproval, approveRequest, rejectRequest, deleteApproval, suggestApprovals } from '../../api/approvals';
import client from '../../api/client';

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

const columnConfig = [
    { id: 'pending', label: 'Pending', dotColor: 'bg-sky-400' },
    { id: 'approved', label: 'Approved', dotColor: 'bg-emerald-400' },
    { id: 'rejected', label: 'Rejected', dotColor: 'bg-rose-400' },
];

const priorityBadge = {
    high: 'bg-red-50 text-red-500',
    medium: 'bg-amber-50 text-amber-500',
    low: 'bg-green-50 text-green-500',
};

export default function ApprovalPanel({ onReady, externalActions }) {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [formData, setFormData] = useState({ type: 'leave', title: '', detail: '' });
    const [submitting, setSubmitting] = useState(false);
    const [suggestions, setSuggestions] = useState([]);
    const [suggestLoading, setSuggestLoading] = useState(false);
    const [suggestContext, setSuggestContext] = useState(null);
    const [suggestError, setSuggestError] = useState(null);

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

    useEffect(() => { loadAll(); }, []);

    useEffect(() => {
        if (onReady && externalActions) {
            onReady({
                refresh: () => loadAll(),
                openCreate: () => setShowModal(true),
                loading
            });
        }
    }, [onReady, externalActions, loading]);

    const handleApproval = async (id, approve) => {
        try {
            if (approve) await approveRequest(id);
            else await rejectRequest(id);
            await loadAll();
        } catch (err) {
            console.error('Action failed', err);
        }
    };

    const handleDelete = async (id) => {
        if (!confirm('이 요청을 삭제하시겠습니까?')) return;
        try {
            await deleteApproval(id);
            await loadAll();
        } catch (err) {
            const msg = err.response?.data?.detail || '삭제에 실패했습니다.';
            alert(msg);
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

    useEffect(() => { handleSuggest(); }, []);

    /* ── 카드 렌더 ── */
    const renderCard = (item) => {
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
                className="bg-white dark:bg-neutral-800 p-4 rounded-xl shadow-[0_1px_4px_rgba(0,0,0,0.06)] hover:shadow-[0_4px_12px_rgba(0,0,0,0.1)] transition-all group"
            >
                {/* Type badge + delete */}
                <div className="flex items-center justify-between mb-2.5">
                    <div className="flex items-center gap-2">
                        <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${cfg.color}`}>
                            <IconComp size={14} />
                        </div>
                        <span className="text-[11px] font-semibold text-slate-400">{cfg.label}</span>
                    </div>
                    <button
                        onClick={() => handleDelete(item.id)}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded-md hover:bg-red-50 text-slate-300 hover:text-red-400 transition-all"
                        title="삭제"
                    >
                        <Trash2 size={12} />
                    </button>
                </div>

                {/* Title & detail */}
                <h4 className="text-[13px] font-bold text-slate-700 dark:text-slate-200 leading-snug mb-1 line-clamp-2">{item.title}</h4>
                {item.detail && (
                    <p className="text-[11px] text-slate-400 line-clamp-2 mb-3">{item.detail}</p>
                )}

                {/* Requester */}
                <div className="flex items-center gap-2 pt-2.5 border-t border-slate-100 dark:border-slate-700">
                    {item.requester_avatar ? (
                        <img src={item.requester_avatar} alt="" className="w-6 h-6 rounded-full object-cover" />
                    ) : (
                        <div className="w-6 h-6 rounded-full bg-sky-100 flex items-center justify-center text-[10px] font-bold text-sky-500">
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

                {/* Pending actions */}
                {item.status === 'pending' && (
                    <div className="flex gap-2 mt-3">
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
                )}
            </motion.div>
        );
    };

    return (
        <div className="space-y-4">
            {/* 4-column Kanban Board */}
            {loading ? (
                <div className="flex items-center justify-center h-64 text-slate-400">
                    <RefreshCw className="animate-spin mr-2" size={18} /> 로딩 중...
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5">
                    {/* Pending / Approved / Rejected columns */}
                    {columnConfig.map((col) => {
                        const colItems = items.filter(i => i.status === col.id);
                        return (
                            <div key={col.id} className="flex flex-col min-h-[420px]">
                                {/* Column label (top) */}
                                <div className="flex items-center justify-center gap-2 mb-3">
                                    <div className={`w-2 h-2 rounded-full ${col.dotColor}`} />
                                    <span className="text-sm font-bold text-slate-600 dark:text-slate-300 tracking-tight">{col.label}</span>
                                    <span className="text-[11px] font-semibold text-slate-400 bg-slate-100 dark:bg-slate-700 px-2 py-0.5 rounded-full">
                                        {colItems.length}
                                    </span>
                                </div>

                                {/* Column container */}
                                <div className="flex-1 bg-slate-50/80 dark:bg-slate-800/40 rounded-2xl p-4 border border-slate-200/50 dark:border-slate-700/50">
                                    {/* Cards */}
                                    <div className="space-y-3">
                                        <AnimatePresence mode="popLayout">
                                            {colItems.map(renderCard)}
                                        </AnimatePresence>

                                        {colItems.length === 0 && (
                                            <div className="h-28 flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 dark:border-slate-600">
                                                <span className="text-[11px] text-slate-300 dark:text-slate-500">비어 있음</span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        );
                    })}

                    {/* AI 추천 Column */}
                    <div className="flex flex-col min-h-[420px]">
                        {/* Column label (top) */}
                        <div className="flex items-center justify-center gap-2 mb-3">
                            <div className="w-2 h-2 rounded-full bg-violet-400" />
                            <span className="text-sm font-bold text-slate-600 dark:text-slate-300 tracking-tight">New Tasks</span>
                            <span className="text-[11px] font-semibold text-slate-400 bg-slate-100 dark:bg-slate-700 px-2 py-0.5 rounded-full">
                                {suggestions.length}
                            </span>
                            <button
                                onClick={handleSuggest}
                                disabled={suggestLoading}
                                className="p-1 rounded-lg hover:bg-slate-200/60 dark:hover:bg-slate-600/40 text-slate-400 hover:text-slate-600 transition-colors"
                                title="새로고침"
                            >
                                <RefreshCw size={12} className={suggestLoading ? 'animate-spin' : ''} />
                            </button>
                        </div>

                        {/* Column container */}
                        <div className="flex-1 bg-slate-50/80 dark:bg-slate-800/40 rounded-2xl p-4 border border-slate-200/50 dark:border-slate-700/50">
                            {/* Context badges */}
                            {suggestContext && !suggestLoading && (
                                <div className="flex flex-wrap gap-1.5 mb-3">
                                    <span className="text-[9px] font-semibold px-2 py-0.5 rounded-full bg-sky-50 text-sky-500">
                                        태스크 {suggestContext.total_tasks}
                                    </span>
                                    <span className="text-[9px] font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-500">
                                        완료 {suggestContext.done_pct}%
                                    </span>
                                    <span className="text-[9px] font-semibold px-2 py-0.5 rounded-full bg-violet-50 text-violet-500">
                                        일정 {suggestContext.upcoming_events}
                                    </span>
                                </div>
                            )}

                            {/* AI Suggestion Cards — 2-column grid like "New Tasks" */}
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
                                            const IconComp = cfg.icon;
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
                        </div>

                    </div>
                </div>
            )}

            {/* 새 요청 모달 */}
            {showModal && createPortal(
                <div className="fixed inset-0 z-[120] flex items-center justify-center p-4">
                    <AnimatePresence>
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="absolute inset-0 bg-slate-900/30 backdrop-blur-sm"
                            onClick={() => setShowModal(false)}
                        />
                    </AnimatePresence>
                    <motion.div
                        initial={{ scale: 0.95, opacity: 0, y: 20 }}
                        animate={{ scale: 1, opacity: 1, y: 0 }}
                        className="relative bg-white dark:bg-neutral-900 rounded-2xl shadow-2xl p-8 w-full max-w-md mx-4 overflow-hidden border border-slate-200/50 dark:border-white/10"
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
                                    className="flex-1 py-2.5 text-xs font-semibold rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-50 transition-all"
                                >
                                    취소
                                </button>
                                <button
                                    type="submit"
                                    disabled={submitting}
                                    className="flex-1 py-2.5 bg-slate-800 text-white text-xs font-bold rounded-lg shadow-lg shadow-slate-800/20 hover:bg-slate-900 transition-all disabled:opacity-50"
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
