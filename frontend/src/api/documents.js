/**
 * 문서 API (팀원 E 담당)
 */
import client from './client'

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
