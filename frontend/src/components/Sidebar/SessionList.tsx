import { useAppStore } from '../../stores/appStore'
import { fetchSession } from '../../api/client'
import { CheckCircle, Circle, AlertCircle, Loader, Plus } from 'lucide-react'

const STATUS_ICONS = {
  completed: <CheckCircle className="w-3.5 h-3.5 text-green-500" />,
  executing: <Loader className="w-3.5 h-3.5 text-yellow-500 animate-spin" />,
  planning: <Circle className="w-3.5 h-3.5 text-planex-dimmed" />,
  failed: <AlertCircle className="w-3.5 h-3.5 text-red-500" />,
}

export function SessionList() {
  const { sessions, selectedSession, setSelectedSession } = useAppStore()

  const handleNew = () => {
    setSelectedSession(null)
    localStorage.removeItem('planex_active_session')
  }

  const handleClick = async (planId: string) => {
    try {
      const session = await fetchSession(planId)
      if (session && session.plan_id) {
        setSelectedSession(session)
        localStorage.setItem('planex_active_session', session.plan_id)
      }
    } catch (e) {
      console.error('Failed to load session:', e)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="flex items-center justify-between px-3 py-2">
        <span className="text-xs text-planex-dimmed uppercase tracking-wide">Sessions</span>
        <button
          onClick={handleNew}
          className="flex items-center gap-1 px-2 py-1 text-xs text-planex-cyan hover:bg-planex-surface rounded transition-colors"
          title="New research session"
        >
          <Plus className="w-3 h-3" /> New
        </button>
      </div>
      {sessions.length === 0 ? (
        <p className="px-3 text-xs text-planex-dimmed">No sessions yet</p>
      ) : (
        sessions.map(s => (
          <button
            key={s.plan_id}
            onClick={() => handleClick(s.plan_id)}
            className={`w-full text-left px-3 py-2 transition-colors ${
              selectedSession?.plan_id === s.plan_id
                ? 'bg-gray-100 dark:bg-planex-surface'
                : 'hover:bg-gray-50 dark:hover:bg-planex-surface'
            }`}
          >
            <div className="flex items-center gap-2">
              {STATUS_ICONS[s.status as keyof typeof STATUS_ICONS] || STATUS_ICONS.planning}
              <span className="text-sm truncate">{s.goal.slice(0, 45)}</span>
            </div>
            <div className="ml-6 text-[10px] text-planex-dimmed">
              {s.task_count} tasks · {s.plan_id}
            </div>
          </button>
        ))
      )}
    </div>
  )
}
