export interface Task {
  id: string
  title: string
  description: string
  tool_hint: string
  depends_on: string[]
  status: 'pending' | 'in_progress' | 'completed' | 'failed'
  result_summary: string
  started_at: string
  completed_at: string
}

export interface LogEntry {
  timestamp: string
  event_type: string
  task_id: string
  tool_name: string
  input_summary: string
  output_summary: string
  tokens_used: number
  duration_ms: number
}

export interface ChatMessage {
  role: string
  content: string
  timestamp?: string
}

export interface PlanState {
  plan_id: string
  goal: string
  plan_title: string
  tasks: Task[]
  status: string
  created_at: string
  synthesis: string
  chat_history: ChatMessage[]
  memory_extracts: string[]
  logs: LogEntry[]
}

export interface SessionSummary {
  plan_id: string
  goal: string
  status: string
  created_at: string
  task_count: number
}

export interface KBStats {
  documents: number
  chunks: number
  sources: number
  tags: string[]
}

export interface KBSearchResult {
  doc_title: string
  source: string
  source_type: string
  text: string
}

export type View = 'research' | 'knowledge' | 'memory'
