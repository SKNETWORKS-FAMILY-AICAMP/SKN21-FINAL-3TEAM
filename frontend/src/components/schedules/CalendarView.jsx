import { useState, useRef, useEffect } from 'react';
import { Pencil, Trash2 } from 'lucide-react';
import MeetLinkBadge from './MeetLinkBadge';
import useScheduleTypeStore, { DEFAULT_TYPES } from '../../store/scheduleTypeStore';

// hex 색상을 rgba로 변환 (커스텀 유형 배경에 사용)
function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

// 기본 유형의 Tailwind 스타일 (기존 디자인 유지)
const DEFAULT_TYPE_STYLES = {
  meeting: 'bg-primary-50 text-primary-700',
  deadline: 'bg-error-bg text-error',
  project: 'bg-purple-50 text-purple-700',
  google: 'bg-success-bg text-success',
  holiday: 'bg-error-bg text-error',
};

// 한국 공휴일 (고정 공휴일 + 연도별 음력 공휴일)
function getKoreanHolidays(year) {
  // 고정 공휴일
  const fixed = [
    { month: 1, day: 1, label: '신정' },
    { month: 3, day: 1, label: '삼일절' },
    { month: 5, day: 5, label: '어린이날' },
    { month: 6, day: 6, label: '현충일' },
    { month: 8, day: 15, label: '광복절' },
    { month: 10, day: 3, label: '개천절' },
    { month: 10, day: 9, label: '한글날' },
    { month: 12, day: 25, label: '크리스마스' },
  ];

  // 음력 기반 공휴일 (연도별 양력 변환 — 주요 연도)
  const lunarByYear = {
    2025: [
      { month: 1, day: 28, label: '설날 연휴' },
      { month: 1, day: 29, label: '설날' },
      { month: 1, day: 30, label: '설날 연휴' },
      { month: 3, day: 3, label: '삼일절 대체공휴일' },
      { month: 5, day: 5, label: '부처님오신날' },
      { month: 5, day: 6, label: '어린이날 대체공휴일' },
      { month: 10, day: 5, label: '추석 연휴' },
      { month: 10, day: 6, label: '추석' },
      { month: 10, day: 7, label: '추석 연휴' },
      { month: 10, day: 8, label: '추석 대체공휴일' },
    ],
    2026: [
      { month: 2, day: 16, label: '설날 연휴' },
      { month: 2, day: 17, label: '설날' },
      { month: 2, day: 18, label: '설날 연휴' },
      { month: 3, day: 2, label: '삼일절 대체공휴일' },
      { month: 5, day: 24, label: '부처님오신날' },
      { month: 5, day: 25, label: '부처님오신날 대체공휴일' },
      { month: 6, day: 8, label: '현충일 대체공휴일' },
      { month: 8, day: 17, label: '광복절 대체공휴일' },
      { month: 9, day: 24, label: '추석 연휴' },
      { month: 9, day: 25, label: '추석' },
      { month: 9, day: 26, label: '추석 연휴' },
      { month: 9, day: 28, label: '추석 대체공휴일' },
      { month: 10, day: 5, label: '개천절 대체공휴일' },
    ],
    2027: [
      { month: 2, day: 6, label: '설날 연휴' },
      { month: 2, day: 7, label: '설날' },
      { month: 2, day: 8, label: '설날 연휴' },
      { month: 2, day: 9, label: '설날 대체공휴일' },
      { month: 5, day: 13, label: '부처님오신날' },
      { month: 6, day: 7, label: '현충일 대체공휴일' },
      { month: 8, day: 16, label: '광복절 대체공휴일' },
      { month: 10, day: 4, label: '개천절 대체공휴일' },
      { month: 10, day: 11, label: '한글날 대체공휴일' },
      { month: 10, day: 14, label: '추석 연휴' },
      { month: 10, day: 15, label: '추석' },
      { month: 10, day: 16, label: '추석 연휴' },
      { month: 10, day: 18, label: '추석 대체공휴일' },
      { month: 12, day: 27, label: '크리스마스 대체공휴일' },
    ],
  };

  const lunar = lunarByYear[year] || [];
  return [...fixed, ...lunar].map((h) => ({ ...h, type: 'holiday' }));
}

