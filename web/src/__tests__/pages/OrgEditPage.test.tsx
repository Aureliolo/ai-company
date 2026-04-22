import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import type { UseOrgEditDataReturn } from '@/hooks/useOrgEditData'
import { makeCompanyConfig, makeDepartmentHealth } from '../helpers/factories'

const noopAsync = vi.fn().mockResolvedValue(undefined)
const noopRollback = vi.fn().mockReturnValue(() => {})

const defaultHookReturn: UseOrgEditDataReturn = {
  config: makeCompanyConfig(),
  departmentHealths: [makeDepartmentHealth('engineering')],
  loading: false,
  error: null,
  saving: false,
  saveError: null,
  wsConnected: true,
  wsSetupError: null,
  updateCompany: noopAsync,
  createDepartment: noopAsync,
  updateDepartment: noopAsync,
  deleteDepartment: noopAsync,
  reorderDepartments: noopAsync,
  createAgent: noopAsync,
  updateAgent: noopAsync,
  deleteAgent: noopAsync,
  reorderAgents: noopAsync,
  createTeam: noopAsync,
  updateTeam: noopAsync,
  deleteTeam: noopAsync,
  reorderTeams: noopAsync,
  optimisticReorderDepartments: noopRollback,
  optimisticReorderAgents: noopRollback,
}

let hookReturn = { ...defaultHookReturn }

const getOrgEditData = vi.fn(() => hookReturn)
vi.mock('@/hooks/useOrgEditData', () => {
  const hookName = 'useOrgEditData'
  return { [hookName]: () => getOrgEditData() }
})

// Must import after vi.mock
import OrgEditPage from '@/pages/OrgEditPage'

function renderPage(initialPath = '/org/edit') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <OrgEditPage />
    </MemoryRouter>,
  )
}

describe('OrgEditPage', () => {
  beforeEach(() => {
    hookReturn = { ...defaultHookReturn }
    vi.clearAllMocks()
  })

  it('renders page heading', () => {
    renderPage()
    expect(screen.getByText('Edit Organization')).toBeInTheDocument()
  })

  it('renders Back to Org Chart link', () => {
    renderPage()
    expect(screen.getByLabelText('Back to Org Chart')).toBeInTheDocument()
  })

  it('renders tab triggers', () => {
    renderPage()
    expect(screen.getByText('General')).toBeInTheDocument()
    expect(screen.getByText('Agents')).toBeInTheDocument()
    expect(screen.getByText('Departments')).toBeInTheDocument()
  })

  it('renders loading skeleton when loading with no config', () => {
    hookReturn = { ...defaultHookReturn, config: null, loading: true }
    renderPage()
    expect(screen.getByLabelText('Loading organization editor')).toBeInTheDocument()
  })

  it('renders error banner when error is present', () => {
    hookReturn = { ...defaultHookReturn, error: 'Network failure' }
    renderPage()
    expect(screen.getByText('Network failure')).toBeInTheDocument()
  })

  it('renders save error banner', () => {
    hookReturn = { ...defaultHookReturn, saveError: 'Save failed' }
    renderPage()
    expect(screen.getByText('Save failed')).toBeInTheDocument()
  })

  it('renders WS disconnect warning after a prior connection drops', () => {
    // Start connected so wasConnectedRef flips to true, then drop the
    // connection. The banner must only show after a real disconnect, not
    // during the initial handshake.
    hookReturn = { ...defaultHookReturn, wsConnected: true }
    const { rerender } = renderPage()
    // Disconnected with no prior connect: banner must stay hidden.
    hookReturn = { ...defaultHookReturn, wsConnected: false }
    rerender(
      <MemoryRouter initialEntries={['/org/edit']}>
        <OrgEditPage />
      </MemoryRouter>,
    )
    expect(screen.getByText(/disconnected/i)).toBeInTheDocument()
  })

  it('does not render WS disconnect warning during initial handshake', () => {
    // First render: never connected, no setup error. Banner must stay hidden
    // to avoid the false-positive flash before the WS finishes connecting.
    hookReturn = { ...defaultHookReturn, wsConnected: false }
    renderPage()
    expect(screen.queryByText(/disconnected/i)).not.toBeInTheDocument()
  })

  it('renders custom WS setup error', () => {
    hookReturn = { ...defaultHookReturn, wsConnected: false, wsSetupError: 'Auth failed' }
    renderPage()
    expect(screen.getByText('Auth failed')).toBeInTheDocument()
  })

  it('renders YAML toggle', () => {
    renderPage()
    expect(screen.getByText('YAML')).toBeInTheDocument()
  })

  it('shows General tab content by default', () => {
    renderPage()
    // GeneralTab renders company settings section
    expect(screen.getByText('Company Settings')).toBeInTheDocument()
  })
})
