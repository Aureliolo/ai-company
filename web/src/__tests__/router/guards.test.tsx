import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useAuthStore } from '@/stores/auth'
import { useSetupStore } from '@/stores/setup'
import { AuthGuard, GuestGuard, SetupCompleteGuard, SetupGuard } from '@/router/guards'
import { renderRoutes } from '../test-utils'

// Mock the setup API
vi.mock('@/api/endpoints/setup', () => ({
  getSetupStatus: vi.fn(),
}))

// Mock the auth API (AuthGuard calls checkSession -> getMe to validate session)
vi.mock('@/api/endpoints/auth', () => ({
  getMe: vi.fn().mockResolvedValue({
    id: '1',
    username: 'admin',
    role: 'ceo',
    must_change_password: false,
    org_roles: [],
    scoped_departments: [],
  }),
  login: vi.fn(),
  setup: vi.fn(),
  logout: vi.fn(),
  changePassword: vi.fn(),
}))

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

function resetStores() {
  useAuthStore.setState({
    authStatus: 'unauthenticated',
    user: null,
    loading: false,
  })
  useSetupStore.setState({
    setupComplete: null,
    loading: false,
    error: false,
  })
}

describe('AuthGuard', () => {
  beforeEach(() => {
    resetStores()
    vi.clearAllMocks()
  })

  it('redirects to /login when unauthenticated', () => {
    useAuthStore.setState({ authStatus: 'unauthenticated' })

    renderRoutes(
      [
        {
          path: '/',
          element: <AuthGuard />,
          children: [{ index: true, element: <div>Protected</div> }],
        },
        { path: '/login', element: <div>Login Page</div> },
      ],
      { initialEntries: ['/'] },
    )

    expect(screen.getByText('Login Page')).toBeInTheDocument()
    expect(screen.queryByText('Protected')).not.toBeInTheDocument()
  })

  it('renders children when authenticated', () => {
    useAuthStore.setState({
      authStatus: 'authenticated',
      user: {
        id: '1',
        username: 'admin',
        role: 'ceo',
        must_change_password: false,
        org_roles: [],
        scoped_departments: [],
      },
    })

    renderRoutes(
      [
        {
          path: '/',
          element: <AuthGuard />,
          children: [{ index: true, element: <div>Protected</div> }],
        },
        { path: '/login', element: <div>Login Page</div> },
      ],
      { initialEntries: ['/'] },
    )

    expect(screen.getByText('Protected')).toBeInTheDocument()
    expect(screen.queryByText('Login Page')).not.toBeInTheDocument()
  })

  it('shows loading while auth status is unknown (page refresh)', async () => {
    useAuthStore.setState({ authStatus: 'unknown' })

    renderRoutes(
      [
        {
          path: '/',
          element: <AuthGuard />,
          children: [{ index: true, element: <div>Protected</div> }],
        },
      ],
      { initialEntries: ['/'] },
    )

    // Guard shows loading while checkSession validates the session
    expect(screen.getByText('Loading...')).toBeInTheDocument()
    expect(screen.queryByText('Protected')).not.toBeInTheDocument()

    // After validation completes (getMe succeeds), protected content renders
    await waitFor(() => {
      expect(screen.getByText('Protected')).toBeInTheDocument()
    })
  })
})

