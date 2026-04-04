import { useState, useEffect } from 'react'
import { fetchStatus } from '../../api/client'
import { Markdown } from '../common/Markdown'
import { Brain, FileText } from 'lucide-react'

export function MemoryView({ compact = false }: { compact?: boolean }) {
  const [memory, setMemory] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchStatus()
      .then(data => {
        setMemory(data.memory || '')
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  if (loading) return <p className="text-xs text-gray-400">Loading...</p>

  // Compact mode for sidebar peek
  if (compact) {
    return (
      <div className="text-xs text-gray-500 dark:text-planex-dimmed space-y-1">
        {memory ? (
          memory.split('\n').filter(l => l.trim()).slice(0, 8).map((line, i) => (
            <p key={i} className="truncate">{line}</p>
          ))
        ) : (
          <p className="italic">Memory is empty</p>
        )}
      </div>
    )
  }

  // Full page mode
  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <h1 className="text-xl font-bold flex items-center gap-2">
        <Brain className="w-5 h-5 text-planex-coral" />
        Long-term Memory
      </h1>
      <div className="bg-white dark:bg-planex-panel rounded-lg p-4 border border-gray-200 dark:border-planex-border">
        <div className="flex items-center gap-2 mb-3 text-sm text-gray-400 dark:text-planex-dimmed">
          <FileText className="w-4 h-4" />
          MEMORY.md
        </div>
        {memory ? <Markdown content={memory} /> : (
          <p className="text-gray-400 dark:text-planex-dimmed text-sm">
            Memory is empty. It grows automatically as you research.
          </p>
        )}
      </div>
    </div>
  )
}
