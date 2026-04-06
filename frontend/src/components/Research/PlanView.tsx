import type { Task } from '../../types'
import { StatusIcon } from '../common/StatusIcon'

export function PlanView({ tasks }: { tasks: Task[] }) {
  return (
    <div className="space-y-1">
      <h2 className="text-sm font-medium text-planex-dimmed uppercase tracking-wide mb-2">Tasks</h2>
      {tasks.map(task => (
        <div
          key={task.id}
          className={`flex items-start gap-3 px-3 py-2 rounded transition-colors ${
            task.status === 'in_progress'
              ? 'bg-yellow-500/5 border border-yellow-500/20'
              : task.status === 'completed'
              ? 'bg-green-500/5'
              : task.status === 'failed'
              ? 'bg-red-500/5'
              : 'bg-white dark:bg-planex-panel'
          }`}
        >
          <StatusIcon status={task.status} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className={`text-sm ${task.status === 'completed' ? 'text-planex-dimmed' : ''}`}>
                {task.title}
              </span>
              {task.tool_hint && (
                <span className="text-[10px] px-1.5 py-0.5 bg-planex-cyan/10 text-planex-cyan rounded">
                  {task.tool_hint}
                </span>
              )}
            </div>
            {task.depends_on?.length > 0 && (
              <span className="text-[10px] text-planex-dimmed">
                after {task.depends_on.join(', ')}
              </span>
            )}
            {task.result_summary && task.status === 'completed' && (
              <p className="text-xs text-planex-dimmed mt-1 line-clamp-2">{task.result_summary}</p>
            )}
          </div>
          <span className="text-[10px] text-planex-dimmed">{task.id}</span>
        </div>
      ))}
    </div>
  )
}
