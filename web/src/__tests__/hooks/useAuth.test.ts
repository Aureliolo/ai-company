import { renderHook } from '@testing-library/react'
import { useAuth } from '@/hooks/useAuth'
import { useAuthStore } from '@/stores/auth'
import type { HumanRole, UserInfoResponse } from '@/api/types'
import { WRITE_ROLES } from '@/utils/constants'

vi.mock('@/api/endpoints/auth', () => ({
  login: vi.fn(),
  setup: vi.fn(),
  getMe: vi.fn(),
  changePassword: vi.fn(),
}))

function resetStore() {
  localStorage.clear()
  useAuthStore.setState({ token: null, user: null, loading: false, _mustChangePasswordFallback: false })
}

describe('useAuth', () => {
  beforeEach(resetStore)

  it('returns not authenticated when no token', () => {
    const { result } = renderHook(() => useAuth())
    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.user).toBeNull()
    expect(result.current.userRole).toBeNull()
    expect(result.current.canWrite).toBe(false)
  })

  it('returns authenticated with user data', () => {
    const user: UserInfoResponse = {
      id: 'user-1',
      username: 'admin',
      role: 'ceo',
      must_change_password: false,
    }
    useAuthStore.setState({ token: 'test-token', user })

    const { result } = renderHook(() => useAuth())
    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.user).toEqual(user)
    expect(result.current.userRole).toBe('ceo')
    expect(result.current.mustChangePassword).toBe(false)
  })

  describe('canWrite', () => {
    const writeRoles = WRITE_ROLES
    const allRoles: readonly HumanRole[] = ['ceo', 'manager', 'board_member', 'pair_programmer', 'observer', 'system']
    const readOnlyRoles = allRoles.filter((r) => !(WRITE_ROLES as readonly string[]).includes(r))

    for (const role of writeRoles) {
      it(`returns canWrite=true for ${role}`, () => {
        useAuthStore.setState({
          token: 'test',
          user: { id: '1', username: 'u', role, must_change_password: false },
        })
        const { result } = renderHook(() => useAuth())
        expect(result.current.canWrite).toBe(true)
      })
    }

    for (const role of readOnlyRoles) {
      it(`returns canWrite=false for ${role}`, () => {
        useAuthStore.setState({
          token: 'test',
          user: { id: '1', username: 'u', role, must_change_password: false },
        })
        const { result } = renderHook(() => useAuth())
        expect(result.current.canWrite).toBe(false)
      })
    }
  })

  it('returns mustChangePassword from user', () => {
    useAuthStore.setState({
      token: 'test',
      user: { id: '1', username: 'u', role: 'ceo', must_change_password: true },
    })
    const { result } = renderHook(() => useAuth())
    expect(result.current.mustChangePassword).toBe(true)
  })

  it('falls back to _mustChangePasswordFallback when user is null', () => {
    useAuthStore.setState({ token: 'test', user: null, _mustChangePasswordFallback: true })
    const { result } = renderHook(() => useAuth())
    expect(result.current.mustChangePassword).toBe(true)
  })
})
