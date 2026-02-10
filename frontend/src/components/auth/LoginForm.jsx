import { useState } from 'react';

export default function LoginForm({ onSubmit, onGoogleLogin }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  return (
    <div>
      <div className="mb-4">
        <label className="block text-[13px] font-semibold text-neutral-main mb-1.5">이메일</label>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@company.com"
          className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm text-neutral-main focus:border-primary-500 focus:shadow-[0_0_0_3px_rgba(110,135,160,0.1)] outline-none placeholder:text-neutral-muted" />
      </div>
      <div className="mb-4">
        <label className="block text-[13px] font-semibold text-neutral-main mb-1.5">비밀번호</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="비밀번호를 입력하세요"
          className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm text-neutral-main focus:border-primary-500 focus:shadow-[0_0_0_3px_rgba(110,135,160,0.1)] outline-none placeholder:text-neutral-muted" />
      </div>
      <button onClick={() => onSubmit?.({ email, password })} className="w-full py-3 rounded-sm bg-primary-700 text-white text-sm font-semibold transition hover:bg-primary-900 mb-2.5">로그인</button>
      <div className="flex items-center gap-3 my-5 text-xs text-neutral-muted"><span className="flex-1 h-px bg-neutral-divider" />또는<span className="flex-1 h-px bg-neutral-divider" /></div>
      <button onClick={onGoogleLogin} className="w-full py-3 rounded-sm bg-surface-card text-neutral-main text-sm font-semibold border border-neutral-border transition hover:bg-surface-hover">🔵 Google 계정으로 로그인</button>
    </div>
  );
}
