import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Check, X, FileSignature, Coffee, HelpCircle, BellRing, ChevronUp, ChevronDown } from 'lucide-react';

const initialApprovals = [
    { id: 1, type: 'leave', title: '연차 신청서', requester: 'Ralph Edwards', detail: '3일 (Feb 12 - Feb 14)', avatar: 'https://i.pravatar.cc/150?u=3', icon: Coffee, color: 'text-orange-500 bg-orange-100 dark:bg-orange-900/30' },
    { id: 2, type: 'review', title: 'PR 리뷰 요청', requester: 'Cody Fisher', detail: 'feat/auth-module #42', avatar: 'https://i.pravatar.cc/150?u=2', icon: FileSignature, color: 'text-blue-500 bg-blue-100 dark:bg-blue-900/30' },
    { id: 3, type: 'budget', title: '품의서 결재', requester: 'Brooklyn Simmons', detail: '디자인 에셋 구매 (₩150,000)', avatar: 'https://i.pravatar.cc/150?u=1', icon: HelpCircle, color: 'text-purple-500 bg-purple-100 dark:bg-purple-900/30' },
];

export default function ApprovalQueueWidget() {
    const [approvals, setApprovals] = useState(initialApprovals);
    const [isCollapsed, setIsCollapsed] = useState(false);

    const handleAction = (id, isApproved) => {
        // 애니메이션을 위해 먼저 상태에서 제거
        setApprovals(prev => prev.filter(a => a.id !== id));
    };

    return (
        <div className="card flex flex-col p-6 shadow-soft transition-all duration-300">
            <div
                className="flex items-center justify-between mb-4 cursor-pointer"
                onClick={() => setIsCollapsed(!isCollapsed)}
            >
                <h3 className="text-xl font-bold text-neutral-main flex items-center gap-2">
                    <BellRing className="text-accent-500" size={24} />
                    Needs Attention
                    {approvals.length > 0 && (
                        <span className="bg-accent-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full ml-1">
                            {approvals.length}
                        </span>
                    )}
                </h3>
                <div className="flex items-center gap-3">
                    <button
                        className="text-xs font-bold text-primary-600 hover:text-primary-700 transition-colors"
                        onClick={(e) => e.stopPropagation()}
                    >
                        View All History
                    </button>
                    <button className="text-neutral-muted hover:text-primary-500 transition-colors p-1 rounded-full hover:bg-surface-hover">
                        {isCollapsed ? <ChevronDown size={20} /> : <ChevronUp size={20} />}
                    </button>
                </div>
            </div>

            <div className="overflow-y-auto pr-2 custom-scrollbar space-y-3">
                <AnimatePresence>
                    {approvals.slice(0, isCollapsed ? 1 : 999).map((item, idx) => (
                        <motion.div
                            key={item.id}
                            layout
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, x: -20, scale: 0.9 }}
                            transition={{ duration: 0.2, delay: idx * 0.1 }}
                            className="bg-white/40 dark:bg-surface-hover p-4 rounded-xl border border-neutral-100 dark:border-neutral-800 shadow-sm hover:shadow-md transition-shadow group"
                        >
                            <div className="flex justify-between items-start mb-3">
                                <div className="flex items-center gap-2">
                                    <div className={`p-1.5 rounded-xl ${item.color}`}>
                                        <item.icon size={16} />
                                    </div>
                                    <span className="text-[10px] font-bold text-neutral-sub px-2.5 py-1 bg-surface-main dark:bg-neutral-800 rounded-full">
                                        {item.type.toUpperCase()}
                                    </span>
                                </div>
                                <span className="text-[10px] font-bold text-accent-700 bg-accent-50 dark:bg-orange-900/20 px-2.5 py-1 rounded-full border border-accent-300 dark:border-orange-800">
                                    Pending
                                </span>
                            </div>

                            <h4 className="text-sm font-semibold text-neutral-main mb-1">{item.title}</h4>

                            <div className="flex items-center gap-2 mb-4 bg-neutral-50/40 dark:bg-neutral-800/40 p-2 rounded-lg">
                                <img src={item.avatar} alt={item.requester} className="w-8 h-8 rounded-full" />
                                <div>
                                    <p className="text-xs font-medium text-neutral-main">{item.requester}</p>
                                    <p className="text-[10px] text-neutral-muted">{item.detail}</p>
                                </div>
                            </div>

                            <div className="flex gap-2">
                                <button
                                    onClick={() => handleAction(item.id, true)}
                                    className="flex-1 flex items-center justify-center gap-1 py-2 bg-success/10 hover:bg-success text-success hover:text-white text-xs font-semibold rounded-lg transition-all duration-200"
                                >
                                    <Check size={14} /> Approve
                                </button>
                                <button
                                    onClick={() => handleAction(item.id, false)}
                                    className="flex-1 flex items-center justify-center gap-1 py-2 bg-error/10 hover:bg-error text-error hover:text-white text-xs font-semibold rounded-lg transition-all duration-200"
                                >
                                    <X size={14} /> Reject
                                </button>
                            </div>
                        </motion.div>
                    ))}
                </AnimatePresence>

                {approvals.length === 0 && !isCollapsed && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="flex flex-col items-center justify-center h-40 text-neutral-muted"
                    >
                        <Check className="mb-2 text-success opacity-50" size={32} />
                        <p className="text-sm">모든 승인 요청을 처리했습니다!</p>
                    </motion.div>
                )}
            </div>
        </div>
    );
}
