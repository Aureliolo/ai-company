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
    // Login page is lazy-loaded, so wait for it
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /login/i })).toBeInTheDocument()
    })
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
    // Wait for lazy-loaded layout to render (increased timeout for concurrent test runs
    // where module resolution may take longer due to framer-motion/cmdk imports)
    await waitFor(
      () => {
        // Verify sidebar navigation is present
        expect(screen.getByRole('navigation', { name: /main navigation/i })).toBeInTheDocument()
      },
      { timeout: 5000 },
    )
    // Verify main content area exists
    expect(screen.getByRole('main')).toBeInTheDocument()
    // Verify brand text is present in the app
    expect(screen.getAllByText('SynthOrg').length).toBeGreaterThanOrEqual(1)
  },
    10_000,
  )
})
