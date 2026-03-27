import { useState } from 'react';
import { AlertTriangle, CalendarPlus, Check, CheckCircle, Download, Info, Loader2, Pencil } from 'lucide-react';
import { createSchedule } from '../../api/schedules';
import { toast } from '../../store/toastStore';
import Badge from '../common/Badge';

// 모델명을 사용자 친화적으로 변환
const formatModel = (name) => {
  if (!name) return null;
  const lower = name.toLowerCase();
  // (placeholder) 제거
  const cleaned = name.replace(/\s*\(placeholder\)/gi, '');
  if (lower.includes('kanana') || lower.includes('lora')) return 'Kanana-1.5-8B';
  if (lower.includes('gpt-4o-mini')) return 'GPT-4o-mini';
  if (lower.includes('gpt-4o')) return 'GPT-4o';
  if (lower.includes('gpt')) return cleaned;
  return cleaned;
};

// LoRA 여부 판별
const isLoraModel = (name) => {
  if (!name) return false;
  return name.toLowerCase().includes('lora') || name.toLowerCase().includes('kanana');
};

export default function GenerateCard({ title, templateType, fields = [], actionItems = [], actionLabel = 'Action Items', downloadUrl, onDownload, modelName, regulationCheck, warnings, suggestedSchedules = [] }) {
  const typeLabels = { meeting_minutes: '회의록', report: '보고서', jd: '채용 공고', proposal: '제안서' };
  const displayModel = formatModel(modelName);
  const lora = isLoraModel(modelName);

  return (
    <div className="bg-surface-card rounded-xl border border-neutral-border overflow-hidden shadow-sm">
      {/* 헤더: 타이틀 + 모델 뱃지 */}
      <div className="px-4 py-3 border-b border-neutral-divider flex items-center justify-between">
        <div className="font-bold text-sm text-primary-700">
          {title || '문서 생성 완료'}
        </div>
        <div className="flex items-center gap-2">
          {displayModel && (
            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[0.6875rem] font-medium ${
              lora ? 'bg-emerald-100 text-emerald-700' : 'bg-violet-100 text-violet-700'
            }`}>
              {lora ? 'sLLM' : 'LLM'} · {displayModel}
            </span>
          )}
        </div>
      </div>

      <div className="p-4">
        <p className="text-sm text-neutral-sub mb-3">문서가 생성되었습니다. 다운로드하여 확인해주세요.</p>
        {/* Action Items / 주요 업무 */}
        {actionItems.length > 0 && (
          <div className="mb-4">
            <div className="text-[0.8125rem] font-semibold text-neutral-sub mb-2">{actionLabel}</div>
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
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-primary-700 text-white text-xs font-semibold transition-all hover:bg-primary-900 hover:shadow-md"
          >
            <Download size={14} />
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


/* ── 일정 제안 서브 컴포넌트 (외부에서도 사용) ── */

export function ScheduleSuggestSection({ items }) {
  // description에서 담당자만 추출 ("담당: 한대리 | 출처: ..." → "한대리")
  const parseAssignee = (desc) => {
    if (!desc) return '';
    const m = desc.match(/담당:\s*([^|]+)/);
    return m ? m[1].trim() : '';
  };

  const [editItems, setEditItems] = useState(() =>
    items.map((item, i) => ({
      ...item,
      checked: true,
      registered: false,
      _key: i,
      _assignee: parseAssignee(item.description),
    })),
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
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[0.625rem] text-neutral-400 flex items-center gap-0.5">
          <Pencil size={9} /> 제목, 날짜 수정 가능
        </span>
      </div>

      <div className="space-y-2">
        {editItems.map((item, idx) => (
          <div
            key={item._key}
            className={`flex items-start gap-2 p-2.5 rounded-lg border text-xs transition-all ${
              item.registered
                ? 'bg-green-50 border-green-200'
                : item.checked
                  ? 'bg-white border-blue-200 hover:shadow-sm'
                  : 'bg-neutral-50 border-neutral-200 opacity-60'
            }`}
          >
            <input
              type="checkbox"
              checked={item.checked}
              disabled={item.registered}
              onChange={() => toggleCheck(idx)}
              className="mt-0.5 shrink-0 accent-blue-600"
            />

            <div className="flex-1 min-w-0 space-y-1.5">
              {/* 제목 (수정 가능, 밑줄 힌트) */}
              <input
                type="text"
                value={item.title}
                disabled={item.registered}
                onChange={(e) => updateField(idx, 'title', e.target.value)}
                className="w-full font-medium text-neutral-main bg-transparent border-b border-dashed border-neutral-300 hover:border-blue-400 focus:border-blue-500 focus:outline-none px-0 py-0.5 disabled:border-transparent disabled:hover:border-transparent"
              />

              {/* 날짜 + 담당자 + 상태 */}
              <div className="flex items-center gap-2 flex-wrap">
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

                {/* 과거 날짜 경고 (날짜 바로 옆) */}
                {isPastDate(item.start_time) && !item.registered && (
                  <span className="text-[0.625rem] text-orange-500 flex items-center gap-0.5" title="날짜를 수정해주세요">
                    <AlertTriangle size={10} /> 지난 날짜입니다
                  </span>
                )}

                {/* 담당자 */}
                {item._assignee && (
                  <span className="text-[0.6875rem] text-neutral-400">
                    {item._assignee}
                  </span>
                )}

                {/* 등록 완료 */}
                {item.registered && (
                  <span className="text-[0.625rem] text-green-600 flex items-center gap-0.5 font-medium">
                    <Check size={10} /> 등록 완료
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

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
