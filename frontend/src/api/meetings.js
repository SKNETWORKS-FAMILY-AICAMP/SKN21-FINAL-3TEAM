/**
 * 회의 API : 회의록 목록 조회, 상세 분석 결과 확인 및 생성(팀원 E 담당)
 */
import client from './client'

// ── 회의 CRUD ──

export const listMeetings = () =>
  client.get('/meetings/')

export const getMeeting = (id) =>
  client.get(`/meetings/${id}`)

export const createMeeting = (data) =>
  client.post('/meetings/', data)

export const analyzeMeeting = (id) =>
  client.post(`/meetings/${id}/analyze`)

// ── 회의록 생성 ──

export const generateMeetingMinutes = (data) =>
  client.post('/meetings/generate', data)

export const downloadMeetingDocument = (meetingId, format = 'docx') =>
  client.get(`/meetings/${meetingId}/download`, {
    params: { format },
    responseType: 'blob',
  })
