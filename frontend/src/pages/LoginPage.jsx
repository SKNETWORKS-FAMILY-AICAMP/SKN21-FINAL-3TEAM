import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import LoginForm from '../components/auth/LoginForm';
import RegisterForm from '../components/auth/RegisterForm';
import PasswordReset from '../components/auth/PasswordReset';
import useAuth from '../hooks/useAuth';
import useAuthStore from '../store/authStore';
import client from '../api/client';

export default function LoginPage() {
  const [tab, setTab] = useState('login'); // 'login' | 'register' | 'reset'
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showRegisterSuccess, setShowRegisterSuccess] = useState(false);
  const [registeredCredentials, setRegisteredCredentials] = useState({ email: '', password: '' });
  const { login, register } = useAuth();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth); // Google 로그인 콜백용

  // Google 소셜 로그인 콜백 처리: URL에 token이 있으면 저장 후 대시보드 이동
  useEffect(() => {
    const token = searchParams.get('token');
    const userName = searchParams.get('user_name');
    const googleError = searchParams.get('error');

    if (token) {
      (async () => {
        localStorage.setItem('access_token', token);
        const { data: me } = await client.get('/auth/me').catch(() => ({ data: { name: userName || '' } }));
        setAuth(me, token);
        navigate('/dashboard', { replace: true });
      })();
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
      let msg;
      if (!err.response) {
        msg = '서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.';
      } else if (Array.isArray(err.response?.data?.detail)) {
        msg = '입력값을 확인해주세요.';
      } else {
        msg = err.response?.data?.detail || '로그인에 실패했습니다. 이메일과 비밀번호를 확인해주세요.';
      }
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async ({ name, email, password, confirmPassword, team }) => {
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
      await register(email, password, name, team);
      setRegisteredCredentials({ email, password });
      setShowRegisterSuccess(true);
    } catch (err) {
      const msg = err.response?.data?.detail || '회원가입에 실패했습니다. 다시 시도해주세요.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleRegisterSuccessConfirm = () => {
    setShowRegisterSuccess(false);
    switchTab('login');
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
      {/* 회원가입 성공 팝업 */}
      {showRegisterSuccess && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white/80 dark:bg-neutral-900/80 backdrop-blur-xl rounded-lg border border-white/40 dark:border-white/10 shadow-xl p-8 w-80 max-w-[90vw] text-center">
            <div className="w-14 h-14 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-primary-700">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </div>
            <h3 className="text-lg font-bold text-primary-900 mb-2">회원가입 완료!</h3>
            <p className="text-sm text-neutral-sub mb-6">환영합니다!<br />로그인 화면으로 이동합니다.</p>
            <button
              onClick={handleRegisterSuccessConfirm}
              className="w-full py-2.5 rounded-sm bg-primary-700 text-white text-sm font-semibold hover:bg-primary-900 transition"
            >
              확인
            </button>
          </div>
        </div>
      )}
      <div className="bg-surface-card rounded-lg border border-neutral-border p-10 w-[28rem] max-w-[90vw] shadow-md">
        <div className="flex items-center gap-3 justify-center mb-8">
          <div className="w-11 h-11 bg-accent-300 rounded-sm flex items-center justify-center text-[1.375rem] font-bold text-primary-900">W</div>
          <span className="font-display text-[1.375rem] font-bold text-primary-700">WorkFlow Agent</span>
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
              ? <LoginForm onSubmit={handleLogin} onGoogleLogin={handleGoogleLogin} error={error} loading={loading} defaultEmail={registeredCredentials.email} defaultPassword={registeredCredentials.password} />
              : <RegisterForm onSubmit={handleRegister} error={error} loading={loading} />
            }

            <div className="text-center mt-5 text-[0.8125rem] text-neutral-sub">
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
