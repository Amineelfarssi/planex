import { useEffect, useRef, useState } from 'react'
import mermaid from 'mermaid'

mermaid.initialize({
  startOnLoad: false,
  theme: 'default',
  securityLevel: 'loose',
  fontFamily: 'inherit',
})

let idCounter = 0

export function MermaidDiagram({ code }: { code: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const [svg, setSvg] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    const id = `mermaid-${++idCounter}`
    mermaid.render(id, code.trim())
      .then(({ svg }) => setSvg(svg))
      .catch((e) => setError(e.message || 'Invalid mermaid syntax'))
  }, [code])

  if (error) {
    return (
      <div className="border border-red-200 dark:border-red-500/30 rounded-lg p-4 text-sm text-red-600 dark:text-red-400">
        <p className="font-medium mb-1">Diagram error</p>
        <pre className="text-xs opacity-70">{error}</pre>
      </div>
    )
  }

  return (
    <div
      ref={ref}
      className="my-4 flex justify-center bg-white dark:bg-planex-surface rounded-lg p-4 border border-gray-200 dark:border-planex-border overflow-x-auto"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}
