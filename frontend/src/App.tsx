import { BrowserRouter, NavLink, Navigate, Route, Routes } from 'react-router-dom'

import { Overview } from '@/features/overview/Overview'
import { History } from '@/features/history/History'
import { RepaymentExplorer } from '@/features/scenario/RepaymentExplorer'
import { StatementEditor } from '@/features/statement/StatementEditor'
import { cn } from '@/lib/utils'

// The demo covers a single seeded statement period. Deriving it from browser
// time would disagree with the backend's stored period, so it is explicit.
const STATEMENT_PERIOD = '2026-08-01'

const NAV_ITEMS = [
  { to: '/overview', label: 'Overview' },
  { to: '/statement', label: 'Update my information' },
  { to: '/history', label: 'History' },
  { to: '/repayment', label: 'Explore a repayment' },
]

function Navigation() {
  return (
    <nav aria-label="Sections" className="mb-8 flex justify-center gap-2">
      {NAV_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className={({ isActive }) =>
            cn(
              'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
              isActive
                ? 'bg-foreground text-background'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground',
            )
          }
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  )
}

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-svh bg-muted/30">
        <main className="mx-auto max-w-3xl px-4 py-10 sm:py-16">
          <h1 className="mb-6 text-center text-2xl font-semibold tracking-tight text-foreground">
            Your financial health
          </h1>
          <Navigation />
          <Routes>
            <Route path="/" element={<Navigate to="/overview" replace />} />
            <Route path="/overview" element={<Overview />} />
            <Route
              path="/statement"
              element={<StatementEditor statementPeriod={STATEMENT_PERIOD} />}
            />
            <Route path="/history" element={<History />} />
            <Route path="/repayment" element={<RepaymentExplorer />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
