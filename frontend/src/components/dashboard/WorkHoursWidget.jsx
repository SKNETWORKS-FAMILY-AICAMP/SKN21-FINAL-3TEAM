import { useState } from 'react';
import { motion } from 'framer-motion';
import { BarChart3, ChevronUp, ChevronDown } from 'lucide-react';

// Mock weekly work hours data (can be replaced with real API later)
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const WORK_HOURS = [8.5, 9.2, 7.8, 10.1, 8.0, 3.5, 0];
const OVERTIME = [0, 1.2, 0, 2.1, 0, 0, 0];

export default function WorkHoursWidget() {
    const [isCollapsed, setIsCollapsed] = useState(false);
    const maxHour = Math.max(...WORK_HOURS.map((w, i) => w + OVERTIME[i]));
    const totalHours = WORK_HOURS.reduce((sum, h) => sum + h, 0);
    const totalMinutes = Math.round((totalHours % 1) * 60);

    return (
        <div className="card p-5 shadow-soft">
            <div
                className="flex items-center justify-between mb-4 cursor-pointer"
                onClick={() => setIsCollapsed(!isCollapsed)}
            >
                <h3 className="text-lg font-bold text-neutral-main flex items-center gap-2">
                    <BarChart3 className="text-primary-500" size={20} />
                    Member Work Hours
                </h3>
                <div className="flex items-center gap-3">
                    <span className="text-xs text-neutral-muted">View by Week</span>
                    <button className="text-neutral-muted hover:text-primary-500 transition-colors p-1 rounded-full hover:bg-surface-hover">
                        {isCollapsed ? <ChevronDown size={20} /> : <ChevronUp size={20} />}
                    </button>
                </div>
            </div>

            {!isCollapsed && (
                <>
                    <div className="flex items-baseline gap-1 mb-4">
                        <span className="text-3xl font-bold text-neutral-main">{Math.floor(totalHours)}h</span>
                        <span className="text-xl font-semibold text-neutral-sub">{totalMinutes}m</span>
                        <div className="ml-4 flex items-center gap-3 text-[11px]">
                            <span className="flex items-center gap-1.5">
                                <span className="w-2.5 h-2.5 rounded-sm bg-primary-400" /> Work Time
                            </span>
                            <span className="flex items-center gap-1.5">
                                <span className="w-2.5 h-2.5 rounded-sm bg-amber-400" /> Overtime
                            </span>
                        </div>
                    </div>

                    <div className="flex items-end gap-2 h-36">
                        {DAYS.map((day, idx) => {
                            const workH = WORK_HOURS[idx];
                            const overH = OVERTIME[idx];
                            const workPct = (workH / maxHour) * 100;
                            const overPct = (overH / maxHour) * 100;
                            const isToday = idx === new Date().getDay() - 1;

                            return (
                                <div key={day} className="flex-1 flex flex-col items-center gap-1">
                                    <div className="w-full flex flex-col items-center gap-0 relative" style={{ height: '100px' }}>
                                        {overH > 0 && (
                                            <motion.div
                                                initial={{ height: 0 }}
                                                animate={{ height: `${overPct}%` }}
                                                transition={{ delay: idx * 0.05, duration: 0.4 }}
                                                className="w-full max-w-8 bg-amber-400 rounded-t-md"
                                                style={{ position: 'absolute', bottom: `${workPct}%` }}
                                            />
                                        )}
                                        <motion.div
                                            initial={{ height: 0 }}
                                            animate={{ height: `${workPct}%` }}
                                            transition={{ delay: idx * 0.05, duration: 0.4 }}
                                            className={`w-full max-w-8 ${isToday ? 'bg-primary-500' : 'bg-primary-300'} rounded-t-md absolute bottom-0`}
                                        />
                                    </div>
                                    <span className={`text-[10px] font-medium ${isToday ? 'text-primary-600 font-bold' : 'text-neutral-muted'}`}>
                                        {day}
                                    </span>
                                </div>
                            );
                        })}
                    </div>
                </>
            )}
        </div>
    );
}
