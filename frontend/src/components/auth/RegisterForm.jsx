import { useState } from 'react';

export default function RegisterForm({ onSubmit, error, loading }) {
  const [form, setForm] = useState({ name: '', email: '', password: '', confirmPassword: '' });
  const [localError, setLocalError] = useState('');

  const update = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const handleSubmit = (e) => {
    e.preventDefault();
    setLocalError('');

    if (!form.name.trim()) {
      setLocalError('이름을 입력해주세요.');
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
        <label className="block text-[0.8125rem] font-semibold mb-1.5">비밀번호</label>
        <input
          type="password"
          value={form.password}
          onChange={update('password')}
          placeholder="8자 이상"
          disabled={loading}
          className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500 focus:shadow-[0_0_0_3px_rgba(110,135,160,0.1)] disabled:opacity-50 disabled:cursor-not-allowed"
        />
        {form.password && form.password.length < 8 && (
          <p className="mt-1 text-xs text-warning">비밀번호는 8자 이상이어야 합니다 ({form.password.length}/8)</p>
        )}
      </div>

      <div>
        <label className="block text-[0.8125rem] font-semibold mb-1.5">비밀번호 확인</label>
        <input
          type="password"
          value={form.confirmPassword}
          onChange={update('confirmPassword')}
          placeholder="비밀번호 재입력"
          disabled={loading}
          className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500 focus:shadow-[0_0_0_3px_rgba(110,135,160,0.1)] disabled:opacity-50 disabled:cursor-not-allowed"
        />
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
