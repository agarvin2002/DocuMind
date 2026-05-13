import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { useDocumentPolling } from '@/hooks/useDocumentPolling'
import { useApiKeyStore } from '@/stores/apiKeyStore'
import { AlertCircle } from 'lucide-react'

function ApiKeyBanner() {
  const apiKey = useApiKeyStore((s) => s.apiKey)
  if (apiKey) return null
  return (
    <div className="flex items-center gap-2 border-b border-status-pending/20 bg-status-pending/5 px-5 py-2.5 text-xs text-status-pending">
      <AlertCircle size={13} />
      <span>
        No API key set — open <strong>Settings</strong> in the sidebar to add your{' '}
        <code className="font-mono">dm_xxx</code> key.
      </span>
    </div>
  )
}

function PollingManager() {
  useDocumentPolling()
  return null
}

export function AppLayout() {
  return (
    <div className="flex h-screen overflow-hidden bg-bg-base">
      <Sidebar />
      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
        <ApiKeyBanner />
        <main className="flex-1 overflow-auto bg-grid">
          <Outlet />
        </main>
      </div>
      <PollingManager />
    </div>
  )
}
