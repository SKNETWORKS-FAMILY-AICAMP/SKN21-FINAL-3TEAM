import { useState } from 'react';
import * as authAPI from '../../api/auth';

export default function PasswordReset({ onBack }) {
  const [step, setStep] = useState('request'); // 'request' | 'confirm' | 'done'
  const [email, setEmail] = useState('');
  const [token, setToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Step 1: 이메일로 재설정 요청
  const handleRequest = async (e) => {
    e.preventDefault();
    setError('');

    if (!email.trim()) {
      setError('이메일을 입력해주세요.');
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError('올바른 이메일 형식을 입력해주세요.');
      return;
    }

    setLoading(true);
    try {
      await authAPI.requestPasswordReset(email);
      setStep('confirm');
    } catch (err) {
      const msg = err.response?.data?.detail || '요청에 실패했습니다. 이메일을 확인해주세요.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  // Step 2: 인증코드 + 새 비밀번호 입력
  const handleConfirm = async (e) => {
    e.preventDefault();
    setError('');

    if (!token.trim()) {
      setError('인증 코드를 입력해주세요.');
      return;
    }
    if (newPassword.length < 8) {
      setError('비밀번호는 8자 이상이어야 합니다.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('비밀번호가 일치하지 않습니다.');
      return;
    }

    setLoading(true);
    try {
      await authAPI.confirmPasswordReset(token, newPassword);
      setStep('done');
    } catch (err) {
      const msg = err.response?.data?.detail || '비밀번호 변경에 실패했습니다. 인증 코드를 확인해주세요.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h3 className="text-base font-semibold text-neutral-main mb-4">비밀번호 찾기</h3>

      {error && (
        <div className="mb-4 p-3 rounded-sm bg-error-bg border border-error text-error text-sm">
          {error}
        </div>
      )}

      {/* Step 1: 이메일 입력 */}
      {step === 'request' && (
        <form onSubmit={handleRequest}>
          <p className="text-sm text-neutral-sub mb-4">
            가입한 이메일을 입력하시면 비밀번호 재설정 코드를 보내드립니다.
          </p>
          <div className="mb-4">
            <label className="block text-[13px] font-semibold text-neutral-main mb-1.5">이메일</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@company.com"
              disabled={loading}
              className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500 focus:shadow-[0_0_0_3px_rgba(110,135,160,0.1)] disabled:opacity-50 disabled:cursor-not-allowed"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 rounded-sm bg-primary-700 text-white text-sm font-semibold transition hover:bg-primary-900 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? '전송 중...' : '인증 코드 받기'}
          </button>
        </form>
      )}

      {/* Step 2: 인증코드 + 새 비밀번호 */}
      {step === 'confirm' && (
        <form onSubmit={handleConfirm}>
          <div className="mb-4 p-3 rounded-sm bg-info-bg text-info text-sm">
            {email}로 인증 코드를 발송했습니다.
          </div>
          <div className="mb-4">
            <label className="block text-[13px] font-semibold text-neutral-main mb-1.5">인증 코드</label>
            <input
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="이메일로 받은 코드 입력"
              disabled={loading}
              className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500 focus:shadow-[0_0_0_3px_rgba(110,135,160,0.1)] disabled:opacity-50 disabled:cursor-not-allowed"
            />
          </div>
          <div className="mb-4">
            <label className="block text-[13px] font-semibold text-neutral-main mb-1.5">새 비밀번호</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="8자 이상"
              disabled={loading}
              className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500 focus:shadow-[0_0_0_3px_rgba(110,135,160,0.1)] disabled:opacity-50 disabled:cursor-not-allowed"
            />
          </div>
          <div className="mb-4">
            <label className="block text-[13px] font-semibold text-neutral-main mb-1.5">새 비밀번호 확인</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="비밀번호 재입력"
              disabled={loading}
              className="w-full px-3.5 py-2.5 border border-neutral-border rounded-sm text-sm outline-none focus:border-primary-500 focus:shadow-[0_0_0_3px_rgba(110,135,160,0.1)] disabled:opacity-50 disabled:cursor-not-allowed"
            />
            {confirmPassword && newPassword !== confirmPassword && (
              <p className="mt-1 text-xs text-error">비밀번호가 일치하지 않습니다</p>
            )}
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 rounded-sm bg-primary-700 text-white text-sm font-semibold transition hover:bg-primary-900 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? '변경 중...' : '비밀번호 변경'}
          </button>
        </form>
      )}

      {/* Step 3: 완료 */}
      {step === 'done' && (
        <div>
          <div className="mb-4 p-3 rounded-sm bg-success-bg text-success text-sm">
            비밀번호가 성공적으로 변경되었습니다.
          </div>
          <button
            onClick={onBack}
            className="w-full py-3 rounded-sm bg-primary-700 text-white text-sm font-semibold transition hover:bg-primary-900"
          >
            로그인으로 돌아가기
          </button>
        </div>
      )}

      {/* 뒤로가기 (완료 상태가 아닐 때) */}
      {step !== 'done' && (
        <button
          type="button"
          onClick={onBack}
          className="w-full mt-3 py-2.5 text-sm text-neutral-sub hover:text-neutral-main transition"
        >
          로그인으로 돌아가기
        </button>
      )}
    </div>
  );
}
