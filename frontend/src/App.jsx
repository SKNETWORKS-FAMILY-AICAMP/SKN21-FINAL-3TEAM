/**
 * 메인 App 라우팅 (팀원 E 담당)
 */
import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/common/Layout'
import DashboardPage from './pages/DashboardPage'
import ChatPage from './pages/ChatPage'
import DocumentsPage from './pages/DocumentsPage'
import MeetingsPage from './pages/MeetingsPage'
import SchedulesPage from './pages/SchedulesPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import AdminPage from './pages/AdminPage'

function App() {
  return (
    <Routes>
      {/* 인증 */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* 메인 레이아웃 */}
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="chat" element={<ChatPage />} />
        <Route path="documents" element={<DocumentsPage />} />
        <Route path="meetings" element={<MeetingsPage />} />
        <Route path="schedules" element={<SchedulesPage />} />
        <Route path="admin" element={<AdminPage />} />
      </Route>
    </Routes>
  )
}

export default App
