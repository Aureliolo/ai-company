import { render, screen } from '@testing-library/react'
import { useAnalyticsStore } from '@/stores/analytics'
import { StatusBar } from '@/components/layout/StatusBar'
import { formatCurrency } from '@/utils/format'
import { DEFAULT_CURRENCY } from '@/utils/currencies'
import type { OverviewMetrics } from '@/api/types'

function makeOverview(overrides: Partial<OverviewMetrics> = {}): OverviewMetrics {
  return {
    total_tasks: 0,
    tasks_by_status: {
      created: 0, assigned: 0, in_progress: 0, in_review: 0, completed: 0,
      blocked: 0, failed: 0, interrupted: 0, suspended: 0, cancelled: 0,
    } as OverviewMetrics['tasks_by_status'],
    total_agents: 0,
    total_cost: 0,
    budget_remaining: 0,
    budget_used_percent: 0,
    cost_7d_trend: [],
    active_agents_count: 0,
    idle_agents_count: 0,
    currency: DEFAULT_CURRENCY,
    ...overrides,
  }
}

vi.mock('@/hooks/usePolling', () => ({
  usePolling: vi.fn().mockReturnValue({
    active: false, error: null, start: vi.fn(), stop: vi.fn(),
  }),
}))

vi.mock('@/api/endpoints/health', () => ({
  getHealth: vi.fn().mockResolvedValue({ status: 'ok', persistence: true, message_bus: true, version: '0.4.9', uptime_seconds: 3600 }),
}))

vi.mock('@/api/endpoints/analytics', () => ({
  getOverviewMetrics: vi.fn().mockResolvedValue(null),
  getForecast: vi.fn().mockResolvedValue(null),
}))

function resetStore() {
  useAnalyticsStore.setState({
    overview: null,
    forecast: null,
    departmentHealths: [],
    activities: [],
    budgetConfig: null,
    orgHealthPercent: null,
    loading: false,
    error: null,
  })
}

describe('StatusBar', () => {
  beforeEach(() => {
    resetStore()
  })

  it('does not duplicate the SynthOrg brand text (sidebar already shows it)', () => {
    render(<StatusBar />)
    // The SynthOrg brand text lives in the sidebar header -- the top
    // StatusBar intentionally omits it so the row can carry status
    // counters without visual redundancy.
    expect(screen.queryByText('SynthOrg')).not.toBeInTheDocument()
  })

  it('shows placeholder values when no data loaded', () => {
    render(<StatusBar />)
    // Should show -- placeholders, not zeros
    const dashes = screen.getAllByText('--')
    expect(dashes.length).toBeGreaterThanOrEqual(3)
  })

  it('shows live values from analytics store', () => {
    useAnalyticsStore.setState({
      overview: makeOverview({
        total_tasks: 42,
        total_agents: 12,
        total_cost: 85.5,
        budget_remaining: 414.5,
        budget_used_percent: 17.1,
        active_agents_count: 8,
        idle_agents_count: 3,
      }),
    })

    render(<StatusBar />)
    expect(screen.getByText('12 agents')).toBeInTheDocument()
    expect(screen.getByText('8 active')).toBeInTheDocument()
    expect(screen.getByText('3 idle')).toBeInTheDocument()
    expect(screen.getByText('42 tasks')).toBeInTheDocument()
  })

  it('renders unknown system status before first poll', () => {
    render(<StatusBar />)
    expect(screen.getByText('checking...')).toBeInTheDocument()
  })

  it('shows cost placeholder when no data loaded', () => {
    render(<StatusBar />)
    // Cost placeholder is a neutral ``--`` (no hardcoded currency
    // symbol). Scope to the ``spend ... today`` chip to avoid matching
    // sibling placeholders (``-- agents``, ``-- active``, ...).
    const spendLabel = screen.getByText('spend')
    const spendChip = spendLabel.parentElement
    expect(spendChip).toHaveTextContent(/spend\s*--\s*today/)
  })

  it('shows budget percentage when data loaded', () => {
    useAnalyticsStore.setState({
      overview: makeOverview({
        total_tasks: 10,
        total_agents: 5,
        total_cost: 50,
        budget_remaining: 450,
        budget_used_percent: 10,
        active_agents_count: 3,
        idle_agents_count: 2,
      }),
    })
    render(<StatusBar />)
    expect(screen.getByText('10%')).toBeInTheDocument()
  })

  it('shows in-review count when non-zero', () => {
    useAnalyticsStore.setState({
      overview: makeOverview({
        total_tasks: 10,
        tasks_by_status: {
          created: 0, assigned: 0, in_progress: 0, in_review: 3, completed: 0,
          blocked: 0, failed: 0, interrupted: 0, suspended: 0, cancelled: 0,
        } as OverviewMetrics['tasks_by_status'],
        total_agents: 5,
        total_cost: 50,
        budget_remaining: 450,
        budget_used_percent: 10,
        active_agents_count: 3,
        idle_agents_count: 2,
      }),
    })
    render(<StatusBar />)
    expect(screen.getByText('3 in review')).toBeInTheDocument()
  })

  it('shows formatted currency for cost display (default currency)', () => {
    const overview = makeOverview({ total_cost: 1234.56 })
    useAnalyticsStore.setState({ overview })
    render(<StatusBar />)
    expect(
      screen.getByText(formatCurrency(1234.56, overview.currency)),
    ).toBeInTheDocument()
  })

  it('shows formatted currency for non-default currency', () => {
    // lint-allow: regional-defaults
    const overview = makeOverview({ total_cost: 99.5, currency: 'GBP' })
    useAnalyticsStore.setState({ overview })
    render(<StatusBar />)
    expect(
      screen.getByText(formatCurrency(99.5, overview.currency)),
    ).toBeInTheDocument()
  })

  it('renders the theme toggle', () => {
    render(<StatusBar />)
    expect(screen.getByRole('button', { name: 'Theme preferences' })).toBeInTheDocument()
  })
})
