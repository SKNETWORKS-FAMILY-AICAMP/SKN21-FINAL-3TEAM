import { useState } from 'react';
import { Link } from 'react-router-dom';
import LoginForm from '../components/auth/LoginForm';
import RegisterForm from '../components/auth/RegisterForm';

export default function LoginPage() {
  const [tab, setTab] = useState('login');

  return (
    <div className="flex items-center justify-center min-h-screen bg-surface-main">
      <div className="bg-surface-card rounded-lg border border-neutral-border p-10 w-[400px] shadow-md">
        <div className="flex items-center gap-3 justify-center mb-8">
          <div className="w-11 h-11 bg-accent-300 rounded-sm flex items-center justify-center text-[22px]">📋</div>
          <span className="font-display text-[22px] font-bold text-primary-700">WorkFlow Agent</span>
        </div>
        <div className="flex mb-6 rounded-sm overflow-hidden border border-neutral-border">
          <button onClick={() => setTab('login')} className={`flex-1 py-2.5 text-center text-sm font-medium transition ${tab === 'login' ? 'bg-primary-700 text-white' : 'bg-surface-card text-neutral-sub'}`}>로그인</button>
          <button onClick={() => setTab('register')} className={`flex-1 py-2.5 text-center text-sm font-medium transition ${tab === 'register' ? 'bg-primary-700 text-white' : 'bg-surface-card text-neutral-sub'}`}>회원가입</button>
        </div>
        {tab === 'login' ? <LoginForm /> : <RegisterForm />}
        <div className="text-center mt-5 text-[13px] text-neutral-sub">
          {tab === 'login' ? <>계정이 없으신가요? <button onClick={() => setTab('register')} className="text-primary-700 font-semibold">회원가입</button></> : <>이미 계정이 있으신가요? <button onClick={() => setTab('login')} className="text-primary-700 font-semibold">로그인</button></>}
        </div>
      </div>
    </div>
  );
}