describe('SetupGuard', () => {
  beforeEach(() => {
    resetStores()
    vi.clearAllMocks()
  })

  it('redirects to /setup when setup is not complete', () => {
    useAuthStore.setState({ authStatus: 'authenticated' })
    useSetupStore.setState({ setupComplete: false })

    renderRoutes(
      [
        {
          path: '/',
          element: <SetupGuard />,
          children: [{ index: true, element: <div>App Content</div> }],
        },
        { path: '/setup', element: <div>Setup Page</div> },
      ],
      { initialEntries: ['/'] },
    )

    expect(screen.getByText('Setup Page')).toBeInTheDocument()
    expect(screen.queryByText('App Content')).not.toBeInTheDocument()
  })

  it('renders children when setup is complete', () => {
    useAuthStore.setState({ authStatus: 'authenticated' })
    useSetupStore.setState({ setupComplete: true })

    renderRoutes(
      [
        {
          path: '/',
          element: <SetupGuard />,
          children: [{ index: true, element: <div>App Content</div> }],
        },
        { path: '/setup', element: <div>Setup Page</div> },
      ],
      { initialEntries: ['/'] },
    )

    expect(screen.getByText('App Content')).toBeInTheDocument()
  })

  it('shows loading state when setup status is unknown', () => {
    useAuthStore.setState({ authStatus: 'authenticated' })
    useSetupStore.setState({ setupComplete: null, loading: true })

    renderRoutes(
      [
        {
          path: '/',
          element: <SetupGuard />,
          children: [{ index: true, element: <div>App Content</div> }],
        },
      ],
      { initialEntries: ['/'] },
    )

    expect(screen.getByText('Loading...')).toBeInTheDocument()
  })

  it('triggers fetchSetupStatus when setup status is unknown', async () => {
    const { getSetupStatus } = await import('@/api/endpoints/setup')
    const mockGetSetupStatus = vi.mocked(getSetupStatus)
    mockGetSetupStatus.mockResolvedValue({
      needs_admin: false,
      needs_setup: false,
      has_providers: true,
      has_name_locales: true,
      has_company: true,
      has_agents: true,
      min_password_length: 12,
    })

    useAuthStore.setState({ authStatus: 'authenticated' })
    // setupComplete is null (not yet fetched), loading is false

    renderRoutes(
      [
        {
          path: '/',
          element: <SetupGuard />,
          children: [{ index: true, element: <div>App Content</div> }],
        },
        { path: '/setup', element: <div>Setup Page</div> },
      ],
      { initialEntries: ['/'] },
    )

    // Should fetch and then render content (setup is complete)
    await waitFor(() => {
      expect(screen.getByText('App Content')).toBeInTheDocument()
    })
    expect(mockGetSetupStatus).toHaveBeenCalledOnce()
  })

  it('shows error with retry when fetchSetupStatus fails', async () => {
    const { getSetupStatus } = await import('@/api/endpoints/setup')
    const mockGetSetupStatus = vi.mocked(getSetupStatus)
    mockGetSetupStatus.mockRejectedValue(new Error('Network error'))

    useAuthStore.setState({ authStatus: 'authenticated' })

    renderRoutes(
      [
        {
          path: '/',
          element: <SetupGuard />,
          children: [{ index: true, element: <div>App Content</div> }],
        },
      ],
      { initialEntries: ['/'] },
    )

    await waitFor(() => {
      expect(screen.getByText('Failed to check setup status.')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()

    // Retry succeeds
    mockGetSetupStatus.mockResolvedValueOnce({
      needs_admin: false,
      needs_setup: false,
      has_providers: true,
      has_name_locales: true,
      has_company: true,
      has_agents: true,
      min_password_length: 12,
    })

    const user = userEvent.setup()
    await user.click(screen.getByRole('button', { name: /retry/i }))

    await waitFor(() => {
      expect(screen.getByText('App Content')).toBeInTheDocument()
    })
    expect(mockGetSetupStatus).toHaveBeenCalledTimes(2)
  })
})

describe('GuestGuard', () => {
  beforeEach(() => {
    resetStores()
    vi.clearAllMocks()
  })

  it('renders children when unauthenticated', () => {
    useAuthStore.setState({ authStatus: 'unauthenticated' })

    renderRoutes(
      [
        {
          path: '/login',
          element: (
            <GuestGuard>
              <div>Login Form</div>
            </GuestGuard>
          ),
        },
        { path: '/', element: <div>Dashboard</div> },
      ],
      { initialEntries: ['/login'] },
    )

    expect(screen.getByText('Login Form')).toBeInTheDocument()
  })

  it('redirects to / when already authenticated', () => {
    useAuthStore.setState({ authStatus: 'authenticated' })

    renderRoutes(
      [
        {
          path: '/login',
          element: (
            <GuestGuard>
              <div>Login Form</div>
            </GuestGuard>
          ),
        },
        { path: '/', element: <div>Dashboard</div> },
      ],
      { initialEntries: ['/login'] },
    )

    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.queryByText('Login Form')).not.toBeInTheDocument()
  })

  it('shows loading when auth status is unknown', () => {
    useAuthStore.setState({ authStatus: 'unknown' })

    renderRoutes(
      [
        {
          path: '/login',
          element: (
            <GuestGuard>
              <div>Login Form</div>
            </GuestGuard>
          ),
        },
      ],
      { initialEntries: ['/login'] },
    )

    expect(screen.getByText('Loading...')).toBeInTheDocument()
    expect(screen.queryByText('Login Form')).not.toBeInTheDocument()
  })
})

describe('SetupCompleteGuard', () => {
  beforeEach(() => {
    resetStores()
    vi.clearAllMocks()
  })

  it('renders children when not authenticated', () => {
    useAuthStore.setState({ authStatus: 'unauthenticated' })

    renderRoutes(
      [
        {
          path: '/setup',
          element: (
            <SetupCompleteGuard>
              <div>Setup Wizard</div>
            </SetupCompleteGuard>
          ),
        },
      ],
      { initialEntries: ['/setup'] },
    )

    expect(screen.getByText('Setup Wizard')).toBeInTheDocument()
  })

  it('redirects to / when authenticated and setup is complete', () => {
    useAuthStore.setState({ authStatus: 'authenticated' })
    useSetupStore.setState({ setupComplete: true })

    renderRoutes(
      [
        {
          path: '/setup',
          element: (
            <SetupCompleteGuard>
              <div>Setup Wizard</div>
            </SetupCompleteGuard>
          ),
        },
        { path: '/', element: <div>Dashboard</div> },
      ],
      { initialEntries: ['/setup'] },
    )

    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.queryByText('Setup Wizard')).not.toBeInTheDocument()
  })

  it('renders children when authenticated but setup is not complete', () => {
    useAuthStore.setState({ authStatus: 'authenticated' })
    useSetupStore.setState({ setupComplete: false })

    renderRoutes(
      [
        {
          path: '/setup',
          element: (
            <SetupCompleteGuard>
              <div>Setup Wizard</div>
            </SetupCompleteGuard>
          ),
        },
        { path: '/', element: <div>Dashboard</div> },
      ],
      { initialEntries: ['/setup'] },
    )

    expect(screen.getByText('Setup Wizard')).toBeInTheDocument()
  })

  it('fetches setup status when authenticated and status unknown', async () => {
    const { getSetupStatus } = await import('@/api/endpoints/setup')
    const mockGetSetupStatus = vi.mocked(getSetupStatus)
    mockGetSetupStatus.mockResolvedValue({
      needs_admin: false,
      needs_setup: true,
      has_providers: false,
      has_name_locales: false,
      has_company: false,
      has_agents: false,
      min_password_length: 12,
    })

    useAuthStore.setState({ authStatus: 'authenticated' })
    // setupComplete is null (not yet fetched)

    renderRoutes(
      [
        {
          path: '/setup',
          element: (
            <SetupCompleteGuard>
              <div>Setup Wizard</div>
            </SetupCompleteGuard>
          ),
        },
        { path: '/', element: <div>Dashboard</div> },
      ],
      { initialEntries: ['/setup'] },
    )

    await waitFor(() => {
      expect(screen.getByText('Setup Wizard')).toBeInTheDocument()
    })
    expect(mockGetSetupStatus).toHaveBeenCalledOnce()
  })

  it('redirects authenticated users to dashboard when fetch fails (fail-closed)', async () => {
    const { getSetupStatus } = await import('@/api/endpoints/setup')
    const mockGetSetupStatus = vi.mocked(getSetupStatus)
    mockGetSetupStatus.mockRejectedValue(new Error('Network error'))

    useAuthStore.setState({ authStatus: 'authenticated' })

    renderRoutes(
      [
        {
          path: '/setup',
          element: (
            <SetupCompleteGuard>
              <div>Setup Wizard</div>
            </SetupCompleteGuard>
          ),
        },
        { path: '/', element: <div>Dashboard</div> },
      ],
      { initialEntries: ['/setup'] },
    )

    // Fail-closed: should redirect to dashboard rather than allowing setup access
    await waitFor(() => {
      expect(screen.getByText('Dashboard')).toBeInTheDocument()
    })
    expect(screen.queryByText('Setup Wizard')).not.toBeInTheDocument()
  })
})
