import { useEffect, useState, useCallback } from 'react'
import { useAppStore } from './stores/appStore'
import { fetchSessions, fetchKBStats, uploadFile, ingestUrl, ingestText } from './api/client'
import { SessionList } from './components/Sidebar/SessionList'
import { ResearchView } from './components/Research/ResearchView'
import { DocumentPanel } from './components/Research/DocumentPanel'
import { MemoryView } from './components/Memory/MemoryView'
import { StatusBar } from './components/StatusBar'
import { ToastContainer, showToast } from './components/common/Toast'
import {
  BookOpen, Sun, Moon, FileText, Menu, X, Plus, Brain, Upload,
  ChevronDown, ChevronRight, Database, Link, Type,
} from 'lucide-react'

export default function App() {
  const {
    view, setView, setSessions, setKBStats, theme, toggleTheme,
    docPanelOpen, setDocPanelOpen, selectedSession,
  } = useAppStore()

  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [memoryExpanded, setMemoryExpanded] = useState(false)
  const [sourcesExpanded, setSourcesExpanded] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const [urlInput, setUrlInput] = useState('')
  const [textInput, setTextInput] = useState('')
  const [showTextArea, setShowTextArea] = useState(false)
  const [ingesting, setIngesting] = useState(false)

  useEffect(() => {
    fetchSessions().then(s => {
      s.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
      setSessions(s)
    }).catch(() => {})
    fetchKBStats().then(setKBStats).catch(() => {})
  }, [])

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    document.documentElement.classList.toggle('light', theme === 'light')
  }, [theme])

  const isDark = theme === 'dark'

  const handleFileIngest = useCallback(async (files: FileList | File[]) => {
    for (const file of Array.from(files)) {
      try {
        const result = await uploadFile(file)
        if (result.already_exists) {
          showToast(`${file.name} already in KB`, 'info')
        } else {
          showToast(`Ingested ${file.name} (${result.chunks_created} chunks)`, 'success')
        }
      } catch {
        showToast(`Failed to ingest ${file.name}`, 'error')
      }
    }
    fetchKBStats().then(setKBStats).catch(() => {})
  }, [setKBStats])

  const handleFileDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    await handleFileIngest(e.dataTransfer.files)
  }, [handleFileIngest])

  return (
    <div className={`h-screen flex flex-col ${isDark ? 'bg-planex-surface text-gray-200' : 'bg-[#f5f0eb] text-gray-800'}`}>
      {/* Top bar */}
      <header className={`flex items-center justify-between px-3 py-2 border-b ${isDark ? 'bg-planex-panel border-planex-border' : 'bg-white border-gray-200'}`}>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className={`p-1.5 rounded ${isDark ? 'hover:bg-planex-surface text-planex-dimmed' : 'hover:bg-gray-100 text-gray-400'}`}
          >
            {sidebarOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
          </button>
          <svg width="20" height="20" viewBox="0 0 36 36" className="animate-[spin_20s_linear_infinite]">
            <circle cx="18" cy="18" r="14" fill="none" stroke="#DA7756" strokeWidth="1.5" opacity="0.3" />
            <circle cx="18" cy="18" r="9" fill="none" stroke="#DA7756" strokeWidth="1" opacity="0.2" />
            <circle cx="18" cy="18" r="4" fill="#DA7756" opacity="0.8" />
            <circle cx="18" cy="4" r="2" fill="#DA7756" opacity="0.9" />
            <circle cx="30" cy="22" r="1.5" fill="#DA7756" opacity="0.6" />
            <circle cx="8" cy="25" r="1.5" fill="#DA7756" opacity="0.4" />
          </svg>
          <span className="font-bold text-planex-coral">Planex</span>
        </div>
        <div className="flex items-center gap-1">
          {selectedSession?.synthesis && (
            <button
              onClick={() => setDocPanelOpen(!docPanelOpen)}
              className={`p-1.5 rounded transition-colors ${
                docPanelOpen ? 'text-planex-coral bg-planex-coral/10'
                  : isDark ? 'text-planex-dimmed hover:text-gray-300' : 'text-gray-400 hover:text-gray-600'
              }`}
              title="Research document"
            >
              <FileText className="w-4 h-4" />
            </button>
          )}
          <button
            onClick={toggleTheme}
            className={`p-1.5 rounded ${isDark ? 'text-planex-dimmed hover:text-gray-300' : 'text-gray-400 hover:text-gray-600'}`}
          >
            {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Collapsible sidebar */}
        {sidebarOpen && (
          <aside className={`w-64 shrink-0 border-r flex flex-col overflow-hidden ${isDark ? 'bg-planex-panel border-planex-border' : 'bg-white border-gray-200'}`}>
            {/* Sessions */}
            <div className="flex-1 overflow-y-auto">
              <SessionList />
            </div>

            {/* Memory peek */}
            <div className={`border-t ${isDark ? 'border-planex-border' : 'border-gray-200'}`}>
              <button
                onClick={() => setMemoryExpanded(!memoryExpanded)}
                className={`w-full flex items-center gap-2 px-3 py-2 text-xs ${isDark ? 'text-planex-dimmed hover:text-gray-300' : 'text-gray-400 hover:text-gray-600'}`}
              >
                {memoryExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                <Brain className="w-3 h-3" />
                Memory
              </button>
              {memoryExpanded && (
                <div className="px-3 pb-3 max-h-40 overflow-y-auto">
                  <MemoryView compact />
                </div>
              )}
            </div>

            {/* Sources — add files, URLs, text */}
            <div className={`border-t ${isDark ? 'border-planex-border' : 'border-gray-200'}`}>
              <button
                onClick={() => setSourcesExpanded(!sourcesExpanded)}
                className={`w-full flex items-center gap-2 px-3 py-2 text-xs ${isDark ? 'text-planex-dimmed hover:text-gray-300' : 'text-gray-400 hover:text-gray-600'}`}
              >
                {sourcesExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                <Database className="w-3 h-3" />
                <span>Sources</span>
                <span className="ml-auto opacity-60">{useAppStore.getState().kbStats.chunks} chunks</span>
              </button>

              {sourcesExpanded && (
                <div className="px-3 pb-3 space-y-2">
                  {/* Upload file */}
                  <label className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer text-xs ${isDark ? 'hover:bg-planex-surface text-planex-dimmed' : 'hover:bg-gray-100 text-gray-500'}`}>
                    <Upload className="w-3.5 h-3.5" />
                    <span>Upload files</span>
                    <input type="file" multiple accept=".pdf,.md,.txt,.html,.htm" className="hidden"
                      onChange={(e) => { if (e.target.files) handleFileIngest(e.target.files) }} />
                  </label>

                  {/* Add URL */}
                  <div className="flex gap-1">
                    <div className="flex-1 relative">
                      <Link className={`absolute left-2 top-1.5 w-3 h-3 ${isDark ? 'text-planex-dimmed' : 'text-gray-400'}`} />
                      <input
                        type="text"
                        value={urlInput}
                        onChange={e => setUrlInput(e.target.value)}
                        onKeyDown={async e => {
                          if (e.key === 'Enter' && urlInput.trim()) {
                            setIngesting(true)
                            try {
                              const r = await ingestUrl(urlInput)
                              showToast(`Ingested URL (${r.chunks_created} chunks)`, 'success')
                              setUrlInput('')
                            } catch { showToast('Failed to fetch URL', 'error') }
                            setIngesting(false)
                            fetchKBStats().then(setKBStats).catch(() => {})
                          }
                        }}
                        placeholder="Paste URL..."
                        className={`w-full pl-6 pr-2 py-1 rounded text-[11px] ${isDark ? 'bg-planex-surface border-planex-border text-gray-300' : 'bg-gray-50 border-gray-200 text-gray-700'} border focus:outline-none focus:border-planex-cyan`}
                        disabled={ingesting}
                      />
                    </div>
                  </div>

                  {/* Paste text toggle */}
                  <button
                    onClick={() => setShowTextArea(!showTextArea)}
                    className={`flex items-center gap-2 px-2 py-1 rounded text-xs ${isDark ? 'text-planex-dimmed hover:bg-planex-surface' : 'text-gray-400 hover:bg-gray-100'}`}
                  >
                    <Type className="w-3.5 h-3.5" />
                    Paste text
                  </button>

                  {showTextArea && (
                    <div className="space-y-1">
                      <textarea
                        value={textInput}
                        onChange={e => setTextInput(e.target.value)}
                        placeholder="Paste content..."
                        rows={3}
                        className={`w-full rounded p-2 text-[11px] resize-y ${isDark ? 'bg-planex-surface border-planex-border text-gray-300' : 'bg-gray-50 border-gray-200 text-gray-700'} border focus:outline-none focus:border-planex-cyan`}
                      />
                      <button
                        onClick={async () => {
                          if (!textInput.trim()) return
                          setIngesting(true)
                          try {
                            const r = await ingestText(textInput)
                            showToast(`Ingested text (${r.chunks_created} chunks)`, 'success')
                            setTextInput('')
                            setShowTextArea(false)
                          } catch { showToast('Failed to ingest text', 'error') }
                          setIngesting(false)
                          fetchKBStats().then(setKBStats).catch(() => {})
                        }}
                        disabled={!textInput.trim() || ingesting}
                        className="px-3 py-1 text-[10px] bg-planex-cyan/20 text-planex-cyan rounded hover:bg-planex-cyan/30 disabled:opacity-40"
                      >
                        {ingesting ? 'Ingesting...' : 'Ingest'}
                      </button>
                    </div>
                  )}

                  {/* Drop zone */}
                  <div
                    onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={handleFileDrop}
                    className={`border border-dashed rounded p-1.5 text-center text-[10px] transition-colors ${
                      dragOver ? 'border-planex-cyan bg-planex-cyan/10 text-planex-cyan'
                        : isDark ? 'border-planex-border text-planex-dimmed' : 'border-gray-300 text-gray-400'
                    }`}
                  >
                    {dragOver ? 'Drop to ingest' : 'or drag files here'}
                  </div>
                </div>
              )}
            </div>
          </aside>
        )}

        {/* Main area */}
        <main className="flex-1 overflow-y-auto">
          <ResearchView />
        </main>

        {/* Document panel */}
        {docPanelOpen && selectedSession?.synthesis && (
          <aside className="w-[45%] max-w-[600px] min-w-[300px] shrink-0">
            <DocumentPanel onClose={() => setDocPanelOpen(false)} />
          </aside>
        )}
      </div>

      <StatusBar />
      <ToastContainer />
    </div>
  )
}
