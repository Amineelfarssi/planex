import { ArrowRight } from 'lucide-react'

interface Option {
  label: string
  description: string
  query: string
}

export function ClarificationCards({
  question,
  options,
  onSelect,
  onDismiss,
}: {
  question: string
  options: Option[]
  onSelect: (query: string) => void
  onDismiss: () => void
}) {
  return (
    <div className="my-4 bg-white dark:bg-planex-panel rounded-lg border border-planex-cyan/30 p-4">
      <p className="text-sm font-medium mb-3 text-gray-700 dark:text-gray-300">{question}</p>
      <div className="grid gap-2">
        {options.map((opt, i) => (
          <button
            key={i}
            onClick={() => onSelect(opt.query)}
            className="flex items-start gap-3 p-3 rounded-lg border border-gray-200 dark:border-planex-border
              bg-gray-50 dark:bg-planex-surface
              hover:border-planex-cyan hover:bg-planex-cyan/5
              transition-colors text-left group"
          >
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-800 dark:text-gray-200">{opt.label}</p>
              <p className="text-xs text-gray-500 dark:text-planex-dimmed mt-0.5">{opt.description}</p>
            </div>
            <ArrowRight className="w-4 h-4 text-gray-300 group-hover:text-planex-cyan mt-0.5 shrink-0" />
          </button>
        ))}
      </div>
      <button
        onClick={onDismiss}
        className="mt-2 text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
      >
        Search as-is instead
      </button>
    </div>
  )
}
