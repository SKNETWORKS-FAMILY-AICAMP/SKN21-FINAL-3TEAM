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

export const createSheet = (title = 'Action Items 추적', meetingId = null) =>
  client.post('/sheets/create', { title, meeting_id: meetingId })

export const syncSheet = (spreadsheetId, meetingId = null) =>
  client.post(`/sheets/${spreadsheetId}/sync`, { meeting_id: meetingId })

export const listSheets = () =>
  client.get('/sheets/')

export const getSheetUrl = (meetingId) =>
  client.get(`/sheets/${meetingId}/url`)

// ── Calendar + Meet ──

export const createEventWithMeet = (data) =>
  client.post('/calendar/event-with-meet', data)