function DayDetailPopup({ day, month, year, events, typeColorMap, typeLabelMap, onClose, onDeleteEvent, onCanDelete, onEditEvent, onCanEdit }) {
  const ref = useRef(null);
  const [deletingId, setDeletingId] = useState(null);

  useEffect(() => {
    const handleClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) onClose();
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [onClose]);

  const handleDelete = async (event) => {
    const key = event.scheduleId || event.id;
    setDeletingId(key);
    try {
      await onDeleteEvent(event);
    } catch {
      // 삭제 실패 시 버튼 원복
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20">
      <div ref={ref} className="bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-lg border border-white/40 dark:border-white/10 shadow-md w-[540px] max-h-[80vh] flex flex-col overflow-hidden">
        {/* 헤더 */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-neutral-divider">
          <span className="text-sm font-bold text-neutral-main">{year}년 {month}월 {day}일</span>
          <button onClick={onClose} className="w-6 h-6 flex items-center justify-center rounded hover:bg-surface-hover text-neutral-muted text-sm">✕</button>
        </div>

        {/* 일정 목록 */}
        <div className="px-4 py-3 overflow-y-auto flex-1 custom-scrollbar">
          {events.length === 0 ? (
            <p className="text-sm text-neutral-muted text-center py-6">등록된 일정이 없습니다</p>
          ) : (
            <ul className="space-y-2.5">
              {events.map((e, i) => {
                const dotColor = typeColorMap[e.type] || '#9CA3AF';
                const typeLabel = typeLabelMap[e.type] || e.type;
                const eventKey = e.scheduleId || e.id;
                const isDeleting = deletingId === eventKey;
                const showDelete = onDeleteEvent && onCanDelete?.(e);
                const showEdit = onEditEvent && onCanEdit?.(e);
                return (
                  <li key={i} className="flex gap-3 items-start">
                    <span
                      className="w-2.5 h-2.5 rounded-full mt-1.5 shrink-0"
                      style={{ backgroundColor: dotColor }}
                    />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-neutral-main">{e.label}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[0.6875rem] text-neutral-muted">{typeLabel}</span>
                        {e.time && <span className="text-[0.6875rem] text-neutral-sub font-medium">{e.time}</span>}
                      </div>
                      {e.meetLink && <div className="mt-1"><MeetLinkBadge meetLink={e.meetLink} /></div>}
                    </div>
                    {(showEdit || showDelete) && (
                      <div className="flex items-center gap-0.5 shrink-0">
                        {showEdit && (
                          <button
                            onClick={() => onEditEvent(e)}
                            className="w-7 h-7 flex items-center justify-center rounded hover:bg-primary-50 text-neutral-muted hover:text-primary-700 transition"
                            aria-label="일정 수정"
                            title="일정 수정"
                          >
                            <Pencil size={14} />
                          </button>
                        )}
                        {showDelete && (
                          <button
                            onClick={() => handleDelete(e)}
                            disabled={isDeleting}
                            className="w-7 h-7 flex items-center justify-center rounded hover:bg-error-bg text-neutral-muted hover:text-error transition disabled:opacity-40"
                            aria-label="일정 삭제"
                            title="일정 삭제"
                          >
                            {isDeleting
                              ? <span className="w-3.5 h-3.5 border-2 border-error border-t-transparent rounded-full animate-spin" />
                              : <Trash2 size={14} />
                            }
                          </button>
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

// 연간 뷰 — 12개월 미니 캘린더
function YearView({ year, events, todayYear, todayMonth, todayDate, onMonthClick }) {
  const monthNames = ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월'];
  const dayNamesShort = ['일', '월', '화', '수', '목', '금', '토'];

  return (
    <div className="grid grid-cols-3 sm:grid-cols-4 gap-4">
      {monthNames.map((name, mIdx) => {
        const month = mIdx + 1;
        const firstDay = new Date(year, mIdx, 1).getDay();
        const daysInMonth = new Date(year, month, 0).getDate();
        const monthEvents = events.filter((e) => e.month === month);

        const cells = [];
        for (let i = 0; i < firstDay; i++) cells.push(null);
        for (let d = 1; d <= daysInMonth; d++) cells.push(d);

        return (
          <div
            key={month}
            onClick={() => onMonthClick(month)}
            className="bg-surface-card border border-neutral-divider rounded-lg p-4 cursor-pointer hover:border-primary-300 transition"
          >
            <div className="text-sm font-bold text-neutral-main mb-2 text-center">{name}</div>
            <div className="grid grid-cols-7 gap-px">
              {dayNamesShort.map((d, idx) => (
                <div key={d} className={`text-[0.625rem] text-center pb-1 ${idx === 0 ? 'text-red-500' : idx === 6 ? 'text-blue-500' : 'text-neutral-muted'
                  }`}>{d}</div>
              ))}
              {cells.map((d, i) => {
                const isToday = d && year === todayYear && month === todayMonth && d === todayDate;
                const isHoliday = d && monthEvents.some((e) => e.day === d && e.type === 'holiday');
                const hasEvent = d && monthEvents.some((e) => e.day === d && e.type !== 'holiday');
                return (
                  <div key={i} className="flex items-center justify-center h-7">
                    {d ? (
                      <span className={`text-[0.6875rem] w-6 h-6 flex items-center justify-center rounded-full
                        ${isToday ? 'bg-primary-700 text-white font-bold' : ''}
                        ${isHoliday && !isToday ? 'bg-error-bg text-error font-semibold' : ''}
                        ${hasEvent && !isToday && !isHoliday ? 'bg-primary-50 text-primary-700 font-semibold' : ''}
                        ${!isToday && !hasEvent && !isHoliday ? (i % 7 === 0 ? 'text-red-500' : i % 7 === 6 ? 'text-blue-500' : 'text-neutral-sub') : ''}
                      `}>{d}</span>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function CalendarView({ events = [], onDeleteEvent, onCanDelete, onEditEvent, onCanEdit }) {
  const now = new Date();
  const [currentYear, setCurrentYear] = useState(now.getFullYear());
  const [currentMonth, setCurrentMonth] = useState(now.getMonth() + 1);
  const [view, setView] = useState('month');
  const [selectedDay, setSelectedDay] = useState(null);
  const [hiddenTypes, setHiddenTypes] = useState(new Set());

  const { customTypes } = useScheduleTypeStore();
  const allTypes = [...DEFAULT_TYPES, ...customTypes];
  const allFilterTypes = [...allTypes, { id: 'holiday', label: '공휴일', color: '#C06060' }];

  // 타입 ID → 색상 맵
  const typeColorMap = {
    holiday: '#C06060',
    ...Object.fromEntries(allTypes.map((t) => [t.id, t.color])),
  };
  // 타입 ID → 라벨 맵
  const typeLabelMap = {
    holiday: '공휴일',
    ...Object.fromEntries(allTypes.map((t) => [t.id, t.label])),
  };

  const toggleType = (id) => {
    setHiddenTypes((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };
  const showAll = hiddenTypes.size === 0;

  const holidays = getKoreanHolidays(currentYear);
  const mergedEvents = [...events, ...holidays].filter((e) => !hiddenTypes.has(e.type));

  const todayDate = now.getDate();
  const todayYear = now.getFullYear();
  const todayMonth = now.getMonth() + 1;

  const dayNames = ['일', '월', '화', '수', '목', '금', '토'];
  const firstDay = new Date(currentYear, currentMonth - 1, 1).getDay();
  const daysInMonth = new Date(currentYear, currentMonth, 0).getDate();
  const prevDays = new Date(currentYear, currentMonth - 1, 0).getDate();

  const goToPrev = () => {
    if (view === 'year') { setCurrentYear(currentYear - 1); return; }
    if (currentMonth === 1) { setCurrentYear(currentYear - 1); setCurrentMonth(12); }
    else setCurrentMonth(currentMonth - 1);
  };
  const goToNext = () => {
    if (view === 'year') { setCurrentYear(currentYear + 1); return; }
    if (currentMonth === 12) { setCurrentYear(currentYear + 1); setCurrentMonth(1); }
    else setCurrentMonth(currentMonth + 1);
  };
  const goToToday = () => { setCurrentYear(todayYear); setCurrentMonth(todayMonth); };

  const days = [];
  for (let i = firstDay - 1; i >= 0; i--) days.push({ day: prevDays - i, other: true });
  for (let i = 1; i <= daysInMonth; i++) days.push({ day: i, other: false });
  const remaining = 7 - (days.length % 7);
  if (remaining < 7) {
    for (let i = 1; i <= remaining; i++) days.push({ day: i, other: true });
  }

  const getWeekDays = () => {
    const todayIdx = days.findIndex(
      (d) => !d.other && d.day === (currentYear === todayYear && currentMonth === todayMonth ? todayDate : 1)
    );
    const startIdx = todayIdx >= 0 ? todayIdx - (new Date(currentYear, currentMonth - 1, days[todayIdx]?.day || 1).getDay()) : 0;
    return days.slice(Math.max(0, startIdx), Math.max(0, startIdx) + 7);
  };

  const displayDays = view === 'week' ? getWeekDays() : days;

  // multi-day 이벤트 분리 (중복 제거) / 단일 이벤트 분리
  const multiDayEventsMap = new Map();
  const singleDayEvents = [];
  mergedEvents.forEach(e => {
    if (e.startDate && e.endDate && e.startDate !== e.endDate) {
      const key = e.scheduleId || e.id;
      if (key && !multiDayEventsMap.has(key)) multiDayEventsMap.set(key, e);
    } else {
      singleDayEvents.push(e);
    }
  });
  const multiDayEvents = Array.from(multiDayEventsMap.values());

  // 멀티데이 이벤트마다 고정 row 배정 (그리디 알고리즘)
  // 같은 이벤트가 모든 셀에서 동일한 row를 쓰도록 사전 배정
  const sortedMultiDay = [...multiDayEvents].sort((a, b) => a.startDate.localeCompare(b.startDate));
  const rowEndDates = [];
  const multiDayRowMap = new Map();
  sortedMultiDay.forEach(event => {
    const key = event.scheduleId || event.id;
    let row = 0;
    while (row < rowEndDates.length && rowEndDates[row] >= event.startDate) {
      row++;
    }
    rowEndDates[row] = event.endDate;
    multiDayRowMap.set(key, row);
  });

  const handleDayClick = (d) => {
    if (d.other) return;
    setSelectedDay(d.day);
  };

  const handleYearMonthClick = (month) => {
    setCurrentMonth(month);
    setView('month');
  };

  const selectedEvents = selectedDay
    ? mergedEvents.filter((e) => e.day === selectedDay && e.month === currentMonth)
    : [];

  const VIEW_BTNS = [
    { key: 'month', label: '월간' },
    { key: 'week', label: '주간' },
    { key: 'year', label: '연간' },
  ];

  return (
    <div className="card">
      <div className="card-header">
        <div className="flex items-center gap-3">
          <div className="flex gap-1">
            <button onClick={goToPrev} className="w-7 h-7 rounded-md border border-neutral-border bg-surface-card text-xs text-neutral-sub flex items-center justify-center hover:bg-primary-50 transition">◀</button>
            <button onClick={goToNext} className="w-7 h-7 rounded-md border border-neutral-border bg-surface-card text-xs text-neutral-sub flex items-center justify-center hover:bg-primary-50 transition">▶</button>
          </div>
          <span className="text-base font-bold">
            {view === 'year' ? `${currentYear}년` : `${currentYear}년 ${currentMonth}월`}
          </span>
          <button onClick={goToToday} className="text-[0.6875rem] px-2 py-1 rounded border border-neutral-divider text-neutral-muted hover:bg-primary-50 hover:text-primary-700 transition">오늘</button>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 flex-wrap">
            <button
              onClick={() => setHiddenTypes(new Set())}
              className={`px-2.5 py-1 rounded-md text-xs font-medium border transition ${showAll
                  ? 'border-primary-500 bg-primary-50 text-primary-700'
                  : 'border-neutral-divider bg-surface-card text-neutral-main opacity-40'
                }`}
            >
              전체
            </button>
            {allFilterTypes.map(({ id, label, color }) => {
              const active = !hiddenTypes.has(id);
              return (
                <button
                  key={id}
                  onClick={() => toggleType(id)}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border transition ${active
                      ? 'border-neutral-border bg-surface-card text-neutral-main'
                      : 'border-neutral-divider bg-surface-card text-neutral-main opacity-40'
                    }`}
                >
                  <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: active ? color : '#9CA3AF' }} />
                  {label}
                </button>
              );
            })}
          </div>
          <div className="w-px h-4 bg-neutral-divider" />
          <div className="flex gap-1">
            {VIEW_BTNS.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setView(key)}
                className={`px-3 py-1 rounded-md text-xs font-medium transition ${view === key ? 'bg-primary-50 text-primary-700 font-semibold' : 'text-neutral-sub hover:bg-surface-hover'}`}
              >{label}</button>
            ))}
          </div>
        </div>
      </div>
      <div className="card-body">
        {view === 'year' ? (
          <YearView
            year={currentYear}
            events={mergedEvents}
            todayYear={todayYear}
            todayMonth={todayMonth}
            todayDate={todayDate}
            onMonthClick={handleYearMonthClick}
          />
        ) : (
          <div className="grid grid-cols-7 gap-1">
            {dayNames.map((d, idx) => (
              <div key={d} className={`text-[0.6875rem] font-semibold py-2 text-center ${idx === 0 ? 'text-red-500' : idx === 6 ? 'text-blue-500' : 'text-neutral-muted'}`}>{d}</div>
            ))}
            {displayDays.map((d, i) => {
              const dayEvents = singleDayEvents.filter(e => e.day === d.day && e.month === currentMonth && !d.other);
              const isToday = !d.other && d.day === todayDate && currentYear === todayYear && currentMonth === todayMonth;
              const isHoliday = dayEvents.some(e => e.type === 'holiday');

              // 이 셀에 걸친 multi-day 이벤트 스트라이프
              const dayStripes = d.other ? [] : multiDayEvents.filter(event => {
                if (!event.startDate || !event.endDate) return false;
                const cellDate = new Date(currentYear, currentMonth - 1, d.day);
                return cellDate >= new Date(event.startDate + 'T00:00:00') && cellDate <= new Date(event.endDate + 'T00:00:00');
              });

              return (
                <div
                  key={i}
                  onClick={() => handleDayClick(d)}
                  className={`relative ${view === 'week' ? 'min-h-[300px]' : 'min-h-[120px]'} bg-surface-card border border-neutral-divider rounded-sm p-1.5 text-xs transition hover:border-primary-300 cursor-pointer ${isToday ? 'border-primary-700 border-2' : ''} ${selectedDay === d.day && !d.other ? 'ring-2 ring-primary-500' : ''}`}
                  style={(() => {
                    if (dayStripes.length === 0) return {};
                    const maxRow = Math.max(...dayStripes.map(e => multiDayRowMap.get(e.scheduleId || e.id) ?? 0));
                    return { paddingBottom: `${(maxRow + 1) * 20 + 4}px` };
                  })()}
                >
                  <div className={`font-semibold mb-1 ${d.other ? 'text-neutral-muted' : (i % 7 === 0 || isHoliday) ? 'text-red-500' : i % 7 === 6 ? 'text-blue-500' : 'text-neutral-main'}`}>{d.day}</div>
                  {dayEvents.map((e, j) => {
                    const builtInStyle = DEFAULT_TYPE_STYLES[e.type];
                    const color = typeColorMap[e.type];
                    return (
                      <div key={j} className="mb-0.5">
                        <div
                          className={`text-[0.625rem] px-1.5 py-0.5 rounded font-medium truncate ${builtInStyle || ''}`}
                          style={!builtInStyle && color ? { backgroundColor: hexToRgba(color, 0.15), color } : {}}
                        >
                          {e.label}
                        </div>
                      </div>
                    );
                  })}

                  {/* 하단 스트라이프 (multi-day 이벤트) */}
                  {dayStripes.map((event) => {
                    const eventStart = new Date(event.startDate + 'T00:00:00');
                    const eventEnd = new Date(event.endDate + 'T00:00:00');
                    const cellDate = new Date(currentYear, currentMonth - 1, d.day);
                    const isStart = cellDate.getTime() === eventStart.getTime();
                    const isEnd = cellDate.getTime() === eventEnd.getTime();
                    const isWeekStart = i % 7 === 0;
                    const showLabel = isStart || isWeekStart;
                    const color = typeColorMap[event.type] || '#9CA3AF';
                    const row = multiDayRowMap.get(event.scheduleId || event.id) ?? 0;
                    return (
                      <div
                        key={event.scheduleId || event.id}
                        className="absolute flex items-center overflow-hidden"
                        style={{
                          bottom: `${row * 20 + 2}px`,
                          height: '18px',
                          left: isStart ? 6 : -2,
                          right: isEnd ? 6 : -2,
                          backgroundColor: hexToRgba(color, 0.18),
                          borderRadius: `${isStart ? '4px' : '0'} ${isEnd ? '4px' : '0'} ${isEnd ? '4px' : '0'} ${isStart ? '4px' : '0'}`,
                          zIndex: isStart ? 2 : 1,
                        }}
                      >
                        {showLabel && (
                          <span style={{ color, fontSize: '10px', fontWeight: 600, paddingLeft: '6px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {event.label}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 날짜 클릭 시 상세 팝업 */}
      {selectedDay && (
        <DayDetailPopup
          day={selectedDay}
          month={currentMonth}
          year={currentYear}
          events={selectedEvents}
          typeColorMap={typeColorMap}
          typeLabelMap={typeLabelMap}
          onClose={() => setSelectedDay(null)}
          onDeleteEvent={onDeleteEvent}
          onCanDelete={onCanDelete}
          onEditEvent={onEditEvent}
          onCanEdit={onCanEdit}
        />
      )}
    </div>
  );
}
