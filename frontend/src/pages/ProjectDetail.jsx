import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { ArrowLeft, MapPin, Building2, Landmark, Gauge, IndianRupee, Wallet, TrendingUp, Info } from 'lucide-react'
import api from '../api/client.js'
import { Card, StatCard, RiskBadge, fmtCr, fmtPct } from '../components/ui.jsx'
import { LoadingState, ErrorState } from '../components/StatusStates.jsx'

function RiskMeter({ label, value }) {
  const v = value == null ? null : Math.max(0, Math.min(100, value))
  const color = v == null ? '#9ca3af' : v >= 61 ? '#dc2626' : v >= 31 ? '#d97706' : '#0f9d76'
  return (
    <div>
      <div className="flex items-center justify-between text-xs mb-1">
        <span className="font-medium text-ink-700">{label}</span>
        <span className="font-semibold text-ink-900">{v == null ? 'N/A' : v.toFixed(0)}</span>
      </div>
      <div className="h-2 rounded-full bg-ink-300/30 overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${v ?? 0}%`, backgroundColor: color }} />
      </div>
    </div>
  )
}

export default function ProjectDetail() {
  const { projectId } = useParams()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [project, setProject] = useState(null)
  const [history, setHistory] = useState([])

  const load = () => {
    setLoading(true)
    setError(null)
    Promise.all([api.getProject(projectId), api.getProjectHistory(projectId)])
      .then(([projectRes, historyRes]) => {
        setProject(projectRes)
        setHistory(historyRes.history || [])
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }

  useEffect(load, [projectId])

  if (loading) return <LoadingState label="Loading project..." />
  if (error) return <ErrorState message={error} onRetry={load} />
  if (!project) return null

  const explanationLines = (project.risk_explanation || '')
    .split('|')
    .map((s) => s.trim())
    .filter(Boolean)

  const costComparisonData = [
    { name: 'Original Cost', value: project.original_cost },
    { name: 'Revised Cost', value: project.revised_cost },
  ]

  return (
    <div className="space-y-6">
      <Link to="/projects" className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-600 hover:text-brand-700">
        <ArrowLeft className="h-4 w-4" /> Back to Projects
      </Link>

      {/* Header */}
      <Card>
        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
          <div>
            <h1 className="text-lg font-bold text-ink-900">{project.project_name}</h1>
            <p className="text-xs text-ink-500 mt-1">Project ID: {project.project_id}</p>
            <div className="flex flex-wrap gap-4 mt-3 text-sm text-ink-700">
              <span className="flex items-center gap-1.5"><MapPin className="h-4 w-4 text-brand-500" /> {project.state}</span>
              <span className="flex items-center gap-1.5"><Building2 className="h-4 w-4 text-brand-500" /> Sector: {project.agency}</span>
              <span className="flex items-center gap-1.5"><Landmark className="h-4 w-4 text-brand-500" /> Agency/Ministry: {project.agency}</span>
            </div>
          </div>
          <RiskBadge level={project.risk_level} />
        </div>
      </Card>

      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard label="Original Cost" value={fmtCr(project.original_cost)} icon={IndianRupee} accent="slate" />
        <StatCard label="Revised Cost" value={fmtCr(project.revised_cost)} icon={TrendingUp} accent="slate" />
        <StatCard label="Expenditure" value={fmtCr(project.expenditure)} icon={Wallet} accent="slate" />
        <StatCard label="Physical Progress" value={fmtPct(project.physical_progress)} icon={Gauge} accent="brand" />
        <StatCard
          label="Risk Score"
          value={project.risk_score != null ? project.risk_score.toFixed(1) : '—'}
          icon={Gauge}
          accent={project.risk_level === 'HIGH' ? 'red' : project.risk_level === 'MEDIUM' ? 'amber' : 'brand'}
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="Physical Progress Trend" subtitle="April - July 2026">
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={history}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="report_month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} domain={[0, 100]} />
              <Tooltip />
              <Line type="monotone" dataKey="physical_progress" name="Progress %" stroke="#0f9d76" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        <Card title="Expenditure Trend" subtitle="Cumulative expenditure, Rs. Crore">
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={history}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="report_month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line type="monotone" dataKey="expenditure" name="Expenditure (Cr)" stroke="#0a7f60" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <Card title="Original vs Revised Cost" subtitle="Rs. Crore" className="lg:w-1/2">
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={costComparisonData}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey="value" fill="#0f9d76" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </Card>

      {/* Risk breakdown + explanation */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="Risk Breakdown">
          <div className="space-y-4">
            <RiskMeter label="Progress Risk" value={project.progress_risk} />
            <RiskMeter label="Schedule Risk" value={project.schedule_risk} />
            <RiskMeter label="Cost Risk" value={project.cost_risk} />
            <RiskMeter label="Trend Risk" value={project.trend_risk} />
          </div>
        </Card>

        <Card title="Why is this project at risk?">
          {explanationLines.length === 0 ? (
            <p className="text-sm text-ink-500">No explanation available.</p>
          ) : (
            <ul className="space-y-2">
              {explanationLines.map((line, idx) => (
                <li key={idx} className="flex items-start gap-2 text-sm text-ink-700">
                  <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-brand-500 shrink-0" />
                  {line}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {/* Forecast placeholder */}
      <Card title="Prototype Forecast">
        <div className="flex items-start gap-2 text-sm text-ink-500">
          <Info className="h-4 w-4 mt-0.5 shrink-0" />
          <p>
            A forecast/prediction endpoint is not yet available on the backend (STEP 5 only implements
            descriptive risk scoring, not predictive modelling). This section will populate once a
            forecast API is added - no forecast is shown here to avoid displaying invented data.
          </p>
        </div>
      </Card>
    </div>
  )
}
