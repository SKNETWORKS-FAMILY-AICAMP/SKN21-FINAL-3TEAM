import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Users, ChevronUp, ChevronDown } from 'lucide-react';
import api from '../../api/client';

const teamColors = {
    '개발': 'bg-blue-100 text-blue-700 border-blue-200',
    'QA기획': 'bg-amber-100 text-amber-700 border-amber-200',
    'UI/UX': 'bg-emerald-100 text-emerald-700 border-emerald-200',
    '영업': 'bg-violet-100 text-violet-700 border-violet-200',
    '마케팅': 'bg-pink-100 text-pink-700 border-pink-200',
    'CS': 'bg-cyan-100 text-cyan-700 border-cyan-200',
    'HR': 'bg-orange-100 text-orange-700 border-orange-200',
    '경영': 'bg-purple-100 text-purple-700 border-purple-200',
};

export default function EmployeeTableWidget() {
    const [members, setMembers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [isCollapsed, setIsCollapsed] = useState(false);

    useEffect(() => {
        const fetchMembers = async () => {
            try {
                const res = await api.get('/auth/team-members');
                setMembers(Array.isArray(res.data) ? res.data : []);
            } catch {
                setMembers([]);
            } finally {
                setLoading(false);
            }
        };
        fetchMembers();
    }, []);

    return (
        <div className="card p-5 shadow-soft">
            <div
                className="flex items-center justify-between mb-4 cursor-pointer"
                onClick={() => setIsCollapsed(!isCollapsed)}
            >
                <h3 className="text-lg font-bold text-neutral-main flex items-center gap-2">
                    <Users className="text-primary-500" size={20} />
                    Employee
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

            {!isCollapsed && (
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-neutral-200 dark:border-neutral-700">
                                <th className="text-left py-2 px-3 text-xs font-semibold text-neutral-muted uppercase tracking-wider">Employee Name</th>
                                <th className="text-left py-2 px-3 text-xs font-semibold text-neutral-muted uppercase tracking-wider">Department</th>
                                <th className="text-left py-2 px-3 text-xs font-semibold text-neutral-muted uppercase tracking-wider">Job Title</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading ? (
                                <tr>
                                    <td colSpan={3} className="text-center py-6 text-neutral-muted">
                                        <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1, ease: 'linear' }} className="inline-block w-4 h-4 border-2 border-primary-500 border-t-transparent rounded-full mr-2" />
                                        로딩 중...
                                    </td>
                                </tr>
                            ) : members.length === 0 ? (
                                <tr>
                                    <td colSpan={3} className="text-center py-6 text-neutral-muted">팀원이 없습니다</td>
                                </tr>
                            ) : (
                                members.slice(0, 5).map((member, idx) => (
                                    <motion.tr
                                        key={member.id}
                                        initial={{ opacity: 0, y: 5 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: idx * 0.05 }}
                                        className="border-b border-neutral-100 dark:border-neutral-800 hover:bg-surface-hover transition-colors"
                                    >
                                        <td className="py-3 px-3">
                                            <div className="flex items-center gap-3">
                                                {member.avatar ? (
                                                    <img src={member.avatar} alt={member.name} className="w-8 h-8 rounded-full object-cover border border-neutral-200" />
                                                ) : (
                                                    <div className="w-8 h-8 rounded-full bg-primary-100 flex items-center justify-center text-primary-700 font-bold text-xs">
                                                        {member.name?.charAt(0)}
                                                    </div>
                                                )}
                                                <div>
                                                    <p className="font-semibold text-neutral-main text-[13px]">{member.name}</p>
                                                    <p className="text-[11px] text-neutral-muted">{member.email}</p>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="py-3 px-3">
                                            <span className={`text-[11px] font-bold px-2.5 py-1 rounded-full border ${teamColors[member.team] || 'bg-neutral-100 text-neutral-600 border-neutral-200'}`}>
                                                {member.team}
                                            </span>
                                        </td>
                                        <td className="py-3 px-3 text-[13px] text-neutral-sub">{member.role || '–'}</td>
                                    </motion.tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
