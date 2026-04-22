import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import type { UseAgentsDataReturn } from '@/hooks/useAgentsData'
import { makeAgent } from '../helpers/factories'


vi.mock('@/pages/agents/AgentsSkeleton', () => ({
  AgentsSkeleton: () => <div data-testid="agents-skeleton" />,
}))
vi.mock('@/pages/agents/AgentFilters', () => ({
  AgentFilters: () => <div data-testid="agent-filters" />,
}))
vi.mock('@/pages/agents/AgentGridView', () => ({
  AgentGridView: () => <div data-testid="agent-grid-view" />,
}))


const defaultHookReturn: UseAgentsDataReturn = {
  agents: [makeAgent('alice')],
  filteredAgents: [makeAgent('alice')],
  totalAgents: 1,
  loading: false,
  error: null,
  wsConnected: true,
  wsSetupError: null,
}

let hookReturn = { ...defaultHookReturn }

const getAgentsData = vi.fn(() => hookReturn)
vi.mock('@/hooks/useAgentsData', () => {
  const hookName = 'useAgentsData'
  return { [hookName]: () => getAgentsData() }
})

// Static import: vi.mock is hoisted so the mock is applied before import
import AgentsPage from '@/pages/AgentsPage'

function renderPage() {
  return render(
    <MemoryRouter>
      <AgentsPage />
    </MemoryRouter>,
  )
}

describe('AgentsPage', () => {
  beforeEach(() => {
    hookReturn = { ...defaultHookReturn }
  })

  it('renders page heading', () => {
    renderPage()
    expect(screen.getByText('Agents')).toBeInTheDocument()
  })

  it('renders loading skeleton when loading with no data', () => {
    hookReturn = {
      ...defaultHookReturn,
      loading: true,
      totalAgents: 0,
      agents: [],
      filteredAgents: [],
    }
    renderPage()
    expect(screen.getByTestId('agents-skeleton')).toBeInTheDocument()
  })

  it('renders agent count', () => {
    renderPage()
    expect(screen.getByText('(1)')).toBeInTheDocument()
  })

  it('shows error banner when error is set', () => {
    hookReturn = { ...defaultHookReturn, error: 'Connection lost' }
    renderPage()
    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByText('Connection lost')).toBeInTheDocument()
  })

  it('does not show skeleton when loading but data already exists', () => {
    hookReturn = { ...defaultHookReturn, loading: true }
    renderPage()
    expect(screen.getByText('Agents')).toBeInTheDocument()
    expect(screen.queryByTestId('agents-skeleton')).not.toBeInTheDocument()
  })

  it('shows WebSocket disconnect warning when not connected', () => {
    hookReturn = { ...defaultHookReturn, wsConnected: false }
    renderPage()
    expect(screen.getByText(/disconnected/i)).toBeInTheDocument()
  })

  it('shows custom wsSetupError message when provided', () => {
    hookReturn = {
      ...defaultHookReturn,
      wsConnected: false,
      wsSetupError: 'WebSocket auth failed',
    }
    renderPage()
    expect(screen.getByText('WebSocket auth failed')).toBeInTheDocument()
  })

  it('hides disconnect warning when loading', () => {
    hookReturn = {
      ...defaultHookReturn,
      wsConnected: false,
      loading: true,
    }
    renderPage()
    expect(
      screen.queryByText(/disconnected/i),
    ).not.toBeInTheDocument()
  })
})
