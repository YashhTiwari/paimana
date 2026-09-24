import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Search, ChevronLeft, ChevronRight } from 'lucide-react'
import api from '../api/client.js'
import { Card, RiskBadge, fmtCr, fmtPct } from '../components/ui.jsx'
import { LoadingState, ErrorState, EmptyState } from '../components/StatusStates.jsx'

const PAGE_SIZE = 25

export default function Projects() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const [search, setSearch] = useState(searchParams.get('search') || '')
  const [stateFilter, setStateFilter] = useState(searchParams.get('state') || '')
  const [sectorFilter, setSectorFilter] = useState(searchParams.get('sector') || '')
  const [riskLevel, setRiskLevel] = useState(searchParams.get('risk_level') || '')
  const [page, setPage] = useState(0)

  const [states, setStates] = useState([])
  const [sectors, setSectors] = useState([])

  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Load filter option lists once
  useEffect(() => {
    api.listStates().then((r) => setStates(r.states || [])).catch(() => {})
    api.listSectors().then((r) => setSectors(r.sectors || [])).catch(() => {})
  }, [])

  // Debounce search input
  useEffect(() => {
    const handle = setTimeout(() => setPage(0), 400)
    return () => clearTimeout(handle)
  }, [search])

  const fetchProjects = () => {
    setLoading(true)
    setError(null)
    api
      .listProjects({
        search: search || undefined,
        state: stateFilter || undefined,
        sector: sectorFilter || undefined,
        risk_level: riskLevel || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      })
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

  useEffect(() => {
    fetchProjects()
    const params = {}
    if (search) params.search = search
    if (stateFilter) params.state = stateFilter
    if (sectorFilter) params.sector = sectorFilter
    if (riskLevel) params.risk_level = riskLevel
    setSearchParams(params, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, stateFilter, sectorFilter, riskLevel, page])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-ink-900">Projects</h1>
        <p className="text-sm text-ink-500">Browse, search and filter all monitored infrastructure projects.</p>
      </div>

      <Card>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div className="relative md:col-span-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-ink-500" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search project name..."
              className="w-full rounded-lg border border-ink-300/60 bg-white pl-9 pr-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
            />
          </div>

          <select
            value={stateFilter}
            onChange={(e) => { setStateFilter(e.target.value); setPage(0) }}
            className="rounded-lg border border-ink-300/60 bg-white px-3 py-2 text-sm outline-none focus:border-brand-500"
          >
            <option value="">All States</option>
            {states.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>

          <select
            value={sectorFilter}
            onChange={(e) => { setSectorFilter(e.target.value); setPage(0) }}
            className="rounded-lg border border-ink-300/60 bg-white px-3 py-2 text-sm outline-none focus:border-brand-500"
          >
            <option value="">All Sectors (Agencies)</option>
            {sectors.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>

          <select
            value={riskLevel}
            onChange={(e) => { setRiskLevel(e.target.value); setPage(0) }}
            className="rounded-lg border border-ink-300/60 bg-white px-3 py-2 text-sm outline-none focus:border-brand-500"
          >
            <option value="">All Risk Levels</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>
        </div>
      </Card>

      <Card
        title={`${total.toLocaleString('en-IN')} project(s) found`}
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
          <LoadingState label="Loading projects..." />
        ) : error ? (
          <ErrorState message={error} onRetry={fetchProjects} />
        ) : rows.length === 0 ? (
          <EmptyState label="No projects match these filters." hint="Try adjusting search or filters." />
        ) : (
          <div className="overflow-x-auto -mx-5">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-ink-500 border-b border-ink-300/40">
                  <th className="px-5 py-2 font-medium">Project ID</th>
                  <th className="px-5 py-2 font-medium">Project Name</th>
                  <th className="px-5 py-2 font-medium">State</th>
                  <th className="px-5 py-2 font-medium">Sector</th>
                  <th className="px-5 py-2 font-medium text-right">Original Cost</th>
                  <th className="px-5 py-2 font-medium text-right">Revised Cost</th>
                  <th className="px-5 py-2 font-medium text-right">Expenditure</th>
                  <th className="px-5 py-2 font-medium text-right">Progress</th>
                  <th className="px-5 py-2 font-medium text-right">Risk Score</th>
                  <th className="px-5 py-2 font-medium">Risk Level</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((p) => (
                  <tr
                    key={p.project_id}
                    onClick={() => navigate(`/projects/${p.project_id}`)}
                    className="border-b border-ink-300/20 hover:bg-surface-muted cursor-pointer transition-colors"
                  >
                    <td className="px-5 py-2.5 text-ink-500">{p.project_id}</td>
                    <td className="px-5 py-2.5 font-medium text-ink-900 max-w-xs truncate">{p.project_name}</td>
                    <td className="px-5 py-2.5 text-ink-700">{p.state}</td>
                    <td className="px-5 py-2.5 text-ink-700 max-w-[10rem] truncate">{p.agency}</td>
                    <td className="px-5 py-2.5 text-right text-ink-700">{fmtCr(p.original_cost)}</td>
                    <td className="px-5 py-2.5 text-right text-ink-700">{fmtCr(p.revised_cost)}</td>
                    <td className="px-5 py-2.5 text-right text-ink-700">{fmtCr(p.expenditure)}</td>
                    <td className="px-5 py-2.5 text-right text-ink-700">{fmtPct(p.physical_progress)}</td>
                    <td className="px-5 py-2.5 text-right font-semibold text-ink-900">
                      {p.risk_score != null ? p.risk_score.toFixed(1) : '—'}
                    </td>
                    <td className="px-5 py-2.5"><RiskBadge level={p.risk_level} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
