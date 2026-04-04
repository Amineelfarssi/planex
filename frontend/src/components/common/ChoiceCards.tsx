import { useState } from 'react'
import { ArrowRight, CheckCircle } from 'lucide-react'

interface Choice {
  label: string
  description?: string
  value: string
}

interface ChoiceConfig {
  question?: string
  options: Choice[]
}

export function ChoiceCards({ code }: { code: string }) {
  const [selected, setSelected] = useState<string | null>(null)

  let config: ChoiceConfig
  try {
    config = JSON.parse(code)
  } catch {
    return null
  }

  const handleSelect = (opt: Choice) => {
    setSelected(opt.label)
    window.dispatchEvent(new CustomEvent('planex:choice', { detail: opt.value }))
  }

  // After selection — collapse to show what was picked
  if (selected) {
    return (
      <div className="my-3 not-prose flex items-center gap-2 text-sm text-gray-500 dark:text-planex-dimmed">
        <CheckCircle className="w-4 h-4 text-green-500" />
        <span>Selected: <strong className="text-gray-700 dark:text-gray-300">{selected}</strong></span>
      </div>
    )
  }

  return (
    <div className="my-4 not-prose">
      {config.question && (
        <p className="text-sm font-medium mb-3 text-gray-700 dark:text-gray-300">{config.question}</p>
      )}
      <div className="grid gap-2">
        {config.options.map((opt, i) => (
          <button
            key={i}
            onClick={() => handleSelect(opt)}
            className="flex items-start gap-3 p-3 rounded-lg border border-gray-200 dark:border-planex-border
              bg-gray-50 dark:bg-planex-surface
              hover:border-planex-coral hover:bg-planex-coral/5
              transition-all text-left group cursor-pointer"
          >
            <div className="w-6 h-6 rounded-full bg-planex-coral/10 flex items-center justify-center shrink-0 mt-0.5">
              <span className="text-xs font-medium text-planex-coral">{String.fromCharCode(65 + i)}</span>
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-800 dark:text-gray-200">{opt.label}</p>
              {opt.description && (
                <p className="text-xs text-gray-500 dark:text-planex-dimmed mt-0.5">{opt.description}</p>
              )}
            </div>
            <ArrowRight className="w-4 h-4 text-gray-300 group-hover:text-planex-coral mt-1 shrink-0 transition-colors" />
          </button>
        ))}
      </div>
    </div>
  )
}
