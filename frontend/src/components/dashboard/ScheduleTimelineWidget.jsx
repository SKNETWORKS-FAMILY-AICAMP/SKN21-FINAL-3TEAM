import { useState } from 'react';
import { motion } from 'framer-motion';
import { Clock, ChevronUp, ChevronDown } from 'lucide-react';


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

const BLOCK_COLOR_HEXES = [
    '#7A90A4',
    '#8FB18E',
    '#B56D6D',
    '#B0D0C8',
    '#CBAA85',
    '#D0B16D',
    '#B197B1',
    '#A5B38B',
];

function timeToFraction(timeStr) {
    if (!timeStr) return 8;
    const d = new Date(timeStr);
    return d.getHours() + d.getMinutes() / 60;
}

export default function ScheduleTimelineWidget({ meetings = [] }) {
    const [isCollapsed, setIsCollapsed] = useState(false);

    // 기본 09~18, 범위 밖 일정이 있으면 자동 확장
    const { dayStart, dayRange, hours } = (() => {
        const DEFAULT_START = 9;
        const DEFAULT_END = 18;
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
            return m.end_time ? new Date(m.end_time).getHours() + new Date(m.end_time).getMinutes() / 60 : (m.start_time ? new Date(m.start_time).getHours() + 1 : DEFAULT_END);
        });
        const validStartHours = startHours.filter(h => !isNaN(h));
        const validEndHours = endHours.filter(h => !isNaN(h));

        const start = validStartHours.length > 0 ? Math.min(DEFAULT_START, Math.floor(Math.min(...validStartHours))) : DEFAULT_START;
        const end = validEndHours.length > 0 ? Math.max(DEFAULT_END, Math.ceil(Math.max(...validEndHours))) : DEFAULT_END;

        const hrs = Array.from({ length: end - start + 1 }, (_, i) => String(start + i).padStart(2, '0'));
        return { dayStart: start, dayRange: end - start, hours: hrs };
    })();

    const blocks = meetings.map((m, idx) => {
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
                if (duration > 10) duration = 1; // fallback if end_time wraps past midnight
            }
        }

        return {
            ...m,
            startH,
            duration,
            color: BLOCK_COLORS[idx % BLOCK_COLORS.length],
            colorHex: BLOCK_COLOR_HEXES[idx % BLOCK_COLOR_HEXES.length],
        };
    });

    return (
        <div className="card p-5 shadow-soft">
            <div
                className="flex items-center justify-between mb-4 cursor-pointer"
                onClick={() => setIsCollapsed(!isCollapsed)}
            >
                <h3 className="text-lg font-bold text-neutral-main flex items-center gap-2">
                    <Clock className="text-primary-500" size={20} />
                    Today Schedule
                </h3>
                <button className="text-neutral-muted hover:text-primary-500 transition-colors p-1 rounded-full hover:bg-surface-hover">
                    {isCollapsed ? <ChevronDown size={20} /> : <ChevronUp size={20} />}
                </button>
            </div>

            {!isCollapsed && (
                <div className="overflow-x-auto scrollbar-thin">
                    {/* Time axis */}
                    <div className="relative min-w-[600px]">
                        <div className="flex items-center border-b border-neutral-200 dark:border-neutral-700 pb-1 mb-3">
                            {hours.map(h => (
                                <div key={h} className="flex-1 text-center text-[10px] font-mono text-neutral-muted">
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
                                    className="absolute top-6 bottom-0 w-0.5 bg-red-500 z-10"
                                    style={{ left: `${leftPct}%` }}
                                >
                                    <div className="absolute -top-1 -left-1.5 w-3.5 h-3.5 bg-red-500 rounded-full border-2 border-white dark:border-neutral-800" />
                                </div>
                            );
                        })()}

                        {/* Schedule blocks */}
                        {(() => {
                            if (blocks.length === 0) {
                                return (
                                    <div className="flex items-center justify-center h-16 text-sm text-neutral-muted">
                                        오늘 예정된 일정이 없습니다
                                    </div>
                                );
                            }

                            const regularBlocks = blocks.filter(b => !b.isAllDay);
                            const allDayBlocks = blocks.filter(b => b.isAllDay);

                            // Row assignment for regular blocks only
                            const sorted = [...regularBlocks].sort((a, b) => a.startH - b.startH);
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

                            const rowH = 40;
                            const gap = 4;
                            const allDayH = 24; // 텍스트(14) + gap(4) + 선(2) + 여백(4)
                            const allDayGap = 4;

                            const rowCount = rows.length;
                            const regularHeight = rowCount * (rowH + gap);
                            const dividerHeight = rowCount > 0 && allDayBlocks.length > 0 ? 8 : 0;
                            const allDaySectionHeight = allDayBlocks.length * (allDayH + allDayGap);
                            const totalHeight = Math.max(regularHeight + dividerHeight + allDaySectionHeight, 44);

                            return (
                                <div className="relative" style={{ height: `${totalHeight}px` }}>
                                    {/* 일반 일정 블록 */}
                                    {regularBlocks.map((block, idx) => {
                                        const startPct = Math.max(0, ((block.startH - dayStart) / dayRange) * 100);
                                        const widthPct = (block.duration / dayRange) * 100;
                                        const row = rowAssign.get(block) || 0;
                                        return (
                                            <motion.div
                                                key={`reg-${idx}`}
                                                initial={{ opacity: 0, scaleX: 0 }}
                                                animate={{ opacity: 1, scaleX: 1 }}
                                                transition={{ delay: idx * 0.1 }}
                                                title={`${block.title} (${block.time} ${block.period})`}
                                                className={`absolute ${block.color} rounded-lg px-2 py-1 text-white text-[11px] font-semibold overflow-hidden cursor-default shadow-sm hover:shadow-md hover:z-20 transition-shadow`}
                                                style={{
                                                    left: `${startPct}%`,
                                                    width: `${Math.max(widthPct, 8)}%`,
                                                    top: `${row * (rowH + gap)}px`,
                                                    height: `${rowH}px`,
                                                    transformOrigin: 'left',
                                                }}
                                            >
                                                <div className="truncate leading-tight">{block.title}</div>
                                                <div className="text-[9px] opacity-80 truncate">{block.time} {block.period}</div>
                                            </motion.div>
                                        );
                                    })}

                                    {/* 종일/멀티데이 일정 — 텍스트 + 얇은 선 */}
                                    {allDayBlocks.map((block, idx) => {
                                        const topOffset = regularHeight + dividerHeight + idx * (allDayH + allDayGap);
                                        return (
                                            <motion.div
                                                key={`allday-${idx}`}
                                                initial={{ opacity: 0, x: -8 }}
                                                animate={{ opacity: 1, x: 0 }}
                                                transition={{ delay: idx * 0.08 }}
                                                title={block.title}
                                                className="absolute cursor-default"
                                                style={{ left: 0, right: 0, top: `${topOffset}px` }}
                                            >
                                                <div
                                                    className="text-[11px] font-semibold truncate mb-1 flex items-center gap-1.5"
                                                    style={{ color: block.colorHex }}
                                                >
                                                    <span className="truncate">{block.title}</span>
                                                    <span className="shrink-0 text-[10px] opacity-70">종일</span>
                                                </div>
                                                <div
                                                    className="w-full rounded-full"
                                                    style={{ height: '3px', backgroundColor: block.colorHex, opacity: 0.85 }}
                                                />
                                            </motion.div>
                                        );
                                    })}
                                </div>
                            );
                        })()}
                    </div>
                </div>
            )}
        </div>
    );
}
