import { useAppStore } from '../../stores/appStore'
import { Database, Brain } from 'lucide-react'

export function QuickStats() {
  const { kbStats } = useAppStore()

  return (
    <div className="p-3 border-b border-gray-200 dark:border-planex-border">
      <div className="flex items-center gap-2 text-xs text-planex-dimmed mb-2">
        <Database className="w-3 h-3" />
        <span>Knowledge Base</span>
      </div>
      <div className="text-sm">
        <span className="text-white font-medium">{kbStats.chunks}</span>
        <span className="text-planex-dimmed"> chunks · </span>
        <span className="text-white font-medium">{kbStats.documents}</span>
        <span className="text-planex-dimmed"> docs</span>
      </div>
      {kbStats.tags.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-1">
          {kbStats.tags.slice(0, 5).map(tag => (
            <span key={tag} className="text-[10px] px-1.5 py-0.5 bg-planex-surface rounded text-planex-dimmed">
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
