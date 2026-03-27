import { render, screen } from '@testing-library/react'
import { AgentsTab, type AgentsTabProps } from '@/pages/org-edit/AgentsTab'
import type { CompanyConfig } from '@/api/types'
import { makeAgent, makeDepartment } from '../../helpers/factories'

const noopAsync = vi.fn().mockResolvedValue(undefined)
const noopRollback = vi.fn().mockReturnValue(() => {})

/** Config with known agents for deterministic assertions. */
const knownConfig: CompanyConfig = {
  company_name: 'Test Corp',
  agents: [
    makeAgent('alice', { department: 'engineering', role: 'Lead Developer', level: 'lead' }),
    makeAgent('bob', { department: 'engineering', role: 'Developer' }),
    makeAgent('carol', { department: 'product', role: 'Product Manager', level: 'senior' }),
  ],
  departments: [
    makeDepartment('engineering'),
    makeDepartment('product'),
  ],
}

function renderTab(overrides?: Partial<AgentsTabProps>) {
  const props: AgentsTabProps = {
    config: knownConfig,
    saving: false,
    onCreateAgent: noopAsync,
    onUpdateAgent: noopAsync,
    onDeleteAgent: noopAsync,
    onReorderAgents: noopAsync,
    optimisticReorderAgents: noopRollback,
    ...overrides,
  }
  return render(<AgentsTab {...props} />)
}

describe('AgentsTab', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders empty state when config has no agents', () => {
    renderTab({ config: { ...knownConfig, agents: [] } })
    expect(screen.getByText('No agents')).toBeInTheDocument()
  })

  it('renders Add Agent button', () => {
    renderTab()
    expect(screen.getByText('Add Agent')).toBeInTheDocument()
  })

  it('renders agent cards grouped by department', () => {
    renderTab()
    // Engineering department header
    expect(screen.getByText('Engineering')).toBeInTheDocument()
    // Product department header
    expect(screen.getByText('Product')).toBeInTheDocument()
  })

  it('renders agent names', () => {
    renderTab()
    expect(screen.getByText('alice')).toBeInTheDocument()
    expect(screen.getByText('bob')).toBeInTheDocument()
    expect(screen.getByText('carol')).toBeInTheDocument()
  })

  it('renders agent count per department', () => {
    renderTab()
    expect(screen.getByText('2 agents')).toBeInTheDocument()
    expect(screen.getByText('1 agent')).toBeInTheDocument()
  })

  it('renders empty state when config is null', () => {
    renderTab({ config: null })
    expect(screen.getByText('No agents')).toBeInTheDocument()
  })
})
