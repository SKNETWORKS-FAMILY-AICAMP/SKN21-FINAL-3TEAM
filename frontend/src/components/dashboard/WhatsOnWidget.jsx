import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles, ChevronUp, ChevronDown } from 'lucide-react';
import api from '../../api/client';

const TABS = ['휴가', '생일'];

// Random statuses for demo
const LEAVE_TYPES = [
    { label: '연차', color: 'bg-[#B0D0C8]/20 text-[#5E8C83]' },
    { label: '병가', color: 'bg-[#CA8A8A]/20 text-[#A66161]' },
    { label: '재택근무', color: 'bg-[#CBAA85]/20 text-[#9E7D56]' },
    { label: '외근', color: 'bg-[#7A90A4]/20 text-[#4D657A]' },
];

function getMonthName() {
    const months = ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월'];
    return months[new Date().getMonth()];
}

export default function WhatsOnWidget() {
    const [activeTab, setActiveTab] = useState(0);
    const [isCollapsed, setIsCollapsed] = useState(false);
    const [members, setMembers] = useState([]);

    useEffect(() => {
        const fetchMembers = async () => {
            try {
                const res = await api.get('/auth/team-members');
                if (Array.isArray(res.data)) {
                    // Assign random leave status to some members for display
                    const withStatus = res.data.map((m, idx) => ({
                        ...m,
                        leaveType: LEAVE_TYPES[idx % LEAVE_TYPES.length],
                        // Generate random birthday in current month for demo
                        birthday: `${new Date().getMonth() + 1}/${(idx * 7 + 3) % 28 + 1}`,
                    }));
                    setMembers(withStatus);
                }
            } catch { }
        };
        fetchMembers();
    }, []);

    const displayMembers = activeTab === 0
        ? members.slice(0, 3) // Time Off - show 3 members
        : members.filter((_, i) => i % 3 === 0).slice(0, 3); // Birthday - show 3

    return (
        <div className="card p-5 shadow-soft">
            <div
                className="flex items-center justify-between mb-4 cursor-pointer"
                onClick={() => setIsCollapsed(!isCollapsed)}
            >
                <h3 className="text-lg font-bold text-neutral-main flex items-center gap-2">
                    <Sparkles className="text-primary-500" size={20} />
                    {getMonthName()} 팀 소식
                </h3>
                <button className="text-neutral-muted hover:text-primary-500 transition-colors p-1 rounded-full hover:bg-surface-hover">
                    {isCollapsed ? <ChevronDown size={20} /> : <ChevronUp size={20} />}
                </button>
            </div>

            {!isCollapsed && (
                <>
                    {/* Tabs */}
                    <div className="flex gap-1 mb-4 bg-surface-hover rounded-lg p-1">
                        {TABS.map((tab, idx) => (
                            <button
                                key={tab}
                                onClick={() => setActiveTab(idx)}
                                className={`flex-1 py-2 px-3 text-xs font-semibold rounded-md transition-all ${activeTab === idx
                                    ? 'bg-white/50 dark:bg-neutral-800/50 text-neutral-main shadow-sm'
                                    : 'text-neutral-muted hover:text-neutral-sub'
                                    }`}
                            >
                                {tab}
                            </button>
                        ))}
                    </div>

                    {/* Content */}
                    <AnimatePresence mode="wait">
                        <motion.div
                            key={activeTab}
                            initial={{ opacity: 0, y: 5 }}
                            animate={{ opacity: 1, y: 0 }}
                            exit={{ opacity: 0, y: -5 }}
                            transition={{ duration: 0.15 }}
                            className="space-y-3"
                        >
                            {displayMembers.length === 0 ? (
                                <p className="text-sm text-neutral-muted text-center py-4">
                                    {activeTab === 0 ? '이번 달 휴가자가 없습니다' : '이번 달 생일자가 없습니다'}
                                </p>
                            ) : (
                                displayMembers.map((member, idx) => (
                                    <div key={member.id} className="flex items-center gap-3 group">
                                        {member.avatar ? (
                                            <img src={member.avatar} alt={member.name} className="w-10 h-10 rounded-full object-cover border-2 border-white dark:border-neutral-800 shadow-sm" />
                                        ) : (
                                            <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center text-primary-700 font-bold text-sm">
                                                {member.name?.charAt(0)}
                                            </div>
                                        )}
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-semibold text-neutral-main truncate">{member.name}</p>
                                            <p className="text-[11px] text-neutral-muted">
                                                {activeTab === 0 ? (
                                                    <span>
                                                        {member.role || 'Staff'} • <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold ${member.leaveType.color}`}>{member.leaveType.label}</span>
                                                    </span>
                                                ) : (
                                                    <span>🎂 {member.birthday}</span>
                                                )}
                                            </p>
                                        </div>
                                    </div>
                                ))
                            )}
                        </motion.div>
                    </AnimatePresence>
                </>
            )}
        </div>
    );
}
