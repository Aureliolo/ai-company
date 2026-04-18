import { render, screen, waitFor } from '@testing-library/react'
import { useAuthStore } from '@/stores/auth'
import { useSetupStore } from '@/stores/setup'
import { router } from '@/router'
import App from '../App'

// Note: `@/api/endpoints/settings` is mocked globally in
// `src/test-setup.tsx`. Do NOT override it here with a partial shape --
// per-file overrides replace the global mock entirely, so any test that
// runs after a partial override inherits the missing exports. Extend
// the global mock in `test-setup.tsx` if more endpoints are needed.

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

// AuthGuard fires `useSettingsStore.getState().fetchLocale()` when the user
// is authenticated; that hits `/settings/display`, which returns 401 in the
// jsdom test environment. The axios 401 interceptor then flips auth state
// back to 'unauthenticated', which bounces the router to /login. Stub the
// settings endpoint to return an empty list so the locale fetch is a no-op.
vi.mock('@/api/endpoints/settings', () => ({
  getSchema: vi.fn().mockResolvedValue([]),
  getNamespaceSchema: vi.fn().mockResolvedValue([]),
  getAllSettings: vi.fn().mockResolvedValue([]),
  getNamespaceSettings: vi.fn().mockResolvedValue([]),
  updateSetting: vi.fn().mockResolvedValue(undefined),
  deleteSetting: vi.fn().mockResolvedValue(undefined),
  restartServer: vi.fn().mockResolvedValue(undefined),
  listSinks: vi.fn().mockResolvedValue([]),
  testSink: vi.fn().mockResolvedValue({ ok: true } satisfies { ok: boolean }),
}))

// AppLayout + LoginPage are React.lazy() imports that transitively pull in
// motion, cmdk, Base UI, and every lazy route module. Under vitest with
// --coverage and --detect-async-leaks, that import chain can take 5-9s and
// race vitest's worker teardown (EnvironmentTeardownError: closing RPC while
// onUserConsoleLog was pending). This test only asserts the router-guard
// routing behavior, so we stub the lazy modules with minimal shells that
// render the landmarks the assertions check (nav + main, sign-in heading).
// Full AppLayout / LoginPage coverage is exercised by Storybook stories
// and the Playwright e2e suite.
vi.mock('@/components/layout/AppLayout', () => ({
  default: () => (
    <>
      <nav aria-label="Main navigation">Nav</nav>
      <main>Content</main>
    </>
  ),
}))

vi.mock('@/pages/LoginPage', () => ({
  default: () => <h1>Sign in</h1>,
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
      authStatus: 'unauthenticated',
      user: null,
      loading: false,
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
    // Auth state is already 'unauthenticated' from beforeEach.
    await router.navigate('/')
    render(<App />)
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /sign in/i })).toBeInTheDocument()
    })
  })

  it('renders app shell for authenticated users with setup complete', async () => {
    useAuthStore.setState({
      authStatus: 'authenticated',
      user: { id: '1', username: 'admin', role: 'ceo', must_change_password: false, org_roles: [], scoped_departments: [] },
    })
    useSetupStore.setState({ setupComplete: true })
    await router.navigate('/')

    render(<App />)
    await waitFor(() => {
      expect(screen.getByRole('navigation', { name: /main navigation/i })).toBeInTheDocument()
    })
    expect(screen.getByRole('main')).toBeInTheDocument()
  })
})
