import { X, CheckCircle, AlertCircle, Info } from 'lucide-react'
import { useToastStore, type ToastMessage } from '@/stores/toastStore'
import { cn } from '@/lib/utils'

const icons = {
  success: <CheckCircle size={15} className="text-status-ready shrink-0" />,
  error: <AlertCircle size={15} className="text-status-failed shrink-0" />,
  info: <Info size={15} className="text-accent shrink-0" />,
}

const styles: Record<ToastMessage['type'], string> = {
  success: 'border-status-ready/20',
  error: 'border-status-failed/20',
  info: 'border-accent/20',
}

function Toast({ toast }: { toast: ToastMessage }) {
  const remove = useToastStore((s) => s.removeToast)
  return (
    <div
      className={cn(
        'flex items-start gap-3 rounded-xl border bg-bg-elevated px-4 py-3 shadow-elevated',
        'animate-slide-up w-80 max-w-full',
        styles[toast.type]
      )}
    >
      {icons[toast.type]}
      <p className="flex-1 text-sm text-txt-primary leading-snug">{toast.message}</p>
      <button
        onClick={() => remove(toast.id)}
        className="text-txt-muted hover:text-txt-primary transition-colors shrink-0 mt-0.5"
      >
        <X size={13} />
      </button>
    </div>
  )
}

export function Toaster() {
  const toasts = useToastStore((s) => s.toasts)

  if (toasts.length === 0) return null

  return (
    <div className="fixed bottom-5 right-5 z-[100] flex flex-col gap-2 items-end">
      {toasts.map((t) => (
        <Toast key={t.id} toast={t} />
      ))}
    </div>
  )
}
