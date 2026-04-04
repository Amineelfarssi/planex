import { create } from 'zustand'
import type { View, SessionSummary, KBStats, PlanState, Task } from '../types'

interface AppState {
  theme: 'dark' | 'light'
  toggleTheme: () => void

  view: View
  setView: (v: View) => void

  sessions: SessionSummary[]
  setSessions: (s: SessionSummary[]) => void

  selectedSession: PlanState | null
  setSelectedSession: (s: PlanState | null) => void

  kbStats: KBStats
  setKBStats: (s: KBStats) => void

  // Live research state (from CopilotKit agent state)
  activePlan: { title: string; tasks: Task[] } | null
  setActivePlan: (p: { title: string; tasks: Task[] } | null) => void

  currentStep: string
  setCurrentStep: (s: string) => void

  totalTokens: number
  setTotalTokens: (n: number) => void

  docPanelOpen: boolean
  setDocPanelOpen: (open: boolean) => void
}

export const useAppStore = create<AppState>((set) => ({
  theme: (localStorage.getItem('planex_theme') as 'dark' | 'light') || 'dark',
  toggleTheme: () => set((s) => {
    const next = s.theme === 'dark' ? 'light' : 'dark'
    localStorage.setItem('planex_theme', next)
    return { theme: next }
  }),

  view: 'research',
  setView: (view) => set({ view }),

  sessions: [],
  setSessions: (sessions) => set({ sessions }),

  selectedSession: null,
  setSelectedSession: (selectedSession) => set({ selectedSession }),

  kbStats: { documents: 0, chunks: 0, sources: 0, tags: [] },
  setKBStats: (kbStats) => set({ kbStats }),

  activePlan: null,
  setActivePlan: (activePlan) => set({ activePlan }),

  currentStep: '',
  setCurrentStep: (currentStep) => set({ currentStep }),

  totalTokens: 0,
  setTotalTokens: (totalTokens) => set({ totalTokens }),

  docPanelOpen: false,
  setDocPanelOpen: (docPanelOpen) => set({ docPanelOpen }),
}))
