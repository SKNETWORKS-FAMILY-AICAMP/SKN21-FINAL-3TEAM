import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Users, Circle, ChevronUp, ChevronDown, Phone, MapPin } from 'lucide-react';
import useUIStore from '../../store/uiStore';
import api from '../../api/client';

const statusList = ['online', 'online', 'meeting', 'away', 'online', 'online', 'away', 'online', 'meeting', 'online'];

const statusColors = {
    online: 'bg-green-500',
    meeting: 'bg-orange-500',
    away: 'bg-neutral-400',
    offline: 'bg-neutral-300'
};

// 팀 이름별 뱃지 색상 (관리자 페이지에 있는 실제 팀 기준)
const teamColors = {
    '개발': 'bg-[#7A90A4]/20 text-[#4D657A] border-[#7A90A4]/30',
    'QA기획': 'bg-[#D0B16D]/20 text-[#8C7642] border-[#D0B16D]/30',
    'UI/UX': 'bg-[#B0D0C8]/20 text-[#5E8C83] border-[#B0D0C8]/30',
    '영업': 'bg-[#B197B1]/20 text-[#7D667D] border-[#B197B1]/30',
    '마케팅': 'bg-[#CA8A8A]/20 text-[#A66161] border-[#CA8A8A]/30',
    'CS': 'bg-[#90B2B2]/20 text-[#5A7A7A] border-[#90B2B2]/30',
    'HR': 'bg-[#CBAA85]/20 text-[#9E7D56] border-[#CBAA85]/30',
    '경영': 'bg-[#A5B38B]/20 text-[#6B7A56] border-[#A5B38B]/30',
};

export default function TeamMembersWidget() {
    const { viewMode } = useUIStore();
    const [isCollapsed, setIsCollapsed] = useState(true);
    const [members, setMembers] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchTeamMembers = async () => {
            try {
                const response = await api.get('/auth/team-members');
                const data = response.data;

                if (Array.isArray(data)) {
                    const mappedMembers = data.map((user, idx) => ({
                        ...user,
                        status: statusList[idx % statusList.length],
                    }));
                    setMembers(mappedMembers);
                } else {
                    setMembers([]);
                }
            } catch (error) {
                console.error("Error fetching team members:", error);
                setMembers([]);
            } finally {
                setLoading(false);
            }
        };

        fetchTeamMembers();
    }, []);

    return (
        <div className="card flex flex-col p-6 shadow-soft transition-all duration-300">
            <div
                className="flex items-center justify-between mb-4 cursor-pointer"
                onClick={() => setIsCollapsed(!isCollapsed)}
            >
                <h3 className="text-xl font-bold text-neutral-main flex items-center gap-2">
                    <Users className="text-primary-500" size={24} />
                    Team Members
                    {members.length > 0 && (
                        <span className="text-xs font-medium text-neutral-muted ml-1">({members.length}명)</span>
                    )}
                </h3>
                <div className="flex items-center gap-3">
                    <button
                        className="text-xs font-bold text-primary-600 hover:text-white bg-primary-50 hover:bg-primary-500 px-4 py-2 rounded-full transition-colors"
                        onClick={(e) => e.stopPropagation()}
                    >
                        See Details
                    </button>
                    <button className="text-neutral-muted hover:text-primary-500 transition-colors p-1 rounded-full hover:bg-surface-hover">
                        {isCollapsed ? <ChevronDown size={20} /> : <ChevronUp size={20} />}
                    </button>
                </div>
            </div>

            <div className="overflow-y-auto pr-2 custom-scrollbar space-y-3">
                {loading ? (
                    <div className="flex items-center justify-center py-8 text-neutral-muted text-sm font-bold">
                        <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: 'linear' }} className="w-5 h-5 border-2 border-primary-500 border-t-transparent rounded-full mr-2" />
                        팀원 정보 불러오는 중...
                    </div>
                ) : members.length === 0 ? (
                    <div className="text-center py-6 text-neutral-muted text-sm">
                        소속 팀원이 없습니다.
                    </div>
                ) : (
                    members.slice(0, isCollapsed ? 2 : 999).map((member, idx) => (
                        <motion.div
                            key={member.id}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: idx * 0.06 }}
                            className="group flex flex-col sm:flex-row sm:items-center justify-between p-4 rounded-xl border border-transparent bg-white/40 hover:border-primary-200 hover:shadow-soft transition-all duration-300 relative overflow-hidden"
                        >
                            {/* Soft background hover effect */}
                            <div className="absolute inset-0 bg-primary-50 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" />

                            {/* User Info */}
                            <div className="relative z-10 flex items-center gap-4 mb-2 sm:mb-0">
                                <div className="relative">
                                    {member.avatar ? (
                                        <img src={member.avatar} alt={member.name} className="w-10 h-10 rounded-full object-cover border-2 border-white dark:border-neutral-800 shadow-sm" />
                                    ) : (
                                        <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center text-primary-700 font-bold text-sm border-2 border-white dark:border-neutral-800 shadow-sm">
                                            {member.name?.charAt(0)}
                                        </div>
                                    )}
                                    <Circle
                                        size={12}
                                        className={`absolute bottom-0 right-0 ${statusColors[member.status] || 'bg-neutral-300'} text-white border-2 border-white dark:border-neutral-800 rounded-full`}
                                        fill="currentColor"
                                    />
                                </div>
                                <div>
                                    <p className="text-sm font-semibold text-neutral-main group-hover:text-primary-600 transition-colors">{member.name}</p>
                                    <p className="text-xs font-medium text-primary-600 mb-1">{member.role || member.email}</p>
                                    <div className="space-y-0.5">
                                        {member.phone && (
                                            <p className="text-[11px] text-neutral-muted flex items-center gap-1.5 font-mono">
                                                <Phone size={10} className="text-primary-400" />
                                                {member.phone}
                                            </p>
                                        )}
                                        {member.address && (
                                            <p className="text-[11px] text-neutral-muted flex items-center gap-1.5">
                                                <MapPin size={10} className="text-primary-400" />
                                                {member.address}
                                            </p>
                                        )}
                                    </div>
                                </div>
                            </div>

                            {/* Team badge */}
                            <div className="relative z-10 flex items-center justify-end pl-14 sm:pl-0">
                                <span className={`text-[11px] font-bold px-3 py-1 rounded-full border ${teamColors[member.team] || 'bg-neutral-100 text-neutral-600 border-neutral-200'}`}>
                                    {member.team}
                                </span>
                            </div>
                        </motion.div>
                    ))
                )}
            </div>
        </div>
    );
}
