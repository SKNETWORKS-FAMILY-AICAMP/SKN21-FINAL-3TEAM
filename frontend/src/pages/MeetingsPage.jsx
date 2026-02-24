import { useState, useEffect } from 'react';
import { useOutletContext } from 'react-router-dom';
import MeetingList from '../components/meetings/MeetingList';
import MeetingDetail from '../components/meetings/MeetingDetail';
import { listMeetings, getMeeting } from '../api/meetings';

const USE_MOCK = true;

const MOCK_MEETINGS = [
  {
    id: 1,
    title: '2월 스프린트 킥오프 회의',
    meeting_date: '2026-02-10T10:00:00',
    summary: '핵심 기능 개발 우선순위 및 담당자 확정',
    risk_level: 'low',
    attendeeCount: 5,
    duration: '1시간 20분',
    raw_content: '참석자: 신지용(PM), 윤경은, 진승언, 안혜빈, 문지영\n장소: 회의실 A\n\n주요 논의사항:\n- 스프린트 목표: AI 챗봇 MVP 완성\n- 백엔드 API 연동 일정 조율\n- 프론트엔드 UI 컴포넌트 구조 확정',
    decisions: [
      { title: 'LangGraph 오케스트레이터 구조 확정', assignee: '신지용' },
      { title: 'RAG 파이프라인 벡터DB Qdrant 사용', assignee: '윤경은' },
      { title: '문서 생성 템플릿 4종 우선 개발', assignee: '진승언' },
    ],
    action_items: [
      { content: 'API 스키마 문서 작성', assignee: '안혜빈', due_date: '2026-02-14', priority: 'high' },
      { content: '챗봇 UI 와이어프레임 완성', assignee: '문지영', due_date: '2026-02-13', priority: 'high' },
      { content: 'LLM 모델 비교 보고서 작성', assignee: '윤경은', due_date: '2026-02-17', priority: 'medium' },
    ],
  },
  {
    id: 2,
    title: '백엔드-AI 연동 기술 협의',
    meeting_date: '2026-02-17T14:00:00',
    summary: 'SSE 스트리밍 방식 및 JWT 인증 플로우 확정',
    risk_level: 'medium',
    attendeeCount: 3,
    duration: '50분',
    raw_content: '참석자: 신지용(PM), 안혜빈, 진승언\n장소: 온라인(Discord)\n\n주요 논의사항:\n- FastAPI SSE 스트리밍 구현 방안\n- JWT 토큰 갱신 로직\n- LangGraph 에이전트와 백엔드 통신 구조',
    decisions: [
      { title: 'SSE 방식으로 스트리밍 응답 구현', assignee: '안혜빈' },
      { title: 'Refresh Token 7일 / Access Token 1시간으로 설정', assignee: '안혜빈' },
    ],
    action_items: [
      { content: 'SSE 엔드포인트 구현 및 테스트', assignee: '안혜빈', due_date: '2026-02-20', priority: 'high' },
      { content: 'LangGraph 스트리밍 콜백 연결', assignee: '진승언', due_date: '2026-02-21', priority: 'medium' },
    ],
  },
  {
    id: 3,
    title: '중간 점검 및 배포 계획 수립',
    meeting_date: '2026-02-24T11:00:00',
    summary: null,
    risk_level: null,
    attendeeCount: 5,
    duration: '1시간',
    raw_content: '',
    decisions: [],
    action_items: [],
  },
];

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
  const { isScrolled } = useOutletContext();
  const [meetings, setMeetings] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (USE_MOCK) {
      const list = MOCK_MEETINGS.map(toListItem);
      setMeetings(list);
      setSelected(toDetail(MOCK_MEETINGS[0]));
      setLoading(false);
      return;
    }
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
    if (USE_MOCK) {
      const full = MOCK_MEETINGS.find((r) => r.id === m.id) || m;
      setSelected(toDetail(full));
      return;
    }
    getMeeting(m.id)
      .then((res) => setSelected(toDetail(res.data)))
      .catch(() => setSelected(toListItem(m)));
  };

  return (
    <div>
      <header className={`flex justify-between items-center sticky top-0 bg-surface-main z-10 transition-all duration-300 ${isScrolled ? 'py-2.5' : 'py-6'}`}>
        <div>
          <h1 className={`font-bold transition-all duration-300 ${isScrolled ? 'text-lg' : 'text-2xl'}`}>회의 관리</h1>
          <p className={`text-neutral-sub transition-all duration-300 overflow-hidden ${isScrolled ? 'text-xs mt-0 max-h-0 opacity-0' : 'text-sm mt-1 max-h-6 opacity-100'}`}>회의록을 업로드하면 AI가 자동으로 분석합니다</p>
        </div>
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
