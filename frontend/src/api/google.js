/**
 * Google 서비스 통합 API 클라이언트
 */
import client from './client'

// ── Google OAuth ──

export const getGoogleStatus = () =>
  client.get('/google/status')

export const connectGoogle = (scopes) =>
  client.post('/google/connect', { scopes })

export const disconnectGoogle = () =>
  client.post('/google/disconnect')

// ── Google Tasks ──

export const syncTask = (actionItemId) =>
  client.post('/tasks/sync', { action_item_id: actionItemId })

export const syncAllTasks = (meetingId = null) =>
  client.post('/tasks/sync-all', { meeting_id: meetingId })

export const createTask = (data) =>
  client.post('/tasks/create', data)

export const deleteTask = (actionItemId) =>
  client.delete(`/tasks/${actionItemId}`)

export const listTasks = () =>
  client.get('/tasks/')

export const updateTaskStatus = (actionItemId, completed) =>
  client.put(`/tasks/${actionItemId}/status`, { completed })

export const pullTaskStatus = () =>
  client.post('/tasks/pull')

// ── Gmail ──

export const sendReminder = (actionItemId, recipientEmail) =>
  client.post('/gmail/send-reminder', {
    action_item_id: actionItemId,
    recipient_email: recipientEmail,
  })

export const sendMeetingInvite = (data) =>
  client.post('/gmail/send-meeting-invite', data)

export const sendBulkReminders = (daysBefore = 3, recipientMap = {}) =>
  client.post('/gmail/send-bulk-reminders', {
    days_before: daysBefore,
    recipient_map: recipientMap,
  })

// ── Google Sheets ──

export const exportProjectToSheet = (projectName, title = null, options = {}) =>
  client.post('/sheets/export-project', {
    project_name: projectName,
    title,
    generate_wbs: options.generateWbs ?? true,
    generate_gantt: options.generateGantt ?? false,
    generate_dashboard: options.generateDashboard ?? false,
    generate_risk: options.generateRisk ?? false,
    generate_report: options.generateReport ?? false,
  })

export const syncSheet = (spreadsheetId, projectName) =>
  client.post(`/sheets/${spreadsheetId}/sync`, { project_name: projectName })

export const listSheets = () =>
  client.get('/sheets/')

export const deleteSheet = (spreadsheetId) =>
  client.delete(`/sheets/${spreadsheetId}`)

export const readSheetData = (spreadsheetId, sheetName = 'Sheet1') =>
  client.get(`/sheets/${spreadsheetId}/data`, { params: { sheet_name: sheetName } })

export const updateSheetData = (spreadsheetId, sheetName, updates) =>
  client.put(`/sheets/${spreadsheetId}/data`, { sheet_name: sheetName, updates })

// ── Calendar + Meet ──

export const listCalendarEvents = (timeMin = null, timeMax = null) => {
  const params = {}
  if (timeMin) params.time_min = timeMin
  if (timeMax) params.time_max = timeMax
  return client.get('/calendar/events', { params })
}

export const createEventWithMeet = (data) =>
  client.post('/calendar/event-with-meet', data)

export const syncEventToGoogle = (eventData) =>
  client.post('/calendar/sync', eventData)

export const deleteCalendarEvent = (eventId, calendarId = 'primary') =>
  client.delete(`/calendar/events/${eventId}`, { params: { calendar_id: calendarId } })

export const createGoogleCalendar = (name, color) =>
  client.post('/calendar/calendars', { name, color })

export const deleteGoogleCalendar = (calendarId) =>
  client.delete('/calendar/calendars', { params: { calendar_id: calendarId } })
