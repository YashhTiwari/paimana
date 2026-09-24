import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import api from '../api/client.js'
import { Card, SeverityBadge } from '../components/ui.jsx'
import { LoadingState, ErrorState, EmptyState } from '../components/StatusStates.jsx'

const PAGE_SIZE = 25
const TABS = [
  { key: '', label: 'All' },
  { key: 'HIGH', label: 'High' },
  { key: 'MEDIUM', label: 'Medium' },
  { key: 'LOW', label: 'Low' },
]

export default function Alerts() {
  const [severity, setSeverity] = useState('')
  const [page, setPage] = useState(0)
  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchAlerts = () => {
    setLoading(true)
    setError(null)
    api
      .listAlerts({ severity: severity || undefined, limit: PAGE_SIZE, offset: page * PAGE_SIZE })
      .then((res) => {
        setRows(res.results || [])
        setTotal(res.total_matching || 0)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }

  useEffect(fetchAlerts, [severity, page])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-ink-900">Alerts</h1>
        <p className="text-sm text-ink-500">Early-warning alerts generated from the STEP 4 rule-based engine.</p>
      </div>

      <div className="flex items-center gap-2">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => { setSeverity(tab.key); setPage(0) }}
            className={`rounded-full px-4 py-1.5 text-sm font-medium border transition-colors ${
              severity === tab.key
                ? 'bg-brand-500 text-white border-brand-500'
                : 'bg-white text-ink-700 border-ink-300/60 hover:border-brand-400'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <Card
        title={`${total.toLocaleString('en-IN')} alert(s)`}
        actions={
          <div className="flex items-center gap-2 text-xs text-ink-500">
            <button
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              className="rounded-md border border-ink-300/60 p-1.5 disabled:opacity-40"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </button>
            <span>Page {page + 1} of {totalPages}</span>
            <button
              disabled={page + 1 >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="rounded-md border border-ink-300/60 p-1.5 disabled:opacity-40"
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        }
      >
        {loading ? (
          <LoadingState label="Loading alerts..." />
        ) : error ? (
          <ErrorState message={error} onRetry={fetchAlerts} />
        ) : rows.length === 0 ? (
          <EmptyState label="No alerts match this filter." />
        ) : (
          <div className="divide-y divide-ink-300/30">
            {rows.map((a, idx) => (
              <div key={idx} className="py-3.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <SeverityBadge severity={a.severity} />
                    <span className="text-xs font-semibold uppercase tracking-wide text-ink-500">{a.alert_type}</span>
                  </div>
                  <Link
                    to={`/projects/${a.project_id}`}
                    className="text-xs font-semibold text-brand-600 hover:text-brand-700"
                  >
                    {a.project_name} (ID {a.project_id})
                  </Link>
                </div>
                <p className="text-sm text-ink-900 mt-1.5">{a.message}</p>
                <p className="text-xs text-ink-500 mt-1">{a.reason}</p>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
