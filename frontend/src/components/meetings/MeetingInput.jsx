import { useState } from 'react';

export default function MeetingInput({ onSubmit, loading }) {
  const [form, setForm] = useState({
    title: '',
    date: new Date().toISOString().split('T')[0],
    attendees: '',
    content: '',
  });

  const update = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!form.content.trim()) return;
    onSubmit?.({
      ...form,
      attendees: form.attendees.split(',').map((s) => s.trim()).filter(Boolean),
    });
  };

  return (
    <form onSubmit={handleSubmit} className="card">
      <div className="card-header">
        <div className="card-title"><span>📝</span>회의 내용 입력</div>
      </div>
      <div className="card-body space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-[13px] font-semibold mb-1.5">회의 제목</label>
            <input
              value={form.title}
              onChange={update('title')}
              placeholder="예: 보안점검 정기회의"
              className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500"
            />
          </div>
          <div>
            <label className="block text-[13px] font-semibold mb-1.5">회의 날짜</label>
            <input
              type="date"
              value={form.date}
              onChange={update('date')}
              className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500"
            />
          </div>
        </div>

        <div>
          <label className="block text-[13px] font-semibold mb-1.5">참석자 (쉼표로 구분)</label>
          <input
            value={form.attendees}
            onChange={update('attendees')}
            placeholder="예: 김정보, 이개발, 박인사"
            className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500"
          />
        </div>

        <div>
          <label className="block text-[13px] font-semibold mb-1.5">회의 내용</label>
          <textarea
            value={form.content}
            onChange={update('content')}
            placeholder="회의에서 논의된 내용을 입력하세요. 음성 녹취 텍스트를 붙여넣어도 됩니다."
            rows={10}
            className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500 resize-y"
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
