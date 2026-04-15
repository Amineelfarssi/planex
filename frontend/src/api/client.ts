import axios from 'axios'
import type { SessionSummary, PlanState, KBStats, KBSearchResult } from '../types'

// Derive API base from page origin — works behind reverse proxies (e.g. SageMaker Studio)
// Page URL like https://host/jupyter/default/proxy/8000/ → apiBase = /jupyter/default/proxy/8000/api
const _pathBase = window.location.pathname.replace(/\/+$/, '')
const apiBase = _pathBase + '/api'

const api = axios.create({ baseURL: apiBase })

export const fetchStatus = () => api.get('/status').then(r => r.data)
export const fetchSessions = () => api.get<SessionSummary[]>('/reports').then(r => r.data)
export const fetchSession = (id: string) => api.get<PlanState>(`/reports/${id}`).then(r => r.data)
export const fetchKBStats = () => api.get<KBStats>('/knowledge/stats').then(r => r.data)

export const searchKB = (query: string, topK = 5) =>
  api.post<KBSearchResult[]>('/knowledge/search', null, { params: { query, top_k: topK } }).then(r => r.data)

export const uploadFile = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/upload', form).then(r => r.data)
}

export const ingestPath = (path: string) =>
  api.post('/ingest', { path }).then(r => r.data)

export const chat = (messages: { role: string; content: string }[], researchId?: string) =>
  api.post('/chat', { messages, research_id: researchId }).then(r => r.data)

// ---------------------------------------------------------------------------
// Unified turn — AG-UI event stream
// ---------------------------------------------------------------------------

export interface AGUIEvent {
  type: string
  [key: string]: any
}

export const sendTurn = async (
  message: string,
  chatHistory: { role: string; content: string }[],
  sessionId: string | undefined,
  onEvent: (event: AGUIEvent) => void,
): Promise<void> => {
  const resp = await fetch(apiBase + '/turn', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, chat_history: chatHistory, session_id: sessionId }),
  })

  const reader = resp.body?.getReader()
  if (!reader) return

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      try {
        const event = JSON.parse(line.slice(6))
        onEvent(event)
      } catch {}
    }
  }
}

// ---------------------------------------------------------------------------
// Research — plan + execute + synthesize (SSE)
// ---------------------------------------------------------------------------

export const sendResearch = async (
  goal: string,
  onEvent: (event: AGUIEvent) => void,
): Promise<void> => {
  const resp = await fetch(apiBase + '/research', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ goal }),
  })

  const reader = resp.body?.getReader()
  if (!reader) return

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      try {
        const event = JSON.parse(line.slice(6))
        onEvent(event)
      } catch {}
    }
  }
}

// Legacy (kept for backward compat)
export const chatStream = async (
  messages: { role: string; content: string }[],
  researchId: string | undefined,
  onToken: (text: string) => void,
  onRewrite?: (query: string) => void,
): Promise<string> => {
  const resp = await fetch(apiBase + '/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, research_id: researchId }),
  })

  const reader = resp.body?.getReader()
  if (!reader) return ''

  const decoder = new TextDecoder()
  let full = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    const text = decoder.decode(value)
    for (const line of text.split('\n')) {
      if (!line.startsWith('data: ')) continue
      try {
        const data = JSON.parse(line.slice(6))
        if (data.type === 'token') {
          full += data.text
          onToken(data.text)
        } else if (data.type === 'rewrite' && onRewrite) {
          onRewrite(data.query)
        } else if (data.type === 'done') {
          full = data.full
        }
      } catch {}
    }
  }

  return full
}

export const fetchMemory = () => api.get('/status').then(r => r.data.memory as string)

export const ingestUrl = (url: string) =>
  api.post('/ingest-url', { url }).then(r => r.data)

export const ingestText = (text: string, title?: string) =>
  api.post('/ingest-text', { text, title }).then(r => r.data)

export const fetchGreeting = () => api.get('/greeting').then(r => r.data as {
  period: string, name: string, date: string, time: string
})

export const assessGoal = (query: string) =>
  api.post('/assess-goal', null, { params: { query } }).then(r => r.data as {
    is_clear: boolean,
    options: { label: string, description: string, query: string }[]
  })

// ---------------------------------------------------------------------------
// Health + Config (Settings UI)
// ---------------------------------------------------------------------------

export interface HealthStatus {
  status: string
  service: string
  version: string
  provider: string
  provider_name: string
  models: Record<string, string>
  needs_setup: boolean
  auto_detected: { provider: string; reason: string }
}

export interface ConfigData {
  PLANEX_PROVIDER: string
  OPENAI_API_KEY: string
  AWS_REGION: string
  AWS_ACCESS_KEY_ID: string
  AWS_SECRET_ACCESS_KEY: string
  PLANEX_USER_NAME: string
  PLANEX_FAST_MODEL: string
  PLANEX_SMART_MODEL: string
  PLANEX_STRATEGIC_MODEL: string
  PLANEX_EMBEDDING_MODEL: string
  _detected?: { provider: string; reason: string }
}

export interface TestResult {
  ok: boolean
  error?: string
  response?: string
}

export const fetchHealth = () =>
  api.get<HealthStatus>('/health').then(r => r.data)

export const fetchConfig = () =>
  api.get<ConfigData>('/config').then(r => r.data)

export const saveConfig = (config: Partial<ConfigData>) =>
  api.post<HealthStatus>('/config', config).then(r => r.data)

export const testConfig = (data: { provider: string } & Record<string, string>) =>
  api.post<TestResult>('/config/test', data).then(r => r.data)
