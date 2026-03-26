import type { Meta, StoryObj } from '@storybook/react'
import { MemoryRouter } from 'react-router'
import { useAnalyticsStore } from '@/stores/analytics'
import DashboardPage from '../DashboardPage'
import type { ActivityItem, DepartmentHealth, OverviewMetrics, BudgetConfig, ForecastResponse } from '@/api/types'

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
    { timestamp: '2026-03-21', value: 6.2 },
    { timestamp: '2026-03-22', value: 7.1 },
    { timestamp: '2026-03-23', value: 5.5 },
    { timestamp: '2026-03-24', value: 8.3 },
    { timestamp: '2026-03-25', value: 6.9 },
    { timestamp: '2026-03-26', value: 5.17 },
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

const mockForecast: ForecastResponse = {
  horizon_days: 7,
  projected_total_usd: 65,
  daily_projections: [
    { day: '2026-03-27', projected_spend_usd: 6.5 },
    { day: '2026-03-28', projected_spend_usd: 7.0 },
    { day: '2026-03-29', projected_spend_usd: 6.8 },
  ],
  days_until_exhausted: null,
  confidence: 0.85,
  avg_daily_spend_usd: 6.3,
}

const mockDepartments: DepartmentHealth[] = [
  { name: 'engineering', display_name: 'Engineering', health_percent: 92, agent_count: 4, task_count: 12, cost_usd: 18.5 },
  { name: 'design', display_name: 'Design', health_percent: 78, agent_count: 2, task_count: 5, cost_usd: 8.2 },
  { name: 'product', display_name: 'Product', health_percent: 85, agent_count: 2, task_count: 4, cost_usd: 7.1 },
  { name: 'operations', display_name: 'Operations', health_percent: 60, agent_count: 1, task_count: 3, cost_usd: 4.3 },
]

const mockActivities: ActivityItem[] = [
  { id: '1', timestamp: new Date(Date.now() - 60_000).toISOString(), agent_name: 'agent-cto', action_type: 'task.created', description: 'Created auth module task', task_id: 'task-42', department: 'engineering' },
  { id: '2', timestamp: new Date(Date.now() - 120_000).toISOString(), agent_name: 'agent-designer', action_type: 'task.status_changed', description: 'Completed wireframe review', task_id: 'task-38', department: 'design' },
  { id: '3', timestamp: new Date(Date.now() - 300_000).toISOString(), agent_name: 'agent-devops', action_type: 'agent.status_changed', description: 'Changed status to idle', task_id: null, department: 'operations' },
  { id: '4', timestamp: new Date(Date.now() - 600_000).toISOString(), agent_name: 'agent-qa', action_type: 'approval.submitted', description: 'Requested deployment approval', task_id: 'task-40', department: 'quality_assurance' },
  { id: '5', timestamp: new Date(Date.now() - 900_000).toISOString(), agent_name: 'agent-eng-2', action_type: 'budget.record_added', description: 'Recorded $2.30 cost', task_id: 'task-35', department: 'engineering' },
]

function setStoreState(overrides: Partial<ReturnType<typeof useAnalyticsStore.getState>> = {}) {
  useAnalyticsStore.setState({
    overview: mockOverview,
    forecast: mockForecast,
    departmentHealths: mockDepartments,
    activities: mockActivities,
    budgetConfig: mockBudgetConfig,
    orgHealthPercent: 79,
    loading: false,
    error: null,
    ...overrides,
  })
}

const meta = {
  title: 'Pages/Dashboard',
  component: DashboardPage,
  decorators: [
    (Story) => (
      <MemoryRouter>
        <div className="p-6">
          <Story />
        </div>
      </MemoryRouter>
    ),
  ],
} satisfies Meta<typeof DashboardPage>

export default meta
type Story = StoryObj<typeof meta>

export const WithData: Story = {
  decorators: [
    (Story) => {
      setStoreState()
      return <Story />
    },
  ],
}

export const Loading: Story = {
  decorators: [
    (Story) => {
      setStoreState({ overview: null, loading: true })
      return <Story />
    },
  ],
}

export const Error: Story = {
  decorators: [
    (Story) => {
      setStoreState({ error: 'Failed to connect to backend API' })
      return <Story />
    },
  ],
}

export const EmptyOrg: Story = {
  decorators: [
    (Story) => {
      setStoreState({
        overview: null,
        departmentHealths: [],
        activities: [],
        orgHealthPercent: null,
      })
      return <Story />
    },
  ],
}
