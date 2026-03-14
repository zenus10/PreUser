import axios from 'axios'
import type {
  UploadResponse,
  ProgressData,
  ProjectInfo,
  AnalysisData,
  Persona,
  SimulationResult,
  TestReport,
  ConversationMessage,
  ConversationInfo,
  ActionLogRecord,
} from './types'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,
})

export async function uploadFile(
  file: File,
  context?: Record<string, string>,
): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  if (context) {
    form.append('context', JSON.stringify(context))
  }
  const { data } = await api.post<UploadResponse>('/upload', form)
  return data
}

export async function listProjects(
  skip = 0,
  limit = 20,
): Promise<{ items: ProjectInfo[]; total: number }> {
  const { data } = await api.get('/projects', { params: { skip, limit } })
  return data
}

export async function getProject(projectId: string): Promise<ProjectInfo> {
  const { data } = await api.get<ProjectInfo>(`/projects/${projectId}`)
  return data
}

export async function getProgress(projectId: string): Promise<ProgressData> {
  const { data } = await api.get<ProgressData>(`/progress/${projectId}`)
  return data
}

export async function getAnalysis(projectId: string): Promise<AnalysisData> {
  const { data } = await api.get<AnalysisData>(`/analysis/${projectId}`)
  return data
}

export async function getPersonas(projectId: string): Promise<{ personas: Persona[] }> {
  const { data } = await api.get(`/analysis/${projectId}/personas`)
  return data
}

export async function getSimulations(projectId: string): Promise<SimulationResult[]> {
  const { data } = await api.get(`/analysis/${projectId}/simulations`)
  return data
}

export async function getReport(projectId: string): Promise<TestReport> {
  const { data } = await api.get(`/analysis/${projectId}/report`)
  return data
}

// --- v2.0 Conversation APIs ---

export async function startConversation(
  analysisId: string,
  mode: string,
  personaIds: string[],
  topic?: string,
): Promise<string> {
  const { data } = await api.post('/conversation/start', {
    analysis_id: analysisId,
    mode,
    persona_ids: personaIds,
    topic,
  })
  return data.conversation_id
}

export async function sendMessage(
  conversationId: string,
  content: string,
): Promise<ConversationMessage[]> {
  const { data } = await api.post(`/conversation/${conversationId}/message`, { content })
  return data.messages
}

export async function getConversation(conversationId: string) {
  const { data } = await api.get(`/conversation/${conversationId}`)
  return data
}

export async function listConversations(analysisId: string): Promise<ConversationInfo[]> {
  const { data } = await api.get('/conversations', { params: { analysis_id: analysisId } })
  return data
}

// --- v2.0 Action Logs ---

export async function getActionLogs(
  projectId: string,
  personaId?: string,
  scene?: string,
): Promise<ActionLogRecord[]> {
  const { data } = await api.get(`/analysis/${projectId}/action-logs`, {
    params: { persona_id: personaId, scene },
  })
  return data
}

// --- v2.0 Persona Editing ---

export async function updatePersonas(projectId: string, personas: Persona[]): Promise<void> {
  await api.put(`/analysis/${projectId}/personas`, { personas })
}

export async function generateCustomPersona(
  projectId: string,
  description: string,
): Promise<Persona> {
  const { data } = await api.post(`/analysis/${projectId}/personas/custom`, { description })
  return data
}

export async function triggerSimulation(projectId: string): Promise<void> {
  await api.post(`/analysis/${projectId}/simulate`)
}

// --- v2.0 Retry ---

export async function retryAnalysis(projectId: string): Promise<void> {
  await api.post(`/analysis/${projectId}/retry`)
}
