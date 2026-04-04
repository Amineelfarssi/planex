import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { MermaidDiagram } from './MermaidDiagram'
import { ChartRenderer } from './ChartRenderer'
import { CardRenderer } from './CardRenderer'
import { ChoiceCards } from './ChoiceCards'

export function Markdown({ content }: { content: string }) {
  return (
    <article className="
      prose prose-sm max-w-none
      dark:prose-invert

      prose-headings:font-semibold
      prose-p:leading-relaxed
      prose-strong:text-gray-900 dark:prose-strong:text-white
      prose-a:text-planex-coral prose-a:no-underline hover:prose-a:underline

      prose-table:border-collapse
      prose-th:bg-gray-50 dark:prose-th:bg-planex-surface
      prose-th:px-3 prose-th:py-2 prose-th:border prose-th:border-gray-200 dark:prose-th:border-planex-border prose-th:text-xs
      prose-td:px-3 prose-td:py-2 prose-td:border prose-td:border-gray-200 dark:prose-td:border-planex-border
    ">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Custom code renderer — handles artifacts + fixes code block colors
          code({ className, children, ...props }) {
            const code = String(children).replace(/\n$/, '')
            const lang = className?.replace('language-', '') || ''

            // Artifact renderers
            if (lang === 'mermaid') return <MermaidDiagram code={code} />
            if (lang === 'chart') return <ChartRenderer code={code} />
            if (lang === 'cards' || lang === 'dashboard') return <CardRenderer code={code} />
            if (lang === 'choices' || lang === 'options') return <ChoiceCards code={code} />

            // Multi-line code block (has language class)
            if (className) {
              return (
                <code className="!text-gray-800 dark:!text-gray-200 !bg-transparent" {...props}>
                  {children}
                </code>
              )
            }

            // Inline code — accent color
            return (
              <code className="!text-planex-coral !bg-gray-100 dark:!bg-planex-surface !px-1.5 !py-0.5 !rounded !text-xs" {...props}>
                {children}
              </code>
            )
          },
          // Links open in external browser
          a({ href, children, ...props }) {
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="!text-planex-coral hover:!underline"
                onClick={(e) => {
                  // In pywebview, open externally
                  if (href && (window as any).pywebview) {
                    e.preventDefault();
                    (window as any).pywebview.api?.openUrl?.(href) ||
                      window.open(href, '_blank');
                  }
                }}
                {...props}
              >
                {children}
              </a>
            )
          },
          // Code blocks wrapper
          pre({ children, ...props }) {
            return (
              <pre className="!bg-gray-50 dark:!bg-planex-surface !border !border-gray-200 dark:!border-planex-border !rounded-lg !text-sm overflow-x-auto" {...props}>
                {children}
              </pre>
            )
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </article>
  )
}
