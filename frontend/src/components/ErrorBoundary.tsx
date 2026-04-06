import { Component, type ReactNode } from 'react'

interface State {
  hasError: boolean
  error: string
}

export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { hasError: false, error: '' }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error: error.message }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('React crash:', error, info.componentStack)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="h-screen flex items-center justify-center bg-planex-surface text-gray-200">
          <div className="text-center space-y-4 max-w-md">
            <p className="text-planex-coral text-lg font-bold">Something went wrong</p>
            <p className="text-sm text-planex-dimmed font-mono">{this.state.error}</p>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: '' })
                window.location.reload()
              }}
              className="px-4 py-2 bg-planex-coral text-white rounded-lg text-sm"
            >
              Reload
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
