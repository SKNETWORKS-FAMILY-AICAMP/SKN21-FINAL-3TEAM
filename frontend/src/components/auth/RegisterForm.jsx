import { useState } from 'react';
import { TEAMS } from '../../utils/constants';

export default function RegisterForm({ onSubmit, error, loading }) {
  const [form, setForm] = useState({ name: '', email: '', password: '', confirmPassword: '', team: '' });
  const [localError, setLocalError] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const update = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const handleSubmit = (e) => {
    e.preventDefault();
    setLocalError('');

    if (!form.name.trim()) {
      setLocalError('이름을 입력해주세요.');
      return;
    }
    if (!form.team) {
      setLocalError('팀(부서)을 선택해주세요.');
      return;
    }
    if (!form.email.trim()) {
      setLocalError('이메일을 입력해주세요.');
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
      setLocalError('올바른 이메일 형식을 입력해주세요.');
      return;
    }
    if (form.password.length < 8) {
      setLocalError('비밀번호는 8자 이상이어야 합니다.');
      return;
    }
    if (form.password !== form.confirmPassword) {
      setLocalError('비밀번호가 일치하지 않습니다.');
      return;
    }

    onSubmit?.(form);
  };

  const displayError = localError || error;

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {displayError && (
        <div className="p-3 rounded-sm bg-error-bg border border-error text-error text-sm">
          {displayError}
        </div>
      )}

      <div>
        <label className="block text-[0.8125rem] font-semibold mb-1.5">이름</label>
        <input
          value={form.name}
          onChange={update('name')}
          placeholder="홍길동"
          disabled={loading}
          className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500 focus:shadow-[0_0_0_3px_rgba(110,135,160,0.1)] disabled:opacity-50 disabled:cursor-not-allowed"
        />
      </div>

      <div>
        <label className="block text-[0.8125rem] font-semibold mb-1.5">이메일</label>
        <input
          type="email"
          value={form.email}
          onChange={update('email')}
          placeholder="name@company.com"
          disabled={loading}
          className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500 focus:shadow-[0_0_0_3px_rgba(110,135,160,0.1)] disabled:opacity-50 disabled:cursor-not-allowed"
        />
      </div>

      <div>
        <label className="block text-[0.8125rem] font-semibold mb-1.5">팀(부서)</label>
        <select
          value={form.team}
          onChange={update('team')}
          disabled={loading}
          className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500 focus:shadow-[0_0_0_3px_rgba(110,135,160,0.1)] bg-surface-card text-neutral-main disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <option value="">팀을 선택해주세요</option>
          {TEAMS.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-[0.8125rem] font-semibold mb-1.5">비밀번호</label>
        <div className="relative">
          <input
            type={showPassword ? 'text' : 'password'}
            value={form.password}
            onChange={update('password')}
            placeholder="8자 이상"
            disabled={loading}
            className="w-full px-3.5 py-2.5 pr-10 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500 focus:shadow-[0_0_0_3px_rgba(110,135,160,0.1)] disabled:opacity-50 disabled:cursor-not-allowed"
          />
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-muted hover:text-neutral-main transition"
            aria-label={showPassword ? '비밀번호 숨기기' : '비밀번호 보기'}
          >
            {showPassword ? (
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                <line x1="1" y1="1" x2="23" y2="23" />
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            )}
          </button>
        </div>
        {form.password && form.password.length < 8 && (
          <p className="mt-1 text-xs text-warning">비밀번호는 8자 이상이어야 합니다 ({form.password.length}/8)</p>
        )}
      </div>

      <div>
        <label className="block text-[0.8125rem] font-semibold mb-1.5">비밀번호 확인</label>
        <div className="relative">
          <input
            type={showConfirm ? 'text' : 'password'}
            value={form.confirmPassword}
            onChange={update('confirmPassword')}
            placeholder="비밀번호 재입력"
            disabled={loading}
            className="w-full px-3.5 py-2.5 pr-10 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500 focus:shadow-[0_0_0_3px_rgba(110,135,160,0.1)] disabled:opacity-50 disabled:cursor-not-allowed"
          />
          <button
            type="button"
            onClick={() => setShowConfirm(!showConfirm)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-neutral-muted hover:text-neutral-main transition"
            aria-label={showConfirm ? '비밀번호 숨기기' : '비밀번호 보기'}
          >
            {showConfirm ? (
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                <line x1="1" y1="1" x2="23" y2="23" />
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
            )}
          </button>
        </div>
        {form.confirmPassword && form.password !== form.confirmPassword && (
          <p className="mt-1 text-xs text-error">비밀번호가 일치하지 않습니다</p>
        )}
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full py-3 rounded-sm bg-primary-700 text-white text-sm font-semibold transition hover:bg-primary-900 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? '회원가입 중...' : '회원가입'}
      </button>
    </form>
  );
}
