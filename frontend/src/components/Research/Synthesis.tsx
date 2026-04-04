import { Markdown } from '../common/Markdown'

export function Synthesis({ content }: { content: string }) {
  return (
    <div className="bg-white dark:bg-planex-panel rounded-lg p-6 border border-green-200 dark:border-green-500/20">
      <h2 className="text-sm font-medium text-green-600 dark:text-green-500 mb-4 flex items-center gap-2">
        <span className="w-2 h-2 bg-green-500 rounded-full" />
        Research Complete
      </h2>
      <Markdown content={content} />
    </div>
  )
}
