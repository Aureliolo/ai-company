import { render, screen } from '@testing-library/react'
import { useAnalyticsStore } from '@/stores/analytics'
import { StatusBar } from '@/components/layout/StatusBar'
import { formatCurrency } from '@/utils/format'
import type { OverviewMetrics } from '@/api/types'

function makeOverview(overrides: Partial<OverviewMetrics> = {}): OverviewMetrics {
  return {
    total_tasks: 0,
    tasks_by_status: {
      created: 0, assigned: 0, in_progress: 0, in_review: 0, completed: 0,
      blocked: 0, failed: 0, interrupted: 0, cancelled: 0,
    } as OverviewMetrics['tasks_by_status'],
    total_agents: 0,
    total_cost_usd: 0,
    budget_remaining_usd: 0,
    budget_used_percent: 0,
    cost_7d_trend: [],
    active_agents_count: 0,
    idle_agents_count: 0,
    currency: 'EUR',
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

  it('renders SynthOrg brand text', () => {
    render(<StatusBar />)
    expect(screen.getByText('SynthOrg')).toBeInTheDocument()
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
        total_cost_usd: 85.5,
        budget_remaining_usd: 414.5,
        budget_used_percent: 17.1,
        active_agents_count: 8,
        idle_agents_count: 3,
      }),
    })

    render(<StatusBar />)
    expect(screen.getByText('12 agents')).toBeInTheDocument()
    expect(screen.getByText('8 active')).toBeInTheDocument()
    expect(screen.getByText('42 tasks')).toBeInTheDocument()
  })

  it('renders unknown system status before first poll', () => {
    render(<StatusBar />)
    expect(screen.getByText('checking...')).toBeInTheDocument()
  })

  it('shows cost placeholder when no data loaded', () => {
    render(<StatusBar />)
    expect(screen.getByText('$--')).toBeInTheDocument()
  })

  it('shows budget percentage when data loaded', () => {
    useAnalyticsStore.setState({
      overview: makeOverview({
        total_tasks: 10,
        total_agents: 5,
        total_cost_usd: 50,
        budget_remaining_usd: 450,
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
          blocked: 0, failed: 0, interrupted: 0, cancelled: 0,
        } as OverviewMetrics['tasks_by_status'],
        total_agents: 5,
        total_cost_usd: 50,
        budget_remaining_usd: 450,
        budget_used_percent: 10,
        active_agents_count: 3,
        idle_agents_count: 2,
      }),
    })
    render(<StatusBar />)
    expect(screen.getByText('3 in review')).toBeInTheDocument()
  })

  it('shows formatted currency for cost display (EUR default)', () => {
    useAnalyticsStore.setState({
      overview: makeOverview({ total_cost_usd: 1234.56 }),
    })
    render(<StatusBar />)
    expect(screen.getByText(formatCurrency(1234.56, 'EUR'))).toBeInTheDocument()
  })

  it('shows formatted currency for non-default currency', () => {
    useAnalyticsStore.setState({
      overview: makeOverview({ total_cost_usd: 99.5, currency: 'GBP' }),
    })
    render(<StatusBar />)
    expect(screen.getByText(formatCurrency(99.5, 'GBP'))).toBeInTheDocument()
  })

  it('renders the theme toggle', () => {
    render(<StatusBar />)
    expect(screen.getByRole('button', { name: 'Theme preferences' })).toBeInTheDocument()
  })
})
