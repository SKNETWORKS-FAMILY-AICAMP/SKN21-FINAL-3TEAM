import client from './client';

export const listApprovals = () => client.get('/approvals/');

export const createApproval = (data, file) => {
  const formData = new FormData();
  formData.append('type', data.type);
  formData.append('title', data.title);
  if (data.detail) formData.append('detail', data.detail);
  if (file) formData.append('file', file);
  return client.post('/approvals/', formData, {
    headers: { 'Content-Type': undefined },
  });
};

export const approveRequest = (id) => client.put(`/approvals/${id}/approve`);
export const rejectRequest = (id) => client.put(`/approvals/${id}/reject`);
export const deleteApproval = (id) => client.delete(`/approvals/${id}`);
export const seedApprovals = () => client.post('/approvals/seed');

export const getApprovalFileUrl = (id) => `/api/v1/approvals/${id}/file`;

export const downloadApprovalFile = async (id, fileName) => {
  const res = await client.get(`/approvals/${id}/file`, { responseType: 'blob' });
  const url = window.URL.createObjectURL(res.data);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName || 'attachment';
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
};

export const getApprovalFileBlobUrl = async (id) => {
  const res = await client.get(`/approvals/${id}/file`, { responseType: 'blob' });
  return window.URL.createObjectURL(res.data);
};
