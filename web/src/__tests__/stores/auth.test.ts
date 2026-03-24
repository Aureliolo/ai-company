import { useAuthStore } from '@/stores/auth'
import type { TokenResponse, UserInfoResponse } from '@/api/types'

// Mock the auth API endpoints
vi.mock('@/api/endpoints/auth', () => ({
  login: vi.fn(),
  setup: vi.fn(),
  getMe: vi.fn(),
  changePassword: vi.fn(),
}))

// Prevent actual navigation in tests
const originalLocation = window.location
beforeAll(() => {
  Object.defineProperty(window, 'location', {
    writable: true,
    value: { ...originalLocation, href: '', pathname: '/dashboard' },
  })
})
afterAll(() => {
  Object.defineProperty(window, 'location', {
    writable: true,
    value: originalLocation,
  })
})

const mockTokenResponse: TokenResponse = {
  token: 'test-jwt-token',
  expires_in: 3600,
  must_change_password: false,
}

const mockUser: UserInfoResponse = {
  id: 'user-1',
  username: 'admin',
  role: 'ceo',
  must_change_password: false,
}

function resetStore() {
  // Use logout() to properly clean up module-scoped expiry timer
  useAuthStore.getState().logout()
  localStorage.clear()
  useAuthStore.setState({
    token: null,
    user: null,
    loading: false,
    _mustChangePasswordFallback: false,
  })
  window.location.pathname = '/dashboard'
  window.location.href = ''
}

