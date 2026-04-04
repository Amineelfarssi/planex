import { useState, useCallback, useRef } from 'react'
import { useAppStore } from '../../stores/appStore'
import { uploadFile, searchKB, fetchKBStats, ingestPath } from '../../api/client'
import type { KBSearchResult } from '../../types'
import { Upload, Search, FileText, FolderOpen, FileUp, Type } from 'lucide-react'

export function KBView() {
  const { kbStats, setKBStats } = useAppStore()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<KBSearchResult[]>([])
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [showTextInput, setShowTextInput] = useState(false)
  const [textContent, setTextContent] = useState('')
  const [pathInput, setPathInput] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFiles = useCallback(async (files: FileList | File[]) => {
    setUploading(true)
    for (const file of Array.from(files)) {
      await uploadFile(file)
    }
    const stats = await fetchKBStats()
    setKBStats(stats)
    setUploading(false)
  }, [setKBStats])

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    await handleFiles(e.dataTransfer.files)
  }, [handleFiles])

  const handleIngestPath = async () => {
    if (!pathInput.trim()) return
    setUploading(true)
    await ingestPath(pathInput)
    const stats = await fetchKBStats()
    setKBStats(stats)
    setUploading(false)
    setPathInput('')
  }

  const handleTextIngest = async () => {
    if (!textContent.trim()) return
    setUploading(true)
    // Create a text blob and upload as file
    const blob = new Blob([textContent], { type: 'text/plain' })
    const file = new File([blob], `pasted-${Date.now()}.txt`, { type: 'text/plain' })
    await uploadFile(file)
    const stats = await fetchKBStats()
    setKBStats(stats)
    setUploading(false)
    setTextContent('')
    setShowTextInput(false)
  }

  const [searching, setSearching] = useState(false)

  const handleSearch = async () => {
    if (!query.trim()) return
    setSearching(true)
    const r = await searchKB(query)
    setResults(r)
    setSearching(false)
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <h1 className="text-xl font-bold">Knowledge Base</h1>

      {/* Stats */}
      <div className="flex gap-6 text-sm">
        <div>
          <span className="text-2xl font-bold text-white">{kbStats.documents}</span>
          <span className="text-gray-400 dark:text-planex-dimmed ml-1">documents</span>
        </div>
        <div>
          <span className="text-2xl font-bold text-white">{kbStats.chunks}</span>
          <span className="text-gray-400 dark:text-planex-dimmed ml-1">chunks</span>
        </div>
        {kbStats.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 items-center">
            {kbStats.tags.slice(0, 8).map(tag => (
              <span key={tag} className="text-xs px-2 py-0.5 bg-gray-100 dark:bg-planex-surface rounded text-gray-400 dark:text-planex-dimmed">
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Upload section */}
      <div className="space-y-3">
        {/* Drop zone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors cursor-pointer ${
            dragOver ? 'border-planex-cyan bg-planex-cyan/5' : 'border-gray-300 dark:border-planex-border hover:border-gray-400 dark:hover:border-planex-dimmed'
          }`}
          onClick={() => fileInputRef.current?.click()}
        >
          <Upload className={`w-8 h-8 mx-auto mb-2 ${dragOver ? 'text-planex-cyan' : 'text-gray-400 dark:text-planex-dimmed'}`} />
          <p className="text-sm text-gray-400 dark:text-planex-dimmed">
            {uploading ? 'Uploading...' : 'Drop files or click to browse (PDF, MD, TXT, HTML)'}
          </p>
        </div>

        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.md,.txt,.html,.htm"
          className="hidden"
          onChange={e => e.target.files && handleFiles(e.target.files)}
        />

        {/* Action buttons */}
        <div className="flex gap-2">
          <button
            onClick={() => fileInputRef.current?.click()}
            className="flex items-center gap-2 px-3 py-2 bg-white dark:bg-planex-panel border border-gray-200 dark:border-planex-border rounded text-sm hover:border-gray-300 dark:hover:border-planex-dimmed"
          >
            <FileUp className="w-4 h-4" /> Upload Files
          </button>
          <button
            onClick={() => setShowTextInput(!showTextInput)}
            className="flex items-center gap-2 px-3 py-2 bg-white dark:bg-planex-panel border border-gray-200 dark:border-planex-border rounded text-sm hover:border-gray-300 dark:hover:border-planex-dimmed"
          >
            <Type className="w-4 h-4" /> Paste Text
          </button>
        </div>

        {/* Paste text area */}
        {showTextInput && (
          <div className="space-y-2">
            <textarea
              value={textContent}
              onChange={e => setTextContent(e.target.value)}
              placeholder="Paste text content here..."
              rows={6}
              className="w-full bg-white dark:bg-planex-surface border border-gray-200 dark:border-planex-border rounded p-3 text-sm focus:outline-none focus:border-planex-cyan resize-y"
            />
            <button
              onClick={handleTextIngest}
              disabled={!textContent.trim()}
              className="px-4 py-2 bg-planex-cyan/20 text-planex-cyan rounded text-sm hover:bg-planex-cyan/30 disabled:opacity-40"
            >
              Ingest Text
            </button>
          </div>
        )}

        {/* Path input */}
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <FolderOpen className="absolute left-3 top-2.5 w-4 h-4 text-gray-400 dark:text-planex-dimmed" />
            <input
              type="text"
              value={pathInput}
              onChange={e => setPathInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleIngestPath()}
              placeholder="Local path to ingest (e.g., ~/Documents/papers/)"
              className="w-full pl-9 pr-3 py-2 bg-white dark:bg-planex-panel border border-gray-200 dark:border-planex-border rounded text-sm focus:outline-none focus:border-planex-cyan"
            />
          </div>
          <button
            onClick={handleIngestPath}
            disabled={!pathInput.trim()}
            className="px-4 py-2 bg-planex-cyan/10 text-planex-cyan rounded text-sm hover:bg-planex-cyan/20 disabled:opacity-40"
          >
            Ingest
          </button>
        </div>
      </div>

      {/* Search */}
      <div>
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400 dark:text-planex-dimmed" />
            <input
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSearch()}
              placeholder="Search knowledge base..."
              className="w-full pl-9 pr-3 py-2 bg-white dark:bg-planex-panel border border-gray-200 dark:border-planex-border rounded text-sm focus:outline-none focus:border-planex-cyan"
            />
          </div>
          <button
            onClick={handleSearch}
            className="px-4 py-2 bg-planex-cyan/10 text-planex-cyan rounded text-sm hover:bg-planex-cyan/20"
          >
            Search
          </button>
        </div>

        {searching && (
          <div className="mt-4 flex items-center gap-2 text-sm text-planex-coral animate-pulse">
            <Search className="w-4 h-4 animate-spin" /> Searching...
          </div>
        )}

        {!searching && results.length > 0 && (
          <div className="mt-4 space-y-2">
            {results.map((r, i) => (
              <div key={i} className="p-3 bg-planex-panel rounded border border-planex-border">
                <div className="flex items-center gap-2 mb-1">
                  <FileText className="w-4 h-4 text-planex-cyan" />
                  <span className="font-medium text-sm">{r.doc_title}</span>
                  <span className="text-[10px] px-1.5 py-0.5 bg-gray-100 dark:bg-planex-surface rounded text-gray-400 dark:text-planex-dimmed">
                    {r.source_type}
                  </span>
                </div>
                <p className="text-xs text-gray-400 dark:text-planex-dimmed line-clamp-3">{r.text}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
