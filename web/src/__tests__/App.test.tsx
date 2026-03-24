import { render, screen, waitFor } from '@testing-library/react'
import { useAuthStore } from '@/stores/auth'
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
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('renders without crashing', async () => {
    render(<App />)
    // App renders a router -- unauthenticated users see the login page
    // Login page is lazy-loaded, so wait for it
    await waitFor(() => {
      expect(screen.getByText('Login')).toBeInTheDocument()
    })
  })

  it('shows login page when not authenticated', async () => {
    render(<App />)
    await waitFor(() => {
      expect(screen.getByText('Login')).toBeInTheDocument()
    })
  })
})
