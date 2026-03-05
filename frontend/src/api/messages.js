import client from './client';

export const listMessages = (box = 'inbox') =>
  client.get('/messages/', { params: { box } }).then(r => r.data);

export const getUnreadCount = () =>
  client.get('/messages/unread-count').then(r => r.data.unread_count);

export const sendMessage = (receiverId, content) =>
  client.post('/messages/', { receiver_id: receiverId, content }).then(r => r.data);

export const markAsRead = (id) =>
  client.put(`/messages/${id}/read`).then(r => r.data);

export const deleteMessage = (id) =>
  client.delete(`/messages/${id}`).then(r => r.data);
