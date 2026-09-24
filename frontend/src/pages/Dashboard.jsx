import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts'
import {
  FolderKanban, AlertOctagon, AlertTriangle, ShieldCheck,
  IndianRupee, Wallet, TrendingUp, ArrowRight,
} from 'lucide-react'
import api from '../api/client.js'
import { Card, StatCard, RiskBadge, SeverityBadge, fmtCr, fmtPct, fmtNum } from '../components/ui.jsx'
import { LoadingState, ErrorState, EmptyState } from '../components/StatusStates.jsx'

const RISK_COLORS = { HIGH: '#dc2626', MEDIUM: '#d97706', LOW: '#0f9d76' }
const PROGRESS_BUCKETS = [
  { key: '0-20%', min: 0, max: 20 },
  { key: '20-40%', min: 20, max: 40 },
  { key: '40-60%', min: 40, max: 60 },
  { key: '60-80%', min: 60, max: 80 },
  { key: '80-100%', min: 80, max: 100.0001 },
]

function topN(counts, n = 10) {
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, n)
    .map(([name, count]) => ({ name, count }))
}

export default function Dashboard() {
  const [state, setState] = useState({ loading: true, error: null, summary: null, topRisk: [], alerts: [], allProjects: [] })

  const load = () => {
    setState((s) => ({ ...s, loading: true, error: null }))
    Promise.all([
      api.dashboardSummary(),
      api.topRiskProjects(10),
      api.listAlerts({ limit: 8 }),
      api.listProjects({ limit: 5000 }),
    ])
      .then(([summary, topRisk, alerts, projects]) => {
        setState({
          loading: false,
          error: null,
          summary,
          topRisk: topRisk.results || [],
          alerts: alerts.results || [],
          allProjects: projects.results || [],
        })
      })
      .catch((err) => setState((s) => ({ ...s, loading: false, error: err.message })))
  }

  useEffect(load, [])

  const sectorData = useMemo(() => {
    const counts = {}
    for (const p of state.allProjects) {
      const key = p.agency || 'Unknown'
      counts[key] = (counts[key] || 0) + 1
    }
    return topN(counts, 10)
  }, [state.allProjects])

  const stateData = useMemo(() => {
    const counts = {}
    for (const p of state.allProjects) {
      const key = p.state || 'Unknown'
      counts[key] = (counts[key] || 0) + 1
    }
    return topN(counts, 10)
  }, [state.allProjects])

  const progressData = useMemo(() => {
    return PROGRESS_BUCKETS.map(({ key, min, max }) => ({
      name: key,
      count: state.allProjects.filter(
        (p) => p.physical_progress !== null && p.physical_progress >= min && p.physical_progress < max
      ).length,
    }))
  }, [state.allProjects])

  if (state.loading) return <LoadingState label="Loading dashboard..." />
  if (state.error) return <ErrorState message={state.error} onRetry={load} />

  const { summary } = state
  const riskDist = summary.risk_level_distribution || {}
  const riskPieData = ['HIGH', 'MEDIUM', 'LOW']
    .filter((k) => riskDist[k])
    .map((k) => ({ name: k, value: riskDist[k] }))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-ink-900">Dashboard</h1>
        <p className="text-sm text-ink-500">
          Live data as of report month {summary.as_of_latest_report_month_available_per_project || '—'}
        </p>
      </div>

      {/* Top stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Projects" value={fmtNum(summary.total_projects)} icon={FolderKanban} accent="brand" />
        <StatCard label="High Risk" value={fmtNum(riskDist.HIGH || 0)} icon={AlertOctagon} accent="red" />
        <StatCard label="Medium Risk" value={fmtNum(riskDist.MEDIUM || 0)} icon={AlertTriangle} accent="amber" />
        <StatCard label="Low Risk" value={fmtNum(riskDist.LOW || 0)} icon={ShieldCheck} accent="brand" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCard
          label="Total Original Cost"
          value={fmtCr(summary.cost_summary?.total_original_cost_cr)}
          icon={IndianRupee}
          accent="slate"
        />
        <StatCard
          label="Total Revised Cost"
          value={fmtCr(summary.cost_summary?.total_revised_cost_cr)}
          icon={TrendingUp}
          accent="slate"
        />
        <StatCard
          label="Total Expenditure"
          value={fmtCr(summary.cost_summary?.total_expenditure_cr)}
          icon={Wallet}
          accent="slate"
        />
      </div>

      {/* Charts row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card title="Risk Distribution" subtitle="Projects by risk level">
          {riskPieData.length === 0 ? (
            <EmptyState label="No risk data available." />
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={riskPieData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2}>
                  {riskPieData.map((entry) => (
                    <Cell key={entry.name} fill={RISK_COLORS[entry.name]} />
                  ))}
                </Pie>
                <Legend />
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card title="Projects by Sector" subtitle="Top 10 executing agencies (used as sector)" className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={sectorData} layout="vertical" margin={{ left: 8, right: 16 }}>
              <CartesianGrid strokeDasharray="3 3" horizontal={false} />
              <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
              <YAxis
                type="category"
                dataKey="name"
                width={160}
                tick={{ fontSize: 10 }}
                tickFormatter={(v) => (v.length > 24 ? v.slice(0, 24) + '…' : v)}
              />
              <Tooltip />
              <Bar dataKey="count" fill="#0f9d76" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Charts row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="Projects by State" subtitle="Top 10 states by project count">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={stateData} margin={{ left: 0, right: 8 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-30} textAnchor="end" height={60} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#0a7f60" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Physical Progress Overview" subtitle="Distribution of latest reported progress %">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={progressData}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#2cc99a" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Top 10 high risk + recent alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card
          title="Top 10 High-Risk Projects"
          actions={
            <Link to="/projects?risk_level=HIGH" className="text-xs font-semibold text-brand-600 hover:text-brand-700 flex items-center gap-1">
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          }
        >
          {state.topRisk.length === 0 ? (
            <EmptyState label="No high-risk projects found." />
          ) : (
            <div className="divide-y divide-ink-300/30">
              {state.topRisk.map((p) => (
                <Link
                  key={p.project_id}
                  to={`/projects/${p.project_id}`}
                  className="flex items-center justify-between gap-3 py-2.5 hover:bg-surface-muted rounded-md px-2 -mx-2 transition-colors"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-ink-900 truncate">{p.project_name}</p>
                    <p className="text-xs text-ink-500">{p.state} &middot; ID {p.project_id}</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-sm font-semibold text-ink-900">{p.risk_score?.toFixed?.(1)}</span>
                    <RiskBadge level={p.risk_level} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </Card>

        <Card
          title="Recent Alerts"
          actions={
            <Link to="/alerts" className="text-xs font-semibold text-brand-600 hover:text-brand-700 flex items-center gap-1">
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          }
        >
          {state.alerts.length === 0 ? (
            <EmptyState label="No alerts found." />
          ) : (
            <div className="divide-y divide-ink-300/30">
              {state.alerts.map((a, idx) => (
                <div key={idx} className="py-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold text-ink-700">{a.alert_type}</span>
                    <SeverityBadge severity={a.severity} />
                  </div>
                  <p className="text-sm text-ink-900 mt-0.5 truncate">{a.project_name}</p>
                  <p className="text-xs text-ink-500 mt-0.5 line-clamp-2">{a.message}</p>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
