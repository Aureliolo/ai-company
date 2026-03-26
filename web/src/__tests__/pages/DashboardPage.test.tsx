import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import type { UseDashboardDataReturn } from '@/hooks/useDashboardData'
import type { OverviewMetrics, BudgetConfig } from '@/api/types'

const mockOverview: OverviewMetrics = {
  total_tasks: 24,
  tasks_by_status: {
    created: 2, assigned: 3, in_progress: 8, in_review: 2, completed: 5,
    blocked: 1, failed: 1, interrupted: 1, cancelled: 1,
  },
  total_agents: 10,
  total_cost_usd: 42.17,
  budget_remaining_usd: 457.83,
  budget_used_percent: 8.43,
  cost_7d_trend: [
    { timestamp: '2026-03-20', value: 5 },
    { timestamp: '2026-03-21', value: 6 },
  ],
  active_agents_count: 5,
  idle_agents_count: 4,
}

const mockBudgetConfig: BudgetConfig = {
  total_monthly: 500,
  alerts: { warn_at: 80, critical_at: 95, hard_stop_at: 100 },
  per_task_limit: 10,
  per_agent_daily_limit: 20,
  auto_downgrade: { enabled: false, threshold: 90, downgrade_map: [], boundary: 'task_assignment' },
  reset_day: 1,
}

const defaultHookReturn: UseDashboardDataReturn = {
  overview: mockOverview,
  forecast: null,
  departmentHealths: [],
  activities: [],
  budgetConfig: mockBudgetConfig,
  orgHealthPercent: null,
  loading: false,
  error: null,
  wsConnected: true,
  wsSetupError: null,
}

let hookReturn = { ...defaultHookReturn }

const getDashboardData = vi.fn(() => hookReturn)
vi.mock('@/hooks/useDashboardData', () => {
  const hookName = 'useDashboardData'
  return { [hookName]: () => getDashboardData() }
})

async function renderDashboard() {
  const { default: DashboardPage } = await import('@/pages/DashboardPage')
  return render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  )
}

describe('DashboardPage', () => {
  beforeEach(() => {
    hookReturn = { ...defaultHookReturn }
  })

  it('renders page heading', async () => {
    await renderDashboard()
    expect(screen.getByText('Overview')).toBeInTheDocument()
  })

  it('renders loading skeleton when loading with no data', async () => {
    hookReturn = { ...defaultHookReturn, loading: true, overview: null }
    await renderDashboard()
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('renders 4 metric cards', async () => {
    await renderDashboard()
    expect(screen.getByText('TASKS')).toBeInTheDocument()
    expect(screen.getByText('ACTIVE AGENTS')).toBeInTheDocument()
    expect(screen.getByText('SPEND')).toBeInTheDocument()
    expect(screen.getByText('PENDING APPROVALS')).toBeInTheDocument()
  })

  it('renders metric values', async () => {
    await renderDashboard()
    expect(screen.getByText('24')).toBeInTheDocument() // total_tasks
    expect(screen.getByText('5')).toBeInTheDocument()  // active_agents
  })

  it('renders Org Health section', async () => {
    await renderDashboard()
    expect(screen.getByText('Org Health')).toBeInTheDocument()
  })

  it('renders Activity section', async () => {
    await renderDashboard()
    expect(screen.getByText('Activity')).toBeInTheDocument()
  })

  it('renders Budget Burn section', async () => {
    await renderDashboard()
    expect(screen.getByText('Budget Burn')).toBeInTheDocument()
  })

  it('shows error banner when error is set', async () => {
    hookReturn = { ...defaultHookReturn, error: 'Connection lost' }
    await renderDashboard()
    expect(screen.getByText('Connection lost')).toBeInTheDocument()
  })

  it('does not show skeleton when loading but data already exists', async () => {
    hookReturn = { ...defaultHookReturn, loading: true }
    await renderDashboard()
    // Should show the page, not the skeleton
    expect(screen.getByText('Overview')).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('shows WebSocket disconnect warning when not connected', async () => {
    hookReturn = { ...defaultHookReturn, wsConnected: false }
    await renderDashboard()
    expect(screen.getByText(/disconnected/i)).toBeInTheDocument()
  })
})
