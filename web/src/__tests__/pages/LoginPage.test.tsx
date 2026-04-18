import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'

// ── Mocks ──────────────────────────────────────────────────

const mockLogin = vi.fn()
const mockSetup = vi.fn()

const authSelector = (selector: (s: Record<string, unknown>) => unknown) =>
  selector({ login: mockLogin, setup: mockSetup })

vi.mock('@/stores/auth', () => {
  const hookName = 'useAuthStore'
  return { [hookName]: (...args: unknown[]) => authSelector(args[0] as (s: Record<string, unknown>) => unknown) }
})

const mockGetSetupStatus = vi.fn()
vi.mock('@/api/endpoints/setup', () => ({
  getSetupStatus: (...args: unknown[]) => mockGetSetupStatus(...args),
}))

// Mock login lockout with controllable state
const mockLockout = {
  locked: false,
  checkAndClearLockout: vi.fn(() => false),
  recordFailure: vi.fn(() => null),
  reset: vi.fn(),
}
vi.mock('@/hooks/useLoginLockout', () => {
  const hookName = 'useLoginLockout'
  return { [hookName]: () => mockLockout }
})

import LoginPage from '@/pages/LoginPage'

// ── Helpers ────────────────────────────────────────────────

function renderLogin() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>,
  )
}

function setupStatusResponse(overrides: Record<string, unknown> = {}) {
  return {
    needs_admin: false,
    needs_setup: true,
    has_providers: false,
    has_name_locales: false,
    has_company: false,
    has_agents: false,
    min_password_length: 12,
    ...overrides,
  }
}

