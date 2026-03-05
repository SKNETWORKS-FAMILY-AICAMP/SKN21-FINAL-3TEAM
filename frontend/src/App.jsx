import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation, useOutletContext } from 'react-router-dom';
import useAuthStore from './store/authStore';
import useUIStore from './store/uiStore';
import Layout from './components/common/Layout';
import FontSizeControl from './components/common/FontSizeControl';
import Toast from './components/common/Toast';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import ChatPage from './pages/ChatPage';
import DocumentsPage from './pages/DocumentsPage';
import SchedulesPage from './pages/SchedulesPage';
import AdminPage from './pages/AdminPage';
import DocumentGeneratePage from './pages/DocumentGeneratePage';
import MyPage from './pages/MyPage';
import TasksPage from './pages/TasksPage';
import ApprovalsPage from './pages/ApprovalsPage';
import NavPreviewPage from './pages/NavPreviewPage';

function ConditionalFontSizeControl() {
  const { pathname } = useLocation();
  const isAuthPage = pathname === '/login' || pathname === '/register';
  return isAuthPage ? <FontSizeControl /> : null;
}

// DEV_BYPASS: true = 로그인 없이 개발 화면 확인 가능
const DEV_BYPASS_AUTH = false;

function PrivateRoute() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const initialized = useAuthStore((s) => s.initialized);
  if (DEV_BYPASS_AUTH) return <Outlet />;
  if (!initialized) return null;
  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />;
}

function AdminRoute() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const initialized = useAuthStore((s) => s.initialized);
  const user = useAuthStore((s) => s.user);
  const ctx = useOutletContext();
  if (DEV_BYPASS_AUTH) return <Outlet context={ctx} />;
  if (!initialized) return null;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return user?.is_admin ? <Outlet context={ctx} /> : <Navigate to="/dashboard" replace />;
}

function PublicOnlyRoute() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const initialized = useAuthStore((s) => s.initialized);
  if (!initialized) return null;
  return isAuthenticated ? <Navigate to="/dashboard" replace /> : <Outlet />;
}

export default function App() {
  const initialize = useAuthStore((s) => s.initialize);
  const theme = useUIStore((s) => s.theme);

  useEffect(() => {
    initialize();
  }, [initialize]);

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  return (
    <BrowserRouter>
      <Toast />
      <ConditionalFontSizeControl />
      <Routes>
        {/* 비로그인 전용 (로그인 상태면 대시보드로) */}
        <Route element={<PublicOnlyRoute />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<LoginPage />} />
        </Route>

        {/* 로그인 필요 (비로그인이면 로그인으로) */}
        <Route element={<PrivateRoute />}>
          <Route element={<Layout />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/document-generate" element={<DocumentGeneratePage />} />
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/schedules" element={<SchedulesPage />} />
            <Route path="/tasks" element={<TasksPage />} />
            <Route path="/approvals" element={<ApprovalsPage />} />
            <Route path="/mypage" element={<MyPage />} />
            <Route element={<AdminRoute />}>
              <Route path="/admin" element={<AdminPage />} />
            </Route>
          </Route>
        </Route>

        {/* 네비게이션 프리뷰 (인증 없이 접근 가능) */}
        <Route path="/nav-preview" element={<NavPreviewPage />} />

        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
