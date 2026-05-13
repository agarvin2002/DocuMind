import { NavLink } from 'react-router-dom'
import {
  FileText,
  MessageSquare,
  Search,
  Zap,
  Settings,
} from 'lucide-react'
import { useState } from 'react'
import { HealthDot } from './HealthDot'
import { Dialog, DialogContent } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { useApiKeyStore } from '@/stores/apiKeyStore'
import { checkHealth } from '@/api/health'
import { cn } from '@/lib/utils'

const navItems = [
  { to: '/', icon: FileText, label: 'Documents', exact: true },
  { to: '/chat', icon: MessageSquare, label: 'Chat' },
  { to: '/search', icon: Search, label: 'Search' },
  { to: '/analysis', icon: Zap, label: 'Analysis' },
]

function SettingsModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { apiKey, setApiKey } = useApiKeyStore()
  const [draft, setDraft] = useState(apiKey)
  const [showKey, setShowKey] = useState(false)
  const [testState, setTestState] = useState<'idle' | 'loading' | 'ok' | 'fail'>('idle')
  const [testMsg, setTestMsg] = useState('')

  const handleTest = async () => {
    setTestState('loading')
    try {
      const res = await checkHealth()
      if (res.status === 'healthy') {
        setTestState('ok')
        setTestMsg(`Connected · v${res.version}`)
      } else {
        setTestState('fail')
        setTestMsg('Backend unhealthy')
      }
    } catch {
      setTestState('fail')
      setTestMsg('Cannot reach backend')
    }
  }

  const handleSave = () => {
    setApiKey(draft.trim())
    onClose()
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent title="Settings" description="Configure your DocuMind connection.">
        <div className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="api-key">API Key</Label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Input
                  id="api-key"
                  type={showKey ? 'text' : 'password'}
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  placeholder="dm_xxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                  className="pr-16 font-mono text-xs"
                />
                <button
                  type="button"
                  onClick={() => setShowKey((s) => !s)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-txt-muted hover:text-txt-secondary transition-colors"
                >
                  {showKey ? 'hide' : 'show'}
                </button>
              </div>
              <Button variant="secondary" size="sm" onClick={handleTest} loading={testState === 'loading'}>
                Test
              </Button>
            </div>
            {testState !== 'idle' && testState !== 'loading' && (
              <p
                className={cn(
                  'text-xs mt-1',
                  testState === 'ok' ? 'text-status-ready' : 'text-status-failed'
                )}
              >
                {testState === 'ok' ? '✓' : '✗'} {testMsg}
              </p>
            )}
          </div>

          <Separator />

          <div className="flex items-center justify-between">
            <p className="text-xs text-txt-muted">
              Key stored in localStorage — never sent to third parties
            </p>
            <Button size="sm" onClick={handleSave}>
              Save
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export function Sidebar() {
  const [settingsOpen, setSettingsOpen] = useState(false)

  return (
    <>
      <aside className="flex h-full w-56 flex-col sidebar-gradient-border bg-bg-surface">
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-5 py-5">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent/15 border border-accent/20">
            <Zap size={14} className="text-accent" />
          </div>
          <span className="font-display text-base font-bold gradient-text tracking-tight">
            DocuMind
          </span>
          <div className="ml-auto">
            <HealthDot />
          </div>
        </div>

        <Separator />

        {/* Nav */}
        <nav className="flex-1 px-3 py-3 space-y-0.5">
          {navItems.map(({ to, icon: Icon, label, exact }) => (
            <NavLink
              key={to}
              to={to}
              end={exact}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all duration-150',
                  isActive
                    ? 'bg-accent/10 text-accent border border-accent/15 font-medium'
                    : 'text-txt-secondary hover:text-txt-primary hover:bg-bg-elevated'
                )
              }
            >
              {({ isActive }) => (
                <>
                  <Icon size={15} className={isActive ? 'text-accent' : ''} />
                  {label}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <Separator />

        {/* Settings */}
        <div className="px-3 py-3">
          <button
            onClick={() => setSettingsOpen(true)}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-txt-secondary hover:text-txt-primary hover:bg-bg-elevated transition-all duration-150"
          >
            <Settings size={15} />
            Settings
          </button>
        </div>
      </aside>

      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </>
  )
}
