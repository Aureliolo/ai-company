import { render, screen } from '@testing-library/react'
import { useAnalyticsStore } from '@/stores/analytics'
import { StatusBar } from '@/components/layout/StatusBar'

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
    // Should show 0 or -- for agent/task counts
    expect(screen.getByText('0 agents')).toBeInTheDocument()
    expect(screen.getByText('0 active')).toBeInTheDocument()
    expect(screen.getByText('0 tasks')).toBeInTheDocument()
  })

  it('shows live values from analytics store', () => {
    useAnalyticsStore.setState({
      overview: {
        total_tasks: 42,
        tasks_by_status: {} as never,
        total_agents: 12,
        total_cost_usd: 85.5,
        budget_remaining_usd: 414.5,
        budget_used_percent: 17.1,
        cost_7d_trend: [],
        active_agents_count: 8,
        idle_agents_count: 3,
      },
    })

    render(<StatusBar />)
    expect(screen.getByText('12 agents')).toBeInTheDocument()
    expect(screen.getByText('8 active')).toBeInTheDocument()
    expect(screen.getByText('42 tasks')).toBeInTheDocument()
  })

  it('renders system status indicator', () => {
    render(<StatusBar />)
    expect(screen.getByText('all systems nominal')).toBeInTheDocument()
  })
})
