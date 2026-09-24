import { Loader2, Inbox, AlertCircle } from 'lucide-react'

export function LoadingState({ label = 'Loading data...' }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-ink-500">
      <Loader2 className="h-6 w-6 animate-spin text-brand-500" />
      <p className="text-sm">{label}</p>
    </div>
  )
}

export function EmptyState({ label = 'No records found.', hint }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-16 text-ink-500">
      <Inbox className="h-8 w-8 text-ink-300" />
      <p className="text-sm font-medium">{label}</p>
      {hint && <p className="text-xs text-ink-500">{hint}</p>}
    </div>
  )
}

export function ErrorState({ message = 'Something went wrong.', onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <AlertCircle className="h-8 w-8 text-red-500" />
      <p className="text-sm font-medium text-ink-900">Could not load data</p>
      <p className="text-xs text-ink-500 max-w-md">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-2 rounded-md bg-brand-500 px-4 py-2 text-xs font-semibold text-white hover:bg-brand-600 transition-colors"
        >
          Try again
        </button>
      )}
    </div>
  )
}
