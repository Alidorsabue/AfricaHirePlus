/**
 * Contexte de notifications toast : succès, erreur, info.
 * Utilisation : const { toast } = useToast(); toast.success('Message');
 */
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

export type ToastType = 'success' | 'error' | 'info'

export interface ToastItem {
  id: number
  type: ToastType
  message: string
  duration?: number
}

interface ToastContextValue {
  toasts: ToastItem[]
  toast: {
    success: (message: string, duration?: number) => void
    error: (message: string, duration?: number) => void
    info: (message: string, duration?: number) => void
  }
  removeToast: (id: number) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

let nextId = 0
const DEFAULT_DURATION = 4000

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const removeToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const addToast = useCallback(
    (type: ToastType, message: string, duration = DEFAULT_DURATION) => {
      const id = ++nextId
      setToasts((prev) => [...prev, { id, type, message, duration }])
      if (duration > 0) {
        setTimeout(() => removeToast(id), duration)
      }
    },
    [removeToast]
  )

  const toast = useMemo(
    () => ({
      success: (message: string, duration?: number) =>
        addToast('success', message, duration ?? DEFAULT_DURATION),
      error: (message: string, duration?: number) =>
        addToast('error', message, duration ?? DEFAULT_DURATION),
      info: (message: string, duration?: number) =>
        addToast('info', message, duration ?? DEFAULT_DURATION),
    }),
    [addToast]
  )

  const value = useMemo(
    () => ({ toasts, toast, removeToast }),
    [toasts, toast, removeToast]
  )

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastContainer toasts={toasts} removeToast={removeToast} />
    </ToastContext.Provider>
  )
}

function ToastContainer({
  toasts,
  removeToast,
}: {
  toasts: ToastItem[]
  removeToast: (id: number) => void
}) {
  if (toasts.length === 0) return null
  return (
    <div
      className="fixed right-4 top-4 z-[9999] flex flex-col gap-2"
      aria-live="polite"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          role="alert"
          className={`flex min-w-[280px] max-w-md items-center rounded-lg border px-4 py-3 shadow-lg ${
            t.type === 'success'
              ? 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-200'
              : t.type === 'error'
                ? 'border-red-200 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-900/30 dark:text-red-200'
                : 'border-slate-200 bg-white text-slate-800 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200'
          }`}
        >
          <span className="flex-1 text-sm font-medium">{t.message}</span>
          <button
            type="button"
            onClick={() => removeToast(t.id)}
            className="ml-2 rounded p-1 opacity-70 hover:opacity-100"
            aria-label="Fermer"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  )
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) {
    throw new Error('useToast must be used within ToastProvider')
  }
  return ctx
}
