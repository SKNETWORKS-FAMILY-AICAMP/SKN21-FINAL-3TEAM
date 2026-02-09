import { useState } from 'react';

export default function RegisterForm({ onSubmit }) {
  const [form, setForm] = useState({ name: '', email: '', password: '', confirmPassword: '' });
  const update = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="space-y-4">
      <div><label className="block text-[13px] font-semibold mb-1.5">이름</label><input value={form.name} onChange={update('name')} placeholder="홍길동" className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500" /></div>
      <div><label className="block text-[13px] font-semibold mb-1.5">이메일</label><input type="email" value={form.email} onChange={update('email')} placeholder="name@company.com" className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500" /></div>
      <div><label className="block text-[13px] font-semibold mb-1.5">비밀번호</label><input type="password" value={form.password} onChange={update('password')} placeholder="8자 이상" className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500" /></div>
      <div><label className="block text-[13px] font-semibold mb-1.5">비밀번호 확인</label><input type="password" value={form.confirmPassword} onChange={update('confirmPassword')} placeholder="비밀번호 재입력" className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500" /></div>
      <button onClick={() => onSubmit?.(form)} className="w-full py-3 rounded-sm bg-primary-700 text-white text-sm font-semibold transition hover:bg-primary-900">회원가입</button>
    </div>
  );
}
