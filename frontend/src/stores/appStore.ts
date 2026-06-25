import { create } from 'zustand';

interface AppState {
  currentProject: string | null;
  theme: 'light' | 'dark';
  user: {
    name: string;
    avatar: string;
    email: string;
  } | null;
  sidebarCollapsed: boolean;
  setCurrentProject: (project: string | null) => void;
  setTheme: (theme: 'light' | 'dark') => void;
  setUser: (user: AppState['user']) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  currentProject: null,
  theme: 'light',
  user: {
    name: 'Studio User',
    avatar: '',
    email: 'user@studio.local',
  },
  sidebarCollapsed: false,
  setCurrentProject: (project) => set({ currentProject: project }),
  setTheme: (theme) => set({ theme }),
  setUser: (user) => set({ user }),
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
}));
