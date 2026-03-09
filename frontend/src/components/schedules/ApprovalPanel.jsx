import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Check, X, Clock, Coffee, GitPullRequest, FileText, FileSignature,
    Filter, Search, BellRing, CheckCircle2, XCircle, Trash2,
    Home, DoorOpen, Palette, Award, Receipt, Rocket, Server, ShieldCheck, RefreshCw
} from 'lucide-react';
import { listApprovals, createApproval, approveRequest, rejectRequest, deleteApproval } from '../../api/approvals';
import client from '../../api/client';

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
const defaultTypeConfig = { icon: FileSignature, color: 'text-gray-500 bg-gray-100 dark:bg-gray-900/30', label: '요청' };

const statusConfig = {
    pending: { label: 'Pending', color: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400', icon: Clock },
    approved: { label: 'Approved', color: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400', icon: CheckCircle2 },
    rejected: { label: 'Rejected', color: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400', icon: XCircle },
};

export default function ApprovalPanel({ onReady, externalActions }) {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('all');
    const [typeFilter, setTypeFilter] = useState('all');
    const [search, setSearch] = useState('');
    const [showModal, setShowModal] = useState(false);
    const [formData, setFormData] = useState({ type: 'leave', title: '', detail: '' });
    const [submitting, setSubmitting] = useState(false);

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

    const filtered = items.filter(i => {
        if (filter !== 'all' && i.status !== filter) return false;
        if (typeFilter !== 'all' && i.type !== typeFilter) return false;
        if (search && !i.title.toLowerCase().includes(search.toLowerCase()) && !(i.requester_name || '').toLowerCase().includes(search.toLowerCase())) return false;
        return true;
    });

    const counts = {
        all: items.length,
        pending: items.filter(i => i.status === 'pending').length,
        approved: items.filter(i => i.status === 'approved').length,
        rejected: items.filter(i => i.status === 'rejected').length,
    };

    return (
        <div className="space-y-6">
            {/* Header (Only if not externalActions) */}
            {!externalActions && (
                <div className="flex items-center justify-between">
                    <h2 className="text-lg font-bold text-neutral-main">결재 요청 내역</h2>
                    <button
                        onClick={() => setShowModal(true)}
                        className="px-4 py-2 bg-primary-500 hover:bg-primary-600 text-white text-sm font-semibold rounded-xl transition-colors shadow-sm"
                    >
                        + 새 요청
                    </button>
                </div>
            )}

            {/* Status Tabs */}
            <div className="flex gap-2">
                {[
                    { key: 'all', label: '전체' },
                    { key: 'pending', label: 'Pending' },
                    { key: 'approved', label: 'Approved' },
                    { key: 'rejected', label: 'Rejected' },
                ].map(tab => (
                    <button
                        key={tab.key}
                        onClick={() => setFilter(tab.key)}
                        className={`px-4 py-2 text-sm font-semibold rounded-xl transition-all ${filter === tab.key
                            ? 'bg-primary-500 text-white shadow-sm'
                            : 'bg-white dark:bg-neutral-800 text-neutral-sub hover:bg-neutral-50 dark:hover:bg-neutral-700 border border-neutral-200 dark:border-neutral-700'
                            }`}
                    >
                        {tab.label}
                        <span className={`ml-1.5 text-xs px-1.5 py-0.5 rounded-full ${filter === tab.key ? 'bg-white/20' : 'bg-neutral-100 dark:bg-neutral-700'
                            }`}>
                            {counts[tab.key]}
                        </span>
                    </button>
                ))}
            </div>

            {/* Filters Row */}
            <div className="p-4 bg-surface-card rounded-2xl border border-neutral-100 dark:border-neutral-700 space-y-4">
                <div className="flex gap-3">
                    <div className="relative flex-1">
                        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-muted" />
                        <input
                            type="text"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            placeholder="제목 또는 요청자 검색..."
                            className="w-full pl-9 pr-4 py-2 rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-sm focus:ring-2 focus:ring-primary-500 outline-none"
                        />
                    </div>
                    <div className="flex items-center gap-2">
                        <Filter size={16} className="text-neutral-muted" />
                        <select
                            value={typeFilter}
                            onChange={(e) => setTypeFilter(e.target.value)}
                            className="px-3 py-2 rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 text-sm focus:ring-2 focus:ring-primary-500 outline-none"
                        >
                            <option value="all">모든 유형</option>
                            {Object.entries(typeConfig).map(([key, cfg]) => (
                                <option key={key} value={key}>{cfg.label}</option>
                            ))}
                        </select>
                    </div>
                </div>
            </div>

            {/* List */}
            {loading ? (
                <div className="flex items-center justify-center h-48 text-neutral-muted">
                    <RefreshCw className="animate-spin mr-2" size={20} /> 로딩 중...
                </div>
            ) : filtered.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-48 bg-neutral-50 dark:bg-neutral-800/30 rounded-2xl border-2 border-dashed border-neutral-200 dark:border-neutral-700">
                    <div className="p-3 bg-neutral-100 dark:bg-neutral-700 rounded-full mb-3 text-neutral-400">
                        <Search size={32} />
                    </div>
                    <p className="text-sm font-medium text-neutral-muted">검색 결과가 없습니다</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 gap-3">
                    <AnimatePresence>
                        {filtered.map((item, idx) => {
                            const cfg = typeConfig[item.type] || defaultTypeConfig;
                            const stCfg = statusConfig[item.status] || statusConfig.pending;
                            const IconComp = cfg.icon;
                            const StatusIcon = stCfg.icon;
                            return (
                                <motion.div
                                    key={item.id}
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0, x: -20 }}
                                    transition={{ duration: 0.2, delay: idx * 0.03 }}
                                    className="bg-white dark:bg-neutral-800 p-5 rounded-2xl border border-neutral-100 dark:border-neutral-700 shadow-sm hover:shadow-md transition-shadow relative overflow-hidden group"
                                >
                                    <div className="flex items-start justify-between gap-4">
                                        {/* Left: Info */}
                                        <div className="flex items-start gap-4 flex-1 min-w-0">
                                            <div className={`p-2.5 rounded-xl shrink-0 ${cfg.color}`}>
                                                <IconComp size={20} />
                                            </div>
                                            <div className="min-w-0 flex-1">
                                                <div className="flex items-center gap-2 mb-1">
                                                    <span className="text-xs font-bold text-neutral-sub px-2 py-0.5 bg-neutral-50 dark:bg-neutral-700 rounded-full">
                                                        {cfg.label}
                                                    </span>
                                                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full flex items-center gap-1 ${stCfg.color}`}>
                                                        <StatusIcon size={12} />
                                                        {stCfg.label}
                                                    </span>
                                                </div>
                                                <h3 className="text-sm font-bold text-neutral-main truncate group-hover:text-primary-600 transition-colors">{item.title}</h3>
                                                {item.detail && (
                                                    <p className="text-xs text-neutral-muted mt-0.5 line-clamp-1">{item.detail}</p>
                                                )}
                                                <div className="flex items-center gap-2 mt-2">
                                                    {item.requester_avatar ? (
                                                        <img src={item.requester_avatar} alt="" className="w-5 h-5 rounded-full border border-neutral-200 dark:border-neutral-700" />
                                                    ) : (
                                                        <div className="w-5 h-5 rounded-full bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center text-[10px] font-black text-primary-600">
                                                            {(item.requester_name || '?')[0]}
                                                        </div>
                                                    )}
                                                    <span className="text-xs font-medium text-neutral-sub">{item.requester_name || '알 수 없음'}</span>
                                                    {item.target_team && (
                                                        <span className="text-xs text-neutral-muted">· {item.target_team}</span>
                                                    )}
                                                    {item.created_at && (
                                                        <span className="text-xs text-neutral-muted">· {new Date(item.created_at).toLocaleDateString('ko-KR')}</span>
                                                    )}
                                                </div>
                                            </div>
                                        </div>

                                        {/* Right: Actions */}
                                        <div className="flex gap-2 shrink-0">
                                            {item.status === 'pending' && (
                                                <>
                                                    <button
                                                        onClick={() => handleApproval(item.id, true)}
                                                        className="flex items-center gap-1 px-3 py-2 bg-green-50 dark:bg-green-900/20 hover:bg-green-500 text-green-600 hover:text-white text-xs font-bold rounded-xl transition-all border border-green-100 dark:border-green-800"
                                                    >
                                                        <Check size={14} /> Approve
                                                    </button>
                                                    <button
                                                        onClick={() => handleApproval(item.id, false)}
                                                        className="flex items-center gap-1 px-3 py-2 bg-red-50 dark:bg-red-900/20 hover:bg-red-500 text-red-600 hover:text-white text-xs font-bold rounded-xl transition-all border border-red-100 dark:border-red-800"
                                                    >
                                                        <X size={14} /> Reject
                                                    </button>
                                                </>
                                            )}
                                            <button
                                                onClick={() => handleDelete(item.id)}
                                                className="flex items-center gap-1 px-2.5 py-2 bg-neutral-50 hover:bg-red-500 text-neutral-400 hover:text-white text-xs font-semibold rounded-xl transition-all dark:bg-neutral-700 dark:hover:bg-red-500 border border-neutral-100 dark:border-neutral-600"
                                                title="삭제"
                                            >
                                                <Trash2 size={14} />
                                            </button>
                                        </div>
                                    </div>
                                </motion.div>
                            );
                        })}
                    </AnimatePresence>
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
                            className="absolute inset-0 bg-neutral-900/40 backdrop-blur-sm"
                            onClick={() => setShowModal(false)}
                        />
                    </AnimatePresence>
                    <motion.div
                        initial={{ scale: 0.95, opacity: 0, y: 20 }}
                        animate={{ scale: 1, opacity: 1, y: 0 }}
                        className="relative bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-[2rem] shadow-2xl p-8 w-full max-w-md mx-4 overflow-hidden border border-white/40 dark:border-white/10"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="flex items-center justify-between mb-8">
                            <h3 className="text-2xl font-black text-neutral-900 dark:text-white tracking-tighter">새 요청 올리기</h3>
                            <button onClick={() => setShowModal(false)} className="w-10 h-10 rounded-xl hover:bg-neutral-100 dark:hover:bg-white/5 text-neutral-400 transition-colors flex items-center justify-center">
                                <X size={20} />
                            </button>
                        </div>
                        <form onSubmit={handleSubmit} className="space-y-5">
                            <div>
                                <label className="block text-[11px] font-black uppercase tracking-wider text-neutral-400 mb-1.5 ml-1">유형</label>
                                <select
                                    value={formData.type}
                                    onChange={(e) => setFormData(prev => ({ ...prev, type: e.target.value }))}
                                    className="w-full px-4 py-3 rounded-xl border border-neutral-200 dark:border-white/10 bg-white/50 dark:bg-black/20 text-sm outline-none focus:ring-2 focus:ring-primary-500 transition-all"
                                >
                                    {Object.entries(typeConfig).map(([key, cfg]) => (
                                        <option key={key} value={key}>{cfg.label}</option>
                                    ))}
                                </select>
                            </div>
                            <div>
                                <label className="block text-[11px] font-black uppercase tracking-wider text-neutral-400 mb-1.5 ml-1">제목</label>
                                <input
                                    type="text"
                                    value={formData.title}
                                    onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
                                    placeholder="요청 제목을 입력하세요"
                                    className="w-full px-4 py-3 rounded-xl border border-neutral-200 dark:border-white/10 bg-white/50 dark:bg-black/20 text-sm outline-none focus:ring-2 focus:ring-primary-500 transition-all placeholder:text-neutral-300"
                                    required
                                />
                            </div>
                            <div>
                                <label className="block text-[11px] font-black uppercase tracking-wider text-neutral-400 mb-1.5 ml-1">상세 내용</label>
                                <textarea
                                    value={formData.detail}
                                    onChange={(e) => setFormData(prev => ({ ...prev, detail: e.target.value }))}
                                    placeholder="상세 내용을 입력하세요 (선택)"
                                    rows={4}
                                    className="w-full px-4 py-3 rounded-xl border border-neutral-200 dark:border-white/10 bg-white/50 dark:bg-black/20 text-sm outline-none focus:ring-2 focus:ring-primary-500 resize-none transition-all placeholder:text-neutral-300"
                                />
                            </div>
                            <div className="flex gap-3 pt-4">
                                <button
                                    type="button"
                                    onClick={() => setShowModal(false)}
                                    className="flex-1 py-3 text-xs font-black rounded-xl text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 transition-all"
                                >
                                    취소
                                </button>
                                <button
                                    type="submit"
                                    disabled={submitting}
                                    className="flex-1 py-3 bg-primary-700 text-white text-xs font-black rounded-xl shadow-xl shadow-primary-700/20 hover:bg-primary-800 hover:scale-105 transition-all disabled:opacity-50"
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