describe('auth store', () => {
  beforeEach(() => {
    resetStore()
    vi.clearAllMocks()
    vi.useRealTimers()
  })

  describe('setToken', () => {
    it('stores token and persists to localStorage', () => {
      useAuthStore.getState().setToken('my-token', 3600)
      expect(useAuthStore.getState().token).toBe('my-token')
      expect(localStorage.getItem('auth_token')).toBe('my-token')
      expect(localStorage.getItem('auth_token_expires_at')).toBeTruthy()
    })

    it('throws for invalid expiresIn', () => {
      expect(() => useAuthStore.getState().setToken('t', 0)).toThrow('invalid session duration')
      expect(() => useAuthStore.getState().setToken('t', -1)).toThrow('invalid session duration')
      expect(() => useAuthStore.getState().setToken('t', Infinity)).toThrow('invalid session duration')
    })
  })

  describe('clearAuth', () => {
    it('clears token, user, and localStorage', () => {
      useAuthStore.setState({ token: 'test', user: mockUser })
      localStorage.setItem('auth_token', 'test')
      localStorage.setItem('auth_token_expires_at', '999999999999')
      localStorage.setItem('auth_must_change_password', 'true')

      useAuthStore.getState().clearAuth()

      expect(useAuthStore.getState().token).toBeNull()
      expect(useAuthStore.getState().user).toBeNull()
      expect(localStorage.getItem('auth_token')).toBeNull()
      expect(localStorage.getItem('auth_token_expires_at')).toBeNull()
      expect(localStorage.getItem('auth_must_change_password')).toBeNull()
    })

    it('redirects to /login when not already there', () => {
      window.location.pathname = '/dashboard'
      useAuthStore.setState({ token: 'test' })
      useAuthStore.getState().clearAuth()
      expect(window.location.href).toBe('/login')
    })

    it('does not redirect when already on /login', () => {
      window.location.pathname = '/login'
      useAuthStore.setState({ token: 'test' })
      useAuthStore.getState().clearAuth()
      expect(window.location.href).toBe('')
    })

    it('does not redirect when on /setup', () => {
      window.location.pathname = '/setup'
      useAuthStore.setState({ token: 'test' })
      useAuthStore.getState().clearAuth()
      expect(window.location.href).toBe('')
    })
  })

  describe('login', () => {
    it('sets token and fetches user on success', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.login).mockResolvedValue(mockTokenResponse)
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser)

      await useAuthStore.getState().login('admin', 'pass')

      expect(useAuthStore.getState().token).toBe('test-jwt-token')
      expect(useAuthStore.getState().user).toEqual(mockUser)
      expect(useAuthStore.getState().loading).toBe(false)
    })

    it('clears auth when login API fails', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.login).mockRejectedValue(new Error('bad credentials'))

      await expect(useAuthStore.getState().login('admin', 'wrong')).rejects.toThrow()
      expect(useAuthStore.getState().token).toBeNull()
      expect(useAuthStore.getState().loading).toBe(false)
    })
  })

  describe('setup', () => {
    it('calls setup API and fetches user', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.setup).mockResolvedValue(mockTokenResponse)
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser)

      await useAuthStore.getState().setup('admin', 'pass')

      expect(authApi.setup).toHaveBeenCalledWith({ username: 'admin', password: 'pass' })
      expect(useAuthStore.getState().token).toBe('test-jwt-token')
      expect(useAuthStore.getState().user).toEqual(mockUser)
    })
  })

  describe('fetchUser', () => {
    it('does nothing when no token', async () => {
      const authApi = await import('@/api/endpoints/auth')
      useAuthStore.setState({ token: null })

      await useAuthStore.getState().fetchUser()

      expect(authApi.getMe).not.toHaveBeenCalled()
    })

    it('sets user on success', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser)
      useAuthStore.setState({ token: 'test-token' })

      await useAuthStore.getState().fetchUser()

      expect(useAuthStore.getState().user).toEqual(mockUser)
    })

    it('persists must_change_password flag', async () => {
      const authApi = await import('@/api/endpoints/auth')
      const mustChangeUser = { ...mockUser, must_change_password: true }
      vi.mocked(authApi.getMe).mockResolvedValue(mustChangeUser)
      useAuthStore.setState({ token: 'test-token' })

      await useAuthStore.getState().fetchUser()

      expect(localStorage.getItem('auth_must_change_password')).toBe('true')
    })

    it('clears auth on 401 error', async () => {
      const { AxiosError } = await import('axios')
      const authApi = await import('@/api/endpoints/auth')
      const error401 = new AxiosError('Unauthorized', 'ERR_BAD_RESPONSE', undefined, undefined, {
        status: 401, data: {}, headers: {}, statusText: 'Unauthorized',
        config: {} as import('axios').AxiosResponse['config'],
      } as import('axios').AxiosResponse)
      vi.mocked(authApi.getMe).mockRejectedValue(error401)
      useAuthStore.setState({ token: 'test-token' })
      localStorage.setItem('auth_token', 'test-token')

      // fetchUser now throws on 401 after clearing auth
      await expect(useAuthStore.getState().fetchUser()).rejects.toThrow('Session expired')

      expect(useAuthStore.getState().token).toBeNull()
      expect(localStorage.getItem('auth_token')).toBeNull()
    })

    it('throws on non-401 errors without clearing auth', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.getMe).mockRejectedValue(new Error('Network error'))
      useAuthStore.setState({ token: 'test-token' })

      await expect(useAuthStore.getState().fetchUser()).rejects.toThrow('Network error')
      expect(useAuthStore.getState().token).toBe('test-token')
    })
  })

  describe('changePassword', () => {
    it('updates user and clears must_change flag', async () => {
      const authApi = await import('@/api/endpoints/auth')
      const updatedUser = { ...mockUser, must_change_password: false }
      vi.mocked(authApi.changePassword).mockResolvedValue(updatedUser)
      useAuthStore.setState({ token: 'test-token', user: { ...mockUser, must_change_password: true } })
      localStorage.setItem('auth_must_change_password', 'true')

      const result = await useAuthStore.getState().changePassword('old', 'new')

      expect(result).toEqual(updatedUser)
      expect(useAuthStore.getState().user).toEqual(updatedUser)
      expect(localStorage.getItem('auth_must_change_password')).toBeNull()
    })
  })

  describe('logout', () => {
    it('calls clearAuth', () => {
      useAuthStore.setState({ token: 'test', user: mockUser })
      localStorage.setItem('auth_token', 'test')

      useAuthStore.getState().logout()

      expect(useAuthStore.getState().token).toBeNull()
      expect(useAuthStore.getState().user).toBeNull()
      expect(localStorage.getItem('auth_token')).toBeNull()
    })
  })

  describe('token expiry', () => {
    beforeEach(() => vi.useFakeTimers())
    afterEach(() => vi.useRealTimers())

    it('clears auth when token expires', () => {
      useAuthStore.getState().setToken('expiring-token', 10)

      expect(useAuthStore.getState().token).toBe('expiring-token')

      vi.advanceTimersByTime(10_000)

      expect(useAuthStore.getState().token).toBeNull()
    })
  })
})
