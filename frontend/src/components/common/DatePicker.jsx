import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { ChevronLeft, ChevronRight, Calendar } from 'lucide-react';

const DAYS = ['일', '월', '화', '수', '목', '금', '토'];
const MONTHS = ['1월', '2월', '3월', '4월', '5월', '6월', '7월', '8월', '9월', '10월', '11월', '12월'];

export default function DatePicker({ value, onChange, placeholder = '날짜 선택...', autoOpen = false }) {
  const [isOpen, setIsOpen] = useState(autoOpen);
  const [popupStyle, setPopupStyle] = useState({});
  const today = new Date();
  const [viewDate, setViewDate] = useState(() => value ? new Date(value) : today);
  const triggerRef = useRef(null);
  const popupRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (
        triggerRef.current && !triggerRef.current.contains(e.target) &&
        popupRef.current && !popupRef.current.contains(e.target)
      ) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (isOpen && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      const popupWidth = 272;
      const popupHeight = 320;
      const spaceBelow = window.innerHeight - rect.bottom;
      const top = spaceBelow >= popupHeight
        ? rect.bottom + 4
        : rect.top - popupHeight - 4;
      const left = Math.min(rect.right - popupWidth, window.innerWidth - popupWidth - 8);
      setPopupStyle({ position: 'fixed', top, left, zIndex: 9999 });
    }
  }, [isOpen]);

  const year = viewDate.getFullYear();
  const month = viewDate.getMonth();
  const firstDay = new Date(year, month, 1).getDay();
  const lastDate = new Date(year, month + 1, 0).getDate();

  const cells = [
    ...Array(firstDay).fill(null),
    ...Array.from({ length: lastDate }, (_, i) => i + 1),
  ];

  const handleSelect = (day) => {
    const selected = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    onChange(selected);
    setIsOpen(false);
  };

  const selectedYear = value ? parseInt(value.split('-')[0]) : null;
  const selectedMonth = value ? parseInt(value.split('-')[1]) - 1 : null;
  const selectedDay = value ? parseInt(value.split('-')[2]) : null;

  const isSelected = (day) =>
    day === selectedDay && month === selectedMonth && year === selectedYear;
  const isToday = (day) =>
    day === today.getDate() && month === today.getMonth() && year === today.getFullYear();

  return (
    <div className="relative" ref={triggerRef}>
      {/* 트리거 버튼 */}
      <button
        type="button"
        onClick={() => setIsOpen((o) => !o)}
        className="flex items-center gap-2 bg-surface-card border border-neutral-border rounded-md px-3.5 w-full py-2.5 text-sm hover:border-primary-400 transition"
      >
        <Calendar size={15} className="text-neutral-muted flex-shrink-0" />
        <span className={value ? 'text-neutral-main' : 'text-neutral-muted'}>
          {value || placeholder}
        </span>
      </button>

      {/* 달력 팝업 — Portal로 body에 렌더링 */}
      {isOpen && createPortal(
        <div
          ref={popupRef}
          style={popupStyle}
          className="bg-surface-card border border-neutral-divider rounded-lg shadow-lg p-4 w-[272px]"
        >
          {/* 월 네비게이션 */}
          <div className="flex items-center justify-between mb-3">
            <button
              onClick={() => setViewDate(new Date(year, month - 1, 1))}
              className="p-1.5 hover:bg-surface-hover rounded transition"
            >
              <ChevronLeft size={15} />
            </button>
            <span className="text-sm font-semibold text-neutral-main">
              {year}년 {MONTHS[month]}
            </span>
            <button
              onClick={() => setViewDate(new Date(year, month + 1, 1))}
              className="p-1.5 hover:bg-surface-hover rounded transition"
            >
              <ChevronRight size={15} />
            </button>
          </div>

          {/* 요일 헤더 */}
          <div className="grid grid-cols-7 mb-1">
            {DAYS.map((d, i) => (
              <div
                key={d}
                className={`text-center text-[0.6875rem] font-medium py-1 ${
                  i === 0 ? 'text-red-400' : i === 6 ? 'text-blue-400' : 'text-neutral-muted'
                }`}
              >
                {d}
              </div>
            ))}
          </div>

          {/* 날짜 그리드 */}
          <div className="grid grid-cols-7 gap-y-0.5">
            {cells.map((day, idx) =>
              day ? (
                <button
                  key={idx}
                  onClick={() => handleSelect(day)}
                  className={[
                    'w-full aspect-square flex items-center justify-center text-xs rounded transition',
                    isSelected(day)
                      ? 'bg-primary-700 text-white font-semibold'
                      : isToday(day)
                      ? 'border border-primary-400 text-primary-700 font-semibold hover:bg-primary-50'
                      : idx % 7 === 0
                      ? 'text-red-400 hover:bg-surface-hover'
                      : idx % 7 === 6
                      ? 'text-blue-400 hover:bg-surface-hover'
                      : 'text-neutral-main hover:bg-surface-hover',
                  ].join(' ')}
                >
                  {day}
                </button>
              ) : (
                <div key={idx} />
              )
            )}
          </div>

          {/* 오늘 선택 버튼 */}
          <div className="mt-3 pt-3 border-t border-neutral-divider">
            <button
              onClick={() => {
                setViewDate(today);
                handleSelect(today.getDate());
              }}
              className="w-full text-xs text-primary-700 hover:bg-primary-50 py-1.5 rounded transition font-medium"
            >
              오늘 선택
            </button>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
