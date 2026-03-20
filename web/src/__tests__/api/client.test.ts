import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { unwrap, unwrapPaginated, apiClient } from '@/api/client'
import { AxiosHeaders, AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'

function mockResponse<T>(data: T): AxiosResponse {
  return {
    data,
    status: 200,
    statusText: 'OK',
    headers: {},
    config: {} as AxiosResponse['config'],
  }
}

describe('request interceptor', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  function makeConfig(): InternalAxiosRequestConfig {
    return { headers: new AxiosHeaders() } as InternalAxiosRequestConfig
  }

  function getInterceptor() {
    const handlers = (apiClient.interceptors.request as unknown as { handlers: Array<{ fulfilled?: (c: InternalAxiosRequestConfig) => InternalAxiosRequestConfig }> }).handlers
    const interceptor = handlers?.[0]?.fulfilled
    expect(typeof interceptor).toBe('function')
    return interceptor!
  }

  it('attaches JWT token to request headers', () => {
    localStorage.setItem('auth_token', 'test-jwt-token')
    const config = makeConfig()
    const interceptor = getInterceptor()
    const result = interceptor(config)
    expect(result.headers.get('Authorization')).toBe('Bearer test-jwt-token')
  })

  it('does not attach Authorization when no token', () => {
    const config = makeConfig()
    const interceptor = getInterceptor()
    const result = interceptor(config)
    expect(result.headers.get('Authorization')).toBeUndefined()
  })
})

describe('unwrap', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('extracts data from successful response', () => {
    const response = mockResponse({ data: { id: '1', name: 'test' }, error: null, success: true })
    const result = unwrap(response)
    expect(result).toEqual({ id: '1', name: 'test' })
  })

  it('throws on error response', () => {
    const response = mockResponse({ data: null, error: 'Not found', success: false })
    expect(() => unwrap(response)).toThrow('Not found')
  })

  it('throws on success:false with null data and null error', () => {
    const response = mockResponse({ data: null, error: null, success: false })
    expect(() => unwrap(response)).toThrow('Unknown API error')
  })

  it('throws on success:true with null data', () => {
    const response = mockResponse({ data: null, error: null, success: true })
    expect(() => unwrap(response)).toThrow('Unknown API error')
  })
})

describe('unwrapPaginated', () => {
  it('extracts paginated data', () => {
    const response = mockResponse({
      data: [{ id: '1' }, { id: '2' }],
      error: null,
      success: true,
      pagination: { total: 10, offset: 0, limit: 50 },
    })
    const result = unwrapPaginated(response)
    expect(result.data).toHaveLength(2)
    expect(result.total).toBe(10)
    expect(result.offset).toBe(0)
    expect(result.limit).toBe(50)
  })

  it('throws on error', () => {
    const response = mockResponse({
      data: null,
      error: 'Server error',
      success: false,
      pagination: null,
    })
    expect(() => unwrapPaginated(response)).toThrow('Server error')
  })

  it('throws on success with missing pagination', () => {
    const response = mockResponse({
      data: [{ id: '1' }],
      error: null,
      success: true,
      pagination: null,
    })
    expect(() => unwrapPaginated(response)).toThrow('Unexpected API response format')
  })

  it('throws on success with non-array data', () => {
    const response = mockResponse({
      data: 'not-an-array',
      error: null,
      success: true,
      pagination: { total: 0, offset: 0, limit: 50 },
    })
    expect(() => unwrapPaginated(response)).toThrow('Unexpected API response format')
  })
})

const { mockLogout, mockFetchStatus } = vi.hoisted(() => ({
  mockLogout: vi.fn(),
  mockFetchStatus: vi.fn(),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({ logout: mockLogout }),
}))

vi.mock('@/stores/setup', () => ({
  useSetupStore: () => ({ fetchStatus: mockFetchStatus }),
}))

describe('response interceptor (401 handling)', () => {
  const originalUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`

  function getErrorInterceptor() {
    const handlers = (apiClient.interceptors.response as unknown as {
      handlers: Array<{ rejected?: (e: AxiosError) => Promise<never> }>
    }).handlers
    const interceptor = handlers?.[0]?.rejected
    expect(typeof interceptor).toBe('function')
    return interceptor!
  }

  function make401Error(url?: string): AxiosError {
    const config = { url, headers: new AxiosHeaders() } as InternalAxiosRequestConfig
    return new AxiosError('Unauthorized', '401', config, undefined, {
      status: 401,
      statusText: 'Unauthorized',
      data: { error: 'Unauthorized' },
      headers: {},
      config,
    })
  }

  /** Wait for fire-and-forget promise chains in the interceptor to settle. */
  async function flushMicrotasks() {
    await new Promise((resolve) => setTimeout(resolve, 0))
  }

  beforeEach(() => {
    localStorage.setItem('auth_token', 'stale-token')
    localStorage.setItem('auth_token_expires_at', '9999999999999')
    localStorage.setItem('auth_must_change_password', 'true')
    mockLogout.mockClear()
    mockFetchStatus.mockClear()
  })

  afterEach(() => {
    window.history.pushState({}, '', originalUrl)
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('clears all auth tokens from localStorage and calls logout on 401', async () => {
    const interceptor = getErrorInterceptor()
    window.history.pushState({}, '', '/dashboard')

    await expect(interceptor(make401Error('/api/v1/agents'))).rejects.toThrow()
    await flushMicrotasks()

    expect(localStorage.getItem('auth_token')).toBeNull()
    expect(localStorage.getItem('auth_token_expires_at')).toBeNull()
    expect(localStorage.getItem('auth_must_change_password')).toBeNull()
    expect(mockLogout).toHaveBeenCalledOnce()
  })

  it('does not re-fetch setup status when not on /setup', async () => {
    const interceptor = getErrorInterceptor()
    window.history.pushState({}, '', '/dashboard')

    await expect(interceptor(make401Error('/api/v1/agents'))).rejects.toThrow()
    await flushMicrotasks()

    expect(mockFetchStatus).not.toHaveBeenCalled()
  })

  it('skips setup re-fetch when failing request is /setup/status (loop guard)', async () => {
    const interceptor = getErrorInterceptor()
    window.history.pushState({}, '', '/setup')

    await expect(interceptor(make401Error('/api/v1/setup/status'))).rejects.toThrow()
    await flushMicrotasks()

    expect(mockFetchStatus).not.toHaveBeenCalled()
  })

  it('triggers setup status re-fetch on 401 when on /setup page', async () => {
    const interceptor = getErrorInterceptor()
    window.history.pushState({}, '', '/setup')

    await expect(interceptor(make401Error('/api/v1/providers'))).rejects.toThrow()
    await flushMicrotasks()

    expect(mockFetchStatus).toHaveBeenCalledOnce()
  })

  it('rejects the error promise on 401', async () => {
    const interceptor = getErrorInterceptor()
    window.history.pushState({}, '', '/setup')

    await expect(interceptor(make401Error('/api/v1/providers'))).rejects.toThrow('Unauthorized')
  })
})
