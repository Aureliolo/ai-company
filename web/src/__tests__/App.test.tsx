import { render, screen, waitFor } from '@testing-library/react'
import { useAuthStore } from '@/stores/auth'
import { useSetupStore } from '@/stores/setup'
import App from '../App'

// Mock the setup API (used by SetupGuard)
vi.mock('@/api/endpoints/setup', () => ({
  getSetupStatus: vi.fn().mockResolvedValue({
    needs_admin: false,
    needs_setup: false,
    has_providers: true,
    has_name_locales: true,
    has_company: true,
    has_agents: true,
    min_password_length: 12,
  }),
}))

// Stub the global WebSocket subscription mounted in AppLayout -- it otherwise
// tries to open a real WS connection during these tests and triggers an
// EnvironmentTeardownError when the worker unmounts.
vi.mock('@/hooks/useGlobalNotifications', () => ({
  useGlobalNotifications: vi.fn(),
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

describe('App', () => {
  beforeEach(() => {
    useAuthStore.setState({
      token: null,
      user: null,
      loading: false,
      _mustChangePasswordFallback: false,
    })
    useSetupStore.setState({
      setupComplete: null,
      loading: false,
      error: false,
    })
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('redirects unauthenticated users to login', async () => {
    render(<App />)
    // Login page is lazy-loaded and calls getSetupStatus on mount,
    // so we need extra time for: Suspense resolve + useEffect + mock.
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /sign in/i })).toBeInTheDocument()
    }, { timeout: 5000 })
  })

  it(
    'renders app shell for authenticated users with setup complete',
    async () => {
    useAuthStore.setState({
      token: 'test-token',
      user: { id: '1', username: 'admin', role: 'ceo', must_change_password: false },
    })
    useSetupStore.setState({ setupComplete: true })

    render(<App />)
    // Wait for lazy-loaded layout to render.  On CI with
    // `--detect-async-leaks` + coverage enabled, the initial import of
    // AppLayout (which transitively pulls in framer-motion, cmdk-base,
    // Base UI primitives, and every lazy page) can take 5-9s before the
    // Suspense fallback resolves -- the 8000ms budget below has margin
    // over observed CI timings while staying under the outer 15s cap.
    await waitFor(
      () => {
        // Verify sidebar navigation is present
        expect(screen.getByRole('navigation', { name: /main navigation/i })).toBeInTheDocument()
      },
      { timeout: 8000 },
    )
    // Verify main content area exists
    expect(screen.getByRole('main')).toBeInTheDocument()
  },
    15_000,
  )
})
