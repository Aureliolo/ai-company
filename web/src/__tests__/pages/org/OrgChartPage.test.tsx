import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import type { Node } from '@xyflow/react'

// ── Module-level mock components/hooks (eslint-react requires top-level) ──

function MockReactFlow({ children }: { children?: React.ReactNode }) {
  return <div data-testid="react-flow">{children}</div>
}

function MockReactFlowProvider({ children }: { children?: React.ReactNode }) {
  return <>{children}</>
}

function MockBackground() {
  return <div data-testid="react-flow-background" />
}

function mockUseReactFlow() {
  return { fitView: vi.fn(), zoomIn: vi.fn(), zoomOut: vi.fn() }
}

function mockUseRegisterCommands() {}

// Track mock return value for useOrgChartData
let mockNodes: Node[] = []
let mockLoading = false
let mockError: string | null = null
let mockWsConnected = true
let mockWsSetupError: string | null = null

function mockUseOrgChartData() {
  return {
    nodes: mockNodes,
    edges: [],
    loading: mockLoading,
    error: mockError,
    wsConnected: mockWsConnected,
    wsSetupError: mockWsSetupError,
  }
}

// ── vi.mock calls ────────────────────────────────────────────

vi.mock('@xyflow/react', () => ({
  ReactFlow: MockReactFlow,
  ReactFlowProvider: MockReactFlowProvider,
  Background: MockBackground,
  useReactFlow: mockUseReactFlow,
  Handle: () => null,
  Position: { Top: 'top', Bottom: 'bottom' },
  getSmoothStepPath: () => ['M0 0'],
  BaseEdge: () => null,
}))

vi.mock('@/hooks/useCommandPalette', () => ({
  useRegisterCommands: mockUseRegisterCommands,
}))

vi.mock('@/hooks/useOrgChartData', () => ({
  useOrgChartData: mockUseOrgChartData,
}))

// Import after mocks
import OrgChartPage from '@/pages/OrgChartPage'

function renderPage() {
  return render(
    <MemoryRouter>
      <OrgChartPage />
    </MemoryRouter>,
  )
}

describe('OrgChartPage', () => {
  beforeEach(() => {
    mockNodes = []
    mockLoading = false
    mockError = null
    mockWsConnected = true
    mockWsSetupError = null
  })

  it('renders page heading', () => {
    renderPage()
    expect(screen.getByText('Org Chart')).toBeInTheDocument()
  })

  it('renders Edit Organization link', () => {
    mockNodes = [{ id: '1', position: { x: 0, y: 0 }, data: {} }]
    renderPage()
    expect(screen.getByText('Edit Organization')).toBeInTheDocument()
  })

  it('shows skeleton while loading', () => {
    mockLoading = true
    renderPage()
    expect(screen.getByLabelText('Loading org chart')).toBeInTheDocument()
  })

  it('shows empty state when no org configured', () => {
    mockLoading = false
    mockNodes = []
    renderPage()
    expect(screen.getByText('No organization configured')).toBeInTheDocument()
  })

  it('shows error banner when error exists', () => {
    mockError = 'Failed to load company'
    mockNodes = [{ id: '1', position: { x: 0, y: 0 }, data: {} }]
    renderPage()
    expect(screen.getByText('Failed to load company')).toBeInTheDocument()
  })

  it('shows WS disconnect warning', () => {
    mockWsConnected = false
    mockWsSetupError = 'Connection refused'
    mockNodes = [{ id: '1', position: { x: 0, y: 0 }, data: {} }]
    renderPage()
    expect(screen.getByText(/Connection refused/)).toBeInTheDocument()
  })

  it('renders React Flow canvas when nodes exist', () => {
    mockNodes = [{ id: '1', position: { x: 0, y: 0 }, data: {} }]
    renderPage()
    expect(screen.getByTestId('react-flow')).toBeInTheDocument()
  })

  it('renders toolbar when nodes exist', () => {
    mockNodes = [{ id: '1', position: { x: 0, y: 0 }, data: {} }]
    renderPage()
    expect(screen.getByTestId('org-chart-toolbar')).toBeInTheDocument()
  })

  it('does not show skeleton when loading with existing nodes', () => {
    mockLoading = true
    mockNodes = [{ id: '1', position: { x: 0, y: 0 }, data: {} }]
    renderPage()
    expect(screen.queryByLabelText('Loading org chart')).not.toBeInTheDocument()
    expect(screen.getByTestId('react-flow')).toBeInTheDocument()
  })
})
