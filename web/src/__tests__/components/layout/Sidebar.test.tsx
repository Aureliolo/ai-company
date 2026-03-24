import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useAuthStore } from '@/stores/auth'
import { Sidebar } from '@/components/layout/Sidebar'
import { renderWithRouter } from '../../test-utils'

// Prevent window.location side effects from auth store
const originalLocation = window.location
beforeAll(() => {
  Object.defineProperty(window, 'location', {
    writable: true,
    value: { ...originalLocation, href: '', pathname: '/' },
  })
})
afterAll(() => {
  Object.defineProperty(window, 'location', {
    writable: true,
    value: originalLocation,
  })
})

function setup(initialEntries: string[] = ['/']) {
  useAuthStore.setState({
    token: 'test-token',
    user: { id: '1', username: 'admin', role: 'ceo', must_change_password: false },
    loading: false,
    _mustChangePasswordFallback: false,
  })
  return renderWithRouter(<Sidebar />, { initialEntries })
}

describe('Sidebar', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('renders all primary navigation items', () => {
    setup()

    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.getByText('Org Chart')).toBeInTheDocument()
    expect(screen.getByText('Task Board')).toBeInTheDocument()
    expect(screen.getByText('Budget')).toBeInTheDocument()
    expect(screen.getByText('Approvals')).toBeInTheDocument()
  })

  it('renders all workspace navigation items', () => {
    setup()

    expect(screen.getByText('Agents')).toBeInTheDocument()
    expect(screen.getByText('Messages')).toBeInTheDocument()
    expect(screen.getByText('Meetings')).toBeInTheDocument()
    expect(screen.getByText('Providers')).toBeInTheDocument()
    expect(screen.getByText('Settings')).toBeInTheDocument()
  })

  it('renders the Workspace section label', () => {
    setup()

    expect(screen.getByText('Workspace')).toBeInTheDocument()
  })

  it('renders user info when authenticated', () => {
    setup()

    expect(screen.getByText('admin')).toBeInTheDocument()
    expect(screen.getByText('ceo')).toBeInTheDocument()
  })

  it('collapses and persists state to localStorage', async () => {
    const user = userEvent.setup()
    setup()

    // Initially expanded
    expect(screen.getByText('SynthOrg')).toBeInTheDocument()
    expect(localStorage.getItem('sidebar_collapsed')).toBeNull()

    // Click collapse
    await user.click(screen.getByTitle('Collapse sidebar'))

    // Labels should be hidden, localStorage updated
    expect(screen.queryByText('SynthOrg')).not.toBeInTheDocument()
    expect(localStorage.getItem('sidebar_collapsed')).toBe('true')
  })

  it('expands from collapsed state', async () => {
    localStorage.setItem('sidebar_collapsed', 'true')
    const user = userEvent.setup()
    setup()

    // Initially collapsed -- SynthOrg text should not show
    expect(screen.queryByText('SynthOrg')).not.toBeInTheDocument()

    // Click expand
    await user.click(screen.getByTitle('Expand sidebar'))

    expect(screen.getByText('SynthOrg')).toBeInTheDocument()
    expect(localStorage.getItem('sidebar_collapsed')).toBe('false')
  })

  it('hides Workspace label when collapsed', () => {
    localStorage.setItem('sidebar_collapsed', 'true')
    setup()

    expect(screen.queryByText('Workspace')).not.toBeInTheDocument()
  })

  it('renders brand mark when collapsed', () => {
    localStorage.setItem('sidebar_collapsed', 'true')
    setup()

    expect(screen.getByText('S')).toBeInTheDocument()
  })
})
