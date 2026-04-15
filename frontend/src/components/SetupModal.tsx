import { useState, useEffect } from 'react'
import { useAppStore } from '../stores/appStore'
import { fetchConfig, saveConfig, testConfig, fetchHealth } from '../api/client'
import type { ConfigData } from '../api/client'
import { X, Settings, Check, AlertTriangle, Loader, ChevronDown, ChevronRight } from 'lucide-react'

type Provider = 'auto' | 'openai' | 'bedrock'

export function SetupModal() {
  const { settingsOpen, setSettingsOpen, setProviderStatus, providerStatus } = useAppStore()
  const isDark = useAppStore(s => s.theme === 'dark')

  const [provider, setProvider] = useState<Provider>('auto')
  const [openaiKey, setOpenaiKey] = useState('')
  const [awsRegion, setAwsRegion] = useState('')
  const [awsAccessKey, setAwsAccessKey] = useState('')
  const [awsSecretKey, setAwsSecretKey] = useState('')
  const [userName, setUserName] = useState('')
  const [fastModel, setFastModel] = useState('')
  const [smartModel, setSmartModel] = useState('')
  const [strategicModel, setStrategicModel] = useState('')
  const [showModels, setShowModels] = useState(false)

  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ ok: boolean; error?: string } | null>(null)
  const [saving, setSaving] = useState(false)

  // Load current config when modal opens
  useEffect(() => {
    if (!settingsOpen) return
    fetchConfig().then((cfg: ConfigData) => {
      const detected = cfg._detected?.provider || ''
      const explicit = cfg.PLANEX_PROVIDER
      if (explicit === 'openai' || explicit === 'bedrock') {
        setProvider(explicit)
      } else if (detected === 'openai' || detected === 'bedrock') {
        setProvider('auto')
      } else {
        setProvider('auto')
      }
      setOpenaiKey(cfg.OPENAI_API_KEY || '')
      setAwsRegion(cfg.AWS_REGION || '')
      setAwsAccessKey(cfg.AWS_ACCESS_KEY_ID || '')
      setAwsSecretKey(cfg.AWS_SECRET_ACCESS_KEY || '')
      setUserName(cfg.PLANEX_USER_NAME || '')
      setFastModel(cfg.PLANEX_FAST_MODEL || '')
      setSmartModel(cfg.PLANEX_SMART_MODEL || '')
      setStrategicModel(cfg.PLANEX_STRATEGIC_MODEL || '')
      setTestResult(null)
    }).catch(() => {})
  }, [settingsOpen])

  if (!settingsOpen) return null

  const effectiveProvider = provider === 'auto'
    ? (providerStatus?.auto_detected?.provider || 'none')
    : provider

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const testProv = provider === 'auto' ? effectiveProvider : provider
      const data: { provider: string } & Record<string, string> = { provider: testProv }
      if (testProv === 'openai') data.OPENAI_API_KEY = openaiKey
      if (testProv === 'bedrock') {
        if (awsRegion) data.AWS_REGION = awsRegion
        if (awsAccessKey) data.AWS_ACCESS_KEY_ID = awsAccessKey
        if (awsSecretKey) data.AWS_SECRET_ACCESS_KEY = awsSecretKey
      }
      const result = await testConfig(data)
      setTestResult(result)
    } catch (e: any) {
      setTestResult({ ok: false, error: e.message || 'Connection failed' })
    }
    setTesting(false)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const cfg: Record<string, string> = {
        PLANEX_PROVIDER: provider === 'auto' ? '' : provider,
        OPENAI_API_KEY: openaiKey,
        AWS_REGION: awsRegion,
        AWS_ACCESS_KEY_ID: awsAccessKey,
        AWS_SECRET_ACCESS_KEY: awsSecretKey,
        PLANEX_USER_NAME: userName,
        PLANEX_FAST_MODEL: fastModel,
        PLANEX_SMART_MODEL: smartModel,
        PLANEX_STRATEGIC_MODEL: strategicModel,
      }
      const health = await saveConfig(cfg)
      setProviderStatus(health)
      setSettingsOpen(false)
    } catch {
      setTestResult({ ok: false, error: 'Failed to save configuration' })
    }
    setSaving(false)
  }

  const inputCls = `w-full px-3 py-2 rounded text-sm border focus:outline-none focus:border-planex-cyan ${
    isDark
      ? 'bg-planex-surface border-planex-border text-gray-200 placeholder:text-planex-dimmed'
      : 'bg-gray-50 border-gray-300 text-gray-800 placeholder:text-gray-400'
  }`

  const cardCls = (active: boolean) =>
    `flex-1 p-3 rounded-lg border-2 cursor-pointer transition-all text-center ${
      active
        ? 'border-planex-coral bg-planex-coral/10'
        : isDark
          ? 'border-planex-border hover:border-planex-dimmed bg-planex-surface'
          : 'border-gray-200 hover:border-gray-300 bg-white'
    }`

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className={`w-full max-w-lg mx-4 rounded-xl shadow-2xl overflow-hidden ${
        isDark ? 'bg-planex-panel' : 'bg-white'
      }`}>
        {/* Header */}
        <div className={`flex items-center justify-between px-5 py-4 border-b ${
          isDark ? 'border-planex-border' : 'border-gray-200'
        }`}>
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-planex-coral" />
            <span className="font-semibold">Settings</span>
          </div>
          <button
            onClick={() => setSettingsOpen(false)}
            className={`p-1 rounded ${isDark ? 'hover:bg-planex-surface text-planex-dimmed' : 'hover:bg-gray-100 text-gray-400'}`}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="px-5 py-4 space-y-5 max-h-[70vh] overflow-y-auto">
          {/* Provider picker */}
          <div>
            <label className={`text-xs font-medium uppercase tracking-wide ${isDark ? 'text-planex-dimmed' : 'text-gray-500'}`}>
              LLM Provider
            </label>
            <div className="flex gap-2 mt-2">
              {([
                { value: 'auto' as Provider, label: 'Auto-detect' },
                { value: 'bedrock' as Provider, label: 'AWS Bedrock' },
                { value: 'openai' as Provider, label: 'OpenAI' },
              ]).map(opt => (
                <div
                  key={opt.value}
                  onClick={() => { setProvider(opt.value); setTestResult(null) }}
                  className={cardCls(provider === opt.value)}
                >
                  <span className="text-sm font-medium">{opt.label}</span>
                </div>
              ))}
            </div>
            {provider === 'auto' && providerStatus?.auto_detected && (
              <p className={`mt-2 text-xs ${isDark ? 'text-planex-dimmed' : 'text-gray-500'}`}>
                Detected: <span className="font-medium text-planex-coral">{providerStatus.auto_detected.provider}</span>
                {' '}&mdash; {providerStatus.auto_detected.reason}
              </p>
            )}
          </div>

          {/* OpenAI credentials */}
          {(provider === 'openai' || (provider === 'auto' && effectiveProvider === 'openai')) && (
            <div>
              <label className={`text-xs font-medium uppercase tracking-wide ${isDark ? 'text-planex-dimmed' : 'text-gray-500'}`}>
                OpenAI API Key
              </label>
              <input
                type="password"
                value={openaiKey}
                onChange={e => setOpenaiKey(e.target.value)}
                placeholder="sk-..."
                className={`mt-1 ${inputCls}`}
              />
            </div>
          )}

          {/* Bedrock credentials */}
          {(provider === 'bedrock' || (provider === 'auto' && effectiveProvider === 'bedrock')) && (
            <div className="space-y-3">
              <div>
                <label className={`text-xs font-medium uppercase tracking-wide ${isDark ? 'text-planex-dimmed' : 'text-gray-500'}`}>
                  AWS Region
                </label>
                <input
                  value={awsRegion}
                  onChange={e => setAwsRegion(e.target.value)}
                  placeholder="eu-west-1 (auto-detected from environment)"
                  className={`mt-1 ${inputCls}`}
                />
              </div>
              <div>
                <label className={`text-xs font-medium uppercase tracking-wide ${isDark ? 'text-planex-dimmed' : 'text-gray-500'}`}>
                  Access Key ID <span className="font-normal opacity-60">(optional if using IAM role)</span>
                </label>
                <input
                  value={awsAccessKey}
                  onChange={e => setAwsAccessKey(e.target.value)}
                  placeholder="Leave blank to use IAM role"
                  className={`mt-1 ${inputCls}`}
                />
              </div>
              <div>
                <label className={`text-xs font-medium uppercase tracking-wide ${isDark ? 'text-planex-dimmed' : 'text-gray-500'}`}>
                  Secret Access Key <span className="font-normal opacity-60">(optional)</span>
                </label>
                <input
                  type="password"
                  value={awsSecretKey}
                  onChange={e => setAwsSecretKey(e.target.value)}
                  placeholder="Leave blank to use IAM role"
                  className={`mt-1 ${inputCls}`}
                />
              </div>
            </div>
          )}

          {/* User name */}
          <div>
            <label className={`text-xs font-medium uppercase tracking-wide ${isDark ? 'text-planex-dimmed' : 'text-gray-500'}`}>
              Your Name <span className="font-normal opacity-60">(for greeting)</span>
            </label>
            <input
              value={userName}
              onChange={e => setUserName(e.target.value)}
              placeholder="Optional"
              className={`mt-1 ${inputCls}`}
            />
          </div>

          {/* Model overrides (collapsible) */}
          <div>
            <button
              onClick={() => setShowModels(!showModels)}
              className={`flex items-center gap-1 text-xs font-medium uppercase tracking-wide ${isDark ? 'text-planex-dimmed hover:text-gray-400' : 'text-gray-500 hover:text-gray-700'}`}
            >
              {showModels ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              Model Overrides
            </button>
            {showModels && (
              <div className="mt-2 space-y-2">
                {([
                  { label: 'Fast (parsing, extraction)', value: fastModel, set: setFastModel, ph: 'Default auto-selected' },
                  { label: 'Smart (tool use, synthesis)', value: smartModel, set: setSmartModel, ph: 'Default auto-selected' },
                  { label: 'Strategic (planning, reasoning)', value: strategicModel, set: setStrategicModel, ph: 'Default auto-selected' },
                ]).map(m => (
                  <div key={m.label}>
                    <label className={`text-xs ${isDark ? 'text-planex-dimmed' : 'text-gray-500'}`}>{m.label}</label>
                    <input value={m.value} onChange={e => m.set(e.target.value)} placeholder={m.ph} className={`mt-0.5 ${inputCls}`} />
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Test result */}
          {testResult && (
            <div className={`flex items-center gap-2 px-3 py-2 rounded text-sm ${
              testResult.ok
                ? 'bg-green-500/10 text-green-400 border border-green-500/30'
                : 'bg-red-500/10 text-red-400 border border-red-500/30'
            }`}>
              {testResult.ok ? <Check className="w-4 h-4 shrink-0" /> : <AlertTriangle className="w-4 h-4 shrink-0" />}
              <span>{testResult.ok ? 'Connection successful!' : testResult.error}</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className={`flex items-center justify-end gap-2 px-5 py-3 border-t ${
          isDark ? 'border-planex-border' : 'border-gray-200'
        }`}>
          <button
            onClick={handleTest}
            disabled={testing || (effectiveProvider === 'none' && provider === 'auto')}
            className={`px-4 py-2 rounded text-sm font-medium transition-colors disabled:opacity-40 ${
              isDark
                ? 'bg-planex-surface hover:bg-planex-border text-gray-300'
                : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
            }`}
          >
            {testing ? <Loader className="w-4 h-4 animate-spin inline mr-1" /> : null}
            {testing ? 'Testing...' : 'Test Connection'}
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 rounded text-sm font-medium bg-planex-coral text-white hover:bg-planex-coral/80 transition-colors disabled:opacity-40"
          >
            {saving ? <Loader className="w-4 h-4 animate-spin inline mr-1" /> : null}
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
