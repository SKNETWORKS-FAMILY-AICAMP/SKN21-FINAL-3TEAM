/**
 * 문서 API : 목록 조회, 상세 보기, 파일 업로드 (Multipart), 삭제(팀원 E 담당)
 */
import client from './client'

// ── 문서 CRUD ──

export const listDocuments = (params) =>
  client.get('/documents/', { params })

export const getDocument = (id) =>
  client.get(`/documents/${id}`)

export const uploadDocument = (file, scope) => {
  const formData = new FormData()
  formData.append('file', file)
  return client.post(`/documents/upload?scope=${scope}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const deleteDocument = (id) =>
  client.delete(`/documents/${id}`)

export const analyzeAllDocuments = () =>
  client.post('/documents/analyze-all')

// ── 문서 생성 ──

export const generateDocument = (data) =>
  client.post('/documents/generate', data)

export const downloadDocument = (id, format = 'docx') =>
  client.get(`/documents/${id}/download`, {
    params: { format },
    responseType: 'blob',
  })

// ── 템플릿 관리 ──

export const listTemplates = (params) =>
  client.get('/documents/templates/', { params })

export const getTemplate = (id) =>
  client.get(`/documents/templates/${id}`)

export const uploadTemplate = (file, metadata) => {
  const formData = new FormData()
  formData.append('file', file)
  const params = new URLSearchParams()
  params.append('name', metadata.name)
  if (metadata.description) params.append('description', metadata.description)
  if (metadata.category) params.append('category', metadata.category)
  if (metadata.scope) params.append('scope', metadata.scope)
  return client.post(`/documents/templates/upload?${params.toString()}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const deleteTemplate = (id) =>
  client.delete(`/documents/templates/${id}`)