// ── Tests ──────────────────────────────────────────────────

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockLockout.locked = false
    mockLockout.checkAndClearLockout.mockReturnValue(false)
    mockLockout.recordFailure.mockReturnValue(null)
  })

  it('shows loading state on mount', async () => {
    // Deferred promise rather than ``new Promise(() => {})`` so the
    // ``--detect-async-leaks`` guard doesn't flag the intentionally-
    // pending state as a leak: the assertion runs while the promise
    // is still pending, then we resolve + await it in teardown so
    // no promise outlives the test.
    let resolveSetup: ((value: ReturnType<typeof setupStatusResponse>) => void) | undefined
    const deferred = new Promise<ReturnType<typeof setupStatusResponse>>(
      (resolve) => {
        resolveSetup = resolve
      },
    )
    mockGetSetupStatus.mockReturnValue(deferred)
    renderLogin()
    expect(screen.getByText('Checking setup status...')).toBeInTheDocument()
    if (!resolveSetup) throw new Error('deferred resolver was never assigned')
    resolveSetup(setupStatusResponse({ needs_admin: false }))
    await waitFor(() => {
      expect(
        screen.queryByText('Checking setup status...'),
      ).not.toBeInTheDocument()
    })
  })

  it('shows login form when needs_admin is false', async () => {
    mockGetSetupStatus.mockResolvedValue(setupStatusResponse({ needs_admin: false }))
    renderLogin()
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign In' })).toBeInTheDocument()
    })
    expect(screen.queryByLabelText('Confirm Password')).not.toBeInTheDocument()
  })

  it('shows admin creation form when needs_admin is true', async () => {
    mockGetSetupStatus.mockResolvedValue(setupStatusResponse({ needs_admin: true }))
    renderLogin()
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create Admin Account' })).toBeInTheDocument()
    })
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument()
    expect(screen.getByText(/Set up your administrator account/)).toBeInTheDocument()
  })

  it('defaults to login mode on setup status fetch failure', async () => {
    mockGetSetupStatus.mockRejectedValue(new Error('network error'))
    renderLogin()
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign In' })).toBeInTheDocument()
    })
  })

  it('renders SynthOrg wordmark', async () => {
    mockGetSetupStatus.mockResolvedValue(setupStatusResponse())
    renderLogin()
    await waitFor(() => {
      expect(screen.getByText('SynthOrg')).toBeInTheDocument()
    })
  })

  it('login form submits credentials', async () => {
    mockGetSetupStatus.mockResolvedValue(setupStatusResponse())
    mockLogin.mockResolvedValue(undefined)
    const user = userEvent.setup()

    renderLogin()
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign In' })).toBeInTheDocument()
    })

    await user.type(screen.getByLabelText('Username'), 'admin')
    await user.type(screen.getByLabelText('Password'), 'secret123456')
    await user.click(screen.getByRole('button', { name: 'Sign In' }))

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('admin', 'secret123456')
    })
  })

  it('login form shows error on failure', async () => {
    mockGetSetupStatus.mockResolvedValue(setupStatusResponse())
    mockLogin.mockRejectedValue(new Error('Invalid credentials'))
    const user = userEvent.setup()

    renderLogin()
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign In' })).toBeInTheDocument()
    })

    await user.type(screen.getByLabelText('Username'), 'admin')
    await user.type(screen.getByLabelText('Password'), 'wrong')
    await user.click(screen.getByRole('button', { name: 'Sign In' }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
  })

  it('validates username is required for login', async () => {
    mockGetSetupStatus.mockResolvedValue(setupStatusResponse())
    const user = userEvent.setup()

    renderLogin()
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign In' })).toBeInTheDocument()
    })

    await user.type(screen.getByLabelText('Password'), 'secret123456')
    await user.click(screen.getByRole('button', { name: 'Sign In' }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Username is required')
    })
    expect(mockLogin).not.toHaveBeenCalled()
  })

  it('validates password is required for login', async () => {
    mockGetSetupStatus.mockResolvedValue(setupStatusResponse())
    const user = userEvent.setup()

    renderLogin()
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign In' })).toBeInTheDocument()
    })

    await user.type(screen.getByLabelText('Username'), 'admin')
    await user.click(screen.getByRole('button', { name: 'Sign In' }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Password is required')
    })
    expect(mockLogin).not.toHaveBeenCalled()
  })

  it('admin creation validates password match', async () => {
    mockGetSetupStatus.mockResolvedValue(setupStatusResponse({ needs_admin: true }))
    const user = userEvent.setup()

    renderLogin()
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create Admin Account' })).toBeInTheDocument()
    })

    await user.type(screen.getByLabelText('Username'), 'admin')
    await user.type(screen.getByLabelText('Password'), 'validpassword1')
    await user.type(screen.getByLabelText(/confirm password/i), 'differentpassword')
    await user.click(screen.getByRole('button', { name: 'Create Account' }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Passwords do not match')
    })
    expect(mockSetup).not.toHaveBeenCalled()
  })

  it('admin creation validates minimum password length', async () => {
    mockGetSetupStatus.mockResolvedValue(
      setupStatusResponse({ needs_admin: true, min_password_length: 12 }),
    )
    const user = userEvent.setup()

    renderLogin()
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create Admin Account' })).toBeInTheDocument()
    })

    await user.type(screen.getByLabelText('Username'), 'admin')
    await user.type(screen.getByLabelText('Password'), 'short')
    await user.type(screen.getByLabelText(/confirm password/i), 'short')
    await user.click(screen.getByRole('button', { name: 'Create Account' }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('at least 12 characters')
    })
    expect(mockSetup).not.toHaveBeenCalled()
  })

  it('admin creation validates username is required', async () => {
    mockGetSetupStatus.mockResolvedValue(setupStatusResponse({ needs_admin: true }))
    const user = userEvent.setup()

    renderLogin()
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create Admin Account' })).toBeInTheDocument()
    })

    await user.type(screen.getByLabelText('Password'), 'validpassword1')
    await user.type(screen.getByLabelText(/confirm password/i), 'validpassword1')
    await user.click(screen.getByRole('button', { name: 'Create Account' }))

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Username is required')
    })
    expect(mockSetup).not.toHaveBeenCalled()
  })

  it('admin creation calls setup on valid input', async () => {
    mockGetSetupStatus.mockResolvedValue(setupStatusResponse({ needs_admin: true }))
    mockSetup.mockResolvedValue(undefined)
    const user = userEvent.setup()

    renderLogin()
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Create Admin Account' })).toBeInTheDocument()
    })

    await user.type(screen.getByLabelText('Username'), 'admin')
    await user.type(screen.getByLabelText('Password'), 'validpassword1')
    await user.type(screen.getByLabelText(/confirm password/i), 'validpassword1')
    await user.click(screen.getByRole('button', { name: 'Create Account' }))

    await waitFor(() => {
      expect(mockSetup).toHaveBeenCalledWith('admin', 'validpassword1')
    })
  })

  it('disables inputs during submission', async () => {
    mockGetSetupStatus.mockResolvedValue(setupStatusResponse())
    // Deferred promise rather than ``new Promise(() => {})`` so
    // --detect-async-leaks doesn't flag the intentionally-pending
    // submission state as a leak: we resolve it at the end of the
    // test so the login store's promise chain settles before teardown.
    let resolveLogin: (() => void) | undefined
    const loginDeferred = new Promise<void>((resolve) => {
      resolveLogin = resolve
    })
    mockLogin.mockReturnValue(loginDeferred)
    const user = userEvent.setup()

    renderLogin()
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign In' })).toBeInTheDocument()
    })

    await user.type(screen.getByLabelText('Username'), 'admin')
    await user.type(screen.getByLabelText('Password'), 'secret123456')
    await user.click(screen.getByRole('button', { name: 'Sign In' }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Signing In...' })).toBeDisabled()
    })

    // Settle the deferred so the in-flight login promise resolves
    // before the worker tears down.
    if (!resolveLogin) throw new Error('deferred resolver was never assigned')
    resolveLogin()
    await loginDeferred
  })

  it('shows lockout warning when locked', async () => {
    mockGetSetupStatus.mockResolvedValue(setupStatusResponse())
    mockLockout.locked = true

    renderLogin()
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign In' })).toBeInTheDocument()
    })

    expect(screen.getByRole('button', { name: 'Sign In' })).toBeDisabled()
    expect(screen.getByText(/too many failed attempts/i)).toBeInTheDocument()
  })

  it('form submits on Enter key', async () => {
    mockGetSetupStatus.mockResolvedValue(setupStatusResponse())
    mockLogin.mockResolvedValue(undefined)
    const user = userEvent.setup()

    renderLogin()
    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign In' })).toBeInTheDocument()
    })

    await user.type(screen.getByLabelText('Username'), 'admin')
    await user.type(screen.getByLabelText('Password'), 'secret123456')
    await user.keyboard('{Enter}')

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('admin', 'secret123456')
    })
  })

  describe('XSS safety', () => {
    const XSS_PAYLOAD = '<script>window.__xss_fired__ = true</script>'

    beforeEach(() => {
      // Remove the flag in case a prior test set it.
      delete (globalThis as { __xss_fired__?: boolean }).__xss_fired__
    })

    it('renders username input as text, not executable HTML', async () => {
      mockGetSetupStatus.mockResolvedValue(setupStatusResponse())
      const user = userEvent.setup()

      renderLogin()
      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Sign In' })).toBeInTheDocument()
      })

      const username = screen.getByLabelText('Username') as HTMLInputElement
      await user.type(username, XSS_PAYLOAD)

      // The input `value` preserves the payload as a literal string.
      expect(username.value).toBe(XSS_PAYLOAD)
      // No script element was added to the DOM.
      expect(document.querySelector('script[data-xss], body script')).toBeNull()
      // The payload did not execute in the test realm.
      expect((globalThis as { __xss_fired__?: boolean }).__xss_fired__).toBeUndefined()
    })

    it('forwards XSS payload to the login action as a plain string', async () => {
      mockGetSetupStatus.mockResolvedValue(setupStatusResponse())
      mockLogin.mockResolvedValue(undefined)
      const user = userEvent.setup()

      renderLogin()
      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Sign In' })).toBeInTheDocument()
      })

      await user.type(screen.getByLabelText('Username'), XSS_PAYLOAD)
      await user.type(screen.getByLabelText('Password'), 'password12345')
      await user.click(screen.getByRole('button', { name: 'Sign In' }))

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith(XSS_PAYLOAD, 'password12345')
      })

      // The payload was never executed as HTML during render.
      expect((globalThis as { __xss_fired__?: boolean }).__xss_fired__).toBeUndefined()
    })
  })
})
