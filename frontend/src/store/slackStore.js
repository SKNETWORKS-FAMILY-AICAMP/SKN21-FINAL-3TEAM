import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { getSlackStatus, connectSlack, disconnectSlack, sendSlackNotification } from '../api/slack';

const useSlackStore = create(
  persist(
    (set) => ({
      connected: false,
      loading: false,

      // 앱 초기화 시 백엔드에서 연결 상태 동기화
      fetchStatus: async () => {
        try {
          const res = await getSlackStatus();
          set({ connected: res.data?.connected ?? false });
        } catch {
          set({ connected: false });
        }
      },

      // Slack 알림 활성화
      connect: async () => {
        set({ loading: true });
        try {
          await connectSlack();
          set({ connected: true });
          return true;
        } catch {
          return false;
        } finally {
          set({ loading: false });
        }
      },

      // 연결 해제
      disconnect: async () => {
        set({ loading: true });
        try {
          await disconnectSlack();
          set({ connected: false });
          return true;
        } catch {
          return false;
        } finally {
          set({ loading: false });
        }
      },

    }),
    {
      name: 'slack-store',
      partialize: (s) => ({ connected: s.connected }),
    }
  )
);

export default useSlackStore;
