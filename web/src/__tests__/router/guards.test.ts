import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import type { NavigationGuardNext, RouteLocationNormalized } from 'vue-router'
import { authGuard } from '@/router/guards'
import { useAuthStore } from '@/stores/auth'
import { useSetupStore } from '@/stores/setup'

// Mock the router module (needed by auth store)
vi.mock('@/router', () => ({
  router: {
    currentRoute: { value: { path: '/' } },
    push: vi.fn(),
  },
}))

vi.mock('@/api/endpoints/auth', () => ({
  setup: vi.fn(),
  login: vi.fn(),
  changePassword: vi.fn(),
  getMe: vi.fn(),
}))

// Mock setup API -- guard now calls fetchStatus on first navigation
vi.mock('@/api/endpoints/setup', () => ({
  getSetupStatus: vi.fn().mockResolvedValue({
    needs_admin: false,
    needs_setup: false,
    has_providers: true,
  }),
  listTemplates: vi.fn().mockResolvedValue([]),
  createCompany: vi.fn(),
  createAgent: vi.fn(),
  completeSetup: vi.fn(),
}))

function createRoute(overrides: Partial<RouteLocationNormalized> = {}): RouteLocationNormalized {
  return {
    path: '/',
    name: undefined,
    params: {},
    query: {},
    hash: '',
    fullPath: '/',
    matched: [],
    meta: {},
    redirectedFrom: undefined,
    ...overrides,
  } as RouteLocationNormalized
}

