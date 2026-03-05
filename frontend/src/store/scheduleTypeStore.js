import { create } from 'zustand';

const STORAGE_KEY = 'schedule-custom-types';

export const DEFAULT_TYPES = [
  { id: 'meeting', label: '회의', color: '#6E87A0', isDefault: true },
  { id: 'deadline', label: '마감일', color: '#C06060', isDefault: true },
  { id: 'project', label: '프로젝트', color: '#7C6BC4', isDefault: true },
  { id: 'google', label: '개인 일정', color: '#5B9A6F', isDefault: true },
];

function loadCustomTypes() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved ? JSON.parse(saved) : [];
  } catch {
    return [];
  }
}

const useScheduleTypeStore = create((set, get) => ({
  customTypes: loadCustomTypes(),

  addType: (label, color, calendarId = null) => {
    const id = `custom_${Date.now()}`;
    const updated = [...get().customTypes, { id, label, color, calendarId, isDefault: false }];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    set({ customTypes: updated });
  },

  removeType: (id) => {
    const updated = get().customTypes.filter((t) => t.id !== id);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    set({ customTypes: updated });
  },
}));

export default useScheduleTypeStore;
