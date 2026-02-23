import { useState, useEffect } from 'react';
import MeetingList from '../components/meetings/MeetingList';
import MeetingDetail from '../components/meetings/MeetingDetail';
import { listMeetings, getMeeting } from '../api/meetings';

const DAY_NAMES = ['일', '월', '화', '수', '목', '금', '토'];

function formatDDay(dateStr) {
  if (!dateStr) return '';
  const diff = Math.ceil((new Date(dateStr) - Date.now()) / (1000 * 60 * 60 * 24));
  const formatted = new Date(dateStr).toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' }).replace(/\. /g, '-').replace('.', '');
  if (diff > 0) return `D-${diff} (${formatted})`;
  if (diff === 0) return `D-Day (${formatted})`;
  return `D+${Math.abs(diff)} (${formatted})`;
}

function toListItem(m) {
  const d = m.meeting_date ? new Date(m.meeting_date) : new Date(m.created_at);
  return {
    ...m,
    dateShort: `${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`,
    dayOfWeek: DAY_NAMES[d.getDay()],
    analyzed: !!m.summary,
    riskLevel: m.risk_level || null,
  };
}

function toDetail(m) {
  let decisions = [];
  if (m.decisions) {
    try {
      const parsed = typeof m.decisions === 'string' ? JSON.parse(m.decisions) : m.decisions;
      decisions = Array.isArray(parsed)
        ? parsed.map((d) => (typeof d === 'string' ? { title: d, assignee: '-' } : { title: d.title || d.content || d, assignee: d.assignee || '-' }))
        : [];
    } catch { decisions = []; }
  }
  const actionItems = (m.action_items || []).map((a) => ({
    title: a.content,
    assignee: a.assignee || '-',
    deadline: formatDDay(a.due_date),
    priority: a.priority || 'medium',
  }));
  return {
    ...toListItem(m),
    info: m.raw_content || '',
    decisions,
    actionItems,
  };
}

export default function MeetingsPage() {
  const [meetings, setMeetings] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listMeetings()
      .then((res) => {
        const list = (res.data || []).map(toListItem);
        setMeetings(list);
        if (list.length > 0) handleSelect(list[0]);
      })
      .catch((err) => console.warn('[MeetingsPage] 목록 로드 실패:', err))
      .finally(() => setLoading(false));
  }, []);

  const handleSelect = (m) => {
    getMeeting(m.id)
      .then((res) => setSelected(toDetail(res.data)))
      .catch(() => setSelected(toListItem(m)));
  };

  return (
    <div>
      <header className="flex justify-between items-center py-6 sticky top-0 bg-surface-main z-10">
        <div><h1 className="text-2xl font-bold">회의 관리</h1><p className="text-sm text-neutral-sub mt-1">회의록을 업로드하면 AI가 자동으로 분석합니다</p></div>
        <button className="btn-primary">+ 회의록 업로드</button>
      </header>
      {loading ? (
        <div className="text-center py-20 text-neutral-muted text-sm">회의 목록을 불러오는 중...</div>
      ) : meetings.length === 0 ? (
        <div className="text-center py-20 text-neutral-muted text-sm">등록된 회의가 없습니다</div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[1.3fr_1fr] gap-5">
          <MeetingList meetings={meetings} selected={selected} onSelect={handleSelect} />
          <MeetingDetail meeting={selected} />
        </div>
      )}
    </div>
  );
}
