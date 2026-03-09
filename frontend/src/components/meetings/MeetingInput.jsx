import { useState, useEffect, useMemo } from 'react';
import { ChevronDown, X } from 'lucide-react';
import useAuthStore from '../../store/authStore';
import client from '../../api/client';

export default function MeetingInput({ onSubmit, loading }) {
  const user = useAuthStore((s) => s.user);
  const [allMembers, setAllMembers] = useState([]);
  const [form, setForm] = useState({
    title: '',
    date: new Date().toISOString().split('T')[0],
    author: user?.name ?? '',
    team: user?.team ?? '',
    content: '',
  });
  const [selectedAttendees, setSelectedAttendees] = useState([]);
  const [showAttendeesDropdown, setShowAttendeesDropdown] = useState(false);

  // Fetch all members to group by team
  useEffect(() => {
    client.get('/auth/all-members')
      .then(res => {
        const members = res.data || [];
        if (user) {
          const hasSelf = members.some(m => m.id === user.id);
          if (!hasSelf) {
            members.push({ id: user.id, name: user.name, team: user.team, avatar: user.avatar });
          }
        }
        setAllMembers(members);
      })
      .catch(() => setAllMembers([]));
  }, [user]);

  // Available teams (extracted from members)
  const teams = useMemo(() => {
    const set = new Set(allMembers.map(m => m.team).filter(Boolean));
    if (user?.team) set.add(user.team);
    return [...set].sort();
  }, [allMembers, user]);

  // Members of currently selected team
  const teamMembers = useMemo(() => {
    return allMembers.filter(m => m.team === form.team);
  }, [allMembers, form.team]);

  const toggleAttendee = (name) => {
    setSelectedAttendees(prev =>
      prev.includes(name) ? prev.filter(n => n !== name) : [...prev, name]
    );
  };

  const removeAttendee = (name) => {
    setSelectedAttendees(prev => prev.filter(n => n !== name));
  };

  const update = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!form.content.trim()) return;
    onSubmit?.({
      ...form,
      attendees: selectedAttendees,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="card">
      <div className="card-header">
        <div className="card-title">회의 내용 입력</div>
      </div>
      <div className="card-body space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-[0.8125rem] font-semibold mb-1.5">회의 제목</label>
            <input
              value={form.title}
              onChange={update('title')}
              placeholder="예: 보안점검 정기회의"
              className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500"
            />
          </div>
          <div>
            <label className="block text-[0.8125rem] font-semibold mb-1.5">회의 날짜</label>
            <input
              type="date"
              value={form.date}
              onChange={update('date')}
              className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-[0.8125rem] font-semibold mb-1.5">팀</label>
            <div className="relative">
              <select
                value={form.team}
                onChange={(e) => setForm({ ...form, team: e.target.value })}
                className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500 appearance-none bg-white dark:bg-neutral-900 cursor-pointer"
              >
                <option value="">팀 선택</option>
                {teams.map(t => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
              <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-400 pointer-events-none" />
            </div>
          </div>
          <div>
            <label className="block text-[0.8125rem] font-semibold mb-1.5">작성자</label>
            <input
              value={form.author}
              onChange={update('author')}
              placeholder="예: 김정보"
              className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500"
            />
          </div>
        </div>

        {/* 참석자 */}
        <div>
          <label className="block text-[0.8125rem] font-semibold mb-1.5">참석자</label>
          <div className="relative">
            <div
              onClick={() => setShowAttendeesDropdown(prev => !prev)}
              className="w-full min-h-[42px] px-3.5 py-2 border border-neutral-border rounded-sm text-sm outline-none focus-within:border-primary-500 cursor-pointer flex flex-wrap items-center gap-1.5"
            >
              {selectedAttendees.length > 0 ? (
                selectedAttendees.map(name => (
                  <span key={name} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-primary-50 text-primary-700 text-xs font-medium">
                    {name}
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); removeAttendee(name); }}
                      className="hover:text-primary-900 transition-colors"
                    >
                      <X size={12} />
                    </button>
                  </span>
                ))
              ) : (
                <span className="text-neutral-400 text-sm">팀원을 선택하세요</span>
              )}
            </div>

            {/* Dropdown */}
            {showAttendeesDropdown && (
              <>
                <div className="fixed inset-0 z-10" onClick={(e) => { e.stopPropagation(); setShowAttendeesDropdown(false); }} />
                <div
                  className="absolute top-full left-0 right-0 mt-1 z-20 bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-700 rounded-lg shadow-xl max-h-[200px] overflow-y-auto"
                  onClick={(e) => e.stopPropagation()}
                >
                  {teamMembers.length > 0 ? (
                    teamMembers.map(m => {
                      const isSelected = selectedAttendees.includes(m.name);
                      return (
                        <div
                          key={m.id}
                          onClick={() => toggleAttendee(m.name)}
                          className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm cursor-pointer hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors ${isSelected ? 'bg-primary-50/50 dark:bg-primary-900/10' : ''}`}
                        >
                          <div className={`w-4 h-4 rounded border-2 flex items-center justify-center flex-shrink-0 transition-all ${isSelected ? 'border-primary-700 bg-primary-700' : 'border-neutral-300 dark:border-neutral-500'}`}>
                            {isSelected && (
                              <svg width="10" height="10" viewBox="0 0 12 12" fill="none"><path d="M2 6l3 3 5-5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
                            )}
                          </div>
                          <img
                            src={m.avatar || `https://api.dicebear.com/7.x/notionists/svg?seed=${encodeURIComponent(m.name)}`}
                            alt={m.name}
                            className="w-7 h-7 rounded-full object-cover bg-neutral-100 dark:bg-neutral-700 flex-shrink-0"
                          />
                          <span className={`${isSelected ? 'font-semibold text-primary-700' : 'text-neutral-700 dark:text-neutral-300'}`}>{m.name}</span>
                        </div>
                      );
                    })
                  ) : (
                    <div className="px-4 py-3 text-sm text-neutral-400 text-center">
                      {form.team ? '팀원이 없습니다' : '팀을 먼저 선택하세요'}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>

        <div>
          <label className="block text-[0.8125rem] font-semibold mb-1.5">회의 내용</label>
          <textarea
            value={form.content}
            onChange={update('content')}
            placeholder="회의에서 논의된 내용을 입력하세요. 음성 녹취 텍스트를 붙여넣어도 됩니다."
            rows={4}
            onInput={(e) => { e.target.style.height = 'auto'; e.target.style.height = Math.min(e.target.scrollHeight, 130) + 'px'; }}
            className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500 resize-none overflow-y-auto max-h-[130px]"
          />
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={loading || !form.content.trim()}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'AI 분석 중...' : 'AI 회의록 생성'}
          </button>
        </div>
      </div>
    </form>
  );
}
