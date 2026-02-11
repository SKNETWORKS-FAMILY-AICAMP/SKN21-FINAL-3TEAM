import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import LoginForm from '../components/auth/LoginForm';
import RegisterForm from '../components/auth/RegisterForm';
import PasswordReset from '../components/auth/PasswordReset';
import useAuth from '../hooks/useAuth';
import useAuthStore from '../store/authStore';

export default function LoginPage() {
  const [tab, setTab] = useState('login'); // 'login' | 'register' | 'reset'
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login, register } = useAuth();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);

  // Google 소셜 로그인 콜백 처리: URL에 token이 있으면 저장 후 대시보드 이동
  useEffect(() => {
    const token = searchParams.get('token');
    const userName = searchParams.get('user_name');
    const googleError = searchParams.get('error');

    if (token) {
      setAuth({ name: userName || '' }, token);
      navigate('/dashboard', { replace: true });
    } else if (googleError) {
      setError('Google 로그인에 실패했습니다. 다시 시도해주세요.');
    }
  }, [searchParams, setAuth, navigate]);

  const handleLogin = async ({ email, password }) => {
    setError('');
    setLoading(true);
    try {
      await login(email, password);
    } catch (err) {
      const msg = err.response?.data?.detail || '로그인에 실패했습니다. 이메일과 비밀번호를 확인해주세요.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async ({ name, email, password, confirmPassword }) => {
    if (password !== confirmPassword) {
      setError('비밀번호가 일치하지 않습니다.');
      return;
    }
    if (password.length < 8) {
      setError('비밀번호는 8자 이상이어야 합니다.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      await register(email, password, name);
    } catch (err) {
      const msg = err.response?.data?.detail || '회원가입에 실패했습니다. 다시 시도해주세요.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = () => {
    window.location.href = '/api/v1/auth/google';
  };

  const switchTab = (newTab) => {
    setTab(newTab);
    setError('');
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-surface-main">
      <div className="bg-surface-card rounded-lg border border-neutral-border p-10 w-[400px] shadow-md">
        <div className="flex items-center gap-3 justify-center mb-8">
          <div className="w-11 h-11 bg-accent-300 rounded-sm flex items-center justify-center text-[22px]">📋</div>
          <span className="font-display text-[22px] font-bold text-primary-700">WorkFlow Agent</span>
        </div>

        {/* 비밀번호 찾기 화면 */}
        {tab === 'reset' ? (
          <PasswordReset onBack={() => switchTab('login')} />
        ) : (
          <>
            <div className="flex mb-6 rounded-sm overflow-hidden border border-neutral-border">
              <button onClick={() => switchTab('login')} className={`flex-1 py-2.5 text-center text-sm font-medium transition ${tab === 'login' ? 'bg-primary-700 text-white' : 'bg-surface-card text-neutral-sub'}`}>로그인</button>
              <button onClick={() => switchTab('register')} className={`flex-1 py-2.5 text-center text-sm font-medium transition ${tab === 'register' ? 'bg-primary-700 text-white' : 'bg-surface-card text-neutral-sub'}`}>회원가입</button>
            </div>

            {tab === 'login'
              ? <LoginForm onSubmit={handleLogin} onGoogleLogin={handleGoogleLogin} error={error} loading={loading} />
              : <RegisterForm onSubmit={handleRegister} error={error} loading={loading} />
            }

            <div className="text-center mt-5 text-[13px] text-neutral-sub">
              {tab === 'login'
                ? (
                  <div className="space-y-2">
                    <div>계정이 없으신가요? <button onClick={() => switchTab('register')} className="text-primary-700 font-semibold">회원가입</button></div>
                    <div>비밀번호를 잊으셨나요? <button onClick={() => switchTab('reset')} className="text-primary-700 font-semibold">비밀번호 찾기</button></div>
                  </div>
                )
                : <>이미 계정이 있으신가요? <button onClick={() => switchTab('login')} className="text-primary-700 font-semibold">로그인</button></>
              }
            </div>
          </>
        )}
      </div>
    </div>
  );
}
