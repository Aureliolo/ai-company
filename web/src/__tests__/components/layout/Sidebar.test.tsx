import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
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

function resetStore() {
  useAuthStore.setState({
    token: null,
    user: null,
    loading: false,
    _mustChangePasswordFallback: false,
  })
}

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
    resetStore()
    useThemeStore.getState().setSidebarMode('collapsible')
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

    expect(screen.getByText('SynthOrg')).toBeInTheDocument()
    expect(localStorage.getItem('sidebar_collapsed')).toBeNull()

    await user.click(screen.getByTitle('Collapse sidebar'))

    expect(screen.queryByText('SynthOrg')).not.toBeInTheDocument()
    expect(localStorage.getItem('sidebar_collapsed')).toBe('true')
  })

  it('expands from collapsed state', async () => {
    localStorage.setItem('sidebar_collapsed', 'true')
    const user = userEvent.setup()
    setup()

    expect(screen.queryByText('SynthOrg')).not.toBeInTheDocument()

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

  it('calls logout when logout button is clicked', async () => {
    const user = userEvent.setup()
    const logoutSpy = vi.fn()
    useAuthStore.setState({
      ...useAuthStore.getState(),
      token: 'test-token',
      user: { id: '1', username: 'admin', role: 'ceo', must_change_password: false },
      loading: false,
      _mustChangePasswordFallback: false,
      logout: logoutSpy,
    })
    renderWithRouter(<Sidebar />, { initialEntries: ['/'] })

    await user.click(screen.getByTitle('Logout'))

    expect(logoutSpy).toHaveBeenCalledOnce()
  })

  describe('sidebarMode', () => {
    it('returns null when mode is hidden', () => {
      useThemeStore.getState().setSidebarMode('hidden')
      setup()

      expect(screen.queryByLabelText('Main navigation')).not.toBeInTheDocument()
    })

    it('is always collapsed in rail mode (no collapse toggle)', () => {
      useThemeStore.getState().setSidebarMode('rail')
      setup()

      // Collapsed state shows brand mark "S" instead of "SynthOrg"
      expect(screen.getByText('S')).toBeInTheDocument()
      expect(screen.queryByText('SynthOrg')).not.toBeInTheDocument()

      // Collapse toggle should not be present
      expect(screen.queryByTitle('Collapse sidebar')).not.toBeInTheDocument()
      expect(screen.queryByTitle('Expand sidebar')).not.toBeInTheDocument()
    })

    it('is always collapsed in compact mode (no collapse toggle)', () => {
      useThemeStore.getState().setSidebarMode('compact')
      setup()

      expect(screen.getByText('S')).toBeInTheDocument()
      expect(screen.queryByText('SynthOrg')).not.toBeInTheDocument()

      expect(screen.queryByTitle('Collapse sidebar')).not.toBeInTheDocument()
      expect(screen.queryByTitle('Expand sidebar')).not.toBeInTheDocument()
    })

    it('is always expanded in persistent mode (no collapse toggle)', () => {
      useThemeStore.getState().setSidebarMode('persistent')
      setup()

      expect(screen.getByText('SynthOrg')).toBeInTheDocument()
      expect(screen.queryByText('S')).not.toBeInTheDocument()

      expect(screen.queryByTitle('Collapse sidebar')).not.toBeInTheDocument()
      expect(screen.queryByTitle('Expand sidebar')).not.toBeInTheDocument()
    })

    it('shows collapse toggle only in collapsible mode', () => {
      useThemeStore.getState().setSidebarMode('collapsible')
      setup()

      expect(screen.getByTitle('Collapse sidebar')).toBeInTheDocument()
    })
  })
})
