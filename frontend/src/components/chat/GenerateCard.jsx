import { useState } from 'react';
import { AlertTriangle, CalendarPlus, Check, CheckCircle, Info, Loader2 } from 'lucide-react';
import { createSchedule } from '../../api/schedules';
import { toast } from '../../store/toastStore';
import Badge from '../common/Badge';

export default function GenerateCard({ title, templateType, fields = [], actionItems = [], downloadUrl, onDownload, modelName, regulationCheck, warnings, suggestedSchedules = [] }) {
  const typeLabels = { meeting_minutes: '회의록', report: '보고서', jd: '채용 공고', proposal: '제안서' };

  return (
    <div className="bg-surface-card rounded-lg border border-neutral-border overflow-hidden">
      <div className="px-4 py-3 border-b border-neutral-divider flex items-center justify-between">
        <div className="flex items-center gap-2 font-bold text-sm text-primary-700">
{title || '문서 생성 완료'}
        </div>
        <div className="flex items-center gap-2">
          {templateType && <Badge variant="document">{typeLabels[templateType] || templateType}</Badge>}
          {modelName && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[0.6875rem] font-medium bg-violet-100 text-violet-700">
              {modelName.includes('LoRA') ? '🔧 ' : '🤖 '}{modelName}
            </span>
          )}
        </div>
      </div>
      <div className="p-4">
        {fields.length > 0 && (
          <div className="space-y-2 mb-4">
            {fields.map((f, i) => (
              <div key={i} className="text-[0.8125rem]">
                <span className="font-semibold text-neutral-sub">{f.label}: </span>
                <span className="text-neutral-main">{f.value}</span>
              </div>
            ))}
          </div>
        )}

        {/* Action Items (회의록만) */}
        {actionItems.length > 0 && (
          <div className="mb-4">
            <div className="text-[0.8125rem] font-semibold text-neutral-sub mb-2">Action Items</div>
            <div className="space-y-1.5">
              {actionItems.map((item, i) => (
                <div key={i} className="flex items-start gap-2 text-[0.8125rem]">
                  <span className="text-neutral-400 shrink-0">{i + 1}.</span>
                  <div>
                    <span className="text-neutral-main">{item.task}</span>
                    {(item.assignee || item.due_date) && (
                      <span className="text-neutral-sub ml-1.5 text-xs">
                        {item.assignee && `(${item.assignee})`}
                        {item.due_date && ` ~${item.due_date}`}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 일정 제안 섹션 */}
        {suggestedSchedules.length > 0 && (
          <ScheduleSuggestSection items={suggestedSchedules} />
        )}

        {/* 규정 검증 결과 */}
        {regulationCheck?.notes?.length > 0 && (
          <div className="mb-4 space-y-1.5">
            <div className="text-[0.8125rem] font-semibold text-neutral-sub mb-1 flex items-center gap-1">
              <AlertTriangle size={14} className="text-yellow-500" />
              규정 검증 결과
            </div>
            {regulationCheck.notes.map((n, i) => (
              <div key={i} className={`flex items-start gap-1.5 p-2.5 rounded-lg border text-xs ${
                n.result === 'no' ? 'bg-red-50 border-red-200 text-red-700' :
                n.result === 'conditional' ? 'bg-yellow-50 border-yellow-200 text-yellow-700' :
                'bg-green-50 border-green-200 text-green-700'
              }`}>
                {n.result === 'no' ? <AlertTriangle size={13} className="shrink-0 mt-0.5" /> :
                 n.result === 'conditional' ? <Info size={13} className="shrink-0 mt-0.5" /> :
                 <CheckCircle size={13} className="shrink-0 mt-0.5" />}
                <div>
                  <span className="font-semibold">{n.result === 'no' ? '[위반]' : n.result === 'conditional' ? '[조건부]' : '[부합]'} {n.topic}</span>
                  <p className="text-[0.6875rem] mt-0.5">{n.reason}</p>
                  {n.regulation && <p className="text-[0.625rem] mt-0.5 italic opacity-75">근거: {n.regulation}</p>}
                </div>
              </div>
            ))}
          </div>
        )}
        {Array.isArray(warnings) && warnings.length > 0 && !regulationCheck?.notes?.length && (
          <div className="mb-4 space-y-1">
            {warnings.map((w, i) => (
              <div key={i} className="flex items-start gap-1.5 text-xs text-yellow-700 bg-yellow-50 border border-yellow-200 rounded-lg px-3 py-2">
                <AlertTriangle size={13} className="text-yellow-500 mt-0.5 shrink-0" />
                <span>{w}</span>
              </div>
            ))}
          </div>
        )}

        <div className="flex gap-2">
          <button
            onClick={onDownload}
            className="btn-primary text-xs"
          >
            다운로드
          </button>
          {downloadUrl && (
            <a href={downloadUrl} target="_blank" rel="noreferrer" className="btn-outline text-xs">
              미리보기
            </a>
          )}
        </div>
      </div>
    </div>
  );
}


/* ── 일정 제안 서브 컴포넌트 ── */

const PRIORITY_STYLES = {
  high: 'bg-red-100 text-red-700',
  medium: 'bg-yellow-100 text-yellow-700',
  low: 'bg-green-100 text-green-700',
};
const PRIORITY_LABELS = { high: '높음', medium: '보통', low: '낮음' };

function ScheduleSuggestSection({ items }) {
  const [editItems, setEditItems] = useState(() =>
    items.map((item, i) => ({ ...item, checked: true, registered: false, _key: i })),
  );
  const [loading, setLoading] = useState(false);

  const checkedCount = editItems.filter((it) => it.checked && !it.registered).length;

  const toggleCheck = (idx) => {
    setEditItems((prev) => prev.map((it, i) => (i === idx ? { ...it, checked: !it.checked } : it)));
  };

  const updateField = (idx, field, value) => {
    setEditItems((prev) => prev.map((it, i) => (i === idx ? { ...it, [field]: value } : it)));
  };

  const handleRegister = async () => {
    const toRegister = editItems.filter((it) => it.checked && !it.registered);
    if (toRegister.length === 0) return;

    setLoading(true);
    let successCount = 0;

    for (const item of toRegister) {
      try {
        await createSchedule({
          title: item.title,
          description: item.description || '',
          start_time: item.start_time,
          end_time: item.end_time,
          schedule_type: item.schedule_type || 'task',
          priority: item.priority || 'medium',
        });
        successCount++;
        setEditItems((prev) =>
          prev.map((it) => (it._key === item._key ? { ...it, registered: true } : it)),
        );
      } catch (err) {
        toast.error(`'${item.title}' 등록 실패: ${err.response?.data?.detail || err.message}`);
      }
    }

    setLoading(false);
    if (successCount > 0) {
      toast.success(`${successCount}건의 일정이 캘린더에 등록되었습니다.`);
    }
  };

  const isPastDate = (dateStr) => {
    try {
      return new Date(dateStr) < new Date(new Date().toDateString());
    } catch { return false; }
  };

  return (
    <div className="mb-4 p-3 rounded-lg border border-blue-200 bg-blue-50/50">
      <div className="text-[0.8125rem] font-semibold text-blue-700 mb-2 flex items-center gap-1.5">
        <CalendarPlus size={14} />
        일정 등록 제안 ({items.length}건)
      </div>

      <div className="space-y-2">
        {editItems.map((item, idx) => (
          <div
            key={item._key}
            className={`flex items-start gap-2 p-2 rounded border text-xs transition-colors ${
              item.registered
                ? 'bg-green-50 border-green-200 opacity-75'
                : item.checked
                  ? 'bg-white border-blue-200'
                  : 'bg-neutral-50 border-neutral-200 opacity-60'
            }`}
          >
            {/* 체크박스 */}
            <input
              type="checkbox"
              checked={item.checked}
              disabled={item.registered}
              onChange={() => toggleCheck(idx)}
              className="mt-1 shrink-0 accent-blue-600"
            />

            <div className="flex-1 min-w-0 space-y-1">
              {/* 제목 (수정 가능) */}
              <input
                type="text"
                value={item.title}
                disabled={item.registered}
                onChange={(e) => updateField(idx, 'title', e.target.value)}
                className="w-full font-medium text-neutral-main bg-transparent border-b border-transparent hover:border-neutral-300 focus:border-blue-400 focus:outline-none px-0 py-0.5 disabled:hover:border-transparent"
              />

              <div className="flex items-center gap-2 flex-wrap">
                {/* 날짜 (수정 가능) */}
                <input
                  type="date"
                  value={item.start_time?.slice(0, 10) || ''}
                  disabled={item.registered}
                  onChange={(e) => {
                    const d = e.target.value;
                    updateField(idx, 'start_time', `${d}T09:00:00`);
                    updateField(idx, 'end_time', `${d}T10:00:00`);
                  }}
                  className="text-[0.6875rem] text-neutral-sub border border-neutral-200 rounded px-1.5 py-0.5 disabled:opacity-50"
                />

                {/* 우선순위 */}
                <span className={`inline-block px-1.5 py-0.5 rounded text-[0.625rem] font-medium ${PRIORITY_STYLES[item.priority] || PRIORITY_STYLES.medium}`}>
                  {PRIORITY_LABELS[item.priority] || '보통'}
                </span>

                {/* 담당자 표시 */}
                {item.description && (
                  <span className="text-[0.6875rem] text-neutral-400 truncate">
                    {item.description}
                  </span>
                )}

                {/* 과거 날짜 경고 */}
                {isPastDate(item.start_time) && !item.registered && (
                  <span className="text-[0.625rem] text-orange-500 flex items-center gap-0.5">
                    <AlertTriangle size={10} /> 과거 날짜
                  </span>
                )}

                {/* 등록 완료 표시 */}
                {item.registered && (
                  <span className="text-[0.625rem] text-green-600 flex items-center gap-0.5">
                    <Check size={10} /> 등록 완료
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* 등록 버튼 */}
      {editItems.some((it) => !it.registered) && (
        <button
          onClick={handleRegister}
          disabled={loading || checkedCount === 0}
          className="mt-2.5 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? (
            <><Loader2 size={12} className="animate-spin" /> 등록 중...</>
          ) : (
            <><CalendarPlus size={12} /> 선택한 일정 등록 ({checkedCount}건)</>
          )}
        </button>
      )}
    </div>
  );
}
