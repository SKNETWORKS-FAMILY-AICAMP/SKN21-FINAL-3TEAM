/**
 * 일정 관리 페이지 (팀원 E 담당)
 * - FullCalendar 주간/월간
 * - 일정 타입 색상 구분
 * - Google 서비스 통합 (Calendar, Tasks, Gmail, Sheets)
 *
 * 레이아웃:
 *   좌측 3/4: CalendarView + ScheduleForm
 *   우측 1/4: GoogleServicesConnect + TasksPanel + SheetsDashboard
 */
import CalendarView from '../components/schedules/CalendarView'
import ScheduleForm from '../components/schedules/ScheduleForm'
import GoogleServicesConnect from '../components/schedules/GoogleServicesConnect'
import TasksPanel from '../components/schedules/TasksPanel'
import SheetsDashboard from '../components/schedules/SheetsDashboard'

export default function SchedulesPage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">일정 관리</h1>
      {/* TODO: 팀원 E 구현 */}
      {/* - 좌측: CalendarView + ScheduleForm (새 일정 토글) */}
      {/* - 우측: GoogleServicesConnect + TasksPanel + SheetsDashboard */}
      <p className="text-gray-500">일정 관리 UI 구현 예정</p>
    </div>
  )
}
