import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Users, CalendarDays, FileText, TrendingUp } from 'lucide-react';
import api from '../../api/client';

export default function QuickStatsWidget() {
    const [stats, setStats] = useState({ totalMembers: 0, todaySchedules: 0, myTeam: '', myTeamCount: 0 });

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const [membersRes, meRes] = await Promise.allSettled([
                    api.get('/auth/team-members'),
                    api.get('/auth/me'),
                ]);
                const members = membersRes.status === 'fulfilled' ? membersRes.value.data : [];
                const me = meRes.status === 'fulfilled' ? meRes.value.data : {};
                setStats({
                    totalMembers: members.length,
                    todaySchedules: 0, // Will be populated from parent props
                    myTeam: me.team || '–',
                    myTeamCount: members.length,
                });
            } catch { }
        };
        fetchStats();
    }, []);

    const cards = [
        { label: '내 팀', value: stats.myTeam, icon: Users, color: 'from-violet-500 to-purple-600', bg: 'bg-violet-50/40 dark:bg-violet-900/20' },
        { label: '팀원 수', value: `${stats.myTeamCount}명`, icon: TrendingUp, color: 'from-blue-500 to-cyan-500', bg: 'bg-blue-50/40 dark:bg-blue-900/20' },
    ];

    return (
        <div className="grid grid-cols-2 gap-4">
            {cards.map((card, idx) => (
                <motion.div
                    key={card.label}
                    initial={{ opacity: 0, y: 15 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.1 }}
                    className={`card p-4 shadow-soft ${card.bg} border-none`}
                >
                    <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-semibold text-neutral-muted uppercase tracking-wide">{card.label}</span>
                        <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${card.color} flex items-center justify-center`}>
                            <card.icon size={16} className="text-white" />
                        </div>
                    </div>
                    <p className="text-2xl font-bold text-neutral-main">{card.value}</p>
                </motion.div>
            ))}
        </div>
    );
}