describe('authGuard', () => {
  let next: NavigationGuardNext

  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    next = vi.fn()
    // Pre-populate setup status so guard doesn't fetch every time.
    // Tests that need setup-needed behavior override this.
    const setup = useSetupStore()
    setup.$patch({
      status: { needs_admin: false, needs_setup: false, has_providers: true },
    })
    // Mark as loaded so isSetupNeeded uses real status
    setup.statusLoaded = true
  })

  it('redirects unauthenticated users to /login on protected routes', async () => {
    const to = createRoute({ path: '/dashboard', fullPath: '/dashboard', meta: {} })
    const from = createRoute()

    await authGuard(to, from, next)
    expect(next).toHaveBeenCalledWith({ path: '/login', query: { redirect: '/dashboard' } })
  })

  it('does not add redirect query for root path', async () => {
    const to = createRoute({ path: '/', fullPath: '/', meta: {} })
    const from = createRoute()

    await authGuard(to, from, next)
    expect(next).toHaveBeenCalledWith({ path: '/login', query: undefined })
  })

  it('allows authenticated users to access protected routes', async () => {
    localStorage.setItem('auth_token', 'test-token')
    localStorage.setItem('auth_token_expires_at', String(Date.now() + 3600_000))
    // Re-create Pinia to pick up the token from localStorage
    setActivePinia(createPinia())
    // Re-populate setup status after Pinia reset
    const setup = useSetupStore()
    setup.$patch({
      status: { needs_admin: false, needs_setup: false, has_providers: true },
    })
    setup.statusLoaded = true
    // Force the store to read the token
    const store = useAuthStore()
    expect(store.isAuthenticated).toBe(true)

    const to = createRoute({ path: '/dashboard', meta: {} })
    const from = createRoute()

    await authGuard(to, from, next)
    expect(next).toHaveBeenCalledWith()
  })

  it('allows unauthenticated users to access public routes', async () => {
    const to = createRoute({ path: '/login', meta: { requiresAuth: false } })
    const from = createRoute()

    await authGuard(to, from, next)
    expect(next).toHaveBeenCalledWith()
  })

  it('redirects authenticated users away from public routes to /', async () => {
    localStorage.setItem('auth_token', 'test-token')
    localStorage.setItem('auth_token_expires_at', String(Date.now() + 3600_000))
    setActivePinia(createPinia())
    const setup = useSetupStore()
    setup.$patch({
      status: { needs_admin: false, needs_setup: false, has_providers: true },
    })
    setup.statusLoaded = true

    const to = createRoute({ path: '/login', meta: { requiresAuth: false } })
    const from = createRoute()

    await authGuard(to, from, next)
    expect(next).toHaveBeenCalledWith('/')
  })

  it('redirects to settings when mustChangePassword is true', async () => {
    localStorage.setItem('auth_token', 'test-token')
    localStorage.setItem('auth_token_expires_at', String(Date.now() + 3600_000))
    setActivePinia(createPinia())
    const setup = useSetupStore()
    setup.$patch({
      status: { needs_admin: false, needs_setup: false, has_providers: true },
    })
    setup.statusLoaded = true
    const store = useAuthStore()
    store.user = { id: 'u1', username: 'ceo', role: 'ceo', must_change_password: true }

    const to = createRoute({ path: '/tasks', name: 'tasks' as never, meta: {} })
    const from = createRoute()

    await authGuard(to, from, next)
    expect(next).toHaveBeenCalledWith({ name: 'settings', query: { tab: 'user' } })
  })

  it('redirects settings without tab=user when mustChangePassword is true', async () => {
    localStorage.setItem('auth_token', 'test-token')
    localStorage.setItem('auth_token_expires_at', String(Date.now() + 3600_000))
    setActivePinia(createPinia())
    const setup = useSetupStore()
    setup.$patch({
      status: { needs_admin: false, needs_setup: false, has_providers: true },
    })
    setup.statusLoaded = true
    const store = useAuthStore()
    store.user = { id: 'u1', username: 'ceo', role: 'ceo', must_change_password: true }

    const to = createRoute({ path: '/settings', name: 'settings' as never, meta: {} })
    const from = createRoute()

    await authGuard(to, from, next)
    expect(next).toHaveBeenCalledWith({ name: 'settings', query: { tab: 'user' } })
  })

  it('allows settings?tab=user when mustChangePassword is true', async () => {
    localStorage.setItem('auth_token', 'test-token')
    localStorage.setItem('auth_token_expires_at', String(Date.now() + 3600_000))
    setActivePinia(createPinia())
    const setup = useSetupStore()
    setup.$patch({
      status: { needs_admin: false, needs_setup: false, has_providers: true },
    })
    setup.statusLoaded = true
    const store = useAuthStore()
    store.user = { id: 'u1', username: 'ceo', role: 'ceo', must_change_password: true }

    const to = createRoute({ path: '/settings', name: 'settings' as never, query: { tab: 'user' }, meta: {} })
    const from = createRoute()

    await authGuard(to, from, next)
    expect(next).toHaveBeenCalledWith()
  })

  // ── Setup routing tests ──────────────────────────────────

  it('redirects to /setup when setup is needed', async () => {
    const setup = useSetupStore()
    setup.$patch({
      status: { needs_admin: true, needs_setup: true, has_providers: false },
    })
    setup.statusLoaded = true

    const to = createRoute({ path: '/dashboard', name: 'dashboard' as never, meta: {} })
    const from = createRoute()

    await authGuard(to, from, next)
    expect(next).toHaveBeenCalledWith({ name: 'setup' })
  })

  it('allows /setup when setup is needed', async () => {
    const setup = useSetupStore()
    setup.$patch({
      status: { needs_admin: true, needs_setup: true, has_providers: false },
    })
    setup.statusLoaded = true

    const toSetup = createRoute({ path: '/setup', name: 'setup' as never, meta: { requiresAuth: false } })
    const from = createRoute()

    await authGuard(toSetup, from, next)
    expect(next).toHaveBeenCalledWith()
  })

  it('redirects /setup to / when setup is complete', async () => {
    localStorage.setItem('auth_token', 'test-token')
    localStorage.setItem('auth_token_expires_at', String(Date.now() + 3600_000))
    setActivePinia(createPinia())
    const setup = useSetupStore()
    setup.$patch({
      status: { needs_admin: false, needs_setup: false, has_providers: true },
    })
    setup.statusLoaded = true

    const to = createRoute({ path: '/setup', name: 'setup' as never, meta: { requiresAuth: false } })
    const from = createRoute()

    await authGuard(to, from, next)
    expect(next).toHaveBeenCalledWith('/')
  })

  it('fetches status and redirects when statusLoaded is false', async () => {
    // When statusLoaded is false, the guard fetches status first.
    // The mock returns needs_setup: false, so after fetch the guard
    // proceeds to auth routing (unauthenticated -> /login).
    const setup = useSetupStore()
    setup.statusLoaded = false
    setup.$patch({ status: null })

    const to = createRoute({ path: '/dashboard', fullPath: '/dashboard', meta: {} })
    const from = createRoute()

    await authGuard(to, from, next)
    // After fetch, statusLoaded becomes true, needs_setup is false,
    // so auth routing applies: unauthenticated -> /login.
    expect(setup.statusLoaded).toBe(true)
    expect(next).toHaveBeenCalledWith({ path: '/login', query: { redirect: '/dashboard' } })
  })

  it('allows /login when setup is needed', async () => {
    const setup = useSetupStore()
    setup.$patch({
      status: { needs_admin: true, needs_setup: true, has_providers: false },
    })
    setup.statusLoaded = true

    const to = createRoute({ path: '/login', name: 'login' as never, meta: { requiresAuth: false } })
    const from = createRoute()

    await authGuard(to, from, next)
    expect(next).toHaveBeenCalledWith()
  })

  it('falls back to auth routing when fetchStatus rejects', async () => {
    const { getSetupStatus } = await import('@/api/endpoints/setup')
    const mocked = vi.mocked(getSetupStatus)
    mocked.mockRejectedValueOnce(new Error('network error'))

    const setup = useSetupStore()
    setup.statusLoaded = false
    setup.$patch({ status: null })

    const to = createRoute({ path: '/dashboard', fullPath: '/dashboard', meta: {} })
    const from = createRoute()

    await authGuard(to, from, next)
    // fetchStatus caught the error internally; status remains null,
    // statusLoaded stays false. Guard falls through to auth routing.
    expect(setup.statusLoaded).toBe(false)
    expect(next).toHaveBeenCalledWith({ path: '/login', query: { redirect: '/dashboard' } })
  })
})
