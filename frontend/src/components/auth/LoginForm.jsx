import { useState } from 'react';

export default function LoginForm({ onSubmit, onGoogleLogin, error, loading }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [localError, setLocalError] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    setLocalError('');

    if (!email.trim()) {
      setLocalError('이메일을 입력해주세요.');
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setLocalError('올바른 이메일 형식을 입력해주세요.');
      return;
    }
    if (!password) {
      setLocalError('비밀번호를 입력해주세요.');
      return;
    }

    onSubmit?.({ email, password });
  };

  const displayError = localError || error;

  return (
    <form onSubmit={handleSubmit}>
      {displayError && (
        <div className="mb-4 p-3 rounded-sm bg-error-bg border border-error text-error text-sm">
          {displayError}
        </div>
      )}

      <div className="mb-4">
        <label className="block text-[0.8125rem] font-semibold text-neutral-main mb-1.5">이메일</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="name@company.com"
          disabled={loading}
          className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm text-neutral-main focus:border-primary-500 focus:shadow-[0_0_0_3px_rgba(110,135,160,0.1)] outline-none placeholder:text-neutral-muted disabled:opacity-50 disabled:cursor-not-allowed"
        />
      </div>

      <div className="mb-4">
        <label className="block text-[0.8125rem] font-semibold text-neutral-main mb-1.5">비밀번호</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="비밀번호를 입력하세요"
          disabled={loading}
          className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm text-neutral-main focus:border-primary-500 focus:shadow-[0_0_0_3px_rgba(110,135,160,0.1)] outline-none placeholder:text-neutral-muted disabled:opacity-50 disabled:cursor-not-allowed"
        />
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full py-3 rounded-sm bg-primary-700 text-white text-sm font-semibold transition hover:bg-primary-900 mb-2.5 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? '로그인 중...' : '로그인'}
      </button>

      <div className="flex items-center gap-3 my-5 text-xs text-neutral-muted">
        <span className="flex-1 h-px bg-neutral-divider" />또는<span className="flex-1 h-px bg-neutral-divider" />
      </div>

      <button
        type="button"
        onClick={onGoogleLogin}
        disabled={loading}
        className="w-full py-3 rounded-sm bg-surface-card text-neutral-main text-sm font-semibold border border-neutral-border transition hover:bg-surface-hover disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Google 계정으로 로그인
      </button>
    </form>
  );
}
