import { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { Clock, ChevronUp, ChevronDown, Calendar as CalendarIcon, Users } from 'lucide-react';
import dayjs from 'dayjs';

const BLOCK_COLORS = [
    'bg-[#7A90A4]', // Meeting (Muted Blue-gray)
    'bg-[#8FB18E]', // Sage Green
    'bg-[#B56D6D]', // Muted Red (Deadline)
    'bg-[#B0D0C8]', // Teal/Mint
    'bg-[#CBAA85]', // Tan/Sand
    'bg-[#D0B16D]', // Gold/Mustard
    'bg-[#B197B1]', // Muted Purple
    'bg-[#A5B38B]', // Olive/Grass
];

export default function TimelineView({ meetings = [] }) {
    const [isCollapsed, setIsCollapsed] = useState(false);

    // 기본 08~20, 범위 밖 일정이 있으면 자동 확장
    const { dayStart, dayRange, hours } = useMemo(() => {
        const DEFAULT_START = 8;
        const DEFAULT_END = 20;
        if (meetings.length === 0) {
            const hrs = Array.from({ length: DEFAULT_END - DEFAULT_START + 1 }, (_, i) => String(DEFAULT_START + i).padStart(2, '0'));
            return { dayStart: DEFAULT_START, dayRange: DEFAULT_END - DEFAULT_START, hours: hrs };
        }
        const startHours = meetings.map(m => {
            if (m.isAllDay) return DEFAULT_START;
            return m.start_time ? new Date(m.start_time).getHours() + new Date(m.start_time).getMinutes() / 60 : DEFAULT_START;
        });
        const endHours = meetings.map(m => {
            if (m.isAllDay) return DEFAULT_END;
            const end = m.end_time ? new Date(m.end_time) : (m.start_time ? new Date(new Date(m.start_time).getTime() + 3600000) : null);
            return end ? end.getHours() + end.getMinutes() / 60 : DEFAULT_END;
        });
        const validStartHours = startHours.filter(h => !isNaN(h));
        const validEndHours = endHours.filter(h => !isNaN(h));

        const start = validStartHours.length > 0 ? Math.min(DEFAULT_START, Math.floor(Math.min(...validStartHours))) : DEFAULT_START;
        const end = validEndHours.length > 0 ? Math.max(DEFAULT_END, Math.ceil(Math.max(...validEndHours))) : DEFAULT_END;

        const hrs = Array.from({ length: end - start + 1 }, (_, i) => String(start + i).padStart(2, '0'));
        return { dayStart: start, dayRange: end - start, hours: hrs };
    }, [meetings]);

    const blocks = useMemo(() => {
        return meetings.map((m, idx) => {
            let startH = 9;
            let duration = 1;

            if (m.isAllDay) {
                startH = dayStart;
                duration = dayRange;
            } else {
                if (m.start_time) {
                    const d = new Date(m.start_time);
                    startH = d.getHours() + d.getMinutes() / 60;
                }

                if (m.end_time && m.start_time) {
                    const ds = new Date(m.start_time);
                    const de = new Date(m.end_time);
                    const diffMs = de.getTime() - ds.getTime();
                    duration = Math.max(diffMs / 3600000, 0.5); // minimum 30 min
                    if (duration > 12) duration = 1; // fallback
                }
            }

            return {
                ...m,
                startH,
                duration,
                color: BLOCK_COLORS[idx % BLOCK_COLORS.length],
            };
        });
    }, [meetings, dayStart, dayRange]);

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <h2 className="text-lg font-bold text-neutral-main">타임라인 뷰</h2>
                    <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-primary-50 text-primary-700 border border-primary-100">
                        <CalendarIcon size={14} strokeWidth={2.5} />
                        <span className="text-xs font-bold">{dayjs().format('YYYY년 MM월 DD일')}</span>
                    </div>
                </div>
            </div>

            <div className="card p-6 shadow-soft overflow-hidden">
                <div className="overflow-x-auto pb-4">
                    <div className="relative min-w-[800px]">
                        {/* Time axis */}
                        <div className="flex items-center border-b border-neutral-100 dark:border-neutral-700 pb-2 mb-4">
                            <div className="w-20 shrink-0" />
                            {hours.map(h => (
                                <div key={h} className="flex-1 text-center text-[11px] font-bold text-neutral-muted uppercase tracking-tighter">
                                    {h}:00
                                </div>
                            ))}
                        </div>

                        {/* Current time indicator */}
                        {(() => {
                            const now = new Date();
                            const currentH = now.getHours() + now.getMinutes() / 60;
                            if (currentH < dayStart || currentH > dayStart + dayRange) return null;
                            const leftPct = ((currentH - dayStart) / dayRange) * 100;
                            return (
                                <div
                                    className="absolute top-10 bottom-0 w-0.5 bg-red-500 z-10 pointer-events-none"
                                    style={{ left: `calc(80px + ${leftPct}%)` }}
                                >
                                    <div className="absolute -top-1 -left-1.5 w-3.5 h-3.5 bg-red-500 rounded-full border-2 border-white dark:border-neutral-800" />
                                    <div className="absolute top-4 left-2 px-1.5 py-0.5 bg-red-500 text-white text-[9px] font-bold rounded shadow-sm">
                                        NOW
                                    </div>
                                </div>
                            );
                        })()}

                        {/* Schedule blocks */}
                        {(() => {
                            if (blocks.length === 0) {
                                return (
                                    <div className="flex flex-col items-center justify-center py-20 text-neutral-muted opacity-50">
                                        <Clock size={32} className="mb-2" />
                                        <p className="text-sm font-medium">오늘 예정된 일정이 없습니다</p>
                                    </div>
                                );
                            }

                            // Overlap logic
                            const sorted = [...blocks].sort((a, b) => a.startH - b.startH);
                            const rows = [];
                            const rowAssign = new Map();

                            sorted.forEach((block) => {
                                const blockEnd = block.startH + block.duration;
                                let placed = false;
                                for (let r = 0; r < rows.length; r++) {
                                    if (rows[r] <= block.startH) {
                                        rows[r] = blockEnd;
                                        rowAssign.set(block, r);
                                        placed = true;
                                        break;
                                    }
                                }
                                if (!placed) {
                                    rows.push(blockEnd);
                                    rowAssign.set(block, rows.length - 1);
                                }
                            });

                            const rowCount = Math.max(rows.length, 1);
                            const rowH = 64;
                            const gap = 8;

                            return (
                                <div className="relative pl-20" style={{ height: `${rowCount * (rowH + gap)}px` }}>
                                    {/* Grid lines */}
                                    <div className="absolute inset-0 flex">
                                        {hours.map((_, i) => (
                                            <div key={i} className="flex-1 border-r border-neutral-100/50 dark:border-neutral-700/30 last:border-0" />
                                        ))}
                                    </div>

                                    {blocks.map((block, idx) => {
                                        const startPct = Math.max(0, ((block.startH - dayStart) / dayRange) * 100);
                                        const widthPct = (block.duration / dayRange) * 100;
                                        const row = rowAssign.get(block) || 0;
                                        const startTimeStr = dayjs(block.start_time).format('HH:mm');
                                        const endTimeStr = block.end_time ? dayjs(block.end_time).format('HH:mm') : '';

                                        return (
                                            <motion.div
                                                key={idx}
                                                initial={{ opacity: 0, x: -20 }}
                                                animate={{ opacity: 1, x: 0 }}
                                                transition={{ delay: idx * 0.05 }}
                                                className={`absolute ${block.color} rounded-xl px-3 py-2 text-white overflow-hidden cursor-default shadow-sm hover:shadow-md hover:z-20 transition-all border border-black/5`}
                                                style={{
                                                    left: `${block.isAllDay ? 0 : startPct}%`,
                                                    width: `${block.isAllDay ? 100 : Math.max(widthPct, 12)}%`,
                                                    top: `${row * (rowH + gap)}px`,
                                                    height: `${rowH}px`,
                                                }}
                                            >
                                                <div className="flex flex-col h-full justify-between">
                                                    <div className="font-bold text-[13px] truncate leading-tight tracking-tight">
                                                        {block.title}
                                                    </div>
                                                    <div className="flex items-center justify-between mt-auto">
                                                        <div className="text-[10px] font-bold opacity-90 tracking-tighter bg-black/10 px-1.5 py-0.5 rounded-md">
                                                            {startTimeStr}{endTimeStr ? ` - ${endTimeStr}` : ''}
                                                        </div>
                                                        {block.schedule_type === 'meeting' && (
                                                            <Users size={12} className="opacity-80" />
                                                        )}
                                                    </div>
                                                </div>
                                            </motion.div>
                                        );
                                    })}
                                </div>
                            );
                        })()}
                    </div>
                </div>
            </div>
        </div>
    );
}
