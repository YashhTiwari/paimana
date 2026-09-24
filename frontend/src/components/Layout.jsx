import { NavLink } from 'react-router-dom'
import { LayoutDashboard, FolderKanban, AlertTriangle, Activity } from 'lucide-react'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/projects', label: 'Projects', icon: FolderKanban },
  { to: '/alerts', label: 'Alerts', icon: AlertTriangle },
]

export default function Layout({ children }) {
  return (
    <div className="min-h-screen flex bg-surface-muted">
      <aside className="hidden md:flex md:flex-col w-64 shrink-0 bg-ink-900 text-white">
        <div className="flex items-center gap-2 px-6 py-6 border-b border-white/10">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-500">
            <Activity className="h-5 w-5 text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold leading-tight">PAIMANA</p>
            <p className="text-xs text-white/50 leading-tight">Infra Monitoring</p>
          </div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-brand-500 text-white'
                    : 'text-white/70 hover:bg-white/5 hover:text-white'
                }`
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="px-6 py-4 border-t border-white/10 text-xs text-white/40">
          SIH 2026 &middot; PS 26103
        </div>
      </aside>

      <div className="flex-1 min-w-0 flex flex-col">
        <header className="md:hidden sticky top-0 z-10 flex items-center gap-2 bg-ink-900 text-white px-4 py-3">
          <Activity className="h-5 w-5 text-brand-400" />
          <span className="font-semibold text-sm">PAIMANA Infra Monitoring</span>
        </header>

        <nav className="md:hidden flex overflow-x-auto gap-2 bg-white border-b border-ink-300/50 px-3 py-2">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium ${
                  isActive ? 'bg-brand-500 text-white' : 'text-ink-700 bg-surface-muted'
                }`
              }
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </NavLink>
          ))}
        </nav>

        <main className="flex-1 min-w-0 p-4 md:p-8">{children}</main>
      </div>
    </div>
  )
}
