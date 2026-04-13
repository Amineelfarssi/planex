import { useState, useEffect, useRef } from 'react'
import { useAppStore } from '../../stores/appStore'
import { fetchSession, fetchSessions, chat, chatStream, sendTurn, sendResearch, fetchGreeting, assessGoal } from '../../api/client'
import type { AGUIEvent } from '../../api/client'
import { PlanView } from './PlanView'
import { LogViewer } from './LogViewer'
import { Synthesis } from './Synthesis'
import { ClarificationCards } from './ClarificationCards'
import { Markdown } from '../common/Markdown'
import { Search, Send, Loader, RefreshCw, MessageSquare, User, Bot, BookOpen, FileText, Globe, Sparkles, Compass } from 'lucide-react'
import { CopyButton } from '../common/CopyButton'
import type { PlanState } from '../../types'

const ACTIVE_SESSION_KEY = 'planex_active_session'

export function ResearchView() {
  const { selectedSession, setSelectedSession, setSessions, setDocPanelOpen } = useAppStore()
  const [goal, setGoal] = useState('')
  const [loading, setLoading] = useState(false)
  const [wsLogs, setWsLogs] = useState<{type: string, content: string, output: string, tasks?: any[], plan_title?: string, goal?: string, plan_id?: string, status?: string}[]>([])
  const [synthesis, setSynthesis] = useState('')
  const [activePlanId, setActivePlanId] = useState<string | null>(null)

  // Time-aware greeting
  const [greeting, setGreeting] = useState({ period: '', name: '', date: '', time: '' })
  useEffect(() => {
    fetchGreeting().then(setGreeting).catch(() => {})
  }, [])

  // Follow-up chat — loaded from session, persisted via API
  // Clarification cards
  const [clarifications, setClarifications] = useState<{label: string, description: string, query: string}[] | null>(null)

  const [chatMessages, setChatMessages] = useState<{role: string, content: string}[]>([])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Restore last active session on mount
  useEffect(() => {
    const savedId = localStorage.getItem(ACTIVE_SESSION_KEY)
    if (savedId && !selectedSession) {
      fetchSession(savedId)
        .then(session => {
          if (session?.plan_id) setSelectedSession(session)
        })
        .catch(() => {})
    }
  }, [])

  // Load chat history from session when switching
  // Don't clear synthesis if we just finished a live research (reloadAfterResearch sets the session)
  // justFinishedRef removed — prevPlanIdRef handles session switch detection

  const prevPlanIdRef = useRef<string | null>(null)

  useEffect(() => {
    if (selectedSession?.chat_history) {
      setChatMessages(
        selectedSession.chat_history.map(m => ({ role: m.role, content: m.content }))
      )
    } else {
      setChatMessages([])
    }
    setChatInput('')

    // Only clear live state on USER-initiated session switch (clicking a different session)
    const isNewSession = prevPlanIdRef.current !== null && prevPlanIdRef.current !== selectedSession?.plan_id
    prevPlanIdRef.current = selectedSession?.plan_id || null

    if (isNewSession) {
      setWsLogs([])
      setSynthesis('')
      setToolActivity([])
    }
  }, [selectedSession?.plan_id])

  const startResearch = async (overrideGoal?: string) => {
    const query = overrideGoal || goal
    if (!query.trim() || loading) return

    // LLM decides if the goal needs clarification
    // Skip if: user picked a card (overrideGoal), or user clicked "Search as-is" (dismiss=true)
    if (!overrideGoal) {
      try {
        setLoading(true)
        const result = await assessGoal(query)
        if (!result.is_clear && result.options?.length > 1) {
          setClarifications(result.options)
          setLoading(false)
          return // Show cards, user picks a direction or edits query
        }
      } catch {} finally {
        setLoading(false)
      }
    }

    setClarifications(null)
    setLoading(true)
    setWsLogs([])
    setSynthesis('')
    setChatMessages([])
    setSelectedSession(null)
    if (overrideGoal) setGoal(overrideGoal)

    try {
      await sendResearch(query, (event: AGUIEvent) => {
        try { switch (event.type) {
          case 'STATE_SNAPSHOT': {
            // Data is under event.snapshot (wrapped by SSE layer)
            const snap = event.snapshot || event
            if (snap?.tasks) {
              setWsLogs(prev => {
                const taskLog = {
                  type: 'plan', content: '', output: '',
                  tasks: snap.tasks,
                  plan_title: snap.plan_title || prev.find((l: any) => l.type === 'plan')?.plan_title,
                  goal: snap.goal || prev.find((l: any) => l.type === 'plan')?.goal,
                  plan_id: snap.plan_id || prev.find((l: any) => l.type === 'plan')?.plan_id,
                  status: snap.status,
                }
                const idx = prev.findIndex(l => l.type === 'plan')
                if (idx >= 0) {
                  const updated = [...prev]
                  updated[idx] = taskLog
                  return updated
                }
                return [...prev, taskLog]
              })
            }
            if (snap?.status === 'completed' && snap?.plan_id) {
              setLoading(false)
              setActivePlanId(snap.plan_id)
              localStorage.setItem(ACTIVE_SESSION_KEY, snap.plan_id)
              // Reload session in background — don't clear live state
              fetchSession(snap.plan_id).then(session => {
                if (session?.plan_id) {
                  setSelectedSession(session)
                  setDocPanelOpen(true)
                  // Refresh sidebar
                  fetchSessions().then(s => {
                    s.sort((a: any, b: any) => (b.created_at || '').localeCompare(a.created_at || ''))
                    setSessions(s)
                  }).catch(() => {})
                }
              }).catch(() => {})
            }
            break
          }

          case 'TOOL_CALL_START':
            setToolActivity(prev => [...prev, { name: event.toolName || '?' }])
            break

          case 'TOOL_CALL_ARGS':
            setToolActivity(prev => {
              try {
                const updated = [...prev]
                if (updated.length > 0) {
                  let args: any = {}
                  try { args = typeof event.args === 'string' ? JSON.parse(event.args) : (event.args || {}) } catch { args = {} }
                  const summary = args.task || args.query || args.description || ''
                  updated[updated.length - 1].summary = String(summary).slice(0, 80)
                }
                return updated
              } catch { return prev }
            })
            break

          case 'TOOL_CALL_END':
            // Keep activity visible
            break

          case 'TOOL_CALL_RESULT':
            setToolActivity(prev => {
              const updated = [...prev]
              if (updated.length > 0) {
                const last = updated[updated.length - 1]
                if (!last.summary) last.summary = String(event.content || '').slice(0, 100)
              }
              return updated
            })
            break

          case 'TEXT_MESSAGE_CONTENT':
            setSynthesis(prev => prev + (event.delta || ''))
            break

          case 'STEP_STARTED':
            setWsLogs(prev => [...prev, { type: 'logs', content: `${event.name || event.stepId}...`, output: '' }])
            break

          case 'STEP_FINISHED':
            break

          case 'RUN_FINISHED':
            setLoading(false)
            setToolActivity([])
            break
        } } catch (e) { console.error('Event handler error:', e) }
      })
    } catch {
      setLoading(false)
    }
  }

  const reloadAfterResearch = async () => {
    try {
      const sessions = await fetchSessions()
      // Sort descending by created_at so newest is first
      sessions.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
      setSessions(sessions)
      if (sessions.length > 0) {
        const latest = sessions[0] // newest session
        const session = await fetchSession(latest.plan_id)
        if (session?.plan_id) {
          setSelectedSession(session)
          setActivePlanId(session.plan_id)
          localStorage.setItem(ACTIVE_SESSION_KEY, session.plan_id)
        }
      }
    } catch {}
  }

  // Listen for choice card clicks (dispatched from ChoiceCards component)
  useEffect(() => {
    const handler = (e: Event) => {
      const value = (e as CustomEvent).detail
      if (value && typeof value === 'string') {
        setChatInput(value)
        // Auto-send after a tick
        setTimeout(() => {
          const input = document.querySelector('[placeholder*="follow-up"]') as HTMLInputElement
          if (input) {
            input.value = value
            const event = new KeyboardEvent('keydown', { key: 'Enter' })
            input.dispatchEvent(event)
          }
          // Direct send
          sendFollowUpDirect(value)
        }, 100)
      }
    }
    window.addEventListener('planex:choice', handler)
    return () => window.removeEventListener('planex:choice', handler)
  }, [chatMessages, selectedSession, activePlanId])

  const sendFollowUpDirect = async (text: string) => {
    setChatInput(text)
    setTimeout(() => {
      setChatInput('')
      // Reuse the main sendFollowUp by setting input and triggering
      const input = document.querySelector('[placeholder*="follow-up"]') as HTMLInputElement
      if (input) {
        // Set the value and trigger send
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set?.call(input, text)
        input.dispatchEvent(new Event('input', { bubbles: true }))
      }
    }, 50)
  }

  // Tool activity feed — shows what the agent is doing in real-time
  const [toolActivity, setToolActivity] = useState<{name: string, summary?: string}[]>([])

  const sendFollowUp = async () => {
    if (!chatInput.trim() || chatLoading) return
    const userMsg = { role: 'user', content: chatInput }
    setChatMessages(prev => [...prev, userMsg])
    setChatInput('')
    setChatLoading(true)
    setToolActivity([])

    // Add empty assistant message that will stream in
    setChatMessages(prev => [...prev, { role: 'assistant', content: '' } as any])

    try {
      const planId = selectedSession?.plan_id || activePlanId

      await sendTurn(
        chatInput,
        chatMessages.map(m => ({ role: m.role, content: m.content })),
        planId || undefined,
        // AG-UI event handler
        (event: AGUIEvent) => {
          switch (event.type) {
            case 'custom':
              if (event.name === 'rewrite') {
                setChatMessages(prev => {
                  const updated = [...prev]
                  const last = updated[updated.length - 1]
                  if (last?.role === 'assistant') (updated[updated.length - 1] as any).rewritten = event.value
                  return updated
                })
              } else if (event.name === 'tool_result') {
                setToolActivity(prev => {
                  const updated = [...prev]
                  if (updated.length > 0) updated[updated.length - 1].summary = event.value?.summary
                  return updated
                })
              }
              break

            case 'TOOL_CALL_START':
              setToolActivity(prev => [...prev, { name: event.toolCallName || event.toolName || '?' }])
              break

            case 'TOOL_CALL_ARGS':
              setToolActivity(prev => {
                try {
                  const updated = [...prev]
                  if (updated.length > 0) {
                    let args: any = {}
                    try { args = event.args ? JSON.parse(event.args) : {} } catch { args = {} }
                    const summary = args.query || args.task || args.description || ''
                    updated[updated.length - 1].summary = String(summary).slice(0, 80)
                  }
                  return updated
                } catch { return prev }
              })
              break

            case 'TOOL_CALL_RESULT':
              setToolActivity(prev => {
                const updated = [...prev]
                const idx = updated.findIndex(t => !t.summary)
                if (idx >= 0) updated[idx].summary = String(event.content || '').slice(0, 100)
                else if (updated.length > 0) updated[updated.length - 1].summary = String(event.content || '').slice(0, 100)
                return updated
              })
              break

            case 'TEXT_MESSAGE_CONTENT':
              setChatMessages(prev => {
                const updated = [...prev]
                const last = updated[updated.length - 1]
                if (last?.role === 'assistant') {
                  updated[updated.length - 1] = { ...last, content: last.content + event.delta }
                }
                return updated
              })
              break

            case 'RUN_FINISHED':
              setChatLoading(false)
              setToolActivity([])
              break
          }
        },
      )
    } catch {
      setChatMessages(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = { role: 'assistant', content: 'Error connecting to backend.' }
        return updated
      })
    }
    setChatLoading(false)
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 100)
  }

  const resumeSession = async () => {
    if (!selectedSession) return
    // Resume by re-running the same goal
    setGoal(selectedSession.goal)
    startResearch(selectedSession.goal)
  }

  // Determine what to show
  const plan = selectedSession
  const livePlan = wsLogs.find(l => l.type === 'plan') as any
  const logs = wsLogs.filter(m => m.type === 'logs')
  const hasPendingTasks = plan?.tasks.some(t => t.status === 'pending')
  const hasLiveResults = synthesis || logs.length > 0 || livePlan

  const showHero = !plan && !hasLiveResults && !loading

  // Quick action suggestions
  const suggestions = [
    { icon: Globe, label: 'Research', example: 'Latest AI trends in legal tech' },
    { icon: FileText, label: 'Analyze', example: 'Summarize our ingested documents' },
    { icon: Search, label: 'Compare', example: 'Compare RAG vs fine-tuning approaches' },
    { icon: Sparkles, label: 'Deep dive', example: 'How do transformer architectures work?' },
  ]

  return (
    <div className={`max-w-4xl mx-auto pb-32 ${showHero ? 'h-full flex flex-col justify-center px-6' : 'p-6 space-y-6'}`}>

      {/* Hero section — centered, like Claude Desktop */}
      {showHero && (
        <div className="flex flex-col items-center">
          {/* Greeting with animated logo */}
          <div className="flex flex-col items-center mb-8">
            <div className="flex items-center gap-3">
              <svg width="36" height="36" viewBox="0 0 36 36" className="animate-[spin_20s_linear_infinite]">
                {/* Orbital rings — research paths */}
                <circle cx="18" cy="18" r="14" fill="none" stroke="#DA7756" strokeWidth="1" opacity="0.3" />
                <circle cx="18" cy="18" r="9" fill="none" stroke="#DA7756" strokeWidth="1" opacity="0.2" />
                {/* Core — knowledge */}
                <circle cx="18" cy="18" r="4" fill="#DA7756" opacity="0.8" />
                {/* Orbiting dots — active research */}
                <circle cx="18" cy="4" r="2" fill="#DA7756" opacity="0.9" />
                <circle cx="30" cy="22" r="1.5" fill="#DA7756" opacity="0.6" />
                <circle cx="8" cy="25" r="1.5" fill="#DA7756" opacity="0.4" />
              </svg>
              <h1 className="text-3xl font-light">
                {greeting.period
                  ? `${greeting.period.charAt(0).toUpperCase() + greeting.period.slice(1)}${greeting.name ? `, ${greeting.name}` : ''}`
                  : '\u00A0'
                }
              </h1>
            </div>
            <p className="text-base text-gray-400 dark:text-planex-dimmed mt-2">
              What would you like to research?
            </p>
            {useAppStore.getState().kbStats.chunks > 0 && (
              <p className="text-xs text-gray-400/60 dark:text-planex-dimmed/60 mt-1">
                {useAppStore.getState().kbStats.chunks} sources in your knowledge base
              </p>
            )}
          </div>

          {/* Input box — Claude Desktop style */}
          <div className="w-full max-w-2xl">
            <div className="bg-white dark:bg-planex-panel border border-gray-200 dark:border-planex-border rounded-2xl p-1 shadow-sm">
              <textarea
                value={goal}
                onChange={e => setGoal(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); startResearch() }
                }}
                placeholder="How can I help you today?"
                rows={2}
                className="w-full bg-transparent px-4 py-3 text-base text-gray-800 dark:text-gray-200 placeholder-gray-400 dark:placeholder-planex-dimmed focus:outline-none resize-none"
                disabled={loading}
              />
              <div className="flex items-center justify-between px-3 pb-2">
                <div className="flex items-center gap-2 text-xs text-gray-400 dark:text-planex-dimmed">
                  <span>{greeting.date ? `${greeting.date}` : ''}</span>
                </div>
                <button
                  onClick={() => startResearch()}
                  disabled={loading || !goal.trim()}
                  className="flex items-center gap-2 px-4 py-2 bg-planex-coral text-white rounded-lg text-sm font-medium hover:bg-planex-coral/90 disabled:opacity-40 transition-colors"
                >
                  {loading ? <Loader className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                  Research
                </button>
              </div>
            </div>
          </div>

          {/* Suggestion chips */}
          <div className="flex gap-2 mt-5 flex-wrap justify-center">
            {suggestions.map(({ icon: Icon, label, example }) => (
              <button
                key={label}
                onClick={() => setGoal(example)}
                className="flex items-center gap-2 px-4 py-2 bg-white dark:bg-planex-panel border border-gray-200 dark:border-planex-border rounded-full text-sm text-gray-500 dark:text-planex-dimmed hover:text-gray-800 dark:hover:text-gray-200 hover:border-gray-300 dark:hover:border-planex-dimmed transition-colors"
              >
                <Icon className="w-4 h-4" />
                {label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Compact input — shown when there's an active session */}
      {!showHero && (
        <div>
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-3 w-4 h-4 text-gray-400 dark:text-planex-dimmed" />
              <input
                type="text"
                value={goal}
                onChange={e => setGoal(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && startResearch()}
                placeholder="New research goal..."
                className="w-full pl-9 pr-3 py-2.5 bg-white dark:bg-planex-panel border border-gray-200 dark:border-planex-border rounded-lg text-sm focus:outline-none focus:border-planex-cyan"
                disabled={loading}
              />
            </div>
            <button
              onClick={() => startResearch()}
              disabled={loading || !goal.trim()}
              className="flex items-center gap-2 px-4 py-2.5 bg-planex-coral/20 text-planex-coral rounded-lg text-sm hover:bg-planex-coral/30 disabled:opacity-40"
            >
              {loading ? <Loader className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              Research
            </button>
          </div>
        </div>
      )}

      {/* Clarification cards — shown when query is ambiguous */}
      {clarifications && (
        <ClarificationCards
          question="What would you like to research?"
          options={clarifications}
          onSelect={(query) => {
            setClarifications(null)
            startResearch(query)
          }}
          onDismiss={() => {
            setClarifications(null)
            startResearch(goal) // pass as override to skip assessment
          }}
        />
      )}

      {/* Live plan — during active research (before session is saved) */}
      {!plan && livePlan && (
        <div>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold">{livePlan.plan_title || 'Researching...'}</h1>
              <p className="text-sm text-gray-400 dark:text-planex-dimmed mt-1">{livePlan.goal || goal}</p>
            </div>
            <span className="text-xs px-2 py-0.5 rounded bg-yellow-500/20 text-yellow-400">
              {loading ? 'in progress' : livePlan.status || 'planning'}
            </span>
          </div>
          {livePlan.tasks && (
            <div className="mt-4">
              <PlanView tasks={livePlan.tasks} />
            </div>
          )}
        </div>
      )}

      {/* Selected/active session */}
      {plan && (
        <div>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold">{plan.plan_title}</h1>
              <p className="text-sm text-planex-dimmed mt-1">{plan.goal}</p>
            </div>
            <div className="flex items-center gap-2">
              <span className={`text-xs px-2 py-0.5 rounded ${
                plan.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                plan.status === 'failed' ? 'bg-red-500/20 text-red-400' :
                'bg-yellow-500/20 text-yellow-400'
              }`}>{plan.status}</span>
              {hasPendingTasks && (
                <button
                  onClick={resumeSession}
                  disabled={loading}
                  className="flex items-center gap-1 px-3 py-1 bg-planex-cyan/20 text-planex-cyan rounded text-xs hover:bg-planex-cyan/30"
                >
                  <RefreshCw className="w-3 h-3" /> Resume
                </button>
              )}
            </div>
          </div>

          <div className="mt-4">
            <PlanView tasks={plan.tasks} />
          </div>
        </div>
      )}

      {/* Live execution logs */}
      {logs.length > 0 && (
        <div className="space-y-1 bg-planex-panel rounded-lg p-4 border border-planex-border">
          <h3 className="text-sm font-medium text-planex-dimmed mb-2">Live Execution</h3>
          {logs.map((log, i) => (
            <div key={i} className="flex items-start gap-2 text-xs font-mono">
              <span className="text-planex-coral shrink-0">●</span>
              <span className="text-gray-300">{log.content}</span>
              {log.output && <span className="text-planex-dimmed">{log.output}</span>}
            </div>
          ))}
          {loading && (
            <div className="flex items-center gap-2 text-xs text-planex-coral animate-pulse mt-2">
              <Loader className="w-3 h-3 animate-spin" /> Working...
            </div>
          )}
        </div>
      )}

      {/* Synthesis from live research */}
      {synthesis && <Synthesis content={synthesis} />}

      {/* Synthesis from loaded session (use saved synthesis, not task summaries) */}
      {!synthesis && plan?.synthesis && (
        <Synthesis content={plan.synthesis} />
      )}

      {/* Execution logs from loaded session */}
      {plan?.logs && plan.logs.length > 0 && <LogViewer logs={plan.logs} />}

      {/* Follow-up chat — connected to the active session */}
      {(plan || synthesis) && (
        <div className="border-t border-gray-200 dark:border-planex-border pt-4">
          <div className="flex items-center gap-2 mb-3">
            <MessageSquare className="w-4 h-4 text-planex-coral" />
            <h3 className="text-sm font-medium">Follow-up Questions</h3>
            <span className="text-[10px] text-planex-dimmed">
              (context-aware — knows about this research)
            </span>
          </div>

          {chatMessages.map((m: any, i: number) => (
            <div key={i} className="mb-4 flex items-start gap-3 group">
              {/* Avatar */}
              <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-0.5 ${
                m.role === 'user' ? 'bg-planex-cyan/20' : 'bg-planex-coral/20'
              }`}>
                {m.role === 'user'
                  ? <User className="w-4 h-4 text-planex-cyan" />
                  : <Bot className="w-4 h-4 text-planex-coral" />
                }
              </div>
              {/* Message */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-medium ${
                    m.role === 'user' ? 'text-planex-cyan' : 'text-planex-coral'
                  }`}>
                    {m.role === 'user' ? 'You' : 'Planex'}
                  </span>
                  {/* Copy button — appears on hover */}
                  {m.content && <CopyButton text={m.content} />}
                </div>
                {/* Rewritten query hint */}
                {m.rewritten && (
                  <details className="mt-1">
                    <summary className="text-[10px] text-gray-400 dark:text-planex-dimmed cursor-pointer hover:text-gray-500">
                      Interpreted query
                    </summary>
                    <p className="text-xs text-gray-400 dark:text-planex-dimmed italic mt-0.5">
                      {m.rewritten}
                    </p>
                  </details>
                )}
                {m.role === 'user' ? (
                  <p className="text-sm text-gray-800 dark:text-gray-200 mt-1">{m.content}</p>
                ) : (
                  <div className="mt-1">
                    <Markdown content={m.content} />
                  </div>
                )}
              </div>
            </div>
          ))}
          {/* Tool activity feed — shows what the agent is doing */}
          {toolActivity.length > 0 && (
            <div className="mb-3 space-y-1">
              {toolActivity.map((t, i) => (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span className="text-planex-cyan">⎿</span>
                  <span className="font-medium text-planex-cyan">{t.name}</span>
                  {t.summary && <span className="text-gray-400 dark:text-planex-dimmed truncate">{t.summary}</span>}
                  {!t.summary && i === toolActivity.length - 1 && <span className="text-planex-coral animate-pulse">...</span>}
                </div>
              ))}
            </div>
          )}
          {chatLoading && toolActivity.length === 0 && (
            <div className="text-planex-coral text-sm animate-pulse mb-2">● Thinking...</div>
          )}

          <div className="flex gap-2 mt-2">
            <input
              type="text"
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && sendFollowUp()}
              placeholder="Ask a follow-up question about this research..."
              className="flex-1 bg-white dark:bg-planex-panel border border-gray-200 dark:border-planex-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-planex-cyan"
            />
            <button
              onClick={sendFollowUp}
              disabled={chatLoading || !chatInput.trim()}
              className="p-2 text-planex-cyan hover:text-white disabled:opacity-40"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
          <div ref={bottomRef} />
        </div>
      )}

      {/* Hero handles empty state now */}
    </div>
  )
}
