import { useState } from 'react'
import { Markdown } from '../common/Markdown'
import { Download, Copy, Check, X, FileText } from 'lucide-react'
import { useAppStore } from '../../stores/appStore'

export function DocumentPanel({ onClose }: { onClose: () => void }) {
  const { selectedSession } = useAppStore()
  const [copied, setCopied] = useState(false)

  const synthesis = selectedSession?.synthesis || ''

  // Build compiled document from session
  const doc = synthesis || '*No research document yet. Start a research session to generate one.*'

  const handleDownload = () => {
    const title = selectedSession?.plan_title || 'research'
    const filename = `${title.replace(/[^a-zA-Z0-9]/g, '_').slice(0, 50)}.md`

    // Use data URI instead of blob URL — pywebview intercepts blob URLs
    const dataUri = 'data:text/markdown;charset=utf-8,' + encodeURIComponent(synthesis)
    const a = document.createElement('a')
    a.href = dataUri
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  const handleCopy = async () => {
    await navigator.clipboard.writeText(synthesis)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="flex flex-col h-full border-l border-gray-200 dark:border-planex-border bg-white dark:bg-planex-panel">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200 dark:border-planex-border">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-planex-coral" />
          <span className="text-sm font-medium">Research Document</span>
        </div>
        <div className="flex items-center gap-1">
          {synthesis && (
            <>
              <button
                onClick={handleCopy}
                className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-planex-surface text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                title="Copy to clipboard"
              >
                {copied ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
              </button>
              <button
                onClick={handleDownload}
                className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-planex-surface text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                title="Download as Markdown"
              >
                <Download className="w-4 h-4" />
              </button>
            </>
          )}
          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-planex-surface text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Document content */}
      <div className="flex-1 overflow-y-auto p-5">
        {selectedSession?.plan_title && (
          <p className="text-[10px] text-gray-400 dark:text-planex-dimmed mb-4 uppercase tracking-wide">
            {selectedSession.plan_title}
          </p>
        )}
        <Markdown content={doc} />
      </div>
    </div>
  )
}
