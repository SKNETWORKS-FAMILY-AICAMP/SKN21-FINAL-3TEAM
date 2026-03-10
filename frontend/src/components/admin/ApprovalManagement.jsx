import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
    Check, X, Coffee, GitPullRequest, FileSignature,
    Home, DoorOpen, Palette, Award, Receipt, Rocket, Server, ShieldCheck,
    RefreshCw, Trash2
} from 'lucide-react';
import client from '../../api/client';
import { approveRequest, rejectRequest, deleteApproval } from '../../api/approvals';

const typeConfig = {
    leave: { icon: Coffee, color: 'text-orange-500 bg-orange-50', label: '연차/반차' },
    remote: { icon: Home, color: 'text-teal-500 bg-teal-50', label: '재택근무' },
    room: { icon: DoorOpen, color: 'text-indigo-500 bg-indigo-50', label: '회의실' },
    design: { icon: Palette, color: 'text-pink-500 bg-pink-50', label: '디자인' },
    certificate: { icon: Award, color: 'text-yellow-600 bg-yellow-50', label: '증명서' },
    budget: { icon: Receipt, color: 'text-purple-500 bg-purple-50', label: '결재' },
    review: { icon: GitPullRequest, color: 'text-blue-500 bg-blue-50', label: 'PR 리뷰' },
    deploy: { icon: Rocket, color: 'text-green-500 bg-green-50', label: '배포' },
    infra: { icon: Server, color: 'text-slate-500 bg-slate-50', label: '인프라' },
    security: { icon: ShieldCheck, color: 'text-red-500 bg-red-50', label: '보안' },
};
const defaultTypeConfig = { icon: FileSignature, color: 'text-gray-500 bg-gray-50', label: '요청' };

const columnConfig = [
    { id: 'pending', label: 'Pending', dotColor: 'bg-sky-400' },
    { id: 'approved', label: 'Approved', dotColor: 'bg-emerald-400' },
    { id: 'rejected', label: 'Rejected', dotColor: 'bg-rose-400' },
];

export default function ApprovalManagement() {
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);

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
            alert(err.response?.data?.detail || '삭제 실패');
        }
    };

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
                className="bg-white dark:bg-neutral-800 p-3.5 rounded-xl shadow-[0_1px_4px_rgba(0,0,0,0.06)] hover:shadow-[0_4px_12px_rgba(0,0,0,0.1)] transition-all group"
            >
                <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                        <div className={`w-6 h-6 rounded-lg flex items-center justify-center ${cfg.color}`}>
                            <IconComp size={12} />
                        </div>
                        <span className="text-[10px] font-semibold text-slate-400">{cfg.label}</span>
                    </div>
                    <button
                        onClick={() => handleDelete(item.id)}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded-md hover:bg-red-50 text-slate-300 hover:text-red-400 transition-all"
                        title="삭제"
                    >
                        <Trash2 size={11} />
                    </button>
                </div>
                <h4 className="text-[12px] font-bold text-slate-700 dark:text-slate-200 leading-snug mb-1 line-clamp-2">{item.title}</h4>
                {item.detail && (
                    <p className="text-[10px] text-slate-400 line-clamp-2 mb-2">{item.detail}</p>
                )}
                <div className="flex items-center gap-2 pt-2 border-t border-slate-100 dark:border-slate-700">
                    {item.requester_avatar ? (
                        <img src={item.requester_avatar} alt="" className="w-5 h-5 rounded-full object-cover" />
                    ) : (
                        <div className="w-5 h-5 rounded-full bg-sky-100 flex items-center justify-center text-[9px] font-bold text-sky-500">
                            {(item.requester_name || '?')[0]}
                        </div>
                    )}
                    <span className="text-[10px] font-medium text-slate-500 truncate">{item.requester_name || '알 수 없음'}</span>
                    {item.created_at && (
                        <span className="text-[9px] text-slate-300 ml-auto shrink-0">
                            {new Date(item.created_at).toLocaleDateString('ko-KR', { month: 'numeric', day: 'numeric' })}
                        </span>
                    )}
                </div>
                {item.status === 'pending' && (
                    <div className="flex gap-2 mt-2.5">
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
        <div className="card p-5">
            <div className="flex items-center justify-between mb-4">
                <h2 className="font-bold text-base text-slate-700 dark:text-white">결재 요청 관리</h2>
                <button
                    onClick={loadAll}
                    disabled={loading}
                    className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400 transition-colors"
                    title="새로고침"
                >
                    <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
                </button>
            </div>

            {loading ? (
                <div className="flex items-center justify-center h-40 text-slate-400">
                    <RefreshCw className="animate-spin mr-2" size={16} /> 로딩 중...
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {columnConfig.map((col) => {
                        const colItems = items.filter(i => i.status === col.id);
                        return (
                            <div key={col.id} className="flex flex-col min-h-[300px]">
                                <div className="flex items-center justify-center gap-2 mb-2.5">
                                    <div className={`w-2 h-2 rounded-full ${col.dotColor}`} />
                                    <span className="text-xs font-bold text-slate-600 dark:text-slate-300">{col.label}</span>
                                    <span className="text-[10px] font-semibold text-slate-400 bg-slate-100 dark:bg-slate-700 px-1.5 py-0.5 rounded-full">
                                        {colItems.length}
                                    </span>
                                </div>
                                <div className="flex-1 bg-slate-50/80 dark:bg-slate-800/40 rounded-xl p-3 border border-slate-200/50 dark:border-slate-700/50 overflow-y-auto max-h-[500px]">
                                    <div className="space-y-2.5">
                                        <AnimatePresence mode="popLayout">
                                            {colItems.map(renderCard)}
                                        </AnimatePresence>
                                        {colItems.length === 0 && (
                                            <div className="h-20 flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-200 dark:border-slate-600">
                                                <span className="text-[10px] text-slate-300 dark:text-slate-500">비어 있음</span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
