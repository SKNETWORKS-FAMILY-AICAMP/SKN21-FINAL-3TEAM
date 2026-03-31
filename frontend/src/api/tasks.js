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

/** 회의록 액션아이템 → Pipeline Todo 일괄 추가 */
export const createPipelineFromActionItems = (items, source) =>
  client.post('/pipeline/from-action-items', { items, source })

/** 프로젝트 CRUD */
export const listProjects = () =>
  client.get('/pipeline/projects')

export const createProject = (data) =>
  client.post('/pipeline/projects', data)

export const updateProject = (id, data) =>
  client.put(`/pipeline/projects/${id}`, data)

export const deleteProject = (id) =>
  client.delete(`/pipeline/projects/${id}`)
