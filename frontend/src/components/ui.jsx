export function StatCard({ label, value, icon: Icon, accent = 'brand', sub }) {
  const accentClasses = {
    brand: 'bg-brand-50 text-brand-700',
    red: 'bg-red-50 text-red-700',
    amber: 'bg-amber-50 text-amber-700',
    slate: 'bg-slate-100 text-slate-700',
  }[accent]

  return (
    <div className="rounded-xl border border-ink-300/40 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-ink-500">{label}</p>
          <p className="mt-2 text-2xl font-bold text-ink-900">{value}</p>
          {sub && <p className="mt-1 text-xs text-ink-500">{sub}</p>}
        </div>
        {Icon && (
          <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${accentClasses}`}>
            <Icon className="h-5 w-5" />
          </div>
        )}
      </div>
    </div>
  )
}

const RISK_STYLES = {
  HIGH: 'bg-red-50 text-red-700 border-red-200',
  MEDIUM: 'bg-amber-50 text-amber-700 border-amber-200',
  LOW: 'bg-brand-50 text-brand-700 border-brand-200',
  UNKNOWN: 'bg-slate-100 text-slate-600 border-slate-200',
}

export function RiskBadge({ level }) {
  const key = (level || 'UNKNOWN').toUpperCase()
  const style = RISK_STYLES[key] || RISK_STYLES.UNKNOWN
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${style}`}>
      {key}
    </span>
  )
}

const SEVERITY_STYLES = {
  HIGH: 'bg-red-50 text-red-700 border-red-200',
  MEDIUM: 'bg-amber-50 text-amber-700 border-amber-200',
  LOW: 'bg-brand-50 text-brand-700 border-brand-200',
}

export function SeverityBadge({ severity }) {
  const key = (severity || '').toUpperCase()
  const style = SEVERITY_STYLES[key] || 'bg-slate-100 text-slate-600 border-slate-200'
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${style}`}>
      {key || 'N/A'}
    </span>
  )
}

export function Card({ title, subtitle, children, className = '', actions }) {
  return (
    <div className={`rounded-xl border border-ink-300/40 bg-white p-5 shadow-sm ${className}`}>
      {(title || actions) && (
        <div className="mb-4 flex items-start justify-between gap-2">
          <div>
            {title && <h3 className="text-sm font-semibold text-ink-900">{title}</h3>}
            {subtitle && <p className="text-xs text-ink-500 mt-0.5">{subtitle}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </div>
  )
}

export function fmtCr(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `₹${Number(value).toLocaleString('en-IN', { maximumFractionDigits: 2 })} Cr`
}

export function fmtPct(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${Number(value).toFixed(1)}%`
}

export function fmtNum(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return Number(value).toLocaleString('en-IN')
}
