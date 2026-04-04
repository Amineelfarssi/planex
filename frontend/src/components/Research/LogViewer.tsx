import type { LogEntry } from '../../types'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { useState } from 'react'

export function LogViewer({ logs }: { logs: LogEntry[] }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-sm text-planex-dimmed hover:text-gray-300 mb-2"
      >
        {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        Execution Log ({logs.length} events)
      </button>
      {expanded && (
        <div className="space-y-0.5 font-mono text-xs">
          {logs.map((log, i) => (
            <div key={i} className="flex gap-3 px-2 py-1 hover:bg-planex-panel rounded">
              <span className="text-planex-dimmed w-16 shrink-0">{log.timestamp.slice(11, 19)}</span>
              <span className={`w-28 shrink-0 ${
                log.event_type === 'tool_call' ? 'text-planex-cyan' :
                log.event_type === 'task_failed' ? 'text-red-400' :
                'text-planex-dimmed'
              }`}>
                {log.event_type}
              </span>
              <span className="text-planex-dimmed w-8 shrink-0">{log.task_id}</span>
              <span className="text-planex-cyan w-24 shrink-0">{log.tool_name}</span>
              <span className="truncate text-planex-dimmed">{log.output_summary || log.input_summary}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
