import { create } from 'zustand';

const useToastStore = create((set, get) => ({
  toasts: [],
  confirm: null, // { message, resolve }

  addToast: (type, message) => {
    const id = Date.now() + Math.random();
    set((s) => ({ toasts: [...s.toasts, { id, type, message }] }));
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
    }, 3500);
  },

  removeToast: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),

  showConfirm: (message) =>
    new Promise((resolve) => {
      set({ confirm: { message, resolve } });
    }),

  resolveConfirm: (result) => {
    const { confirm } = get();
    confirm?.resolve(result);
    set({ confirm: null });
  },
}));

export const toast = {
  success: (message) => useToastStore.getState().addToast('success', message),
  error: (message) => useToastStore.getState().addToast('error', message),
  info: (message) => useToastStore.getState().addToast('info', message),
  warning: (message) => useToastStore.getState().addToast('warning', message),
};

export const confirm = (message) => useToastStore.getState().showConfirm(message);

export default useToastStore;
