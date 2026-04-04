import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

const COLORS = ['#DA7756', '#5B9BD5', '#6BC76B', '#E5C07B', '#E06C75', '#9B7DDB', '#5BCACA']

interface ChartConfig {
  type: 'bar' | 'line' | 'pie'
  title?: string
  data: Record<string, any>[]
  xKey?: string
  yKeys?: string[]
  nameKey?: string
  valueKey?: string
}

export function ChartRenderer({ code }: { code: string }) {
  let config: ChartConfig
  try {
    config = JSON.parse(code)
  } catch {
    return (
      <div className="border border-red-200 dark:border-red-500/30 rounded-lg p-4 text-sm text-red-600 dark:text-red-400">
        Invalid chart JSON. Expected: {"{"} type, data, xKey, yKeys {"}"}
      </div>
    )
  }

  const { type, title, data, xKey = 'name', yKeys = ['value'], nameKey = 'name', valueKey = 'value' } = config

  return (
    <div className="my-4 bg-white dark:bg-planex-surface rounded-lg p-4 border border-gray-200 dark:border-planex-border">
      {title && <h4 className="text-sm font-medium mb-3 text-gray-700 dark:text-gray-300">{title}</h4>}
      <ResponsiveContainer width="100%" height={300}>
        {type === 'pie' ? (
          <PieChart>
            <Pie data={data} dataKey={valueKey} nameKey={nameKey} cx="50%" cy="50%" outerRadius={100} label>
              {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        ) : type === 'line' ? (
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
            <XAxis dataKey={xKey} tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Legend />
            {yKeys.map((key, i) => (
              <Line key={key} type="monotone" dataKey={key} stroke={COLORS[i % COLORS.length]} strokeWidth={2} />
            ))}
          </LineChart>
        ) : (
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
            <XAxis dataKey={xKey} tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip />
            <Legend />
            {yKeys.map((key, i) => (
              <Bar key={key} dataKey={key} fill={COLORS[i % COLORS.length]} radius={[4, 4, 0, 0]} />
            ))}
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  )
}
