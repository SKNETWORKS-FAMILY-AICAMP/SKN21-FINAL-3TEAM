/**
 * Pipeline Task API (팀원 D 담당)
 * - 백엔드 /api/v1/pipeline/ 연동
 * - 팀별 분리 (같은 팀끼리만 공유)
 */
import client from './client'

export const listPipelineTasks = () =>
  client.get('/pipeline/')

export const createPipelineTask = (data) =>
  client.post('/pipeline/', data)

export const updatePipelineTask = (id, data) =>
  client.put(`/pipeline/${id}`, data)

export const deletePipelineTask = (id) =>
  client.delete(`/pipeline/${id}`)
