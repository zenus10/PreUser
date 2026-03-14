import { create } from 'zustand'
import type {
  ProgressData,
  AnalysisData,
  Persona,
  SimulationResult,
  TestReport,
  ProjectInfo,
} from '../api/types'
import * as api from '../api/client'

interface ProjectState {
  /* Current project */
  projectId: string | null
  filename: string | null
  status: string | null

  /* Pipeline progress */
  progress: ProgressData | null

  /* Analysis results */
  analysis: AnalysisData | null
  personas: Persona[]
  simulations: SimulationResult[]
  report: TestReport | null

  /* Project list */
  projects: ProjectInfo[]
  projectsTotal: number

  /* UI state */
  loading: boolean
  error: string | null

  /* Actions */
  setProject: (id: string, filename: string) => void
  loadProject: (project: ProjectInfo) => void
  setProgress: (p: ProgressData) => void
  fetchProgress: () => Promise<void>
  fetchAnalysis: () => Promise<void>
  fetchPersonas: () => Promise<void>
  fetchSimulations: () => Promise<void>
  fetchReport: () => Promise<void>
  fetchProjects: () => Promise<void>
  reset: () => void
}

const initialState = {
  projectId: null,
  filename: null,
  status: null,
  progress: null,
  analysis: null,
  personas: [],
  simulations: [],
  report: null,
  projects: [],
  projectsTotal: 0,
  loading: false,
  error: null,
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  ...initialState,

  setProject: (id, filename) => set({ projectId: id, filename, status: 'parsing', error: null }),

  loadProject: (project) =>
    set({
      projectId: project.id,
      filename: project.filename,
      status: project.status,
      error: null,
      // Reset analysis data — will be fetched fresh
      analysis: null,
      personas: [],
      simulations: [],
      report: null,
      progress: null,
    }),

  setProgress: (p) => set({ progress: p, status: p.stage }),

  fetchProgress: async () => {
    const { projectId } = get()
    if (!projectId) return
    try {
      const p = await api.getProgress(projectId)
      set({ progress: p, status: p.stage })
    } catch {
      /* silent - will retry */
    }
  },

  fetchAnalysis: async () => {
    const { projectId } = get()
    if (!projectId) return
    set({ loading: true, error: null })
    try {
      const data = await api.getAnalysis(projectId)
      set({
        analysis: data,
        status: data.status || 'completed',
        personas: data.personas?.personas ?? [],
        simulations: data.simulations ?? [],
        report: data.report ?? null,
        loading: false,
      })
    } catch (e: any) {
      set({ error: e.message, loading: false })
    }
  },

  fetchPersonas: async () => {
    const { projectId } = get()
    if (!projectId) return
    try {
      const data = await api.getPersonas(projectId)
      set({ personas: data.personas ?? [] })
    } catch { /* not ready yet */ }
  },

  fetchSimulations: async () => {
    const { projectId } = get()
    if (!projectId) return
    try {
      const data = await api.getSimulations(projectId)
      set({ simulations: Array.isArray(data) ? data : [] })
    } catch { /* not ready yet */ }
  },

  fetchReport: async () => {
    const { projectId } = get()
    if (!projectId) return
    try {
      const data = await api.getReport(projectId)
      set({ report: data })
    } catch { /* not ready yet */ }
  },

  fetchProjects: async () => {
    try {
      const { items, total } = await api.listProjects()
      set({ projects: items, projectsTotal: total })
    } catch { /* silent */ }
  },

  reset: () => set(initialState),
}))
