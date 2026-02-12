import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import useAuthStore from './store/authStore';
import Layout from './components/common/Layout';
import FontSizeControl from './components/common/FontSizeControl';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import ChatPage from './pages/ChatPage';
import DocumentsPage from './pages/DocumentsPage';
import MeetingsPage from './pages/MeetingsPage';
import SchedulesPage from './pages/SchedulesPage';
import AdminPage from './pages/AdminPage';
import MeetingMinutesPage from './pages/MeetingMinutesPage';
import DocumentGeneratePage from './pages/DocumentGeneratePage';

// DEV_BYPASS: 백엔드 JWT 인증 연동 완료 — 실제 인증 플로우 사용
const DEV_BYPASS_AUTH = false;

function PrivateRoute() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const initialized = useAuthStore((s) => s.initialized);
  if (!initialized) return null; // 초기화 완료 전 빈 화면
  return (DEV_BYPASS_AUTH || isAuthenticated) ? <Outlet /> : <Navigate to="/login" replace />;
}

function PublicOnlyRoute() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const initialized = useAuthStore((s) => s.initialized);
  if (!initialized) return null;
  return isAuthenticated ? <Navigate to="/dashboard" replace /> : <Outlet />;
}

export default function App() {
  const initialize = useAuthStore((s) => s.initialize);

  useEffect(() => {
    initialize();
  }, [initialize]);

  return (
    <BrowserRouter>
      <FontSizeControl />
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
            <Route path="/meeting-minutes" element={<MeetingMinutesPage />} />
            <Route path="/document-generate" element={<DocumentGeneratePage />} />
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/meetings" element={<MeetingsPage />} />
            <Route path="/schedules" element={<SchedulesPage />} />
            <Route path="/admin" element={<AdminPage />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
