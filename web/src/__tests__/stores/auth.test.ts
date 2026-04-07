import { useAuthStore } from '@/stores/auth'
import type { AuthResponse, UserInfoResponse } from '@/api/types'

// Mock the auth API endpoints
vi.mock('@/api/endpoints/auth', () => ({
  login: vi.fn(),
  setup: vi.fn(),
  logout: vi.fn(),
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

const mockAuthResponse: AuthResponse = {
  expires_in: 3600,
  must_change_password: false,
}

const mockUser: UserInfoResponse = {
  id: 'user-1',
  username: 'admin',
  role: 'ceo',
  must_change_password: false,
  org_roles: [],
  scoped_departments: [],
}

function resetStore() {
  useAuthStore.setState({
    authStatus: 'unknown',
    user: null,
    loading: false,
  })
  window.location.pathname = '/dashboard'
  window.location.href = ''
}

describe('auth store', () => {
  beforeEach(() => {
    resetStore()
    vi.clearAllMocks()
  })

  describe('handleUnauthorized', () => {
    it('sets unauthenticated and clears user', () => {
      useAuthStore.setState({ authStatus: 'authenticated', user: mockUser })

      useAuthStore.getState().handleUnauthorized()

      expect(useAuthStore.getState().authStatus).toBe('unauthenticated')
      expect(useAuthStore.getState().user).toBeNull()
    })

    it('redirects to /login when not already there', () => {
      window.location.pathname = '/dashboard'
      useAuthStore.setState({ authStatus: 'authenticated' })
      useAuthStore.getState().handleUnauthorized()
      expect(window.location.href).toBe('/login')
    })

    it('does not redirect when already on /login', () => {
      window.location.pathname = '/login'
      useAuthStore.setState({ authStatus: 'authenticated' })
      useAuthStore.getState().handleUnauthorized()
      expect(window.location.href).toBe('')
    })

    it('does not redirect when on /setup', () => {
      window.location.pathname = '/setup'
      useAuthStore.setState({ authStatus: 'authenticated' })
      useAuthStore.getState().handleUnauthorized()
      expect(window.location.href).toBe('')
    })
  })

  describe('login', () => {
    it('authenticates and fetches user on success', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.login).mockResolvedValue(mockAuthResponse)
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser)

      await useAuthStore.getState().login('admin', 'pass')

      expect(useAuthStore.getState().authStatus).toBe('authenticated')
      expect(useAuthStore.getState().user).toEqual(mockUser)
      expect(useAuthStore.getState().loading).toBe(false)
    })

    it('clears auth when login API fails', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.login).mockRejectedValue(new Error('bad credentials'))

      await expect(useAuthStore.getState().login('admin', 'wrong')).rejects.toThrow()
      expect(useAuthStore.getState().loading).toBe(false)
    })
  })

  describe('setup', () => {
    it('calls setup API and fetches user', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.setup).mockResolvedValue(mockAuthResponse)
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser)

      await useAuthStore.getState().setup('admin', 'pass')

      expect(authApi.setup).toHaveBeenCalledWith({ username: 'admin', password: 'pass' })
      expect(useAuthStore.getState().authStatus).toBe('authenticated')
      expect(useAuthStore.getState().user).toEqual(mockUser)
    })
  })

  describe('fetchUser', () => {
    it('skips when already authenticated with user loaded', async () => {
      const authApi = await import('@/api/endpoints/auth')
      useAuthStore.setState({ authStatus: 'authenticated', user: mockUser })

      await useAuthStore.getState().fetchUser()

      expect(authApi.getMe).not.toHaveBeenCalled()
    })

    it('sets user and authenticated on success', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser)
      useAuthStore.setState({ authStatus: 'unknown' })

      await useAuthStore.getState().fetchUser()

      expect(useAuthStore.getState().user).toEqual(mockUser)
      expect(useAuthStore.getState().authStatus).toBe('authenticated')
    })

    it('clears auth on 401 error', async () => {
      const { AxiosError } = await import('axios')
      const authApi = await import('@/api/endpoints/auth')
      const error401 = new AxiosError('Unauthorized', 'ERR_BAD_RESPONSE', undefined, undefined, {
        status: 401, data: {}, headers: {}, statusText: 'Unauthorized',
        config: {} as import('axios').AxiosResponse['config'],
      } as import('axios').AxiosResponse)
      vi.mocked(authApi.getMe).mockRejectedValue(error401)
      useAuthStore.setState({ authStatus: 'authenticated' })

      await expect(useAuthStore.getState().fetchUser()).rejects.toThrow('Session expired')

      expect(useAuthStore.getState().authStatus).toBe('unauthenticated')
    })

    it('throws on non-401 errors without clearing auth', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.getMe).mockRejectedValue(new Error('Network error'))
      useAuthStore.setState({ authStatus: 'authenticated' })

      await expect(useAuthStore.getState().fetchUser()).rejects.toThrow('Network error')
      expect(useAuthStore.getState().authStatus).toBe('authenticated')
    })
  })

  describe('changePassword', () => {
    it('updates user on success', async () => {
      const authApi = await import('@/api/endpoints/auth')
      const updatedUser = { ...mockUser, must_change_password: false }
      vi.mocked(authApi.changePassword).mockResolvedValue(updatedUser)
      useAuthStore.setState({ authStatus: 'authenticated', user: { ...mockUser, must_change_password: true } })

      const result = await useAuthStore.getState().changePassword('old', 'new')

      expect(result).toEqual(updatedUser)
      expect(useAuthStore.getState().user).toEqual(updatedUser)
    })
  })

  describe('logout', () => {
    it('calls logout API and sets unauthenticated', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.logout).mockResolvedValue(undefined)
      useAuthStore.setState({ authStatus: 'authenticated', user: mockUser })

      await useAuthStore.getState().logout()

      expect(authApi.logout).toHaveBeenCalled()
      expect(useAuthStore.getState().authStatus).toBe('unauthenticated')
      expect(useAuthStore.getState().user).toBeNull()
    })

    it('still clears auth when logout API fails', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.logout).mockRejectedValue(new Error('network error'))
      useAuthStore.setState({ authStatus: 'authenticated', user: mockUser })

      await useAuthStore.getState().logout()

      expect(useAuthStore.getState().authStatus).toBe('unauthenticated')
      expect(useAuthStore.getState().user).toBeNull()
    })
  })

  describe('checkSession', () => {
    it('sets authenticated when server confirms session', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.getMe).mockResolvedValue(mockUser)

      await useAuthStore.getState().checkSession()

      expect(useAuthStore.getState().authStatus).toBe('authenticated')
      expect(useAuthStore.getState().user).toEqual(mockUser)
    })

    it('sets unauthenticated on 401 response', async () => {
      const { AxiosError } = await import('axios')
      const authApi = await import('@/api/endpoints/auth')
      const err = new AxiosError(
        'Unauthorized',
        'ERR_BAD_RESPONSE',
        undefined,
        undefined,
        {
          status: 401,
          data: {},
          headers: {},
          statusText: 'Unauthorized',
          config: {} as import('axios').AxiosResponse['config'],
        } as import('axios').AxiosResponse,
      )
      vi.mocked(authApi.getMe).mockRejectedValue(err)

      await useAuthStore.getState().checkSession()

      expect(useAuthStore.getState().authStatus).toBe('unauthenticated')
      expect(useAuthStore.getState().user).toBeNull()
    })

    it('stays unknown on non-401 error (network/5xx)', async () => {
      const authApi = await import('@/api/endpoints/auth')
      vi.mocked(authApi.getMe).mockRejectedValue(new Error('Network Error'))

      await useAuthStore.getState().checkSession()

      expect(useAuthStore.getState().authStatus).toBe('unknown')
      expect(useAuthStore.getState().user).toBeNull()
    })
  })
})
