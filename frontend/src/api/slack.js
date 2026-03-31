import client from './client';

// Slack 연결 상태 조회
export const getSlackStatus = () =>
  client.get('/slack/status');

// Slack 알림 활성화
export const connectSlack = () =>
  client.post('/slack/connect');

// 연결 해제
export const disconnectSlack = () =>
  client.delete('/slack/disconnect');

// 알림 전송
export const sendSlackNotification = (payload) =>
  client.post('/slack/notify', payload);
