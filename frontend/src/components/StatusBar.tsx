import { useAppStore } from '../stores/appStore'

export function StatusBar() {
  const { kbStats, totalTokens, currentStep } = useAppStore()

  return (
    <footer className="flex items-center justify-between px-4 py-1 bg-white dark:bg-planex-panel border-t border-gray-200 dark:border-planex-border text-xs text-gray-400 dark:text-planex-dimmed">
      <div className="flex items-center gap-3">
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
