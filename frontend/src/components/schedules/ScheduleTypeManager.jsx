import { useState } from 'react';
import useScheduleTypeStore, { DEFAULT_TYPES } from '../../store/scheduleTypeStore';

// 디자인 시스템과 동일한 톤다운 계열 (채도 낮고 차분한 색상)
const PRESET_COLORS = [
  '#3D5164', // 딥 슬레이트
  '#6E87A0', // 뮤트 블루 (primary)
  '#5B8FA0', // 뮤트 틸
  '#5B9A6F', // 뮤트 세이지 (success)
  '#8A9A5B', // 뮤트 올리브
  '#C49A3C', // 뮤트 앰버 (warning)
  '#C07850', // 뮤트 테라코타
  '#C06060', // 뮤트 레드 (error)
  '#A05878', // 뮤트 로즈
  '#7870A0', // 뮤트 라벤더
  '#8B7D6E', // 다크 토프 (accent)
  '#A89580', // 웜 베이지 (accent)
];

export default function ScheduleTypeManager({ onClose }) {
  const { customTypes, addType, removeType } = useScheduleTypeStore();
  const [newLabel, setNewLabel] = useState('');
  const [newColor, setNewColor] = useState('#6E87A0');

  const handleAdd = () => {
    const trimmed = newLabel.trim();
    if (!trimmed) return;
    addType(trimmed, newColor);
    setNewLabel('');
    setNewColor('#6E87A0');
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/20"
      onClick={onClose}
    >
      <div className="w-[420px] card p-5" onClick={(e) => e.stopPropagation()}>
        {/* 헤더 */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-bold">일정 유형 관리</h3>
          <button
            onClick={onClose}
            className="w-6 h-6 flex items-center justify-center rounded hover:bg-surface-hover text-neutral-muted text-sm"
          >✕</button>
        </div>

        {/* 기본 유형 */}
        <div className="mb-4">
          <p className="text-[0.8125rem] font-semibold text-neutral-sub mb-2">기본 유형</p>
          <div className="space-y-1.5">
            {DEFAULT_TYPES.map((t) => (
              <div key={t.id} className="flex items-center gap-2.5 px-3 py-2 bg-surface-hover rounded-sm">
                <span
                  className="w-3 h-3 rounded-full flex-shrink-0"
                  style={{ backgroundColor: t.color }}
                />
                <span className="text-sm text-neutral-main">{t.label}</span>
                <span className="ml-auto text-[0.6875rem] text-neutral-muted">기본</span>
              </div>
            ))}
          </div>
        </div>

        {/* 커스텀 유형 */}
        {customTypes.length > 0 && (
          <div className="mb-4">
            <p className="text-[0.8125rem] font-semibold text-neutral-sub mb-2">커스텀 유형</p>
            <div className="space-y-1.5">
              {customTypes.map((t) => (
                <div key={t.id} className="flex items-center gap-2.5 px-3 py-2 bg-surface-hover rounded-sm">
                  <span
                    className="w-3 h-3 rounded-full flex-shrink-0"
                    style={{ backgroundColor: t.color }}
                  />
                  <span className="text-sm text-neutral-main">{t.label}</span>
                  <button
                    onClick={() => removeType(t.id)}
                    className="ml-auto text-neutral-muted hover:text-error text-xs px-1.5 py-0.5 rounded hover:bg-error-bg transition"
                  >삭제</button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 새 유형 추가 */}
        <div className="border-t border-neutral-divider pt-4">
          <p className="text-[0.8125rem] font-semibold mb-2.5">새 유형 추가</p>
          <div className="space-y-3">
            {/* 이름 입력 + 추가 버튼 인라인 */}
            <div className="flex">
              <input
                value={newLabel}
                onChange={(e) => setNewLabel(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
                placeholder="유형 이름 (예: 워크숍, 점심 약속)"
                className="flex-1 px-3.5 py-2.5 border border-neutral-border rounded-l-sm text-sm focus:border-primary-500 outline-none"
              />
              <button
                onClick={handleAdd}
                disabled={!newLabel.trim()}
                className="px-4 py-2.5 text-white text-sm font-semibold rounded-r-sm border disabled:opacity-40 disabled:cursor-not-allowed transition whitespace-nowrap"
                style={{ backgroundColor: newColor, borderColor: newColor }}
              >
                + 추가
              </button>
            </div>

            <div>
              <p className="text-[0.75rem] text-neutral-sub mb-1.5">색상 선택</p>
              <div className="flex flex-wrap gap-2 mb-2">
                {PRESET_COLORS.map((c) => (
                  <button
                    key={c}
                    onClick={() => setNewColor(c)}
                    title={c}
                    className={`w-6 h-6 rounded-full transition border-2 ${
                      newColor === c ? 'border-neutral-main scale-110' : 'border-transparent hover:scale-105'
                    }`}
                    style={{ backgroundColor: c }}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
