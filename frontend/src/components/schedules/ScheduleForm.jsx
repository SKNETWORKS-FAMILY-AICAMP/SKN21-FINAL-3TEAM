import { useState } from 'react';

export default function ScheduleForm({ onSubmit, onClose }) {
  const [form, setForm] = useState({ title: '', date: '', time: '', type: 'meeting' });

  return (
    <div className="card p-5">
      <h3 className="text-base font-bold mb-4">일정 추가</h3>
      <div className="space-y-3">
        <div><label className="text-[13px] font-semibold block mb-1">제목</label><input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm focus:border-primary-500 focus:shadow-[0_0_0_3px_rgba(110,135,160,0.1)] outline-none" /></div>
        <div className="grid grid-cols-2 gap-3">
          <div><label className="text-[13px] font-semibold block mb-1">날짜</label><input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none" /></div>
          <div><label className="text-[13px] font-semibold block mb-1">시간</label><input type="time" value={form.time} onChange={(e) => setForm({ ...form, time: e.target.value })} className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none" /></div>
        </div>
        <div className="flex gap-2 pt-2">
          <button onClick={() => onSubmit?.(form)} className="btn-primary">등록</button>
          <button onClick={onClose} className="btn-outline">취소</button>
        </div>
      </div>
    </div>
  );
}
