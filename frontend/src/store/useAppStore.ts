import { create } from 'zustand'
import type { View } from '../types'

interface AppState {
  view: View
  currentProjectId: number | null
  currentExecutionId: number | null
  settingsPanelOpen: boolean

  openProject: (id: number) => void
  goBack: () => void
  showDashboard: () => void
  setExecutionId: (id: number | null) => void
  toggleSettings: () => void
  closeSettings: () => void
}

export const useAppStore = create<AppState>((set) => ({
  view: 'proyectos',
  currentProjectId: null,
  currentExecutionId: null,
  settingsPanelOpen: false,

  openProject: (id) => set({ view: 'proyecto', currentProjectId: id, currentExecutionId: null }),
  goBack: () => set({ view: 'proyectos', currentProjectId: null, currentExecutionId: null }),
  showDashboard: () => set({ view: 'dashboard' }),
  setExecutionId: (id) => set({ currentExecutionId: id }),
  toggleSettings: () => set((s) => ({ settingsPanelOpen: !s.settingsPanelOpen })),
  closeSettings: () => set({ settingsPanelOpen: false }),
}))
