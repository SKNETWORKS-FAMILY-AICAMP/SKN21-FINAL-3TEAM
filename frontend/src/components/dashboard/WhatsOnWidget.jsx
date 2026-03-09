import { useState, useEffect } from 'react';
import { Sparkles, ChevronUp, ChevronDown } from 'lucide-react';
import api from '../../api/client';

function getMonthName() {
    const months = ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월'];
    return months[new Date().getMonth()];
}

export default function WhatsOnWidget() {
    const [isCollapsed, setIsCollapsed] = useState(false);
    const [items, setItems] = useState([]);

    useEffect(() => {
        const fetchLeaves = async () => {
            try {
                const res = await api.get('/approvals/history', { params: { status: 'approved' } });
                if (!Array.isArray(res.data)) return;

                const now = new Date();
                const thisYear = now.getFullYear();
                const thisMonth = now.getMonth();

                const leaveItems = res.data.filter((item) => {
                    if (item.type !== 'leave') return false;
                    const d = new Date(item.created_at);
                    return d.getFullYear() === thisYear && d.getMonth() === thisMonth;
                });

                setItems(leaveItems);
            } catch { }
        };
        fetchLeaves();
    }, []);

    return (
        <div className="card p-5 shadow-soft">
            <div
                className="flex items-center justify-between mb-4 cursor-pointer"
                onClick={() => setIsCollapsed(!isCollapsed)}
            >
                <h3 className="text-lg font-bold text-neutral-main flex items-center gap-2">
                    <Sparkles className="text-primary-500" size={20} />
                    {getMonthName()} 팀 휴가
                </h3>
                <button className="text-neutral-muted hover:text-primary-500 transition-colors p-1 rounded-full hover:bg-surface-hover">
                    {isCollapsed ? <ChevronDown size={20} /> : <ChevronUp size={20} />}
                </button>
            </div>

            {!isCollapsed && (
                <div className="space-y-3">
                    {items.length === 0 ? (
                        <p className="text-sm text-neutral-muted text-center py-4">이번 달 휴가자가 없습니다</p>
                    ) : (
                        items.slice(0, 3).map((item) => (
                            <div key={item.id} className="flex items-center gap-3">
                                {item.requester_avatar ? (
                                    <img src={item.requester_avatar} alt={item.requester_name} className="w-10 h-10 rounded-full object-cover border-2 border-white dark:border-neutral-800 shadow-sm" />
                                ) : (
                                    <div className="w-10 h-10 rounded-full bg-primary-100 flex items-center justify-center text-primary-700 font-bold text-sm">
                                        {item.requester_name?.charAt(0)}
                                    </div>
                                )}
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-semibold text-neutral-main truncate">{item.requester_name}</p>
                                    <p className="text-[11px] text-neutral-muted truncate">
                                        <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-bold bg-orange-100 text-orange-600 dark:bg-orange-900/30 dark:text-orange-400 mr-1">연차</span>
                                        {item.detail || item.title}
                                    </p>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            )}
        </div>
    );
}
