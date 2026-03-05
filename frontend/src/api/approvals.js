import client from './client';

export const listApprovals = () => client.get('/approvals/');
export const createApproval = (data) => client.post('/approvals/', data);
export const approveRequest = (id) => client.put(`/approvals/${id}/approve`);
export const rejectRequest = (id) => client.put(`/approvals/${id}/reject`);
export const seedApprovals = () => client.post('/approvals/seed');
