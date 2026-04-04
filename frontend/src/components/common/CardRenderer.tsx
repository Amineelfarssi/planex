import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

interface CardConfig {
  title?: string
  cards: {
    label: string
    value: string | number
    change?: string
    trend?: 'up' | 'down' | 'neutral'
    color?: string
  }[]
}

export function CardRenderer({ code }: { code: string }) {
  let config: CardConfig
  try {
    config = JSON.parse(code)
  } catch {
    return (
      <div className="border border-red-200 dark:border-red-500/30 rounded-lg p-4 text-sm text-red-600 dark:text-red-400">
        Invalid card JSON. Expected: {"{"} cards: [{"{"} label, value, change?, trend? {"}"}] {"}"}
      </div>
    )
  }

  const TrendIcon = ({ trend }: { trend?: string }) => {
    if (trend === 'up') return <TrendingUp className="w-4 h-4 text-green-500" />
    if (trend === 'down') return <TrendingDown className="w-4 h-4 text-red-500" />
    return <Minus className="w-4 h-4 text-gray-400" />
  }

  return (
    <div className="my-4">
      {config.title && <h4 className="text-sm font-medium mb-3 text-gray-700 dark:text-gray-300">{config.title}</h4>}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        {config.cards.map((card, i) => (
          <div key={i} className="bg-white dark:bg-planex-surface rounded-lg p-4 border border-gray-200 dark:border-planex-border">
            <p className="text-xs text-gray-500 dark:text-planex-dimmed mb-1">{card.label}</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">{card.value}</p>
            {card.change && (
              <div className="flex items-center gap-1 mt-1">
                <TrendIcon trend={card.trend} />
                <span className={`text-xs ${
                  card.trend === 'up' ? 'text-green-600' : card.trend === 'down' ? 'text-red-500' : 'text-gray-400'
                }`}>{card.change}</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
