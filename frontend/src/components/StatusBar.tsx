import { useAppStore } from '../stores/appStore'
import { Settings } from 'lucide-react'

export function StatusBar() {
  const { kbStats, totalTokens, currentStep, providerStatus, setSettingsOpen } = useAppStore()

  const connected = providerStatus && !providerStatus.needs_setup
  const providerLabel = providerStatus?.provider_name || 'Unknown'

  return (
    <footer className="flex items-center justify-between px-4 py-1 bg-white dark:bg-planex-panel border-t border-gray-200 dark:border-planex-border text-xs text-gray-400 dark:text-planex-dimmed">
      <div className="flex items-center gap-3">
        <button
          onClick={() => setSettingsOpen(true)}
          className="flex items-center gap-1.5 hover:text-planex-coral transition-colors"
          title="Settings"
        >
          <span className={`inline-block w-1.5 h-1.5 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500 animate-pulse'}`} />
          <Settings className="w-3 h-3" />
          <span>{providerLabel}</span>
        </button>
        {currentStep && (
          <span className="text-planex-coral animate-pulse">● {currentStep}</span>
        )}
        <span>KB: {kbStats.documents} docs, {kbStats.chunks} chunks</span>
        {totalTokens > 0 && <span>tokens: {totalTokens.toLocaleString()}</span>}
      </div>
      <span>Planex v0.1.0</span>
    </footer>
  )
}
